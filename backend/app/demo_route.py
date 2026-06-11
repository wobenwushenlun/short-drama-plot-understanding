from __future__ import annotations

from typing import Any

from backend.app.content_catalog import (
    DRAMA_ID,
    build_evidence_graph,
    build_home_highlight_feed,
    build_timed_events,
    get_drama_by_id,
)
from backend.app.runtime_sqlite_store import get_runtime_store


def build_defense_demo_route(request_base_url: str, drama_id: str = DRAMA_ID) -> dict[str, Any] | None:
    if get_drama_by_id(drama_id) is None:
        return None

    feed = build_home_highlight_feed(request_base_url, size=3, strategy="heat_score_desc_v1", drama_id=drama_id) or {}
    moments = feed.get("items") if isinstance(feed.get("items"), list) else []
    moment = moments[0] if moments else {}
    episode_id = str(moment.get("episodeId") or f"{drama_id}_ep01")
    start_ms = _safe_int(moment.get("startMs"), 0)
    source_node_id = str(moment.get("sourceNodeId") or "")

    timed_payload = build_timed_events(request_base_url, episode_id) or {}
    events = timed_payload.get("events") if isinstance(timed_payload.get("events"), list) else []
    focused_event = _find_event(events, source_node_id) or (events[0] if events else {})
    event_start_ms = _safe_int(focused_event.get("startMs"), start_ms)
    evidence_graph = build_evidence_graph(request_base_url, episode_id, event_start_ms) or {}
    graph_nodes = evidence_graph.get("nodes") if isinstance(evidence_graph.get("nodes"), list) else []
    graph_evidence = evidence_graph.get("evidence") if isinstance(evidence_graph.get("evidence"), list) else []
    dashboard = get_runtime_store().build_operations_dashboard(episode_id)

    steps = [
        {
            "stepId": "home_highlight_feed",
            "order": 1,
            "title": "首页高能流",
            "description": "从真实高能片段流进入，不依赖临时假数据。",
            "actionType": "open_home",
            "api": "/home/highlight-feed?size=3&strategy=heat_score_desc_v1",
            "status": "ready" if moments else "degraded",
            "momentId": str(moment.get("momentId") or ""),
            "episodeId": episode_id,
            "startMs": start_ms,
        },
        {
            "stepId": "player_highlight",
            "order": 2,
            "title": "播放高光点",
            "description": "直接跳转到爽点前几秒，展示播放器、弹幕和互动安全区。",
            "actionType": "open_episode",
            "api": f"/episodes/{episode_id}/play",
            "status": "ready",
            "episodeId": episode_id,
            "startMs": start_ms,
        },
        {
            "stepId": "xray_evidence",
            "order": 3,
            "title": "X-Ray 证据解释",
            "description": "解释当前互动节点为什么出现，展示证据来源和置信度。",
            "actionType": "open_xray",
            "api": f"/episodes/{episode_id}/evidence-graph?timeMs={event_start_ms}",
            "status": "ready" if graph_evidence else "degraded",
            "episodeId": episode_id,
            "startMs": event_start_ms,
            "evidenceCount": len(graph_evidence),
            "nodeCount": len(graph_nodes),
        },
        {
            "stepId": "interaction_click",
            "order": 4,
            "title": "互动点击",
            "description": "点击互动组件，埋点进入 SQLite，后续进入运营看板统计。",
            "actionType": "submit_interaction",
            "api": "/interactions/submit",
            "status": "ready" if focused_event else "degraded",
            "eventId": str(focused_event.get("eventId") or ""),
            "componentType": str(focused_event.get("componentType") or ""),
        },
        {
            "stepId": "aigc_generation",
            "order": 5,
            "title": "Agnes 续写/打卡",
            "description": "通过异步生成任务中心触发 Agnes 或本地模板兜底，失败不覆盖最后成功产物。",
            "actionType": "open_ai_generation_task",
            "api": "/ai/generation/tasks",
            "status": "ready",
            "taskTypes": ["story_continuation_video", "checkin_card"],
        },
        {
            "stepId": "operations_dashboard",
            "order": 6,
            "title": "运营看板",
            "description": "展示互动 CTR、完播、QoE、AIGC 成功/降级等 SQLite 指标。",
            "actionType": "open_operations_dashboard",
            "api": f"/dashboard/operations?episode_id={episode_id}",
            "status": "ready",
            "episodeId": episode_id,
            "metricSource": str(dashboard.get("storage", {}).get("engine") or "sqlite"),
        },
    ]

    return {
        "routeId": f"{drama_id}_defense_demo_v1",
        "dramaId": drama_id,
        "title": "推荐答辩演示路线",
        "source": "existing_cache_sqlite_artifact",
        "entry": {
            "episodeId": episode_id,
            "startMs": start_ms,
            "momentId": str(moment.get("momentId") or ""),
            "title": str(moment.get("title") or "高能片段"),
        },
        "steps": steps,
        "checks": {
            "usesFakeData": False,
            "restartSafe": True,
            "homeFallbackAvailable": True,
            "sqliteBacked": True,
            "evidenceGraphAvailable": bool(graph_evidence),
        },
    }


def build_defense_demo_mode(request_base_url: str, drama_id: str = DRAMA_ID) -> dict[str, Any] | None:
    route = build_defense_demo_route(request_base_url, drama_id=drama_id)
    if route is None:
        return None
    steps = route.get("steps") if isinstance(route.get("steps"), list) else []
    checks = route.get("checks") if isinstance(route.get("checks"), dict) else {}
    entry = route.get("entry") if isinstance(route.get("entry"), dict) else {}
    episode_id = str(entry.get("episodeId") or "")
    latest_video = get_runtime_store().get_latest_success_generation_task("story_continuation_video", episode_id)
    latest_image = get_runtime_store().get_latest_success_generation_task("checkin_card", episode_id)
    ready_count = sum(1 for step in steps if isinstance(step, dict) and str(step.get("status") or "") == "ready")
    content_source = "backend" if ready_count == len(steps) and steps else "cache"
    if not checks.get("evidenceGraphAvailable"):
        content_source = "cache"
    return {
        "enabled": True,
        "routeId": str(route.get("routeId") or ""),
        "dramaId": str(route.get("dramaId") or drama_id),
        "title": "答辩演示模式",
        "description": "固定首页高能流、播放高光点、X-Ray 证据、互动点击、AIGC 生成和运营看板链路。",
        "fixedStrategy": "heat_score_desc_v1",
        "contentSource": content_source,
        "entry": entry,
        "quickSteps": [
            {
                "stepId": str(step.get("stepId") or ""),
                "title": str(step.get("title") or ""),
                "actionType": str(step.get("actionType") or ""),
                "status": str(step.get("status") or ""),
                "api": str(step.get("api") or ""),
            }
            for step in steps
            if isinstance(step, dict)
        ],
        "fallbacks": {
            "homeFallbackAvailable": bool(checks.get("homeFallbackAvailable")),
            "sqliteBacked": bool(checks.get("sqliteBacked")),
            "evidenceGraphAvailable": bool(checks.get("evidenceGraphAvailable")),
            "lastSuccessArtifactAvailable": bool(latest_video or latest_image),
        },
    }


def _find_event(events: list[Any], source_node_id: str) -> dict[str, Any] | None:
    for event in events:
        if not isinstance(event, dict):
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if source_node_id and str(payload.get("id") or "") == source_node_id:
            return event
    return None


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
