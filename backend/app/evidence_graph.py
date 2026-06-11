from __future__ import annotations

from typing import Any

from backend.app.domain_utils import safe_int


def build_episode_evidence_graph_payload(
    *,
    episode_id: str,
    timed_payload: dict[str, Any],
    evidence_context: dict[str, Any],
    focus_time_ms: int | None = None,
) -> dict[str, Any]:
    evidence = _build_evidence_items(episode_id, evidence_context)
    evidence_by_ref = {str(item.get("refId") or ""): item for item in evidence}
    nodes = _build_graph_nodes(timed_payload, evidence_by_ref, focus_time_ms)
    relations = _build_relations(nodes, evidence_by_ref)
    story_facets = _build_story_facets(nodes, evidence)
    explanations = _build_node_explanations(nodes, evidence_by_ref, story_facets)
    return {
        "schemaVersion": "1.1",
        "episodeId": episode_id,
        "focusTimeMs": focus_time_ms if focus_time_ms is not None else 0,
        "sourceStatus": str(timed_payload.get("generationPipeline", {}).get("sourceStatus") or "unknown"),
        "evidenceSources": timed_payload.get("generationPipeline", {}).get("evidenceSources", []),
        "nodeCount": len(nodes),
        "evidenceCount": len(evidence),
        "relationCount": len(relations),
        "storyFacets": story_facets,
        "explanations": explanations,
        "nodes": nodes,
        "evidence": evidence,
        "relations": relations,
    }


def _build_graph_nodes(
    timed_payload: dict[str, Any],
    evidence_by_ref: dict[str, dict[str, Any]],
    focus_time_ms: int | None,
) -> list[dict[str, Any]]:
    raw_events = timed_payload.get("events") if isinstance(timed_payload.get("events"), list) else []
    nodes: list[dict[str, Any]] = []
    for event in raw_events:
        if not isinstance(event, dict):
            continue
        start_ms = safe_int(event.get("startMs"), 0, minimum=0)
        end_ms = safe_int(event.get("endMs"), start_ms, minimum=start_ms)
        if focus_time_ms is not None and not _is_near_time_window(focus_time_ms, start_ms, end_ms):
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        evidence_refs = [str(ref) for ref in event.get("evidenceRefs", []) if str(ref).strip()]
        resolved_refs = [ref for ref in evidence_refs if ref in evidence_by_ref]
        nodes.append(
            {
                "nodeId": str(payload.get("id") or event.get("eventId") or ""),
                "eventId": str(event.get("eventId") or ""),
                "title": str(payload.get("title") or event.get("componentType") or "剧情互动"),
                "timeMs": start_ms,
                "endMs": end_ms,
                "componentType": str(event.get("componentType") or ""),
                "generationSource": str(event.get("generationSource") or "manual"),
                "reviewStatus": str(event.get("reviewStatus") or ""),
                "confidence": float(event.get("confidence") or 0.0),
                "evidenceRefs": evidence_refs,
                "resolvedEvidenceRefs": resolved_refs,
                "whyText": _build_why_text(payload, resolved_refs, evidence_by_ref),
            }
        )
    return nodes


