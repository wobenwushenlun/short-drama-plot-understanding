from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from ipaddress import ip_address
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from backend.app.agnes_client import AgnesClient
from backend.app.domain_utils import safe_int as _safe_int
from backend.app.generated_asset_store import cache_remote_generated_asset


DEFAULT_AIGC_INSERT_ROOT = Path("tmp/aigc_inserts")
DEFAULT_UNDERSTANDING_ROOT = Path("tmp/video_understanding_results")
DEFAULT_UNDERSTANDING_FRAME_ROOT = Path("tmp/video_understanding_frames")
DEFAULT_INSERT_DURATION_MS = 3_000
DEFAULT_INSERT_FPS = 15


class AigcInsertProvider(ABC):
    name: str

    @abstractmethod
    def build_insert(
        self,
        *,
        episode_id: str,
        node: dict[str, Any],
        episode_summary: str,
        request_base_url: str,
    ) -> dict[str, Any]:
        raise NotImplementedError


class TemplateAigcInsertProvider(AigcInsertProvider):
    name = "template_ffmpeg"

    def __init__(
        self,
        asset_root: Path | None = None,
        understanding_root: Path | None = None,
    ):
        self.asset_root = asset_root or _resolve_insert_root()
        self.understanding_root = understanding_root or _resolve_understanding_root()

    def build_insert(
        self,
        *,
        episode_id: str,
        node: dict[str, Any],
        episode_summary: str,
        request_base_url: str,
    ) -> dict[str, Any]:
        context = _load_understanding_context(self.understanding_root, episode_id)
        script = _build_insert_script(node, episode_summary, context)
        asset_name = f"{_safe_asset_id(node.get('id', 'insert'))}.mp4"
        output_dir = self.asset_root / episode_id
        output_path = output_dir / asset_name
        status = "ok"
        message = ""
        if not output_path.exists():
            try:
                self._render_mp4(output_path, script)
            except Exception as exc:  # pragma: no cover - ffmpeg/Pillow 环境异常由接口降级
                status = "asset_generation_failed"
                message = str(exc)
        if not output_path.exists():
            status = status if status != "ok" else "asset_missing"

        media_url = ""
        if output_path.exists():
            media_url = f"{request_base_url.rstrip('/')}/media/aigc-inserts/{episode_id}/{asset_name}"

        return {
            "schemaVersion": "1.0",
            "provider": {
                "name": self.name,
                "mode": "template",
                "compatibleProviders": ["agnes-video-v2.0", "doubao-video", "revideo", "template_ffmpeg"],
            },
            "status": status,
            "message": message,
            "assetId": output_path.stem,
            "mediaUrl": media_url,
            "mediaType": "video/mp4" if media_url else "",
            "durationMs": DEFAULT_INSERT_DURATION_MS,
            "title": script["title"],
            "highEnergyLine": script["high_energy_line"],
            "subtitle": script["subtitle"],
            "style": "短视频字幕 + 光效 + 进度冲刺",
            "playback": {
                "mode": str(node.get("playbackMode") or "REPLACE_MAIN"),
                "segmentId": output_path.stem,
                "startMs": 0,
                "endMs": DEFAULT_INSERT_DURATION_MS,
                "returnSeekMs": _safe_int(node.get("trigger", {}).get("timeMs"), 0, minimum=0),
            },
            "sourceEvidence": script["source_evidence"],
            "script": script,
        }

    def _render_mp4(self, output_path: Path, script: dict[str, Any]) -> None:
        ffmpeg = _find_ffmpeg_tool("ffmpeg")
        if ffmpeg is None:
            raise RuntimeError("ffmpeg_missing")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame_dir = output_path.parent / f"{output_path.stem}_frames"
        if frame_dir.exists():
            shutil.rmtree(frame_dir)
        frame_dir.mkdir(parents=True, exist_ok=True)
        try:
            _render_frames(frame_dir, script)
            command = [
                str(ffmpeg),
                "-y",
                "-framerate",
                str(DEFAULT_INSERT_FPS),
                "-i",
                str(frame_dir / "frame_%03d.png"),
                "-t",
                f"{DEFAULT_INSERT_DURATION_MS / 1000:.2f}",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, timeout=45, check=False)
            if completed.returncode != 0:
                raise RuntimeError((completed.stderr or "ffmpeg_render_failed")[-400:])
        finally:
            shutil.rmtree(frame_dir, ignore_errors=True)


