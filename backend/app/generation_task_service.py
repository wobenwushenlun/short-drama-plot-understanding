from __future__ import annotations

import time
import uuid
from typing import Any

from backend.app.runtime_sqlite_store import get_runtime_store


SUPPORTED_GENERATION_TASKS = {"story_continuation_video", "checkin_card"}


def enqueue_generation_task(*, payload: dict[str, Any]) -> dict[str, Any] | None:
    task_type = str(payload.get("taskType") or payload.get("task_type") or "").strip()
    if task_type not in SUPPORTED_GENERATION_TASKS:
        return None
    episode_id = str(payload.get("episodeId") or payload.get("episode_id") or "").strip()
    if not episode_id:
        return None
    drama_id = str(payload.get("dramaId") or payload.get("drama_id") or "tainai3").strip() or "tainai3"
    now_ms = _now_ms()
    task_id = f"gen_{task_type}_{now_ms}_{uuid.uuid4().hex[:8]}"
    public_payload = _public_request_payload({**payload, "episodeId": episode_id, "dramaId": drama_id})
    store = get_runtime_store()
    queued = store.save_generation_task(
        {
            "taskId": task_id,
            "taskType": task_type,
            "dramaId": drama_id,
            "episodeId": episode_id,
            "status": "queued",
            "createdAtMs": now_ms,
            "updatedAtMs": now_ms,
            "result": {"request": public_payload},
        }
    )
    return _with_last_success(queued)


def run_generation_task(
    *,
    task_id: str,
    payload: dict[str, Any],
    request_base_url: str,
    ai_service: Any,
) -> dict[str, Any] | None:
    store = get_runtime_store()
    task = store.get_generation_task(task_id)
    if not task:
        return None
    running = store.save_generation_task({**task, "status": "running", "updatedAtMs": _now_ms()})
    try:
        completed = _run_generation_task(
            task=running,
            payload=payload,
            request_base_url=request_base_url,
            ai_service=ai_service,
        )
    except Exception as exc:  # pragma: no cover - 兜底保护，具体分支由接口 smoke 覆盖
        completed = {
            **running,
            "status": "failed",
            "degradeReason": str(exc),
            "updatedAtMs": _now_ms(),
            "result": {"error": str(exc), "request": _public_request_payload(payload)},
        }
    saved = store.save_generation_task(completed)
    return _with_last_success(saved)


def get_generation_task(task_id: str) -> dict[str, Any] | None:
    task = get_runtime_store().get_generation_task(task_id)
    return _with_last_success(task) if task else None


def build_generated_asset_management(*, drama_id: str = "", limit: int = 30) -> dict[str, Any]:
    tasks = get_runtime_store().list_generation_tasks(
        drama_id=drama_id or None,
        limit=limit,
    )
    successes = [task for task in tasks if str(task.get("status") or "") == "succeeded"]
    failed = [task for task in tasks if str(task.get("status") or "") in {"failed", "degraded"}]
    recent_successes = [_asset_management_item(task) for task in successes]
    failed_attempts = [_asset_management_item(task) for task in failed]
    total_bytes = sum(
        int((item.get("assetCache") or {}).get("byteSize") or 0)
        for item in recent_successes
        if isinstance(item.get("assetCache"), dict)
    )
    return {
        "dramaId": drama_id,
        "summary": {
            "successCount": len(successes),
            "failedCount": len(failed),
            "cachedByteSize": total_bytes,
            "source": "sqlite_generation_tasks",
        },
        "recentSuccesses": recent_successes,
        "failedAttempts": failed_attempts,
    }


def cleanup_failed_generated_assets(*, drama_id: str = "") -> dict[str, Any]:
    deleted = get_runtime_store().delete_generation_tasks_by_statuses(
        statuses={"failed", "degraded"},
        drama_id=drama_id or None,
    )
    return {
        "dramaId": drama_id,
        "deletedCount": deleted,
        "statuses": ["failed", "degraded"],
    }


def _run_generation_task(
    *,
    task: dict[str, Any],
    payload: dict[str, Any],
    request_base_url: str,
    ai_service: Any,
) -> dict[str, Any]:
    task_type = str(task["taskType"])
    if task_type == "story_continuation_video":
        envelope = ai_service.story_continuation(payload, request_base_url)
        return _task_from_story_continuation(task, envelope)
    if task_type == "checkin_card":
        envelope = ai_service.checkin_card(payload, request_base_url)
        return _task_from_checkin_card(task, envelope)
    raise ValueError("unsupported generation task")