def _build_relations(
    nodes: list[dict[str, Any]],
    evidence_by_ref: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []
    for node in nodes:
        for ref_id in node.get("evidenceRefs", []):
            if ref_id not in evidence_by_ref:
                continue
            relations.append(
                {
                    "fromNodeId": str(node.get("nodeId") or ""),
                    "toEvidenceRef": ref_id,
                    "relationType": "SUPPORTED_BY",
                    "timeDeltaMs": abs(
                        safe_int(node.get("timeMs"), 0, minimum=0)
                        - safe_int(evidence_by_ref[ref_id].get("timeMs"), 0, minimum=0)
                    ),
                }
            )
    return relations


def _build_evidence_items(episode_id: str, evidence_context: dict[str, Any]) -> list[dict[str, Any]]:
    result = evidence_context.get("result") if isinstance(evidence_context.get("result"), dict) else {}
    items: list[dict[str, Any]] = []
    items.extend(_asr_evidence_items(episode_id, result))
    items.extend(_ocr_evidence_items(episode_id, result))
    items.extend(_frame_evidence_items(episode_id, evidence_context))
    items.extend(_danmaku_evidence_items(episode_id, evidence_context))
    for item in items:
        item.setdefault("assetPath", "")
    return sorted(items, key=lambda item: (safe_int(item.get("timeMs"), 0, minimum=0), str(item.get("kind") or "")))


def _asr_evidence_items(episode_id: str, result: dict[str, Any]) -> list[dict[str, Any]]:
    audio_text = result.get("audio_text") if isinstance(result.get("audio_text"), dict) else {}
    turns = audio_text.get("speaker_turns") if isinstance(audio_text.get("speaker_turns"), list) else []
    items: list[dict[str, Any]] = []
    for index, turn in enumerate(turns, start=1):
        if not isinstance(turn, dict):
            continue
        text = str(turn.get("text") or turn.get("transcript") or "").strip()
        start_ms = safe_int(turn.get("start_ms"), 0, minimum=0)
        items.append(
            {
                "refId": f"asr_segment:{episode_id}:{index:02d}",
                "kind": "asr_segment",
                "sourceLabel": "台词证据",
                "timeMs": start_ms,
                "endMs": safe_int(turn.get("end_ms"), start_ms, minimum=start_ms),
                "displayText": text[:80] or "台词片段",
            }
        )
    return items


def _ocr_evidence_items(episode_id: str, result: dict[str, Any]) -> list[dict[str, Any]]:
    cues = result.get("screen_text_cues") if isinstance(result.get("screen_text_cues"), list) else []
    items: list[dict[str, Any]] = []
    for index, cue in enumerate(cues, start=1):
        if not isinstance(cue, dict):
            continue
        items.append(
            {
                "refId": f"ocr_cue:{episode_id}:{index:02d}",
                "kind": "ocr_cue",
                "sourceLabel": "画面文字证据",
                "timeMs": safe_int(cue.get("time_ms"), 0, minimum=0),
                "displayText": str(cue.get("text") or cue.get("content") or "屏幕文字").strip()[:80],
            }
        )
    return items


def _frame_evidence_items(episode_id: str, evidence_context: dict[str, Any]) -> list[dict[str, Any]]:
    frames = evidence_context.get("frames") if isinstance(evidence_context.get("frames"), list) else []
    items: list[dict[str, Any]] = []
    for index, frame in enumerate(frames, start=1):
        if not isinstance(frame, dict):
            continue
        items.append(
            {
                "refId": f"frame:{episode_id}:{index:02d}",
                "kind": "frame",
                "sourceLabel": "关键帧证据",
                "timeMs": safe_int(frame.get("timeMs"), 0, minimum=0),
                "displayText": str(frame.get("samplingReason") or frame.get("samplingSource") or "关键画面").strip()[:80],
                "assetPath": str(frame.get("path") or ""),
            }
        )
    return items


def _danmaku_evidence_items(episode_id: str, evidence_context: dict[str, Any]) -> list[dict[str, Any]]:
    danmaku = evidence_context.get("danmaku") if isinstance(evidence_context.get("danmaku"), dict) else {}
    candidates = danmaku.get("candidates") if isinstance(danmaku.get("candidates"), list) else []
    items: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        time_ms = safe_int(candidate.get("timeMs"), 0, minimum=0)
        reason = str(candidate.get("reason") or "弹幕聚合热区").strip()
        for ref_id in candidate.get("evidenceRefs", []):
            ref_text = str(ref_id or "")
            if not ref_text:
                continue
            kind = "reviewed_frame" if ref_text.startswith("reviewed_frame:") else "danmaku_bucket"
            items.append(
                {
                    "refId": ref_text,
                    "kind": kind,
                    "sourceLabel": "观众共鸣证据" if kind == "danmaku_bucket" else "人工复核画面",
                    "timeMs": time_ms,
                    "displayText": reason[:100],
                }
            )
    return items


def _build_why_text(
    payload: dict[str, Any],
    resolved_refs: list[str],
    evidence_by_ref: dict[str, dict[str, Any]],
) -> str:
    title = str(payload.get("title") or "这个互动点").strip()
    if not resolved_refs:
        return f"{title} 来自人工配置或兜底规则，当前没有可解析的多模态证据。"
    labels = [str(evidence_by_ref[ref].get("sourceLabel") or "证据") for ref in resolved_refs if ref in evidence_by_ref]
    unique_labels = "、".join(dict.fromkeys(labels))
    return f"{title} 由{unique_labels}共同支撑，适合在当前剧情高光处触发互动。"


def _build_story_facets(nodes: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> dict[str, list[str]]:
    text_blob = " ".join(
        [
            *(str(node.get("title") or "") for node in nodes),
            *(str(node.get("whyText") or "") for node in nodes),
            *(str(item.get("displayText") or "") for item in evidence),
        ]
    )
    return {
        "characters": _dedupe(
            [
                name
                for name in ["容遇", "纪家", "太奶奶", "晚辈"]
                if name in text_blob
            ]
        ),
        "conflicts": _dedupe(_match_story_tags(text_blob, _CONFLICT_KEYWORDS, "身份质疑")),
        "reversals": _dedupe(_match_story_tags(text_blob, _REVERSAL_KEYWORDS, "气场反转")),
        "audienceResonance": _dedupe(_match_story_tags(text_blob, _RESONANCE_KEYWORDS, "观众共鸣")),
    }


def _build_node_explanations(
    nodes: list[dict[str, Any]],
    evidence_by_ref: dict[str, dict[str, Any]],
    story_facets: dict[str, list[str]],
) -> list[dict[str, Any]]:
    explanations: list[dict[str, Any]] = []
    for node in nodes:
        refs = [ref for ref in node.get("resolvedEvidenceRefs", []) if ref in evidence_by_ref]
        evidence_labels = _dedupe([str(evidence_by_ref[ref].get("sourceLabel") or "证据") for ref in refs])
        story_tags = _dedupe(
            [
                *story_facets.get("characters", [])[:2],
                *story_facets.get("conflicts", [])[:1],
                *story_facets.get("reversals", [])[:1],
            ]
        )
        audience_resonance = "、".join(story_facets.get("audienceResonance", [])[:2]) or "观众共鸣"
        explanations.append(
            {
                "nodeId": str(node.get("nodeId") or ""),
                "title": str(node.get("title") or "剧情互动"),
                "storyTags": story_tags,
                "audienceResonance": audience_resonance,
                "evidenceSummary": "、".join(evidence_labels) or "人工审核节点",
                "explainText": _build_explain_text(node, evidence_labels, audience_resonance),
                "confidence": float(node.get("confidence") or 0.0),
            }
        )
    return explanations


def _build_explain_text(node: dict[str, Any], evidence_labels: list[str], audience_resonance: str) -> str:
    title = str(node.get("title") or "当前互动").strip()
    evidence_text = "、".join(evidence_labels) if evidence_labels else "人工审核"
    return f"{title} 命中{audience_resonance}，并由{evidence_text}支撑，可解释为当前剧情爽点。"


def _match_story_tags(text: str, mapping: dict[str, str], fallback: str) -> list[str]:
    tags = [label for keyword, label in mapping.items() if keyword in text]
    return tags or ([fallback] if text.strip() else [])


def _dedupe(values: list[str]) -> list[str]:
    return [value for value in dict.fromkeys(str(item).strip() for item in values if str(item).strip())]


def _is_near_time_window(focus_time_ms: int, start_ms: int, end_ms: int) -> bool:
    if start_ms <= focus_time_ms <= end_ms:
        return True
    center_ms = (start_ms + end_ms) // 2
    return abs(center_ms - focus_time_ms) <= 20_000


_CONFLICT_KEYWORDS = {
    "身份": "身份质疑",
    "到底是谁": "身份追问",
    "质疑": "被质疑",
    "冲突": "正面冲突",
}

_REVERSAL_KEYWORDS = {
    "气场": "气场压制",
    "反转": "局面反转",
    "压住": "压住局面",
    "登场": "人物登场",
}

_RESONANCE_KEYWORDS = {
    "弹幕": "弹幕热区",
    "共振": "观众共振",
    "共鸣": "观众共鸣",
    "高能": "高能爽点",
}