class AgnesAigcInsertProvider(AigcInsertProvider):
    name = "agnes-video"

    def __init__(
        self,
        *,
        agnes_client: AgnesClient | None = None,
        fallback_provider: AigcInsertProvider | None = None,
        understanding_root: Path | None = None,
        frame_root: Path | None = None,
    ):
        self.agnes_client = agnes_client or AgnesClient()
        self.fallback_provider = fallback_provider or TemplateAigcInsertProvider()
        self.understanding_root = understanding_root or _resolve_understanding_root()
        self.frame_root = frame_root or _resolve_understanding_frame_root()

    def build_insert(
        self,
        *,
        episode_id: str,
        node: dict[str, Any],
        episode_summary: str,
        request_base_url: str,
    ) -> dict[str, Any]:
        context = _load_understanding_context(self.understanding_root, episode_id)
        references = _build_agnes_video_references(
            episode_id=episode_id,
            node=node,
            context=context,
            request_base_url=request_base_url,
            frame_root=self.frame_root,
        )
        prompt = _build_agnes_video_prompt(node, episode_summary, context, references)
        if references.get("reference_status") == "blocked_local_url":
            return self._fallback_result(
                episode_id=episode_id,
                node=node,
                episode_summary=episode_summary,
                request_base_url=request_base_url,
                degrade_reason="reference_frame_url_not_public",
                reference_status=str(references.get("reference_status") or ""),
            )
        created = self.agnes_client.create_video_task(
            prompt,
            image_urls=references["image_urls"],
            keyframes=references["keyframes"],
        )
        if created.get("status") == "ok" and created.get("task_id"):
            polled = self.agnes_client.poll_video_task(str(created["task_id"]))
            if polled.get("status") == "ok" and polled.get("media_url"):
                return self._remote_result(
                    episode_id=episode_id,
                    node=node,
                    prompt=prompt,
                    created=created,
                    polled=polled,
                    request_base_url=request_base_url,
                )
            degrade_reason = str(polled.get("degrade_reason") or "agnes video result missing")
        else:
            degrade_reason = str(created.get("degrade_reason") or "agnes video task create failed")
        return self._fallback_result(
            episode_id=episode_id,
            node=node,
            episode_summary=episode_summary,
            request_base_url=request_base_url,
            degrade_reason=degrade_reason,
            reference_status=str(references.get("reference_status") or ""),
        )

    def _fallback_result(
        self,
        *,
        episode_id: str,
        node: dict[str, Any],
        episode_summary: str,
        request_base_url: str,
        degrade_reason: str,
        reference_status: str,
    ) -> dict[str, Any]:
        fallback = self.fallback_provider.build_insert(
            episode_id=episode_id,
            node=node,
            episode_summary=episode_summary,
            request_base_url=request_base_url,
        )
        provider = fallback.setdefault("provider", {})
        if isinstance(provider, dict):
            provider["attemptedProvider"] = self.name
            provider["degradeReason"] = degrade_reason
            compatible = provider.setdefault("compatibleProviders", [])
            if isinstance(compatible, list) and self.agnes_client.credentials.video_model not in compatible:
                compatible.insert(0, self.agnes_client.credentials.video_model)
        fallback["remoteAttempt"] = {
            "provider": self.name,
            "status": "degraded",
            "degradeReason": degrade_reason,
            "referenceStatus": reference_status,
        }
        return fallback

    def _remote_result(
        self,
        *,
        episode_id: str,
        node: dict[str, Any],
        prompt: str,
        created: dict[str, Any],
        polled: dict[str, Any],
        request_base_url: str,
    ) -> dict[str, Any]:
        asset_id = _safe_asset_id(node.get("id", "agnes_insert"))
        duration_ms = _safe_int(node.get("durationMs"), DEFAULT_INSERT_DURATION_MS, minimum=1)
        remote_media_url = str(polled.get("media_url") or "")
        asset_cache = cache_remote_generated_asset(
            remote_url=remote_media_url,
            media_type="video/mp4",
            request_base_url=request_base_url,
            asset_hint=f"story_continuation_{episode_id}_{asset_id}",
        )
        return {
            "schemaVersion": "1.0",
            "provider": {
                "name": self.name,
                "mode": "remote",
                "modelName": self.agnes_client.credentials.video_model,
                "compatibleProviders": [self.agnes_client.credentials.video_model, "template_ffmpeg"],
            },
            "status": "ok",
            "message": "",
            "assetId": asset_id,
            "mediaUrl": str(asset_cache.get("mediaUrl") or remote_media_url),
            "mediaType": "video/mp4",
            "durationMs": duration_ms,
            "assetCache": asset_cache,
            "title": str(node.get("generatedTitle") or node.get("title") or "AI 下一幕预演")[:24],
            "highEnergyLine": str(node.get("generatedHighEnergyLine") or "")[:42],
            "subtitle": str(node.get("generatedSubtitle") or "")[:40],
            "style": "Agnes 远端视频生成",
            "playback": {
                "mode": str(node.get("playbackMode") or "REPLACE_MAIN"),
                "segmentId": asset_id,
                "startMs": 0,
                "endMs": duration_ms,
                "returnSeekMs": _safe_int(node.get("trigger", {}).get("timeMs"), 0, minimum=0),
            },
            "sourceEvidence": ["剧情续写结果", "Agnes 视频生成"],
            "script": {
                "prompt": prompt,
                "task_id": str(polled.get("task_id") or created.get("task_id") or ""),
                "latency_ms": _safe_int(polled.get("latency_ms"), 0, minimum=0),
            },
        }