def _task_from_story_continuation(task: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
    result = envelope.get("result") if isinstance(envelope.get("result"), dict) else {}
    asset = result.get("generated_asset") if isinstance(result.get("generated_asset"), dict) else {}
    provider = asset.get("provider") if isinstance(asset.get("provider"), dict) else {}
    remote_attempt = asset.get("remoteAttempt") if isinstance(asset.get("remoteAttempt"), dict) else {}
    media_url = str(asset.get("mediaUrl") or "")
    envelope_status = str(envelope.get("status") or "")
    remote_status = str(remote_attempt.get("status") or "")
    status = "succeeded" if envelope_status == "ok" and media_url and remote_status != "degraded" else "degraded"
    if not media_url:
        status = "failed"
    degrade_reason = str(remote_attempt.get("degradeReason") or envelope.get("degrade_reason") or "")
    return {
        **task,
        "status": status,
        "provider": str(provider.get("name") or "story_continuation"),
        "modelName": str((envelope.get("model") or {}).get("model_name") or provider.get("modelName") or ""),
        "mediaUrl": media_url,
        "mediaType": str(asset.get("mediaType") or "video/mp4" if media_url else ""),
        "latencyMs": int(envelope.get("latency_ms") or remote_attempt.get("latencyMs") or 0),
        "degradeReason": degrade_reason,
        "updatedAtMs": _now_ms(),
        "result": {
            "title": str(result.get("continuation_title") or ""),
            "summary": str(result.get("continuation_summary") or ""),
            "providerMode": str(provider.get("mode") or ""),
            "remoteAttempt": remote_attempt,
            "assetCache": asset.get("assetCache") if isinstance(asset.get("assetCache"), dict) else {},
            "artifact": envelope.get("artifact") if isinstance(envelope.get("artifact"), dict) else {},
        },
    }


def _task_from_checkin_card(task: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
    result = envelope.get("result") if isinstance(envelope.get("result"), dict) else {}
    media_url = str(result.get("imageUrl") or "")
    result_status = str(result.get("status") or envelope.get("status") or "")
    status = "succeeded" if result_status == "ok" and media_url else "degraded"
    if not media_url and result_status not in {"ok", "degraded"}:
        status = "failed"
    return {
        **task,
        "status": status,
        "provider": str(result.get("provider") or "checkin_card"),
        "modelName": str((envelope.get("model") or {}).get("model_name") or ""),
        "mediaUrl": media_url,
        "mediaType": "image/png" if media_url else "",
        "latencyMs": int(envelope.get("latency_ms") or result.get("latencyMs") or 0),
        "degradeReason": str(result.get("degradeReason") or envelope.get("degrade_reason") or ""),
        "updatedAtMs": _now_ms(),
        "result": {
            "title": str(result.get("title") or ""),
            "prompt": str(result.get("prompt") or "")[:240],
            "assetCache": result.get("assetCache") if isinstance(result.get("assetCache"), dict) else {},
            "artifact": envelope.get("artifact") if isinstance(envelope.get("artifact"), dict) else {},
        },
    }


def _with_last_success(task: dict[str, Any]) -> dict[str, Any]:
    latest = get_runtime_store().get_latest_success_generation_task(
        str(task.get("taskType") or ""),
        str(task.get("episodeId") or ""),
    )
    return {
        **task,
        "lastSuccess": _last_success_payload(latest),
    }


def _last_success_payload(task: dict[str, Any] | None) -> dict[str, Any]:
    if not task:
        return {
            "taskId": "",
            "mediaUrl": "",
            "mediaType": "",
            "provider": "",
            "assetCache": {},
            "updatedAtMs": 0,
        }
    result = task.get("result") if isinstance(task.get("result"), dict) else {}
    return {
        "taskId": str(task.get("taskId") or ""),
        "mediaUrl": str(task.get("mediaUrl") or ""),
        "mediaType": str(task.get("mediaType") or ""),
        "provider": str(task.get("provider") or ""),
        "assetCache": result.get("assetCache") if isinstance(result.get("assetCache"), dict) else {},
        "updatedAtMs": int(task.get("updatedAtMs") or 0),
    }


def _asset_management_item(task: dict[str, Any]) -> dict[str, Any]:
    result = task.get("result") if isinstance(task.get("result"), dict) else {}
    asset_cache = result.get("assetCache") if isinstance(result.get("assetCache"), dict) else {}
    return {
        "taskId": str(task.get("taskId") or ""),
        "taskType": str(task.get("taskType") or ""),
        "dramaId": str(task.get("dramaId") or ""),
        "episodeId": str(task.get("episodeId") or ""),
        "status": str(task.get("status") or ""),
        "provider": str(task.get("provider") or ""),
        "modelName": str(task.get("modelName") or ""),
        "mediaUrl": str(task.get("mediaUrl") or ""),
        "mediaType": str(task.get("mediaType") or ""),
        "latencyMs": int(task.get("latencyMs") or 0),
        "degradeReason": str(task.get("degradeReason") or ""),
        "title": str(result.get("title") or ""),
        "assetCache": asset_cache,
        "updatedAtMs": int(task.get("updatedAtMs") or 0),
    }


def _public_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "taskType": str(payload.get("taskType") or payload.get("task_type") or ""),
        "dramaId": str(payload.get("dramaId") or payload.get("drama_id") or ""),
        "episodeId": str(payload.get("episodeId") or payload.get("episode_id") or ""),
        "momentId": str(payload.get("momentId") or payload.get("moment_id") or ""),
        "style": str(payload.get("style") or ""),
    }


def _now_ms() -> int:
    return int(time.time() * 1000)
