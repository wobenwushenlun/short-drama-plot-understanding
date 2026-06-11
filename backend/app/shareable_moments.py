from __future__ import annotations

import re
from typing import Any

from backend.app.domain_utils import safe_int


SUPPORTED_SHAREABLE_STRATEGIES = {
    "heat_score_desc_v1",
    "episode_spread_v1",
    "recent_episode_v1",
    "interaction_first",
    "danmaku_first",
    "ai_evidence_first",
    "hybrid",
}


def build_shareable_moment_from_node(
    *,
    request_base_url: str,
    drama_id: str,
    episode: dict[str, Any],
    node: dict[str, Any],
    selection_strategy: str,
    play_url: str,
) -> dict[str, Any]:
    trigger_ms = safe_int(node.get("trigger", {}).get("timeMs"), 0, minimum=0)
    duration_ms = safe_int(episode.get("duration_ms"), trigger_ms + 12_000, minimum=0)
    start_ms = max(trigger_ms - 8_000, 0)
    end_ms = min(max(trigger_ms + 16_000, start_ms + 6_000), duration_ms)
    generation = node.get("generation") if isinstance(node.get("generation"), dict) else {}
    confidence = float(generation.get("confidence") or 0.55)
    component_boost = 12 if node.get("componentType") in {"AIGC_CARD", "DANMAKU_STICKER"} else 0
    heat_score = int(min(100, max(40, round(confidence * 100) + component_boost)))
    return {
        "momentId": f"moment_{node.get('id')}",
        "dramaId": drama_id,
        "episodeId": str(episode["episode_id"]),
        "episodeNo": int(episode.get("episode_no") or 0),
        "episodeTitle": str(episode.get("title") or ""),
        "startMs": start_ms,
        "endMs": end_ms,
        "title": str(node.get("title") or ""),
        "hookText": str(node.get("display", {}).get("promptText") or node.get("subtitle") or ""),
        "sourceNodeId": str(node.get("id") or ""),
        "source": str(generation.get("generationSource") or node.get("componentType") or "interaction_node"),
        "selectionStrategy": selection_strategy,
        "heatScore": heat_score,
        "playUrl": play_url or f"{request_base_url.rstrip('/')}/media/episodes/{episode['episode_id']}",
    }


def normalize_shareable_strategy(selection_strategy: str) -> str:
    strategy = selection_strategy.strip() or "heat_score_desc_v1"
    if strategy in SUPPORTED_SHAREABLE_STRATEGIES:
        return strategy
    return "heat_score_desc_v1"


def sort_shareable_moments(items: list[dict[str, Any]], selection_strategy: str) -> list[dict[str, Any]]:
    normalized_strategy = normalize_shareable_strategy(selection_strategy)
    if normalized_strategy == "interaction_first":
        return sorted(
            items,
            key=lambda item: (
                _is_danmaku_moment(item),
                -int(item.get("heatScore") or 0),
                int(item.get("startMs") or 0),
            ),
        )
    if normalized_strategy == "danmaku_first":
        return sorted(
            items,
            key=lambda item: (
                not _is_danmaku_moment(item),
                -int(item.get("heatScore") or 0),
                int(item.get("startMs") or 0),
            ),
        )
    if normalized_strategy == "ai_evidence_first":
        return sorted(
            items,
            key=lambda item: (
                not _is_ai_evidence_moment(item),
                -int(item.get("heatScore") or 0),
                str(item.get("episodeId") or ""),
            ),
        )
    if normalized_strategy == "hybrid":
        return sorted(
            items,
            key=lambda item: (
                -_hybrid_strategy_score(item),
                int(item.get("episodeNo") or 0),
                int(item.get("startMs") or 0),
            ),
        )
    if normalized_strategy == "recent_episode_v1":
        return sorted(
            items,
            key=lambda item: (
                -int(item.get("episodeNo") or 0),
                -int(item.get("heatScore") or 0),
                int(item.get("startMs") or 0),
            ),
        )
    if normalized_strategy == "episode_spread_v1":
        grouped: dict[int, list[dict[str, Any]]] = {}
        for item in sorted(
            items,
            key=lambda item: (
                int(item.get("episodeNo") or 0),
                -int(item.get("heatScore") or 0),
                int(item.get("startMs") or 0),
            ),
        ):
            grouped.setdefault(int(item.get("episodeNo") or 0), []).append(item)
        ordered_episode_nos = sorted(grouped, reverse=True)
        result: list[dict[str, Any]] = []
        while any(grouped.values()):
            for episode_no in ordered_episode_nos:
                episode_items = grouped.get(episode_no, [])
                if episode_items:
                    result.append(episode_items.pop(0))
        return result
    return sorted(
        items,
        key=lambda item: (
            -int(item.get("heatScore") or 0),
            str(item.get("episodeId") or ""),
            int(item.get("startMs") or 0),
        ),
    )