def get_aigc_insert_provider() -> AigcInsertProvider:
    if os.environ.get("AIGC_INSERT_PROVIDER", "").strip().lower() == "agnes":
        return AgnesAigcInsertProvider()
    return TemplateAigcInsertProvider()


def get_aigc_insert_asset_path(episode_id: str, asset_name: str) -> Path | None:
    if not _is_safe_asset_name(asset_name):
        return None
    asset_path = _resolve_insert_root() / episode_id / asset_name
    try:
        asset_path.resolve().relative_to((_resolve_insert_root() / episode_id).resolve())
    except ValueError:
        return None
    return asset_path


def get_video_understanding_frame_path(
    episode_id: str,
    asset_name: str,
    *,
    frame_root: Path | None = None,
) -> Path | None:
    if not _is_safe_asset_name(asset_name):
        return None
    root = frame_root or _resolve_understanding_frame_root()
    frame_path = root / episode_id / asset_name
    try:
        frame_path.resolve().relative_to((root / episode_id).resolve())
    except ValueError:
        return None
    return frame_path


def _render_frames(frame_dir: Path, script: dict[str, Any]) -> None:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    width, height = 720, 1280
    frame_count = int(DEFAULT_INSERT_DURATION_MS / 1000 * DEFAULT_INSERT_FPS)
    title_font = _load_font(54)
    line_font = _load_font(62)
    meta_font = _load_font(30)
    small_font = _load_font(26)
    line_chunks = _wrap_text(script["high_energy_line"], 11)[:3]
    evidence = script.get("source_evidence", [])[:2]
    for index in range(frame_count):
        progress = (index + 1) / frame_count
        image = Image.new("RGB", (width, height), (12, 10, 24))
        draw = ImageDraw.Draw(image)
        _paint_background(draw, width, height, progress)

        glow_x = int(width * (0.15 + 0.75 * progress))
        glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.ellipse((glow_x - 210, 150, glow_x + 210, 570), fill=(128, 90, 255, 72))
        glow = glow.filter(ImageFilter.GaussianBlur(55))
        image = Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")
        draw = ImageDraw.Draw(image)

        _draw_centered(draw, script["title"], title_font, width, 132, (255, 255, 255))
        _draw_badge(draw, script["badge_text"], 196, meta_font)
        y = 390
        for chunk in line_chunks:
            _draw_centered(draw, chunk, line_font, width, y, (255, 246, 185))
            y += 82
        _draw_centered(draw, script["subtitle"], small_font, width, 705, (228, 222, 255))

        bar_left, bar_top, bar_right, bar_bottom = 92, 840, 628, 866
        draw.rounded_rectangle((bar_left, bar_top, bar_right, bar_bottom), radius=13, fill=(48, 44, 75))
        draw.rounded_rectangle(
            (bar_left, bar_top, bar_left + int((bar_right - bar_left) * progress), bar_bottom),
            radius=13,
            fill=(255, 87, 126),
        )
        draw.text((92, 890), script["progress_text"], font=small_font, fill=(230, 226, 255))
        draw.text((520, 890), f"{int(progress * 100)}%", font=small_font, fill=(255, 246, 185))

        for offset, text in enumerate(evidence):
            draw.text((92, 1010 + offset * 42), f"证据：{text}", font=small_font, fill=(190, 184, 220))
        draw.text((92, 1168), "可替换 Provider：Doubao 视频生成 / Revideo / 本地模板", font=small_font, fill=(158, 151, 194))
        image.save(frame_dir / f"frame_{index + 1:03d}.png")


