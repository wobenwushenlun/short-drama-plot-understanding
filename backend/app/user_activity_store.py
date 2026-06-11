from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from backend.app.runtime_sqlite_store import get_runtime_store


def record_watch_progress(payload: dict[str, Any]) -> dict[str, Any] | None:
    drama_id = str(payload.get("dramaId", "")).strip()
    episode_id = str(payload.get("episodeId", "")).strip()
    if not drama_id or not episode_id:
        return None

    now_ms = int(time.time() * 1000)
    progress_ms = int(payload.get("progressMs", 0) or 0)
    duration_ms = int(payload.get("durationMs", 0) or 0)
    record = {
        "record_id": f"wp_{episode_id}",
        "drama_id": drama_id,
        "episode_id": episode_id,
        "progress_ms": progress_ms,
        "duration_ms": duration_ms,
        "is_completed": bool(payload.get("isCompleted", False)),
        "client_ts_ms": int(payload.get("clientTsMs", now_ms) or now_ms),
        "updated_at_ms": now_ms,
    }
    return get_runtime_store().save_watch_progress(record)


def list_watch_history(size: int = 20) -> list[dict[str, Any]]:
    return get_runtime_store().list_watch_history(size)


def record_analytics_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    accepted_ids: list[str] = []
    retryable_ids: list[str] = []
    now_ms = int(time.time() * 1000)

    records: list[dict[str, Any]] = []
    for raw_event in events:
        if not isinstance(raw_event, dict):
            continue

        event_name = str(raw_event.get("eventName", "")).strip()
        if not event_name:
            retryable_ids.append(str(raw_event.get("eventId", "")))
            continue

        event_id = str(raw_event.get("eventId", "")).strip() or f"ae_{uuid4().hex}"
        record = {
            "event_id": event_id,
            "event_name": event_name,
            "screen_name": str(raw_event.get("screenName", "")).strip(),
            "drama_id": str(raw_event.get("dramaId", "")).strip(),
            "episode_id": str(raw_event.get("episodeId", "")).strip(),
            "node_id": str(raw_event.get("nodeId", "")).strip(),
            "progress_ms": raw_event.get("progressMs"),
            "client_ts_ms": int(raw_event.get("clientTsMs", now_ms) or now_ms),
            "properties": raw_event.get("properties") or {},
            "received_at_ms": now_ms,
        }
        records.append(record)
        accepted_ids.append(event_id)

    get_runtime_store().save_analytics_events(records)
    return {
        "accepted_ids": accepted_ids,
        "retryable_ids": [event_id for event_id in retryable_ids if event_id],
    }
