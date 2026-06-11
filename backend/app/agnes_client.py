from __future__ import annotations

import os
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib import error as urlerror
from urllib import request as urlrequest


DEFAULT_AGNES_BASE_URL = "https://apihub.agnes-ai.com"
DEFAULT_AGNES_IMAGE_MODEL = "agnes-image-2.0-flash"
DEFAULT_AGNES_VIDEO_MODEL = "agnes-video-v2.0"
DEFAULT_AGNES_CONFIG_FILE = "agnes.txt"
DEFAULT_AGNES_TIMEOUT_SECONDS = 45

RequestJson = Callable[[str, str, dict[str, Any] | None, int], dict[str, Any]]
SleepFn = Callable[[float], None]


@dataclass(frozen=True)
class AgnesCredentials:
    api_key: str
    base_url: str
    image_model: str
    video_model: str
    source: str

    def public_status(self) -> dict[str, Any]:
        return {
            "configured": bool(self.api_key),
            "source": self.source,
            "baseUrl": self.base_url,
            "imageModel": self.image_model,
            "videoModel": self.video_model,
        }


def load_agnes_credentials(config_path: Path | None = None) -> AgnesCredentials:
    api_key = os.environ.get("AGNES_API_KEY", "").strip()
    source = "env" if api_key else ""
    if not api_key:
        path = config_path or _default_config_path()
        if path.exists():
            api_key = path.read_text(encoding="utf-8-sig", errors="ignore").strip()
            source = "agnes.txt" if api_key else ""
    return AgnesCredentials(
        api_key=api_key,
        base_url=os.environ.get("AGNES_BASE_URL", DEFAULT_AGNES_BASE_URL).strip() or DEFAULT_AGNES_BASE_URL,
        image_model=os.environ.get("AGNES_IMAGE_MODEL", DEFAULT_AGNES_IMAGE_MODEL).strip() or DEFAULT_AGNES_IMAGE_MODEL,
        video_model=os.environ.get("AGNES_VIDEO_MODEL", DEFAULT_AGNES_VIDEO_MODEL).strip() or DEFAULT_AGNES_VIDEO_MODEL,
        source=source,
    )