def _paint_background(draw: Any, width: int, height: int, progress: float) -> None:
    for y in range(height):
        ratio = y / height
        r = int(18 + 35 * ratio)
        g = int(14 + 10 * ratio)
        b = int(37 + 42 * ratio)
        draw.line((0, y, width, y), fill=(r, g, b))
    for step in range(8):
        x = int((step * 110 + progress * 280) % (width + 160)) - 80
        draw.line((x, 0, x - 230, height), fill=(120, 88, 255), width=4)


def _draw_centered(draw: Any, text: str, font: Any, width: int, y: int, fill: tuple[int, int, int]) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    x = max((width - (bbox[2] - bbox[0])) // 2, 24)
    draw.text((x + 3, y + 3), text, font=font, fill=(0, 0, 0))
    draw.text((x, y), text, font=font, fill=fill)


def _draw_badge(draw: Any, text: str, y: int, font: Any) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0] + 48
    left = (720 - width) // 2
    draw.rounded_rectangle((left, y, left + width, y + 54), radius=27, fill=(255, 87, 126))
    draw.text((left + 24, y + 10), text, font=font, fill=(255, 255, 255))


def _load_font(size: int) -> Any:
    from PIL import ImageFont

    for font_path in (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ):
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)
    return ImageFont.load_default()


def _build_insert_script(node: dict[str, Any], episode_summary: str, context: dict[str, Any]) -> dict[str, Any]:
    generated_line = str(node.get("generatedHighEnergyLine") or "").strip()
    high_energy_line = generated_line or _pick_high_energy_line(context, episode_summary)
    screen_text = _pick_screen_text(context)
    source_evidence = []
    if generated_line:
        source_evidence.append("Doubao 续写台词")
    elif high_energy_line:
        source_evidence.append("ASR 高能台词")
    if screen_text:
        source_evidence.append(f"OCR 屏幕文字：{screen_text[:18]}")
    if not source_evidence:
        source_evidence.append("剧集摘要")
    return {
        "title": str(node.get("generatedTitle") or "反击加速包")[:24],
        "high_energy_line": high_energy_line or episode_summary or "局势开始反转，反击马上加速",
        "subtitle": str(node.get("generatedSubtitle") or "").strip()[:32] or (
            screen_text[:32] if screen_text else str(node.get("subtitle") or "基于剧情理解生成高能推进片段")[:32]
        ),
        "badge_text": str(node.get("badgeText") or "AI 生成 · 3 秒反击加速包")[:30],
        "progress_text": str(node.get("progressText") or "进度冲刺")[:12],
        "node_id": str(node.get("id") or ""),
        "node_title": str(node.get("title") or ""),
        "source_evidence": source_evidence,
        "created_at_ms": int(time.time() * 1000),
    }


def _build_agnes_video_prompt_legacy(node: dict[str, Any], episode_summary: str) -> str:
    title = str(node.get("generatedTitle") or node.get("title") or "下一幕预演").strip()
    line = str(node.get("generatedHighEnergyLine") or "").strip()
    direction = str(node.get("generatedSubtitle") or "").strip()
    return "\n".join(
        item
        for item in [
            "生成一段 3 秒竖屏短剧续写预演视频，9:16，电影感灯光，快节奏，不能出现字幕水印。",
            f"标题：{title}",
            f"剧情承接：{episode_summary.strip()}",
            f"场景调度：{direction}" if direction else "",
            f"关键台词氛围：{line}" if line else "",
            "风格：豪门短剧、强反转、爽点推进，画面要像预告片，不冒充原剧正片。",
        ]
        if item
    )


