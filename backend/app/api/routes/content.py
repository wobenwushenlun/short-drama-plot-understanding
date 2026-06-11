from pathlib import Path

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import FileResponse, StreamingResponse

from backend.app.aigc_insert_service import get_aigc_insert_asset_path, get_video_understanding_frame_path
from backend.app.generated_asset_store import generated_asset_media_type, get_generated_asset_path
from backend.app.content_catalog import (
    build_danmaku_emotion_report,
    build_evidence_graph,
    build_home_highlight_feed,
    build_interaction_nodes,
    build_interaction_candidate_review_queue,
    build_interaction_insights,
    build_quality_evaluation_report,
    build_play_response,
    build_drama_registry_status,
    build_shareable_moments,
    build_story_summary_cache_status,
    build_timed_events,
    get_drama_by_id,
    get_drama_cover_asset_path,
    get_episode_file_path,
    get_hls_asset_path,
    list_episodes,
    list_interaction_records,
    list_saved_shareable_moments,
    list_home_items,
    refresh_story_summary_cache,
    review_interaction_candidate,
    save_shareable_moment,
    submit_interaction_answer,
)
from backend.app.demo_route import build_defense_demo_mode, build_defense_demo_route


router = APIRouter()
_MEDIA_CHUNK_SIZE = 1024 * 1024


def _ok(data: dict[str, object]) -> dict[str, object]:
    return {"code": 0, "message": "ok", "data": data}


def _error(response: Response, status_code: int, message: str) -> dict[str, object]:
    response.status_code = status_code
    return {"code": status_code, "message": message, "data": {}}


def _file_headers(file_size: int) -> dict[str, str]:
    return {
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=3600",
        "Content-Length": str(file_size),
        "Content-Type": "video/mp4",
        "Content-Disposition": "inline",
        "X-Content-Type-Options": "nosniff",
    }


def _parse_range_header(range_header: str | None, file_size: int) -> tuple[int, int] | None:
    if not range_header:
        return None
    if not range_header.startswith("bytes="):
        raise ValueError("invalid range unit")

    range_spec = range_header.removeprefix("bytes=").strip()
    if "," in range_spec:
        raise ValueError("multiple ranges are not supported")

    start_text, end_text = range_spec.split("-", 1)
    if start_text == "":
        if not end_text:
            raise ValueError("invalid suffix range")
        suffix_length = int(end_text)
        if suffix_length <= 0:
            raise ValueError("invalid suffix range")
        start = max(file_size - suffix_length, 0)
        end = file_size - 1
        return start, end

    start = int(start_text)
    if start < 0 or start >= file_size:
        raise ValueError("range start out of bounds")

    if end_text:
        end = int(end_text)
        if end < start:
            raise ValueError("range end before start")
        end = min(end, file_size - 1)
    else:
        end = file_size - 1
    return start, end