class AgnesClient:
    def __init__(
        self,
        credentials: AgnesCredentials | None = None,
        *,
        request_json: RequestJson | None = None,
        sleep: SleepFn | None = None,
    ):
        self.credentials = credentials or load_agnes_credentials()
        self._request_json = request_json or self._request_json
        self._sleep = sleep or time.sleep

    def status(self) -> dict[str, Any]:
        return self.credentials.public_status()

    def generate_image(self, prompt: str, *, size: str = "1024x1024", n: int = 1) -> dict[str, Any]:
        start_ms = _now_ms()
        try:
            response = self._request_json(
                "POST",
                "/v1/images/generations",
                {
                    "model": self.credentials.image_model,
                    "prompt": prompt,
                    "size": size,
                    "n": n,
                },
                DEFAULT_AGNES_TIMEOUT_SECONDS,
            )
            return self._result(
                model_name=self.credentials.image_model,
                status="ok",
                latency_ms=_now_ms() - start_ms,
                media_url=_extract_media_url(response),
                raw_status=str(response.get("status") or ""),
            )
        except Exception as exc:
            return self._result(
                model_name=self.credentials.image_model,
                status="degraded",
                latency_ms=_now_ms() - start_ms,
                degrade_reason=str(exc),
            )

    def create_video_task(
        self,
        prompt: str,
        *,
        image_urls: list[str] | None = None,
        keyframes: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        start_ms = _now_ms()
        body: dict[str, Any] = {
            "model": self.credentials.video_model,
            "prompt": prompt,
        }
        if image_urls:
            body["image_urls"] = image_urls
        if keyframes:
            body["keyframes"] = keyframes
        try:
            response = self._request_json("POST", "/v1/videos", body, DEFAULT_AGNES_TIMEOUT_SECONDS)
            task_id = str(response.get("id") or response.get("task_id") or response.get("taskId") or "").strip()
            if not task_id:
                raise RuntimeError("agnes video task id missing")
            return self._result(
                model_name=self.credentials.video_model,
                status="ok",
                latency_ms=_now_ms() - start_ms,
                task_id=task_id,
                raw_status=str(response.get("status") or ""),
            )
        except Exception as exc:
            return self._result(
                model_name=self.credentials.video_model,
                status="degraded",
                latency_ms=_now_ms() - start_ms,
                degrade_reason=str(exc),
            )

    def poll_video_task(
        self,
        task_id: str,
        *,
        timeout_seconds: int = 90,
        interval_seconds: int = 3,
    ) -> dict[str, Any]:
        start_ms = _now_ms()
        deadline = time.monotonic() + max(timeout_seconds, 1)
        while time.monotonic() <= deadline:
            try:
                response = self._request_json("GET", f"/v1/videos/{task_id}", None, DEFAULT_AGNES_TIMEOUT_SECONDS)
            except Exception as exc:
                return self._result(
                    model_name=self.credentials.video_model,
                    status="degraded",
                    latency_ms=_now_ms() - start_ms,
                    task_id=task_id,
                    degrade_reason=str(exc),
                )
            raw_status = str(response.get("status") or "").lower()
            media_url = _extract_media_url(response)
            if media_url or raw_status in {"completed", "succeeded", "success", "done"}:
                return self._result(
                    model_name=self.credentials.video_model,
                    status="ok",
                    latency_ms=_now_ms() - start_ms,
                    task_id=task_id,
                    media_url=media_url,
                    raw_status=raw_status,
                )
            if raw_status in {"failed", "error", "cancelled", "canceled"}:
                return self._result(
                    model_name=self.credentials.video_model,
                    status="degraded",
                    latency_ms=_now_ms() - start_ms,
                    task_id=task_id,
                    raw_status=raw_status,
                    degrade_reason=str(response.get("error") or response.get("message") or raw_status),
                )
            self._sleep(max(interval_seconds, 1))
        return self._result(
            model_name=self.credentials.video_model,
            status="degraded",
            latency_ms=_now_ms() - start_ms,
            task_id=task_id,
            degrade_reason="agnes video task timeout",
        )

    def _request_json(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        timeout_seconds: int = DEFAULT_AGNES_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        if not self.credentials.api_key:
            raise RuntimeError("agnes api key missing")
        request = urlrequest.Request(
            f"{self.credentials.base_url.rstrip('/')}{path}",
            data=json.dumps(body or {}, ensure_ascii=False).encode("utf-8") if method.upper() != "GET" else None,
            method=method.upper(),
            headers={
                "Authorization": f"Bearer {self.credentials.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlrequest.urlopen(request, timeout=timeout_seconds) as response:
                text = response.read().decode("utf-8")
        except urlerror.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} {text}") from exc
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise RuntimeError("agnes response is not object")
        return parsed

    def _result(
        self,
        *,
        model_name: str,
        status: str,
        latency_ms: int,
        task_id: str = "",
        media_url: str = "",
        raw_status: str = "",
        degrade_reason: str = "",
    ) -> dict[str, Any]:
        return {
            "provider": "agnes",
            "model_name": model_name,
            "status": status,
            "task_id": task_id,
            "media_url": media_url,
            "latency_ms": latency_ms,
            "raw_status": raw_status,
            "degrade_reason": degrade_reason,
        }


def _default_config_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / DEFAULT_AGNES_CONFIG_FILE


def _now_ms() -> int:
    return int(time.time() * 1000)


def _extract_media_url(response: dict[str, Any]) -> str:
    for key in ("url", "media_url", "video_url", "image_url", "output_url", "remixed_from_video_id"):
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    data = response.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                nested = _extract_media_url(item)
                if nested:
                    return nested
    output = response.get("output")
    if isinstance(output, dict):
        nested = _extract_media_url(output)
        if nested:
            return nested
    if isinstance(output, list):
        for item in output:
            if isinstance(item, dict):
                nested = _extract_media_url(item)
                if nested:
                    return nested
            if isinstance(item, str) and item.strip():
                return item.strip()
    return ""