def _build_agnes_video_prompt(
    node: dict[str, Any],
    episode_summary: str,
    context: dict[str, Any] | None = None,
    references: dict[str, Any] | None = None,
) -> str:
    title = str(node.get("generatedTitle") or node.get("title") or "下一幕预演").strip()
    line = str(node.get("generatedHighEnergyLine") or "").strip()
    direction = str(node.get("generatedSubtitle") or "").strip()
    creative_prompt = node.get("creativePrompt") if isinstance(node.get("creativePrompt"), dict) else {}
    user_intent = str(node.get("userIntent") or "").strip()
    desired_ending = str(node.get("desiredEnding") or "").strip()
    visual_direction = str(node.get("visualDirection") or "").strip()
    context = context or {}
    result = context.get("result") if isinstance(context.get("result"), dict) else {}
    story_summary = str(result.get("story_summary") or result.get("summary") or "").strip()
    characters = _format_character_prompt(result.get("characters"))
    reference_count = len((references or {}).get("image_urls") or [])
    return "\n".join(
        item
        for item in [
            "生成一段 3 秒竖屏短剧续写预演视频，9:16，电影感灯光，快节奏，不能出现字幕水印。",
            f"标题：{title}",
            f"剧情承接：{episode_summary.strip()}",
            f"本集剧情概述：{story_summary}" if story_summary else "",
            f"人物一致性：参考输入截图中的人物脸型、发型、服装气质和站位；不要改变主角年龄感与豪门短剧氛围。参考截图数量：{reference_count}" if reference_count else "",
            f"主要人物：{characters}" if characters else "",
            f"场景调度：{direction}" if direction else "",
            f"关键台词氛围：{line}" if line else "",
            f"用户希望：{user_intent}" if user_intent else "",
            f"用户期望结局：{desired_ending}" if desired_ending else "",
            f"用户画面方向：{visual_direction}" if visual_direction else "",
            f"语言模型优化剧情方向：{creative_prompt.get('storyDirection')}" if creative_prompt.get("storyDirection") else "",
            f"语言模型优化视频提示：{creative_prompt.get('videoPromptAddon')}" if creative_prompt.get("videoPromptAddon") else "",
            f"负向约束：{creative_prompt.get('negativePrompt')}" if creative_prompt.get("negativePrompt") else "",
            "风格：豪门短剧、强反转、爽点推进，画面要像预告片，不冒充原剧正片。",
        ]
        if item
    )


def _build_agnes_video_references(
    *,
    episode_id: str,
    node: dict[str, Any],
    context: dict[str, Any],
    request_base_url: str,
    frame_root: Path,
) -> dict[str, Any]:
    frames = _select_reference_frames(context, node)
    if frames and not _is_remote_accessible_base_url(request_base_url):
        return {
            "image_urls": [],
            "keyframes": [],
            "source_frame_count": len(frames),
            "reference_status": "blocked_local_url",
        }
    image_urls: list[str] = []
    keyframes: list[dict[str, Any]] = []
    for frame in frames:
        frame_url = _frame_media_url(
            episode_id=episode_id,
            frame=frame,
            request_base_url=request_base_url,
            frame_root=frame_root,
        )
        if not frame_url:
            continue
        image_urls.append(frame_url)
        keyframes.append(
            {
                "image_url": frame_url,
                "time_ms": _safe_int(frame.get("timeMs") or frame.get("time_ms"), 0, minimum=0),
                "reason": str(frame.get("samplingReason") or frame.get("sampling_reason") or "剧情参考帧"),
            }
        )
    return {
        "image_urls": image_urls[:2],
        "keyframes": keyframes[:2],
        "source_frame_count": len(frames),
        "reference_status": "ready" if image_urls else ("no_reference_frames" if not frames else "missing_frame_file"),
    }