def _is_danmaku_moment(item: dict[str, Any]) -> bool:
    haystack = " ".join(
        [
            str(item.get("momentId") or ""),
            str(item.get("sourceNodeId") or ""),
            str(item.get("title") or ""),
            str(item.get("hookText") or ""),
            str(item.get("source") or ""),
        ]
    ).lower()
    return "danmaku" in haystack or "弹幕" in haystack


def _is_ai_evidence_moment(item: dict[str, Any]) -> bool:
    source = str(item.get("source") or "")
    return source in {"model", "reviewed_model", "rule"} or source.startswith("ai_")


def _hybrid_strategy_score(item: dict[str, Any]) -> int:
    score = int(item.get("heatScore") or 0)
    if _is_ai_evidence_moment(item):
        score += 8
    if _is_danmaku_moment(item):
        score += 6
    score += min(int(item.get("episodeNo") or 0), 5)
    return score


def normalize_incoming_moment(
    payload: dict[str, Any],
    *,
    drama_id: str,
    valid_episode_ids: set[str],
    now_ms: int,
) -> dict[str, Any] | None:
    moment_id = str(payload.get("momentId") or payload.get("moment_id") or "").strip()
    payload_drama_id = str(payload.get("dramaId") or payload.get("drama_id") or drama_id).strip()
    episode_id = str(payload.get("episodeId") or payload.get("episode_id") or "").strip()
    if not moment_id or payload_drama_id != drama_id or episode_id not in valid_episode_ids:
        return None
    start_ms = safe_int(payload.get("startMs") or payload.get("start_ms"), 0, minimum=0)
    end_ms = safe_int(payload.get("endMs") or payload.get("end_ms"), start_ms + 10_000, minimum=start_ms)
    return {
        "moment_id": moment_id,
        "drama_id": payload_drama_id,
        "episode_id": episode_id,
        "title": str(payload.get("title") or "高能片段").strip()[:80],
        "hook_text": str(payload.get("hookText") or payload.get("hook_text") or "").strip()[:160],
        "source_node_id": str(payload.get("sourceNodeId") or payload.get("source_node_id") or "").strip(),
        "source": str(payload.get("source") or "player_collect").strip()[:40],
        "start_ms": start_ms,
        "end_ms": end_ms,
        "heat_score": safe_int(payload.get("heatScore") or payload.get("heat_score"), 0, minimum=0, maximum=100),
        "created_at_ms": safe_int(payload.get("clientTsMs") or payload.get("created_at_ms"), now_ms, minimum=0),
    }


def format_saved_moment(row: dict[str, Any], *, drama_id: str, play_url: str) -> dict[str, Any]:
    episode_id = str(row.get("episode_id") or "")
    episode_no = _episode_no_from_id(episode_id) or 0
    return {
        "momentId": str(row.get("moment_id") or ""),
        "dramaId": str(row.get("drama_id") or drama_id),
        "episodeId": episode_id,
        "episodeNo": episode_no,
        "episodeTitle": f"第{episode_no}集" if episode_no else episode_id,
        "startMs": int(row.get("start_ms") or 0),
        "endMs": int(row.get("end_ms") or 0),
        "title": str(row.get("title") or ""),
        "hookText": str(row.get("hook_text") or ""),
        "sourceNodeId": str(row.get("source_node_id") or ""),
        "source": str(row.get("source") or ""),
        "heatScore": int(row.get("heat_score") or 0),
        "savedAtMs": int(row.get("created_at_ms") or 0),
        "playUrl": play_url,
    }


def _episode_no_from_id(episode_id: str) -> int | None:
    match = re.search(r"ep0*(\d+)$", episode_id, re.IGNORECASE)
    if match is None:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None
