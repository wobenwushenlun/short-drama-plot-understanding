from fastapi import APIRouter, Request, Response

from backend.app.api.routes.content import _error, _ok
from backend.app.content_catalog import build_interaction_insights, get_drama_by_id, get_episode_by_id
from backend.app.runtime_sqlite_store import get_runtime_store
from backend.app.user_activity_store import (
    list_watch_history,
    record_analytics_events,
    record_watch_progress,
)


router = APIRouter()


@router.post("/watch/progress")
def watch_progress(payload: dict[str, object], response: Response):
    record = record_watch_progress(payload)
    if record is None:
        return _error(response, 400, "invalid watch progress")
    return _ok(record)


@router.get("/user/history")
def user_history(request: Request, size: int = 20, cursor: str | None = None):
    items: list[dict[str, object]] = []
    for record in list_watch_history(size):
        drama = get_drama_by_id(str(record["drama_id"]))
        episode = get_episode_by_id(str(record["episode_id"]))
        title = episode["title"] if episode is not None else str(record["episode_id"])
        items.append(
            {
                "drama_id": record["drama_id"],
                "drama_title": drama["title"] if drama is not None else str(record["drama_id"]),
                "episode_id": record["episode_id"],
                "episode_title": title,
                "play_url": f"{str(request.base_url).rstrip('/')}/media/episodes/{record['episode_id']}",
                "last_progress_ms": record["progress_ms"],
                "duration_ms": record["duration_ms"],
                "is_completed": record["is_completed"],
                "updated_at_ms": record["updated_at_ms"],
            }
        )
    return _ok(
        {
            "items": items,
            "next_cursor": cursor or "",
            "has_more": False,
        }
    )


@router.post("/analytics/events")
def analytics_events(payload: dict[str, object], response: Response):
    events = payload.get("events")
    if not isinstance(events, list):
        return _error(response, 400, "invalid analytics payload")
    result = record_analytics_events(events)
    return _ok(result)


@router.get("/analytics/summary")
def analytics_summary(episode_id: str | None = None):
    result = get_runtime_store().build_runtime_summary(episode_id)
    if episode_id:
        interaction_insights = build_interaction_insights(episode_id)
        result["interaction"]["nodeHeat"] = (
            interaction_insights.get("nodes", []) if interaction_insights else []
        )
    return _ok(result)


@router.get("/user/profile")
def user_profile():
    return _ok(get_runtime_store().build_user_profile())


@router.get("/dashboard/operations")
def operations_dashboard(episode_id: str | None = None, drama_id: str | None = None):
    return _ok(get_runtime_store().build_operations_dashboard(episode_id, drama_id=drama_id))