def _stream_file_range(file_path: Path, start: int, end: int):
    with file_path.open("rb") as file_obj:
        file_obj.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = file_obj.read(min(_MEDIA_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@router.get("/home/recommend")
def home_recommend(
    request: Request,
    cursor: str | None = None,
    size: int = 10,
):
    items = list_home_items(str(request.base_url), size=size)
    return _ok(
        {
            "items": items,
            "next_cursor": cursor or "",
            "has_more": False,
        }
    )


@router.get("/home/highlight-feed")
def home_highlight_feed(
    request: Request,
    response: Response,
    size: int = 6,
    strategy: str = "heat_score_desc_v1",
    drama_id: str = "",
):
    payload = build_home_highlight_feed(str(request.base_url), size=size, strategy=strategy, drama_id=drama_id)
    if payload is None:
        return _error(response, 404, "home feed not available")
    return _ok(payload)


@router.get("/demo/route")
def defense_demo_route(request: Request, response: Response, drama_id: str = "tainai3"):
    payload = build_defense_demo_route(str(request.base_url), drama_id=drama_id)
    if payload is None:
        return _error(response, 404, "demo route not available")
    return _ok(payload)


@router.get("/demo/mode")
def defense_demo_mode(request: Request, response: Response, drama_id: str = "tainai3"):
    payload = build_defense_demo_mode(str(request.base_url), drama_id=drama_id)
    if payload is None:
        return _error(response, 404, "demo mode not available")
    return _ok(payload)


@router.get("/quality/evaluation")
def quality_evaluation(request: Request):
    return _ok(build_quality_evaluation_report(str(request.base_url)))


@router.get("/story-summary/cache")
def story_summary_cache_status(
    request: Request,
    response: Response,
    drama_id: str = "tainai3",
):
    if get_drama_by_id(drama_id, str(request.base_url)) is None:
        return _error(response, 404, "drama not found")
    return _ok(build_story_summary_cache_status(str(request.base_url), drama_id=drama_id))


@router.post("/story-summary/cache/refresh")
def story_summary_cache_refresh(
    request: Request,
    response: Response,
    payload: dict[str, object] | None = None,
):
    drama_id = str((payload or {}).get("dramaId") or (payload or {}).get("drama_id") or "tainai3")
    if get_drama_by_id(drama_id, str(request.base_url)) is None:
        return _error(response, 404, "drama not found")
    return _ok(refresh_story_summary_cache(str(request.base_url), drama_id=drama_id))


@router.get("/media/aigc-inserts/{episode_id}/{asset_name}")
def stream_aigc_insert_asset(
    episode_id: str,
    asset_name: str,
    response: Response,
):
    asset_path = get_aigc_insert_asset_path(episode_id, asset_name)
    if asset_path is None or not asset_path.exists():
        return _error(response, 404, "aigc insert asset not found")

    suffix = asset_path.suffix.lower()
    media_type = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
    }.get(suffix, "application/octet-stream")
    return FileResponse(
        asset_path,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/media/video-understanding-frames/{episode_id}/{asset_name}")
def stream_video_understanding_frame(
    episode_id: str,
    asset_name: str,
    response: Response,
):
    frame_path = get_video_understanding_frame_path(episode_id, asset_name)
    if frame_path is None or not frame_path.exists():
        return _error(response, 404, "video understanding frame not found")

    suffix = frame_path.suffix.lower()
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
    return FileResponse(
        frame_path,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/media/generated-assets/{asset_id}")
def stream_generated_asset(
    asset_id: str,
    response: Response,
):
    asset_path = get_generated_asset_path(asset_id)
    if asset_path is None or not asset_path.exists():
        return _error(response, 404, "generated asset not found")

    return FileResponse(
        asset_path,
        media_type=generated_asset_media_type(asset_id),
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/media/drama-covers/{asset_name}")
def stream_drama_cover_asset(
    asset_name: str,
    response: Response,
):
    asset_path = get_drama_cover_asset_path(asset_name)
    if asset_path is None or not asset_path.exists():
        return _error(response, 404, "drama cover asset not found")

    suffix = asset_path.suffix.lower()
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")
    return FileResponse(
        asset_path,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/dramas/registry/status")
def drama_registry_status():
    return _ok(build_drama_registry_status())


@router.get("/dramas/{drama_id}")
def drama_detail(
    drama_id: str,
    request: Request,
    response: Response,
):
    drama = get_drama_by_id(drama_id, str(request.base_url))
    if drama is None:
        return _error(response, 404, "drama not found")
    return _ok(drama)


@router.get("/dramas/{drama_id}/episodes")
def drama_episodes(
    drama_id: str,
    request: Request,
    response: Response,
):
    episodes = list_episodes(drama_id, str(request.base_url))
    if episodes is None:
        return _error(response, 404, "drama not found")
    return _ok(
        {
            "drama_id": drama_id,
            "episodes": episodes,
        }
    )


@router.get("/dramas/{drama_id}/shareable-moments")
def drama_shareable_moments(
    drama_id: str,
    request: Request,
    response: Response,
):
    payload = build_shareable_moments(str(request.base_url), drama_id)
    if payload is None:
        return _error(response, 404, "drama not found")
    return _ok(payload)


@router.post("/moments/save")
def moments_save(payload: dict[str, object], response: Response):
    result = save_shareable_moment(payload)
    if result is None:
        return _error(response, 400, "invalid moment")
    return _ok(result)


@router.get("/moments/saved")
def moments_saved(request: Request, drama_id: str = "tainai3"):
    return _ok(list_saved_shareable_moments(str(request.base_url), drama_id))


@router.get("/episodes/{episode_id}/play")
def episode_play(
    episode_id: str,
    request: Request,
    response: Response,
):
    play_response = build_play_response(str(request.base_url), episode_id)
    if play_response is None:
        return _error(response, 404, "episode not found")
    return _ok(play_response)


@router.get("/episodes/{episode_id}/interaction-nodes")
def episode_interaction_nodes(
    episode_id: str,
    request: Request,
    response: Response,
):
    payload = build_interaction_nodes(str(request.base_url), episode_id)
    if payload is None:
        return _error(response, 404, "episode not found")
    return _ok(payload)


@router.get("/episodes/{episode_id}/timed-events")
def episode_timed_events(
    episode_id: str,
    request: Request,
    response: Response,
):
    payload = build_timed_events(str(request.base_url), episode_id)
    if payload is None:
        return _error(response, 404, "episode not found")
    return _ok(payload)


@router.get("/episodes/{episode_id}/evidence-graph")
def episode_evidence_graph(
    episode_id: str,
    request: Request,
    response: Response,
    timeMs: int | None = None,
):
    payload = build_evidence_graph(str(request.base_url), episode_id, timeMs)
    if payload is None:
        return _error(response, 404, "episode not found")
    return _ok(payload)


@router.get("/episodes/{episode_id}/interaction-candidates")
def episode_interaction_candidates(
    episode_id: str,
    request: Request,
    response: Response,
):
    payload = build_interaction_candidate_review_queue(str(request.base_url), episode_id)
    if payload is None:
        return _error(response, 404, "episode not found")
    return _ok(payload)


@router.post("/interaction-candidates/{candidate_id}/review")
def interaction_candidate_review(
    candidate_id: str,
    payload: dict[str, object],
    response: Response,
):
    result = review_interaction_candidate(candidate_id, payload)
    if result is None:
        return _error(response, 400, "invalid candidate review")
    return _ok(result)


@router.get("/episodes/{episode_id}/interaction-insights")
def episode_interaction_insights(
    episode_id: str,
    response: Response,
):
    payload = build_interaction_insights(episode_id)
    if payload is None:
        return _error(response, 404, "episode not found")
    return _ok(payload)


@router.get("/episodes/{episode_id}/danmaku-emotion-report")
def episode_danmaku_emotion_report(
    episode_id: str,
    response: Response,
):
    payload = build_danmaku_emotion_report(episode_id)
    if payload is None:
        return _error(response, 404, "episode not found")
    return _ok(payload)


@router.post("/interaction/submit")
def interaction_submit(payload: dict[str, object], request: Request, response: Response):
    result = submit_interaction_answer(payload, str(request.base_url))
    if result is None:
        return _error(response, 400, "invalid interaction submit")
    return _ok(result)


@router.get("/interaction/records")
def interaction_records(episode_id: str | None = None):
    return _ok(
        {
            "items": list_interaction_records(episode_id),
        }
    )


@router.api_route(
    "/media/episodes/{episode_id}",
    methods=["GET", "HEAD"],
    name="stream_episode_video",
)
def stream_episode_video(
    episode_id: str,
    request: Request,
    response: Response,
    range_header: str | None = Header(default=None, alias="Range"),
):
    file_path = get_episode_file_path(episode_id)
    if file_path is None or not file_path.exists():
        return _error(response, 404, "episode media not found")

    file_size = file_path.stat().st_size
    base_headers = _file_headers(file_size)

    try:
        range_bounds = _parse_range_header(range_header, file_size)
    except ValueError:
        return Response(
            status_code=416,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Range": f"bytes */{file_size}",
            },
        )

    if request.method == "HEAD":
        return Response(status_code=200, headers=base_headers)

    if range_bounds is None:
        return StreamingResponse(
            _stream_file_range(file_path, 0, file_size - 1),
            status_code=200,
            media_type="video/mp4",
            headers=base_headers,
        )

    start, end = range_bounds
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=3600",
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Content-Length": str(end - start + 1),
        "Content-Type": "video/mp4",
        "Content-Disposition": "inline",
        "X-Content-Type-Options": "nosniff",
    }
    return StreamingResponse(
        _stream_file_range(file_path, start, end),
        status_code=206,
        media_type="video/mp4",
        headers=headers,
    )


@router.get("/media/hls/{episode_id}/{asset_name}")
def stream_episode_hls_asset(
    episode_id: str,
    asset_name: str,
    response: Response,
):
    asset_path = get_hls_asset_path(episode_id, asset_name)
    if asset_path is None or not asset_path.exists():
        return _error(response, 404, "hls asset not found")

    suffix = asset_path.suffix.lower()
    media_type = {
        ".m3u8": "application/vnd.apple.mpegurl",
        ".ts": "video/mp2t",
        ".m4s": "video/iso.segment",
        ".mp4": "video/mp4",
    }.get(suffix, "application/octet-stream")
    return FileResponse(
        asset_path,
        media_type=media_type,
        headers={
            "Cache-Control": "public, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )
