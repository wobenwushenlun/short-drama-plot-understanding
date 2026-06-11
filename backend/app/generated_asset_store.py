from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from urllib import request as urlrequest


DEFAULT_GENERATED_ASSET_ROOT = Path("tmp/generated_assets")
DEFAULT_FETCH_TIMEOUT_SECONDS = 12

FetchRemoteMedia = Callable[[str, int], bytes]


def cache_remote_generated_asset(
    *,
    remote_url: str,
    media_type: str,
    request_base_url: str,
    asset_hint: str = "generated_asset",
    asset_root: Path | None = None,
    fetcher: FetchRemoteMedia | None = None,
) -> dict[str, object]:
    normalized_url = str(remote_url or "").strip()
    content_type = _normalize_media_type(media_type)
    if not _is_remote_http_url(normalized_url):
        return _asset_result(
            remote_url=normalized_url,
            local_url="",
            media_url=normalized_url,
            content_type=content_type,
            cache_status="skipped",
            asset_id="",
            byte_size=0,
            degrade_reason="remote url is empty or not http",
        )

    try:
        data = (fetcher or _fetch_remote_media)(normalized_url, DEFAULT_FETCH_TIMEOUT_SECONDS)
        if not data:
            raise ValueError("remote media is empty")
        root = asset_root or DEFAULT_GENERATED_ASSET_ROOT
        root.mkdir(parents=True, exist_ok=True)
        asset_id = _build_asset_id(normalized_url, content_type, asset_hint)
        asset_path = root / asset_id
        asset_path.write_bytes(data)
        local_url = f"{request_base_url.rstrip('/')}/media/generated-assets/{asset_id}"
        return _asset_result(
            remote_url=normalized_url,
            local_url=local_url,
            media_url=local_url,
            content_type=content_type,
            cache_status="cached",
            asset_id=asset_id,
            byte_size=len(data),
            degrade_reason="",
        )
    except Exception as exc:
        return _asset_result(
            remote_url=normalized_url,
            local_url="",
            media_url=normalized_url,
            content_type=content_type,
            cache_status="failed",
            asset_id="",
            byte_size=0,
            degrade_reason=str(exc),
        )


def get_generated_asset_path(asset_id: str, *, asset_root: Path | None = None) -> Path | None:
    normalized = str(asset_id or "").strip()
    if not normalized or "/" in normalized or "\\" in normalized or ".." in normalized:
        return None
    root = asset_root or DEFAULT_GENERATED_ASSET_ROOT
    path = (root / normalized).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    return path


def generated_asset_media_type(asset_id: str) -> str:
    suffix = Path(asset_id).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".mp4": "video/mp4",
        ".webm": "video/webm",
    }.get(suffix, "application/octet-stream")


def _fetch_remote_media(url: str, timeout_seconds: int) -> bytes:
    with urlrequest.urlopen(url, timeout=timeout_seconds) as response:
        return response.read()


def _is_remote_http_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _normalize_media_type(media_type: str) -> str:
    value = str(media_type or "").strip().lower()
    if value:
        return value
    return "application/octet-stream"


def _build_asset_id(remote_url: str, media_type: str, asset_hint: str) -> str:
    safe_hint = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in asset_hint.lower())[:36]
    if not safe_hint:
        safe_hint = "generated_asset"
    digest = hashlib.sha256(remote_url.encode("utf-8")).hexdigest()[:16]
    return f"{safe_hint}_{digest}{_extension_for_media(remote_url, media_type)}"


def _extension_for_media(remote_url: str, media_type: str) -> str:
    suffix = Path(urlparse(remote_url).path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm"}:
        return suffix
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
    }.get(media_type, ".bin")


def _asset_result(
    *,
    remote_url: str,
    local_url: str,
    media_url: str,
    content_type: str,
    cache_status: str,
    asset_id: str,
    byte_size: int,
    degrade_reason: str,
) -> dict[str, object]:
    return {
        "assetId": asset_id,
        "remoteUrl": remote_url,
        "localUrl": local_url,
        "mediaUrl": media_url,
        "contentType": content_type,
        "cacheStatus": cache_status,
        "byteSize": max(int(byte_size), 0),
        "degradeReason": degrade_reason,
    }
