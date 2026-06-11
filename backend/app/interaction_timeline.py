from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.app.domain_utils import safe_int


def build_timed_event_from_timeline_item(episode_id: str, item: dict[str, Any]) -> dict[str, Any]:
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    display = item.get("displayStyle") if isinstance(item.get("displayStyle"), dict) else {}
    generation = payload.get("generation") if isinstance(payload.get("generation"), dict) else {}
    payload_hash = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]
    return {
        "eventId": str(item.get("itemId") or f"event_{payload.get('id', '')}"),
        "episodeId": episode_id,
        "startMs": safe_int(item.get("startMs"), 0, minimum=0),
        "endMs": safe_int(item.get("endMs"), 0, minimum=0),
        "type": str(item.get("type") or "INTERACTION"),
        "componentType": str(display.get("componentType") or payload.get("componentType") or ""),
        "visualStyle": str(display.get("visualStyle") or payload.get("visualStyle") or display.get("style") or ""),
        "placement": str(display.get("placement") or payload.get("placement") or ""),
        "safeArea": display.get("safeArea") if isinstance(display.get("safeArea"), dict) else {},
        "maxLines": safe_int(display.get("maxLines"), 2, minimum=1),
        "analyticsKey": str(item.get("analyticsKey") or payload.get("analyticsKey") or ""),
        "evidenceRefs": [str(ref) for ref in generation.get("evidenceRefs", [])],
        "generationSource": str(generation.get("generationSource") or "manual"),
        "confidence": float(generation.get("confidence") or 0.0),
        "reviewStatus": str(generation.get("reviewStatus") or ""),
        "payloadHash": payload_hash,
        "payload": payload,
    }


def build_timeline_items(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    timeline_items: list[dict[str, Any]] = []
    for node in nodes:
        trigger = node.get("trigger", {})
        display = node.get("display", {})
        trigger_ms = int(trigger.get("timeMs") or 0)
        timeout_ms = int(display.get("timeoutMs") or 7_000)
        node_id = str(node.get("id") or "")
        timeline_items.append(
            {
                "itemId": f"timeline_{node_id}",
                "type": "INTERACTION",
                "track": "interaction_track",
                "startMs": trigger_ms,
                "endMs": trigger_ms + timeout_ms,
                "triggerPolicy": {
                    "event": str(trigger.get("event") or "TIMECODE"),
                    "timeMs": trigger_ms,
                    "windowMs": 1_500,
                    "maxShowsPerUser": 2,
                },
                "displayStyle": {
                    "mode": str(display.get("mode") or "SOFT"),
                    "layout": str(display.get("layout") or "BOTTOM_CARD"),
                    "componentType": str(display.get("componentType") or node.get("componentType") or "CHOICE_CARD"),
                    "style": str(display.get("style") or "高光互动"),
                    "visualStyle": str(display.get("visualStyle") or display.get("style") or "高光互动"),
                    "placement": str(display.get("placement") or node.get("placement") or "BOTTOM_CENTER"),
                    "safeArea": display.get("safeArea") if isinstance(display.get("safeArea"), dict) else {},
                    "maxLines": safe_int(display.get("maxLines"), 2, minimum=1),
                    "effectText": str(display.get("effectText") or "点"),
                    "badgeText": str(display.get("badgeText") or "互动"),
                    "promptText": str(display.get("promptText") or "选择一个即时反应"),
                    "timeoutMs": timeout_ms,
                    "allowSkip": bool(display.get("allowSkip", True)),
                    "skipText": str(display.get("skipText") or "继续看"),
                    "analyticsKey": str(display.get("analyticsKey") or node.get("analyticsKey") or f"interaction_component.{node_id}"),
                },
                "action": {
                    "type": "SHOW_INTERACTION",
                    "nodeId": node_id,
                    "submitEndpoint": "/interaction/submit",
                    "nextActionPolicy": "CONTINUE_UNLESS_BRANCH",
                },
                "analyticsKey": str(node.get("analyticsKey") or f"interaction_component.{node_id}"),
                "payload": node,
            }
        )
    return timeline_items
