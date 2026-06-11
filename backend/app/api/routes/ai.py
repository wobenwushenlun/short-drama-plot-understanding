from fastapi import APIRouter, BackgroundTasks, Request, Response

from backend.app.ai_service import get_ai_service
from backend.app.generation_task_service import (
    build_generated_asset_management,
    cleanup_failed_generated_assets,
    enqueue_generation_task,
    get_generation_task,
    run_generation_task,
)


router = APIRouter()


def _ok(data: dict[str, object]) -> dict[str, object]:
    return {"code": 0, "message": "ok", "data": data}


def _error(response: Response, status_code: int, message: str) -> dict[str, object]:
    response.status_code = status_code
    return {"code": status_code, "message": message, "data": {}}


@router.post("/ai/content/recap")
def ai_content_recap(payload: dict[str, object], request: Request, response: Response):
    try:
        result = get_ai_service().content_recap(payload, str(request.base_url))
    except ValueError as exc:
        return _error(response, 400, str(exc))
    except Exception as exc:  # pragma: no cover - 兜底异常由测试覆盖接口返回
        return _error(response, 500, str(exc))
    return _ok(result)


@router.post("/ai/interaction/feedback")
def ai_interaction_feedback(payload: dict[str, object], request: Request, response: Response):
    try:
        result = get_ai_service().interaction_feedback(payload, str(request.base_url))
    except ValueError as exc:
        return _error(response, 400, str(exc))
    except Exception as exc:  # pragma: no cover - 兜底异常由测试覆盖接口返回
        return _error(response, 500, str(exc))
    return _ok(result)


@router.post("/ai/tag/extract")
def ai_tag_extract(payload: dict[str, object], request: Request, response: Response):
    try:
        result = get_ai_service().tag_extract(payload, str(request.base_url))
    except ValueError as exc:
        return _error(response, 400, str(exc))
    except Exception as exc:  # pragma: no cover - 兜底异常由测试覆盖接口返回
        return _error(response, 500, str(exc))
    return _ok(result)


@router.post("/ai/moderation/check")
def ai_moderation_check(payload: dict[str, object], response: Response):
    try:
        result = get_ai_service().moderation_check(payload)
    except ValueError as exc:
        return _error(response, 400, str(exc))
    except Exception as exc:  # pragma: no cover - 兜底异常由测试覆盖接口返回
        return _error(response, 500, str(exc))
    return _ok(result)


@router.post("/ai/discussion/seed")
def ai_discussion_seed(payload: dict[str, object], request: Request, response: Response):
    try:
        result = get_ai_service().discussion_seed(payload, str(request.base_url))
    except ValueError as exc:
        return _error(response, 400, str(exc))
    except Exception as exc:  # pragma: no cover - 兜底异常由测试覆盖接口返回
        return _error(response, 500, str(exc))
    return _ok(result)


@router.post("/ai/story/continuation")
def ai_story_continuation(payload: dict[str, object], request: Request, response: Response):
    try:
        result = get_ai_service().story_continuation(payload, str(request.base_url))
    except ValueError as exc:
        return _error(response, 400, str(exc))
    except Exception as exc:  # pragma: no cover - 兜底异常由测试覆盖接口返回
        return _error(response, 500, str(exc))
    return _ok(result)


@router.post("/ai/history/recap")
def ai_history_recap(payload: dict[str, object], request: Request, response: Response):
    try:
        result = get_ai_service().history_recap(payload, str(request.base_url))
    except ValueError as exc:
        return _error(response, 400, str(exc))
    except Exception as exc:  # pragma: no cover - 兜底异常由测试覆盖接口返回
        return _error(response, 500, str(exc))
    return _ok(result)


@router.post("/ai/recommend/home")
def ai_recommend_home(payload: dict[str, object], request: Request, response: Response):
    try:
        result = get_ai_service().recommend_home(payload, str(request.base_url))
    except ValueError as exc:
        return _error(response, 400, str(exc))
    except Exception as exc:  # pragma: no cover - 兜底异常由测试覆盖接口返回
        return _error(response, 500, str(exc))
    return _ok(result)


@router.get("/ai/agnes/status")
def ai_agnes_status(response: Response):
    try:
        result = get_ai_service().agnes_status()
    except Exception as exc:  # pragma: no cover - 配置状态接口只返回兜底错误
        return _error(response, 500, str(exc))
    return _ok(result)


@router.post("/ai/checkin-card")
def ai_checkin_card(payload: dict[str, object], request: Request, response: Response):
    try:
        result = get_ai_service().checkin_card(payload, str(request.base_url))
    except ValueError as exc:
        return _error(response, 400, str(exc))
    except Exception as exc:  # pragma: no cover - 远端生成异常由服务层降级
        return _error(response, 500, str(exc))
    return _ok(result)


@router.post("/ai/generation/tasks")
def ai_generation_task_create(
    payload: dict[str, object],
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
):
    result = enqueue_generation_task(
        payload=dict(payload or {}),
    )
    if result is None:
        return _error(response, 400, "invalid generation task")
    background_tasks.add_task(
        run_generation_task,
        task_id=str(result["taskId"]),
        payload=dict(result.get("result", {}).get("request", {})),
        request_base_url=str(request.base_url),
        ai_service=get_ai_service(),
    )
    return _ok(result)


@router.get("/ai/generation/tasks/{task_id}")
def ai_generation_task_get(task_id: str, response: Response):
    result = get_generation_task(task_id)
    if result is None:
        return _error(response, 404, "generation task not found")
    return _ok(result)


@router.get("/ai/generated-assets")
def ai_generated_assets(drama_id: str = "", limit: int = 30):
    return _ok(build_generated_asset_management(drama_id=drama_id, limit=limit))


@router.delete("/ai/generated-assets/failed")
def ai_generated_assets_cleanup_failed(drama_id: str = ""):
    return _ok(cleanup_failed_generated_assets(drama_id=drama_id))
