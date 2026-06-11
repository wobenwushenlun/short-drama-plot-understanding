from fastapi import APIRouter, Request, Response

from backend.app.video_understanding_service import get_video_understanding_service


router = APIRouter()


def _ok(data: dict[str, object]) -> dict[str, object]:
    return {"code": 0, "message": "ok", "data": data}


def _error(response: Response, status_code: int, message: str) -> dict[str, object]:
    response.status_code = status_code
    return {"code": status_code, "message": message, "data": {}}


@router.post("/ai/video/analyze")
def ai_video_analyze(payload: dict[str, object], request: Request, response: Response):
    try:
        result = get_video_understanding_service().analyze_episode(payload, str(request.base_url))
    except ValueError as exc:
        return _error(response, 400, str(exc))
    except Exception as exc:  # pragma: no cover - 兜底异常由测试覆盖接口返回
        return _error(response, 500, str(exc))
    return _ok(result)


@router.get("/ai/video/episodes/{episode_id}/understanding")
def ai_video_episode_understanding(
    episode_id: str,
    request: Request,
    response: Response,
    drama_id: str = "tainai3",
    force_refresh: bool = False,
):
    try:
        result = get_video_understanding_service().analyze_episode(
            {
                "episodeId": episode_id,
                "dramaId": drama_id,
                "forceRefresh": force_refresh,
            },
            str(request.base_url),
        )
    except ValueError as exc:
        return _error(response, 400, str(exc))
    except Exception as exc:  # pragma: no cover - 兜底异常由测试覆盖接口返回
        return _error(response, 500, str(exc))
    return _ok(result)