def _is_remote_accessible_base_url(request_base_url: str) -> bool:
    parsed = urlparse(str(request_base_url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    if not host or host in {"localhost", "0.0.0.0"} or host.endswith(".local"):
        return False
    if host == "10.0.2.2":
        return False
    try:
        ip = ip_address(host)
    except ValueError:
        return True
    return not (ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved)


def _select_reference_frames(context: dict[str, Any], node: dict[str, Any]) -> list[dict[str, Any]]:
    assets = context.get("assets") if isinstance(context.get("assets"), dict) else {}
    raw_frames = assets.get("frames") if isinstance(assets.get("frames"), list) else []
    frames = [frame for frame in raw_frames if isinstance(frame, dict) and frame.get("availableForVision", True)]
    if not frames:
        return []
    trigger_ms = _safe_int(node.get("trigger", {}).get("timeMs"), 0, minimum=0)
    return sorted(
        frames,
        key=lambda frame: (
            abs(_safe_int(frame.get("timeMs") or frame.get("time_ms"), 0, minimum=0) - trigger_ms),
            -float(frame.get("samplingScore") or frame.get("sampling_score") or 0),
        ),
    )[:2]


def _frame_media_url(
    *,
    episode_id: str,
    frame: dict[str, Any],
    request_base_url: str,
    frame_root: Path,
) -> str:
    raw_path = str(frame.get("path") or "").strip()
    if not raw_path:
        return ""
    path = Path(raw_path)
    if not path.exists():
        return ""
    frame_path = get_video_understanding_frame_path(episode_id, path.name, frame_root=frame_root)
    if frame_path is None:
        return ""
    return f"{request_base_url.rstrip('/')}/media/video-understanding-frames/{episode_id}/{path.name}"


def _format_character_prompt(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    parts: list[str] = []
    for item in value[:4]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("canonical_name") or "").strip()
        traits = item.get("traits") if isinstance(item.get("traits"), list) else []
        trait_text = "、".join(str(trait).strip() for trait in traits[:3] if str(trait).strip())
        if name:
            parts.append(f"{name}（{trait_text}）" if trait_text else name)
    return "；".join(parts)


def _load_understanding_context(root: Path, episode_id: str) -> dict[str, Any]:
    path = root / episode_id / "understanding.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _pick_high_energy_line(context: dict[str, Any], fallback: str) -> str:
    result = ((context.get("envelope") or {}).get("result") or {}) if isinstance(context, dict) else {}
    high_lines = result.get("high_energy_lines")
    if isinstance(high_lines, list):
        for item in high_lines:
            text = str(item.get("text") if isinstance(item, dict) else item).strip()
            if text:
                return text[:42]
    audio_text = result.get("audio_text") if isinstance(result.get("audio_text"), dict) else {}
    transcript = str(audio_text.get("corrected_transcript") or audio_text.get("transcript") or "").strip()
    for chunk in _split_dialogue(transcript):
        if 5 <= len(chunk) <= 42:
            return chunk
    return fallback[:42]


def _pick_screen_text(context: dict[str, Any]) -> str:
    result = ((context.get("envelope") or {}).get("result") or {}) if isinstance(context, dict) else {}
    cues = result.get("screen_text_cues")
    if isinstance(cues, list):
        for cue in cues:
            text = str(cue.get("text") if isinstance(cue, dict) else cue).strip()
            if text:
                return text
    return ""


def _split_dialogue(text: str) -> list[str]:
    cleaned = text.replace("\r", " ").replace("\n", " ")
    chunks = []
    current = ""
    for char in cleaned:
        current += char
        if char in "。！？!?，,":
            chunks.extend(_split_long_dialogue(current.strip(" ，,。！？!?")))
            current = ""
    if current.strip():
        chunks.extend(_split_long_dialogue(current.strip()))
    return [chunk for chunk in chunks if chunk]


def _split_long_dialogue(text: str) -> list[str]:
    parts: list[str] = []
    for raw_part in text.split():
        part = raw_part.strip(" ，,。！？!?")
        if not part:
            continue
        if len(part) <= 42:
            parts.append(part)
            continue
        for index in range(0, min(len(part), 126), 28):
            chunk = part[index : index + 28].strip()
            if chunk:
                parts.append(chunk)
    return parts


def _wrap_text(text: str, chunk_size: int) -> list[str]:
    if not text:
        return []
    return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)]


def _find_ffmpeg_tool(tool_name: str) -> Path | None:
    executable = f"{tool_name}.exe" if os.name == "nt" else tool_name
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [repo_root / "tools" / "ffmpeg" / "bin" / executable]
    env_dir = os.environ.get("AIGC_FFMPEG_DIR", "").strip()
    if env_dir:
        candidates.append(Path(env_dir) / executable)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    found = shutil.which(executable) or shutil.which(tool_name)
    return Path(found) if found else None


def _resolve_insert_root() -> Path:
    raw = os.environ.get("AIGC_INSERT_ROOT", "").strip()
    return Path(raw) if raw else DEFAULT_AIGC_INSERT_ROOT


def _resolve_understanding_root() -> Path:
    raw = os.environ.get("AIGC_VIDEO_UNDERSTANDING_ROOT", "").strip()
    return Path(raw) if raw else DEFAULT_UNDERSTANDING_ROOT


def _resolve_understanding_frame_root() -> Path:
    raw = os.environ.get("AIGC_VIDEO_UNDERSTANDING_FRAME_ROOT", "").strip()
    return Path(raw) if raw else DEFAULT_UNDERSTANDING_FRAME_ROOT


def _safe_asset_id(value: Any) -> str:
    text = str(value or "insert")
    safe = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in text)
    return safe.strip("_") or "insert"


def _is_safe_asset_name(asset_name: str) -> bool:
    return bool(asset_name) and "/" not in asset_name and "\\" not in asset_name and asset_name not in {".", ".."}
