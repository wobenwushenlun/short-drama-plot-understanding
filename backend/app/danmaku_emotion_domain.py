from __future__ import annotations

import re
from typing import Any

from backend.app.domain_utils import safe_int


def build_danmaku_emotion_payload(
    *,
    episode_id: str,
    episode: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    candidates = evidence.get("candidates") if isinstance(evidence, dict) else []
    published_nodes = evidence.get("publishedNodes") if isinstance(evidence, dict) else []
    if not isinstance(candidates, list):
        candidates = []
    if not isinstance(published_nodes, list):
        published_nodes = []
    published_by_candidate = {
        str(item.get("candidateId") or ""): item
        for item in published_nodes
        if isinstance(item, dict)
    }
    items = [
        item
        for candidate in candidates
        if isinstance(candidate, dict)
        for item in [_build_danmaku_emotion_item(episode_id, episode, candidate, published_by_candidate)]
        if item is not None
    ]
    items.sort(key=lambda item: (-int(item["heatScore"]), int(item["timeMs"])))
    return {
        "schemaVersion": "1.0",
        "episodeId": episode_id,
        "episodeNo": episode["episode_no"],
        "source": "danmaku_aggregate_review",
        "privacy": {
            "rawContentExported": False,
            "rawRowsExported": False,
            "wordAggregationOnly": True,
        },
        "summary": _build_danmaku_emotion_summary(items),
        "items": items,
    }


def _build_danmaku_emotion_item(
    episode_id: str,
    episode: dict[str, Any],
    candidate: dict[str, Any],
    published_by_candidate: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    candidate_id = str(candidate.get("candidateId") or "")
    if not candidate_id:
        return None
    node = published_by_candidate.get(candidate_id, {})
    time_ms = safe_int(candidate.get("timeMs"), 0, minimum=0)
    comment_count = _extract_count_from_text(str(candidate.get("reason") or ""), r"弹幕\s*(\d+)")
    like_count = _extract_count_from_text(str(candidate.get("reason") or ""), r"点赞\s*(\d+)")
    keywords = _infer_danmaku_keywords(candidate, node if isinstance(node, dict) else {})
    emotion = _infer_danmaku_emotion(str(candidate.get("type") or ""), keywords)
    suggested = _suggest_danmaku_interaction(str(candidate.get("type") or ""), emotion)
    confidence = float(candidate.get("confidence") or 0.0)
    return {
        "hotspotId": candidate_id,
        "episodeId": episode_id,
        "timeMs": time_ms,
        "startMs": max(0, time_ms - 5_000),
        "endMs": min(int(episode["duration_ms"]), time_ms + 10_000),
        "keywords": keywords,
        "emotion": emotion,
        "emotionScore": round(confidence, 3),
        "commentIntensity": comment_count,
        "likeIntensity": like_count,
        "heatScore": _score_danmaku_heat(comment_count, like_count, confidence),
        "suggestedInteraction": suggested["label"],
        "suggestedComponentType": suggested["componentType"],
        "sceneSummary": _summarize_danmaku_scene(candidate, node if isinstance(node, dict) else {}),
        "evidenceRefs": [str(ref) for ref in candidate.get("evidenceRefs", [])],
        "sourceCandidateId": candidate_id,
        "reviewStatus": str(candidate.get("reviewStatus") or "pending"),
    }


def _extract_count_from_text(text: str, pattern: str) -> int:
    match = re.search(pattern, text)
    if match is None:
        return 0
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return 0


def _infer_danmaku_keywords(candidate: dict[str, Any], node: dict[str, Any]) -> list[str]:
    source_text = " ".join(
        [
            str(candidate.get("question") or ""),
            str(candidate.get("reason") or ""),
            str(node.get("title") or ""),
            str(node.get("subtitle") or ""),
            " ".join(str(option) for option in candidate.get("options", []) if str(option).strip()),
        ]
    )
    keyword_rules = [
        ("排面", ["排面", "豪车", "登场", "气场"]),
        ("身份", ["身份", "变化", "王妈", "隐藏"]),
        ("反转", ["反差", "逆袭", "改造", "反转"]),
        ("笑点", ["笑", "医生", "破防", "震惊"]),
        ("关系", ["司机", "孩子", "关系", "对峙"]),
        ("应援", ["终于", "拉满", "压住", "支持"]),
    ]
    keywords = [
        label
        for label, tokens in keyword_rules
        if any(token in source_text for token in tokens)
    ]
    if not keywords:
        node_type = str(candidate.get("type") or "").upper()
        if "PLOT" in node_type:
            keywords.append("剧情预判")
        elif "REACTION" in node_type:
            keywords.append("即时反应")
        else:
            keywords.append("观众共鸣")
    return keywords[:4]


def _infer_danmaku_emotion(candidate_type: str, keywords: list[str]) -> str:
    normalized_type = candidate_type.upper()
    if "FUNNY" in normalized_type or "笑点" in keywords:
        return "欢乐惊讶"
    if "PLOT" in normalized_type or "身份" in keywords or "关系" in keywords:
        return "好奇推理"
    if "REACTION" in normalized_type or "排面" in keywords or "应援" in keywords:
        return "燃爽期待"
    return "共鸣讨论"


def _suggest_danmaku_interaction(candidate_type: str, emotion: str) -> dict[str, str]:
    normalized_type = candidate_type.upper()
    if "FUNNY" in normalized_type:
        return {"label": "表情贴纸 + 轻投票", "componentType": "REACTION_STICKER"}
    if "PLOT" in normalized_type or emotion == "好奇推理":
        return {"label": "剧情预判卡", "componentType": "CHOICE_CARD"}
    if "REACTION" in normalized_type:
        return {"label": "弹幕应援贴纸", "componentType": "DANMAKU_STICKER"}
    return {"label": "共鸣选择卡", "componentType": "CHOICE_CARD"}


def _score_danmaku_heat(comment_count: int, like_count: int, confidence: float) -> int:
    raw_score = comment_count / 35 + like_count / 120 + confidence * 25
    return int(min(100, max(10, round(raw_score))))


def _summarize_danmaku_scene(candidate: dict[str, Any], node: dict[str, Any]) -> str:
    node_title = str(node.get("title") or "").strip()
    node_subtitle = str(node.get("subtitle") or "").strip()
    reason = str(candidate.get("reason") or "").strip()
    if node_title and node_subtitle:
        return f"{node_title}：{node_subtitle}"
    if node_title:
        return node_title
    if reason:
        return reason
    return str(candidate.get("question") or "观众在该时间点出现集中互动").strip()


def _build_danmaku_emotion_summary(items: list[dict[str, Any]]) -> str:
    if not items:
        return "当前分集暂无可用的聚合弹幕热区。"
    top = items[0]
    return (
        f"最强共鸣点出现在 {top['timeMs'] // 1000} 秒附近，情绪为{top['emotion']}，"
        f"适合使用{top['suggestedInteraction']}承接互动。"
    )
