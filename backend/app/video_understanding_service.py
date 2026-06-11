from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.app.asr_service import get_asr_service
from backend.app.ai_service import get_ai_service
from backend.app.content_catalog import (
    build_interaction_nodes,
    get_drama_by_id,
    get_episode_by_id,
    get_episode_file_path,
)
from backend.app.domain_utils import safe_int as _safe_int
from backend.app.ocr_service import get_ocr_service


VIDEO_UNDERSTANDING_PROMPT_VERSION = "video.understanding/p1-story-summary"
DEFAULT_FRAME_CACHE_DIR = Path("tmp/video_understanding_frames")
DEFAULT_AUDIO_CACHE_DIR = Path("tmp/video_understanding_audio")
DEFAULT_SUBTITLE_CACHE_DIR = Path("tmp/video_understanding_subtitles")
DEFAULT_RESULT_CACHE_DIR = Path("tmp/video_understanding_results")


@dataclass
class VideoProbeResult:
    duration_ms: int
    width: int
    height: int
    codec_name: str
    tool_status: str


class VideoUnderstandingService:
    def __init__(
        self,
        frame_cache_dir: Path | None = None,
        audio_cache_dir: Path | None = None,
        subtitle_cache_dir: Path | None = None,
        result_cache_dir: Path | None = None,
    ):
        self.frame_cache_dir = frame_cache_dir or DEFAULT_FRAME_CACHE_DIR
        self.audio_cache_dir = audio_cache_dir or DEFAULT_AUDIO_CACHE_DIR
        self.subtitle_cache_dir = subtitle_cache_dir or DEFAULT_SUBTITLE_CACHE_DIR
        self.result_cache_dir = result_cache_dir or DEFAULT_RESULT_CACHE_DIR

    def analyze_episode(self, payload: dict[str, Any], request_base_url: str) -> dict[str, Any]:
        episode_id = str(payload.get("episodeId", "")).strip()
        drama_id = str(payload.get("dramaId", "")).strip() or "tainai3"
        if not episode_id:
            raise ValueError("episodeId is required")

        drama = get_drama_by_id(drama_id)
        episode = get_episode_by_id(episode_id)
        file_path = get_episode_file_path(episode_id)
        if drama is None or episode is None:
            raise ValueError("episode or drama not found")
        if file_path is None or not file_path.exists():
            raise ValueError("episode video not found")

        include_frames = bool(payload.get("includeFrames", True))
        include_audio = bool(payload.get("includeAudio", True))
        include_subtitles = bool(payload.get("includeSubtitles", True))
        max_frames = _safe_int(payload.get("maxFrames"), 3, minimum=0, maximum=5)
        force_refresh = bool(payload.get("forceRefresh", False))

        persisted = None if force_refresh else self._read_persistent_evidence(episode_id, drama_id=drama_id)
        if persisted is not None and str(persisted.get("status") or "") == "ok":
            return persisted

        probe = self._probe_video(file_path)
        interaction_payload = build_interaction_nodes(request_base_url, episode_id)
        audio_asset = self._extract_audio_track(file_path, episode_id, drama_id=drama_id) if include_audio else {
            "status": "disabled",
            "path": "",
            "format": "",
            "transcript": "",
            "source": "none",
            "utterances": [],
        }
        frame_items = self._extract_key_frames(
            file_path,
            episode_id,
            probe.duration_ms,
            max_frames,
            drama_id=drama_id,
            interaction_nodes=interaction_payload["nodes"] if interaction_payload else [],
            utterances=audio_asset.get("utterances", []),
        ) if include_frames else []
        ocr_asset = get_ocr_service().analyze_frames(frame_items) if include_frames else {
            "status": "disabled",
            "source": "none",
            "cues": [],
        }
        subtitle_asset = self._extract_embedded_subtitles(file_path, episode_id, drama_id=drama_id) if include_subtitles else {
            "status": "disabled",
            "path": "",
            "text": "",
        }
        character_profiles = _build_character_profiles(drama.get("characters", []))
        role_vocabulary = _build_role_vocabulary(character_profiles)
        transcript_text = str(audio_asset.get("transcript") or subtitle_asset.get("text") or "").strip()
        speaker_turns = _build_speaker_turns(
            transcript=transcript_text,
            utterances=audio_asset.get("utterances", []),
            role_vocabulary=role_vocabulary,
            character_profiles=character_profiles,
            ocr_cues=ocr_asset.get("cues", []),
        )
        speaker_role_map = _infer_speaker_role_map(speaker_turns, character_profiles, ocr_asset.get("cues", []))
        speaker_transcript = _render_speaker_transcript(speaker_turns, speaker_role_map)
        corrected_transcript = _correct_text_by_roles(
            speaker_transcript or transcript_text,
            role_vocabulary,
        )
        fused_media_text = _build_fused_media_text(
            transcript=corrected_transcript,
            ocr_cues=ocr_asset.get("cues", []),
            role_vocabulary=role_vocabulary,
            speaker_turns=speaker_turns,
            speaker_role_map=speaker_role_map,
        )
        prompt_context = {
            "drama": {
                "dramaId": drama["drama_id"],
                "title": drama["title"],
                "description": drama["description"],
                "tags": drama["tags"],
                "characters": drama.get("characters", []),
                "interaction_hint": drama.get("interaction_hint", ""),
            },
            "episode": {
                "episodeId": episode["episode_id"],
                "episodeNo": episode["episode_no"],
                "title": episode["title"],
                "summary": episode["summary"],
                "durationMs": episode["duration_ms"],
            },
            "video": {
                "fileName": file_path.name,
                "fileSizeBytes": file_path.stat().st_size,
                "durationMs": probe.duration_ms or episode["duration_ms"],
                "width": probe.width,
                "height": probe.height,
                "codecName": probe.codec_name,
                "toolStatus": probe.tool_status,
            },
            "frames": [
                {
                    "timeMs": item["timeMs"],
                    "path": item["path"],
                    "availableForVision": bool(item.get("dataUrl")),
                    "samplingSource": item.get("samplingSource", "anchor"),
                    "samplingReason": item.get("samplingReason", ""),
                    "samplingScore": item.get("samplingScore", 0.0),
                }
                for item in frame_items
            ],
            "mediaText": {
                "audio": {
                    "status": audio_asset["status"],
                    "path": audio_asset["path"],
                    "format": audio_asset["format"],
                    "transcript": transcript_text,
                    "correctedTranscript": corrected_transcript,
                "speakerTranscript": speaker_transcript,
                "speakerTurns": speaker_turns,
                "speakerRoleMap": speaker_role_map,
                "characterProfiles": character_profiles,
                "utterances": audio_asset.get("utterances", []),
                "source": audio_asset.get("source", "audio_asset"),
            },
                "ocr": {
                    "status": ocr_asset["status"],
                    "source": ocr_asset["source"],
                    "cues": ocr_asset.get("cues", []),
                },
                "subtitles": {
                    "status": subtitle_asset["status"],
                    "path": subtitle_asset["path"],
                    "textPreview": str(subtitle_asset.get("text", ""))[:1000],
                    "source": subtitle_asset.get("source", "embedded_subtitle"),
                },
            },
            "fusion": fused_media_text,
            "interactionNodes": interaction_payload["nodes"] if interaction_payload else [],
            "request": {
                "includeFrames": include_frames,
                "includeAudio": include_audio,
                "includeSubtitles": include_subtitles,
                "maxFrames": max_frames,
            },
        }

        ai_service = get_ai_service()
        cache_key = ai_service._make_cache_key(
            "video.understanding",
            {
                "prompt_version": VIDEO_UNDERSTANDING_PROMPT_VERSION,
                "context": prompt_context,
            },
        )
        cached = None if force_refresh else ai_service._get_cache(cache_key)
        if cached is not None:
            envelope = ai_service._decorate_response(
                capability="video.understanding",
                result=cached["result"],
                status=cached["status"],
                latency_ms=0,
                usage=cached["usage"],
                cache_hit=True,
                model_info=cached["model"],
            )
            ai_service._append_audit(
                capability="video.understanding",
                payload=prompt_context,
                envelope=envelope,
                prompt_version=VIDEO_UNDERSTANDING_PROMPT_VERSION,
            )
            return envelope

        start_ms = int(time.time() * 1000)
        messages = self._build_messages(prompt_context, frame_items)
        quality_status = ""
        if not ai_service._remote_model_enabled():
            result = self._fallback_understanding(prompt_context)
            status = "degraded"
            degrade_reason = "远端模型默认关闭，已使用本地兜底"
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            quality_status = "degraded"
        else:
            try:
                result, usage, quality_status = self._run_remote_understanding(
                    ai_service,
                    prompt_context,
                    messages,
                )
                status = "ok"
                degrade_reason = ""
            except Exception as exc:  # pragma: no cover - 网络和模型异常由接口兜底
                result = self._fallback_understanding(prompt_context)
                status = "degraded"
                degrade_reason = str(exc)
                usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                quality_status = "degraded"

        model_info = ai_service._model_info()
        envelope = ai_service._decorate_response(
            capability="video.understanding",
            result=result,
            status=status,
            latency_ms=int(time.time() * 1000) - start_ms,
            usage=usage,
            cache_hit=False,
            model_info=model_info,
            degrade_reason=degrade_reason or None,
        )
        envelope["quality_status"] = quality_status or ("success" if status == "ok" else "degraded")
        if isinstance(envelope.get("result"), dict):
            envelope["result"]["quality_status"] = envelope["quality_status"]
        ai_service._append_audit(
            capability="video.understanding",
            payload=prompt_context,
            envelope=envelope,
            prompt_version=VIDEO_UNDERSTANDING_PROMPT_VERSION,
        )
        evidence_path = self._write_persistent_evidence(
            drama_id=drama_id,
            episode_id=episode_id,
            prompt_context=prompt_context,
            envelope=envelope,
            frame_items=frame_items,
            audio_asset=audio_asset,
            subtitle_asset=subtitle_asset,
            ocr_asset=ocr_asset,
        )
        if evidence_path:
            envelope["result"]["evidence_manifest"] = {
                "path": evidence_path,
                "source": "persistent_json",
            }
        ai_service._set_cache(
            cache_key,
            {"result": envelope["result"], "status": status, "usage": usage, "model": model_info},
            ttl_seconds=ai_service._cache_ttl_seconds(),
        )
        return envelope

    def _run_remote_understanding(
        self,
        ai_service: Any,
        prompt_context: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, int], str]:
        response = ai_service._call_chat_completion_best_effort(
            capability="video.understanding",
            messages=messages,
            max_tokens=1100,
            temperature=0.2,
        )
        parsed = self._parse_understanding_response(ai_service, response)
        if parsed is not None:
            return self._normalize_understanding(parsed, prompt_context), ai_service._extract_usage(response), "success"

        retry_response = ai_service._call_chat_completion_best_effort(
            capability="video.understanding.minimal_retry",
            messages=self._build_minimal_retry_messages(prompt_context),
            max_tokens=420,
            temperature=0.1,
        )
        retry_parsed = self._parse_understanding_response(ai_service, retry_response)
        if retry_parsed is None:
            raise ValueError("invalid model response")
        return self._normalize_understanding(retry_parsed, prompt_context), ai_service._extract_usage(retry_response), "ok_retried_json"

    def _parse_understanding_response(self, ai_service: Any, response: dict[str, Any]) -> dict[str, Any] | None:
        parsed = ai_service._parse_model_result(response)
        if parsed is not None:
            return parsed
        raw_text = ai_service._extract_model_text(response)
        if raw_text and not _looks_jsonish(raw_text):
            return {"summary": raw_text}
        return None

    def _read_persistent_evidence(self, episode_id: str, drama_id: str = "tainai3") -> dict[str, Any] | None:
        evidence_path = next(
            (
                path
                for path in (
                    self._latest_success_path(episode_id, drama_id=drama_id),
                    self._evidence_path(episode_id, drama_id=drama_id),
                    self._legacy_latest_success_path(episode_id),
                    self._legacy_evidence_path(episode_id),
                )
                if path.exists()
            ),
            None,
        )
        if evidence_path is None:
            return None
        try:
            document = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if document.get("prompt_version") != VIDEO_UNDERSTANDING_PROMPT_VERSION:
            return None
        envelope = document.get("envelope")
        if not isinstance(envelope, dict):
            return None
        result = envelope.get("result")
        if isinstance(result, dict):
            result["evidence_manifest"] = {
                "path": str(evidence_path),
                "source": "persistent_json",
                "persistedAtMs": int(document.get("persisted_at_ms") or 0),
            }
        artifact = envelope.get("artifact")
        if not isinstance(artifact, dict):
            artifact = {}
        artifact = dict(artifact)
        artifact["source"] = "persistent_json"
        envelope["artifact"] = artifact
        envelope["cached"] = True
        envelope["latency_ms"] = 0
        return envelope

    def _write_persistent_evidence(
        self,
        *,
        drama_id: str = "tainai3",
        episode_id: str,
        prompt_context: dict[str, Any],
        envelope: dict[str, Any],
        frame_items: list[dict[str, Any]],
        audio_asset: dict[str, str],
        subtitle_asset: dict[str, str],
        ocr_asset: dict[str, Any],
    ) -> str:
        evidence_path = self._evidence_path(episode_id, drama_id=drama_id)
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        frame_assets = [
            {
                "timeMs": item.get("timeMs", 0),
                "path": item.get("path", ""),
                "availableForVision": bool(item.get("dataUrl")),
                "samplingSource": item.get("samplingSource", "anchor"),
                "samplingReason": item.get("samplingReason", ""),
                "samplingScore": item.get("samplingScore", 0.0),
            }
            for item in frame_items
        ]
        generated_at = int(time.time() * 1000)
        status = str(envelope.get("status") or "")
        version = _safe_int((envelope.get("artifact") or {}).get("version"), 0, minimum=0)
        document = {
            "schema_version": "1.1",
            "prompt_version": VIDEO_UNDERSTANDING_PROMPT_VERSION,
            "persisted_at_ms": generated_at,
            "generated_at": generated_at,
            "result_version": version,
            "quality_status": "success" if status == "ok" else "degraded",
            "drama_id": drama_id,
            "episode_id": episode_id,
            "episode": prompt_context.get("episode", {}),
            "video": prompt_context.get("video", {}),
            "assets": {
                "frames": frame_assets,
                "audio": audio_asset,
                "ocr": ocr_asset,
                "subtitles": subtitle_asset,
            },
            "interaction_nodes": prompt_context.get("interactionNodes", []),
            "envelope": envelope,
        }
        latest_attempt_path = self._latest_attempt_path(episode_id, drama_id=drama_id)
        latest_attempt_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        existing_status = ""
        if evidence_path.exists():
            try:
                existing = json.loads(evidence_path.read_text(encoding="utf-8"))
                existing_status = str((existing.get("envelope") or {}).get("status") or "")
            except (OSError, json.JSONDecodeError):
                existing_status = ""
        if status == "degraded" and existing_status == "ok":
            attempt_dir = evidence_path.parent / "attempts"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            attempt_path = attempt_dir / f"understanding_degraded_{document['persisted_at_ms']}.json"
            attempt_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
            return str(evidence_path)
        evidence_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        if status == "ok":
            self._latest_success_path(episode_id, drama_id=drama_id).write_text(
                json.dumps(document, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        if status == "ok" and version > 0:
            version_dir = evidence_path.parent / "versions"
            version_dir.mkdir(parents=True, exist_ok=True)
            version_path = version_dir / f"understanding_v{version:03d}.json"
            version_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(evidence_path)

    def _evidence_path(self, episode_id: str, drama_id: str = "tainai3") -> Path:
        return self.result_cache_dir / drama_id / episode_id / "understanding.json"

    def _latest_success_path(self, episode_id: str, drama_id: str = "tainai3") -> Path:
        return self.result_cache_dir / drama_id / episode_id / "latest_success.json"

    def _latest_attempt_path(self, episode_id: str, drama_id: str = "tainai3") -> Path:
        return self.result_cache_dir / drama_id / episode_id / "latest_attempt.json"

    def _asset_episode_dir(self, root: Path, drama_id: str, episode_id: str) -> Path:
        return root / drama_id / episode_id

    def _legacy_evidence_path(self, episode_id: str) -> Path:
        return self.result_cache_dir / episode_id / "understanding.json"

    def _legacy_latest_success_path(self, episode_id: str) -> Path:
        return self.result_cache_dir / episode_id / "latest_success.json"

    def _build_messages(self, context: dict[str, Any], frame_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        task_text = json.dumps(
            {
                    "task": "video.understanding",
                    "prompt_version": VIDEO_UNDERSTANDING_PROMPT_VERSION,
                    "rules": [
                        "所有数组最多返回 2 条",
                        "字段内容保持简短",
                        "必须返回可被 json.loads 解析的 JSON 对象",
                        "如果关键帧里有屏幕文字、人名牌、履历介绍，请写入 screen_text_cues",
                        "如果没有可用字幕或 ASR 文本，audio_text.status 返回 unavailable 或 audio_extracted_asr_pending",
                        "必须结合角色表纠正 ASR/OCR 中的人名、称呼和明显错字",
                        "如果 context.mediaText.audio.speakerTurns 存在，优先按说话人分段理解台词，不要把不同角色混成同一人",
                        "summary 和 story_summary 必须是面向观众的剧情简介，写成短剧平台介绍文案，不要写技术过程",
                        "summary 和 story_summary 不得出现 ASR、OCR、关键帧、识别、证据、互动节点、模型等技术词",
                        "每集剧情简介要说明本集发生了什么、谁和谁发生冲突、埋下什么悬念",
                        "可以使用 correctedTranscript、OCR cues 和角色表作为依据，但只能把它们转写成剧情内容",
                    ],
                    "output_schema": {
                    "summary": "string",
                    "story_summary": "string",
                    "segments": [
                        {
                            "start_ms": 0,
                            "end_ms": 0,
                            "scene": "string",
                            "characters": ["string"],
                            "visual_events": ["string"],
                            "dialogue_summary": "string",
                            "interaction_suggestion": "string",
                        }
                    ],
                    "characters": [{"name": "string", "traits": ["string"]}],
                    "interaction_candidates": [
                        {
                            "time_ms": 0,
                            "type": "string",
                            "question": "string",
                            "reason": "string",
                        }
                    ],
                    "evidence": ["string"],
                    "production_notes": ["string"],
                    "screen_text_cues": [
                        {
                            "time_ms": 0,
                            "text": "string",
                            "cue_type": "character_intro|subtitle|onscreen_text",
                            "reason": "string",
                        }
                    ],
                    "audio_text": {
                        "status": "string",
                        "transcript": "string",
                        "corrected_transcript": "string",
                        "speaker_transcript": "string",
                        "speaker_turns": [
                            {
                                "speaker_id": "string",
                                "speaker_name": "string",
                                "start_ms": 0,
                                "end_ms": 0,
                                "text": "string",
                                "reason": "string",
                            }
                        ],
                        "speaker_role_map": [
                            {
                                "speaker_id": "string",
                                "role_name": "string",
                                "reason": "string",
                            }
                        ],
                        "source": "string",
                    },
                    "high_energy_lines": [
                        {
                            "time_ms": 0,
                            "text": "string",
                            "reason": "string",
                        }
                    ],
                    "fusion_notes": ["string"],
                },
                "context": context,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        image_content: list[dict[str, Any]] = []
        for item in frame_items:
            data_url = item.get("dataUrl")
            if data_url:
                image_content.append({"type": "image_url", "image_url": {"url": data_url}})

        user_content: str | list[dict[str, Any]]
        if image_content:
            user_content = [{"type": "text", "text": task_text}] + image_content
        else:
            user_content = task_text

        return [
            {
                "role": "system",
                "content": (
                    "你是短剧视频理解助手。只输出 JSON，不要 Markdown，不要解释。"
                    "如果收到关键帧，请结合画面、剧集元数据和互动节点判断剧情冲突、角色状态和可互动点。"
                    "请对关键帧上的人物介绍、字幕、榜单、奖项、身份说明等屏幕文字做 OCR 式提取。"
                    "你必须用角色表、ASR 台词和 OCR 结果互相校验，修正明显错字后再生成摘要。"
                    "如果没有关键帧，请明确基于已有元数据进行保守理解。"
                    "如果 audio_text.speaker_turns 已提供，请优先使用它输出更准确的角色归因。"
                ),
            },
            {
                "role": "user",
                "content": user_content,
            },
        ]

    def _build_minimal_retry_messages(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        episode = context.get("episode", {})
        drama = context.get("drama", {})
        media_text = context.get("mediaText", {}) if isinstance(context.get("mediaText"), dict) else {}
        audio = media_text.get("audio", {}) if isinstance(media_text.get("audio"), dict) else {}
        ocr = media_text.get("ocr", {}) if isinstance(media_text.get("ocr"), dict) else {}
        cues = ocr.get("cues") if isinstance(ocr.get("cues"), list) else []
        minimal_context = {
            "drama_title": drama.get("title", ""),
            "episode_id": episode.get("episodeId", ""),
            "episode_title": episode.get("title", ""),
            "episode_summary": episode.get("summary", ""),
            "duration_ms": episode.get("durationMs", 0),
            "transcript_preview": str(
                audio.get("correctedTranscript")
                or audio.get("speakerTranscript")
                or audio.get("transcript")
                or ""
            )[:600],
            "screen_texts": [
                {
                    "time_ms": item.get("time_ms") or item.get("timeMs") or 0,
                    "text": str(item.get("text") or "")[:80],
                }
                for item in cues[:3]
                if isinstance(item, dict) and str(item.get("text") or "").strip()
            ],
        }
        return [
            {
                "role": "system",
                "content": (
                    "你是短剧剧情理解助手。上一次输出不是合法 JSON。"
                    "这次只返回一个可被 json.loads 解析的 JSON 对象，不要 Markdown，不要解释。"
                    "字段只能包含 story_summary、segments、high_energy_lines。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "video.understanding.minimal_retry",
                        "rules": [
                            "story_summary 面向观众，不出现 ASR、OCR、prompt、模型、证据等技术词",
                            "segments 最多 2 条，每条只包含 start_ms、end_ms、summary",
                            "high_energy_lines 最多 2 条，可以是字符串数组",
                        ],
                        "output_schema": {
                            "story_summary": "string",
                            "segments": [{"start_ms": 0, "end_ms": 0, "summary": "string"}],
                            "high_energy_lines": ["string"],
                        },
                        "context": minimal_context,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ]

    def _probe_video(self, file_path: Path) -> VideoProbeResult:
        ffprobe = _find_ffmpeg_tool("ffprobe")
        if not ffprobe:
            return VideoProbeResult(0, 0, 0, "", "ffprobe_missing")
        command = [
            str(ffprobe),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,codec_name,duration",
            "-of",
            "json",
            str(file_path),
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
            if completed.returncode != 0:
                return VideoProbeResult(0, 0, 0, "", "ffprobe_failed")
            parsed = json.loads(completed.stdout)
            stream = (parsed.get("streams") or [{}])[0]
            duration_ms = int(float(stream.get("duration", 0) or 0) * 1000)
            return VideoProbeResult(
                duration_ms=duration_ms,
                width=int(stream.get("width", 0) or 0),
                height=int(stream.get("height", 0) or 0),
                codec_name=str(stream.get("codec_name") or ""),
                tool_status="ok",
            )
        except Exception:
            return VideoProbeResult(0, 0, 0, "", "ffprobe_error")

    def _extract_key_frames(
        self,
        file_path: Path,
        episode_id: str,
        duration_ms: int,
        max_frames: int,
        *,
        drama_id: str = "tainai3",
        interaction_nodes: list[dict[str, Any]] | None = None,
        utterances: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        ffmpeg = _find_ffmpeg_tool("ffmpeg")
        if not ffmpeg or max_frames <= 0:
            return []
        duration_seconds = max(float(duration_ms) / 1000.0, 1.0)
        selections = _select_keyframe_candidates(
            duration_seconds=duration_seconds,
            max_frames=max_frames,
            interaction_nodes=interaction_nodes or [],
            utterances=utterances or [],
        )
        output_dir = self._asset_episode_dir(self.frame_cache_dir, drama_id, episode_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        frames: list[dict[str, Any]] = []
        for index, selection in enumerate(selections, start=1):
            timestamp = float(selection["timeSeconds"])
            output_path = output_dir / f"frame_v3_{index:02d}_{int(timestamp * 1000)}.jpg"
            if not output_path.exists():
                command = [
                    str(ffmpeg),
                    "-y",
                    "-ss",
                    f"{timestamp:.2f}",
                    "-i",
                    str(file_path),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale='min(480,iw)':-2",
                    "-q:v",
                    "6",
                    str(output_path),
                ]
                subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=False)
            data_url = ""
            if output_path.exists():
                data_url = "data:image/jpeg;base64," + base64.b64encode(output_path.read_bytes()).decode("ascii")
            frames.append(
                {
                    "timeMs": int(timestamp * 1000),
                    "path": str(output_path),
                    "dataUrl": data_url,
                    "samplingSource": selection["source"],
                    "samplingReason": selection["reason"],
                    "samplingScore": selection["score"],
                }
            )
        return frames

    def _extract_audio_track(self, file_path: Path, episode_id: str, drama_id: str = "tainai3") -> dict[str, str]:
        ffmpeg = _find_ffmpeg_tool("ffmpeg")
        if not ffmpeg:
            return {"status": "ffmpeg_missing", "path": "", "format": "", "transcript": "", "source": "none", "utterances": []}
        output_dir = self._asset_episode_dir(self.audio_cache_dir, drama_id, episode_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "audio_16k_mono.wav"
        if not output_path.exists():
            command = [
                str(ffmpeg),
                "-y",
                "-i",
                str(file_path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-f",
                "wav",
                str(output_path),
            ]
            completed = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=60,
                check=False,
            )
            if completed.returncode != 0:
                return {"status": "audio_extract_failed", "path": "", "format": "wav", "transcript": "", "source": "ffmpeg", "utterances": []}
        if not output_path.exists():
            return {"status": "audio_missing", "path": "", "format": "wav", "transcript": "", "source": "ffmpeg", "utterances": []}
        asr_result = get_asr_service().recognize_file(output_path)
        transcript = str(asr_result.get("transcript") or "").strip()
        utterances = asr_result.get("utterances") if isinstance(asr_result.get("utterances"), list) else []
        if transcript:
            return {
                "status": str(asr_result.get("status") or "ok"),
                "path": str(output_path),
                "format": "wav/16000hz/mono",
                "transcript": transcript,
                "source": str(asr_result.get("source") or "volc.bigasr.auc_turbo"),
                "utterances": utterances,
            }
        return {
            "status": str(asr_result.get("status") or "audio_extracted_asr_pending"),
            "path": str(output_path),
            "format": "wav/16000hz/mono",
            "transcript": "",
            "source": str(asr_result.get("source") or "ffmpeg"),
            "utterances": utterances,
        }

    def _extract_embedded_subtitles(self, file_path: Path, episode_id: str, drama_id: str = "tainai3") -> dict[str, str]:
        ffmpeg = _find_ffmpeg_tool("ffmpeg")
        if not ffmpeg:
            return {"status": "ffmpeg_missing", "path": "", "text": "", "source": "none"}
        output_dir = self._asset_episode_dir(self.subtitle_cache_dir, drama_id, episode_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "embedded_subtitle.srt"
        if not output_path.exists():
            command = [
                str(ffmpeg),
                "-y",
                "-i",
                str(file_path),
                "-map",
                "0:s:0",
                str(output_path),
            ]
            subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
        if not output_path.exists():
            return {"status": "no_embedded_subtitle", "path": "", "text": "", "source": "ffmpeg"}
        text = output_path.read_text(encoding="utf-8", errors="ignore")
        return {
            "status": "ok",
            "path": str(output_path),
            "text": text,
            "source": "embedded_subtitle",
        }

    def _fallback_understanding(self, context: dict[str, Any]) -> dict[str, Any]:
        episode = context["episode"]
        drama = context["drama"]
        nodes = context.get("interactionNodes", [])
        duration_ms = int(context["video"].get("durationMs") or episode["durationMs"])
        segments = [
            {
                "start_ms": 0,
                "end_ms": min(duration_ms, 60_000),
                "scene": "开场与核心冲突建立",
                "characters": [item.get("name", "") for item in drama.get("characters", []) if item.get("name")],
                "visual_events": ["P0 未完成关键帧视觉解析，当前基于剧集元数据生成"],
                "dialogue_summary": episode["summary"],
                "interaction_suggestion": "适合用站队或预测类互动承接剧情冲突。",
            }
        ]
        for node in nodes:
            start_ms = int(node.get("trigger", {}).get("timeMs", 0) or 0)
            segments.append(
                {
                    "start_ms": start_ms,
                    "end_ms": min(start_ms + 30_000, duration_ms),
                    "scene": str(node.get("title") or "互动节点"),
                    "characters": [item.get("name", "") for item in drama.get("characters", []) if item.get("name")],
                    "visual_events": [str(node.get("subtitle") or "")],
                    "dialogue_summary": "该位置适合围绕用户选择生成剧情理解。",
                    "interaction_suggestion": f"沿用 {node.get('type', 'INTERACTION')} 互动。",
                }
            )
        transcript_preview = str(context["mediaText"]["audio"].get("correctedTranscript") or context["mediaText"]["audio"].get("transcript") or "").strip()
        ocr_preview = "；".join(
            str(item.get("text") or "").strip()
            for item in context["mediaText"].get("ocr", {}).get("cues", [])[:2]
            if isinstance(item, dict) and str(item.get("text") or "").strip()
        )
        story_summary = _build_user_facing_story_summary(
            episode_summary=str(episode["summary"]),
            transcript_preview=transcript_preview,
            ocr_preview=ocr_preview,
        )
        return {
            "episode_id": episode["episodeId"],
            "summary": story_summary,
            "story_summary": story_summary,
            "segments": segments,
            "characters": [
                {
                    "name": item.get("name", ""),
                    "traits": ["核心角色", "推动剧情冲突"],
                }
                for item in drama.get("characters", [])
            ],
            "interaction_candidates": [
                {
                    "time_ms": int(node.get("trigger", {}).get("timeMs", 0) or 0),
                    "type": str(node.get("type") or "INTERACTION"),
                    "question": str(node.get("title") or "你会怎么选？"),
                    "reason": str(node.get("subtitle") or "该处具有互动价值"),
                    "options": [
                        str(option.get("text", ""))
                        for option in node.get("options", [])
                        if str(option.get("text", "")).strip()
                    ],
                }
                for node in nodes
            ],
            "evidence": [
                f"视频文件：{context['video']['fileName']}",
                f"工具状态：{context['video']['toolStatus']}",
                f"关键帧数量：{len(context.get('frames', []))}",
                f"OCR状态：{context['mediaText'].get('ocr', {}).get('status', 'disabled')}",
                f"音频状态：{context['mediaText']['audio']['status']}",
                f"transcript长度：{len(context['mediaText']['audio'].get('correctedTranscript') or context['mediaText']['audio'].get('transcript') or '')}",
                f"字幕状态：{context['mediaText']['subtitles']['status']}",
            ],
            "production_notes": [
                "P0 优先保证可用的结构化理解结果。",
                "FFmpeg 已用于关键帧、音频和内嵌字幕资产抽取。",
                "ASR/OCR/角色表已进入融合摘要链路，远端 Doubao-Seed 可继续做语义纠错。",
            ],
            "screen_text_cues": _ensure_screen_text_cues(
                context["mediaText"].get("ocr", {}).get("cues"),
                _fallback_screen_text_cues(nodes),
            ),
            "audio_text": {
                "status": context["mediaText"]["audio"]["status"],
                "transcript": context["mediaText"]["audio"].get("transcript", ""),
                "corrected_transcript": context["mediaText"]["audio"].get("correctedTranscript", ""),
                "speaker_transcript": context["mediaText"]["audio"].get("speakerTranscript", ""),
                "speaker_turns": context["mediaText"]["audio"].get("speakerTurns", []),
                "speaker_role_map": context["mediaText"]["audio"].get("speakerRoleMap", []),
                "source": context["mediaText"]["audio"].get("source", "audio_asset"),
            },
            "high_energy_lines": _fallback_high_energy_lines(context),
            "fusion_notes": context.get("fusion", {}).get("notes", []),
            "frame_sampling": {
                "strategy": "interaction_audio_anchor_v1",
                "selected_frames": [
                    {
                        "time_ms": int(item.get("timeMs", 0) or 0),
                        "source": str(item.get("samplingSource") or "anchor"),
                        "reason": str(item.get("samplingReason") or ""),
                        "score": float(item.get("samplingScore") or 0.0),
                    }
                    for item in context.get("frames", [])
                ],
            },
        }

    def _normalize_understanding(self, parsed: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        result = parsed.get("result") if isinstance(parsed.get("result"), dict) else parsed
        fallback = self._fallback_understanding(context)
        story_summary = str(
            result.get("story_summary")
            or result.get("plot_summary")
            or result.get("summary")
            or fallback["story_summary"]
        ).strip()
        return {
            "episode_id": context["episode"]["episodeId"],
            "summary": story_summary,
            "story_summary": story_summary,
            "segments": _ensure_segments(result.get("segments"), fallback["segments"]),
            "characters": _ensure_characters(result.get("characters"), fallback["characters"]),
            "interaction_candidates": _ensure_interaction_candidates(
                result.get("interaction_candidates"),
                fallback["interaction_candidates"],
            ),
            "evidence": _ensure_string_list(result.get("evidence"), fallback["evidence"]),
            "production_notes": _ensure_string_list(result.get("production_notes"), fallback["production_notes"]),
            "screen_text_cues": _ensure_screen_text_cues(
                result.get("screen_text_cues"),
                fallback["screen_text_cues"],
            ),
            "audio_text": _ensure_audio_text(result.get("audio_text"), fallback["audio_text"]),
            "high_energy_lines": _ensure_high_energy_lines(
                result.get("high_energy_lines"),
                fallback["high_energy_lines"],
            ),
            "fusion_notes": _ensure_string_list(result.get("fusion_notes"), fallback["fusion_notes"]),
            "frame_sampling": fallback["frame_sampling"],
        }


def get_video_understanding_service() -> VideoUnderstandingService:
    return VideoUnderstandingService()


def _build_user_facing_story_summary(
    *,
    episode_summary: str,
    transcript_preview: str,
    ocr_preview: str,
) -> str:
    parts = [episode_summary.strip().rstrip("。")] if episode_summary.strip() else []
    transcript_text = _clean_story_fragment(transcript_preview, 90)
    if transcript_text:
        parts.append(transcript_text.rstrip("。"))
    ocr_text = _clean_story_fragment(ocr_preview, 50)
    if ocr_text:
        parts.append(f"画面信息进一步交代了{ocr_text}等身份线索")
    cleaned = [part for part in parts if part]
    if not cleaned:
        return "本集围绕主角回到家族后的身份误会和正面冲突展开，局势在质疑与反击中逐步升级。"
    return "。".join(cleaned) + "。"


def _clean_story_fragment(text: str, limit: int) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip(" ，。；;")
    return cleaned[:limit].strip(" ，。；;")


def _find_ffmpeg_tool(tool_name: str) -> Path | None:
    executable = f"{tool_name}.exe" if os.name == "nt" else tool_name
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        repo_root / "tools" / "ffmpeg" / "bin" / executable,
    ]
    env_dir = os.environ.get("AIGC_FFMPEG_DIR", "").strip()
    if env_dir:
        candidates.append(Path(env_dir) / executable)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    found = shutil.which(executable) or shutil.which(tool_name)
    return Path(found) if found else None


def _sample_timestamps(duration_seconds: float, max_frames: int) -> list[float]:
    if max_frames <= 0:
        return []
    if max_frames == 1:
        return [max(duration_seconds * 0.5, 0.5)]
    return [
        max(duration_seconds * ratio, 0.5)
        for ratio in (0.18, 0.5, 0.82, 0.32, 0.68)[:max_frames]
    ]


def _select_keyframe_candidates(
    *,
    duration_seconds: float,
    max_frames: int,
    interaction_nodes: list[dict[str, Any]],
    utterances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if max_frames <= 0:
        return []
    candidates: list[dict[str, Any]] = []

    def append_candidate(time_seconds: float, source: str, reason: str, score: float) -> None:
        clamped = min(max(time_seconds, 0.5), max(duration_seconds - 0.2, 0.5))
        candidates.append(
            {
                "timeSeconds": clamped,
                "source": source,
                "reason": reason,
                "score": round(score, 3),
            }
        )

    for node in interaction_nodes:
        trigger_ms = _safe_int(node.get("trigger", {}).get("timeMs"), 0, minimum=0)
        if trigger_ms <= 0:
            continue
        append_candidate(
            trigger_ms / 1000.0,
            "interaction_trigger",
            str(node.get("title") or "互动节点触发点"),
            0.9,
        )

    audio_candidates: list[dict[str, Any]] = []
    for utterance in utterances:
        if not isinstance(utterance, dict):
            continue
        text = str(utterance.get("text") or "").strip()
        if not text:
            continue
        start_ms = _safe_int(utterance.get("start_ms"), 0, minimum=0)
        end_ms = _safe_int(utterance.get("end_ms"), start_ms, minimum=start_ms)
        if end_ms <= 0:
            continue
        score = _score_audio_energy(text)
        audio_candidates.append(
            {
                "timeSeconds": (start_ms + end_ms) / 2000.0,
                "source": "audio_energy",
                "reason": text[:36],
                "score": score,
            }
        )
    candidates.extend(sorted(audio_candidates, key=lambda item: float(item["score"]), reverse=True)[:3])

    for index, timestamp in enumerate(_sample_timestamps(duration_seconds, 5), start=1):
        append_candidate(timestamp, "anchor", f"基础覆盖锚点 {index}", 0.35)

    selected: list[dict[str, Any]] = []
    min_distance = max(duration_seconds * 0.06, 2.0)
    ranked = sorted(
        candidates,
        key=lambda item: (
            1 if item["source"] == "audio_energy" else 0,
            float(item["score"]),
        ),
        reverse=True,
    )
    for candidate in ranked:
        if any(abs(float(item["timeSeconds"]) - float(candidate["timeSeconds"])) < min_distance for item in selected):
            continue
        selected.append(candidate)
        if len(selected) >= max_frames:
            break
    if len(selected) < max_frames:
        for candidate in sorted(candidates, key=lambda item: float(item["timeSeconds"])):
            if candidate in selected:
                continue
            selected.append(candidate)
            if len(selected) >= max_frames:
                break
    return sorted(selected[:max_frames], key=lambda item: float(item["timeSeconds"]))


def _score_audio_energy(text: str) -> float:
    markers = ("！", "!", "？", "?", "证据", "反击", "够了", "不可能", "回来", "真相", "身份")
    marker_hits = sum(1 for marker in markers if marker in text)
    length_bonus = min(len(text), 36) / 180.0
    return min(0.98, 0.48 + marker_hits * 0.1 + length_bonus)


def _safe_float(value: Any, default: float, *, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    if minimum is not None:
        number = max(number, minimum)
    if maximum is not None:
        number = min(number, maximum)
    return number


def _looks_jsonish(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith("{") or stripped.startswith("```")


def _ensure_string_list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        result = [str(item).strip() for item in value if str(item).strip()]
        if result:
            return result
    return fallback


def _ensure_segments(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    segments: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        scene = str(item.get("scene") or "").strip()
        if not scene:
            continue
        segments.append(
            {
                "start_ms": _safe_int(item.get("start_ms"), 0, minimum=0),
                "end_ms": _safe_int(item.get("end_ms"), 0, minimum=0),
                "scene": scene,
                "characters": _ensure_string_list(item.get("characters"), []),
                "visual_events": _ensure_string_list(item.get("visual_events"), []),
                "dialogue_summary": str(item.get("dialogue_summary") or "").strip(),
                "interaction_suggestion": str(item.get("interaction_suggestion") or "").strip(),
            }
        )
    return segments or fallback


def _ensure_characters(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    characters: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        characters.append({"name": name, "traits": _ensure_string_list(item.get("traits"), [])})
    return characters or fallback


def _ensure_interaction_candidates(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    candidates: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        if not question:
            continue
        candidate_type = str(item.get("type") or "INTERACTION").strip()
        options = _ensure_string_list(item.get("options"), [])
        candidates.append(
            {
                "time_ms": _safe_int(item.get("time_ms"), 0, minimum=0),
                "type": candidate_type,
                "question": question,
                "reason": str(item.get("reason") or "").strip(),
                "options": options or _default_interaction_options(question, candidate_type),
            }
        )
    return candidates or fallback


def _default_interaction_options(question: str, candidate_type: str) -> list[str]:
    text = f"{question} {candidate_type}"
    if "登场" in text or "帅" in text or "气场" in text:
        return ["好帅", "这气场绝了", "有意思，继续看"]
    if "文字" in text or "身份" in text or "履历" in text or "介绍" in text:
        return ["履历太强", "原来有隐藏身份", "想看她打脸"]
    if "剧情" in text or "反转" in text or "期待" in text:
        return ["继续反转", "身份揭晓", "家族对线"]
    return ["有意思", "想继续看", "先记下"]


def _ensure_screen_text_cues(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    cues: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        cues.append(
            {
                "time_ms": _safe_int(item.get("time_ms"), 0, minimum=0),
                "text": text,
                "cue_type": str(item.get("cue_type") or item.get("type") or "onscreen_text").strip(),
                "reason": str(item.get("reason") or "").strip(),
            }
        )
    return cues or fallback


def _ensure_audio_text(value: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return fallback
    status = str(value.get("status") or fallback.get("status") or "unavailable").strip()
    return {
        "status": status,
        "transcript": str(value.get("transcript") or fallback.get("transcript") or "").strip(),
        "corrected_transcript": str(
            value.get("corrected_transcript")
            or value.get("correctedTranscript")
            or fallback.get("corrected_transcript")
            or fallback.get("transcript")
            or ""
        ).strip(),
        "speaker_transcript": str(
            value.get("speaker_transcript")
            or value.get("speakerTranscript")
            or fallback.get("speaker_transcript")
            or fallback.get("corrected_transcript")
            or fallback.get("transcript")
            or ""
        ).strip(),
        "speaker_turns": _ensure_speaker_turns(value.get("speaker_turns") or value.get("speakerTurns"), fallback.get("speaker_turns", [])),
        "speaker_role_map": _ensure_speaker_role_map(value.get("speaker_role_map") or value.get("speakerRoleMap"), fallback.get("speaker_role_map", [])),
        "character_profiles": _ensure_character_profiles(value.get("character_profiles") or value.get("characterProfiles"), fallback.get("character_profiles", [])),
        "source": str(value.get("source") or fallback.get("source") or "unknown").strip(),
    }


def _ensure_speaker_turns(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    turns: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        turns.append(
            {
                "speaker_id": str(item.get("speaker_id") or item.get("speakerId") or "").strip(),
                "speaker_name": str(item.get("speaker_name") or item.get("speakerName") or "").strip(),
                "speaker_label": str(item.get("speaker_label") or item.get("speakerLabel") or "").strip(),
                "speaker_role": str(item.get("speaker_role") or item.get("speakerRole") or "").strip(),
                "speaker_role_type": str(item.get("speaker_role_type") or item.get("speakerRoleType") or "").strip(),
                "speaker_alias": str(item.get("speaker_alias") or item.get("speakerAlias") or "").strip(),
                "start_ms": _safe_int(item.get("start_ms") or item.get("startMs"), 0, minimum=0),
                "end_ms": _safe_int(item.get("end_ms") or item.get("endMs"), 0, minimum=0),
                "text": text,
                "reason": str(item.get("reason") or "").strip(),
            }
        )
    return turns if turns else fallback


def _ensure_speaker_role_map(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    bindings: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        speaker_id = str(item.get("speaker_id") or item.get("speakerId") or "").strip()
        role_name = str(item.get("role_name") or item.get("roleName") or "").strip()
        if not speaker_id or not role_name:
            continue
        bindings.append(
            {
                "speaker_id": speaker_id,
                "role_name": role_name,
                "canonical_role_name": str(item.get("canonical_role_name") or item.get("canonicalRoleName") or role_name).strip(),
                "role_type": str(item.get("role_type") or item.get("roleType") or "").strip(),
                "matched_alias": str(item.get("matched_alias") or item.get("matchedAlias") or "").strip(),
                "mentioned_role_name": str(item.get("mentioned_role_name") or item.get("mentionedRoleName") or "").strip(),
                "confidence": _safe_float(item.get("confidence"), 0.0, minimum=0.0, maximum=1.0),
                "reason": str(item.get("reason") or "").strip(),
            }
        )
    return bindings if bindings else fallback


def _ensure_character_profiles(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return fallback
    profiles: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        display_name = str(item.get("display_name") or item.get("name") or "").strip()
        canonical_name = str(item.get("canonical_name") or display_name).strip()
        if not canonical_name and not display_name:
            continue
        profiles.append(
            {
                "character_id": str(item.get("character_id") or "").strip(),
                "display_name": display_name or canonical_name,
                "canonical_name": canonical_name or display_name,
                "aliases": _ensure_string_list(item.get("aliases"), []),
                "role_type": str(item.get("role_type") or "character").strip() or "character",
            }
        )
    return profiles if profiles else fallback


def _ensure_high_energy_lines(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(value, list):
        lines: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
                reason = "模型识别出的高能台词"
                time_ms = 0
            elif isinstance(item, dict):
                text = str(item.get("text") or "").strip()
                reason = str(item.get("reason") or "模型识别出的高能台词").strip()
                time_ms = _safe_int(item.get("time_ms") or item.get("timeMs"), 0, minimum=0)
            else:
                continue
            if text:
                lines.append({"time_ms": time_ms, "text": text, "reason": reason})
        if lines:
            return lines[:3]
    return fallback


def _fallback_screen_text_cues(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    for node in nodes:
        node_type = str(node.get("type") or "")
        if node_type not in {"SCREEN_TEXT_REACTION", "HISTORY_RECAP"}:
            continue
        trigger = node.get("trigger", {}) if isinstance(node.get("trigger"), dict) else {}
        cues.append(
            {
                "time_ms": _safe_int(trigger.get("timeMs"), 0, minimum=0),
                "text": str(node.get("title") or "屏幕文字/剧情线索"),
                "cue_type": "character_intro" if node_type == "SCREEN_TEXT_REACTION" else "onscreen_text",
                "reason": str(node.get("subtitle") or "视频理解链路根据互动节点生成屏幕文字候选。"),
            }
        )
    return cues


def _build_character_profiles(characters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for item in characters:
        if not isinstance(item, dict):
            continue
        display_name = str(item.get("name") or "").strip()
        canonical_name = str(item.get("canonical_name") or display_name).strip()
        aliases = []
        for alias in [display_name, canonical_name, *_ensure_string_list(item.get("aliases"), [])]:
            alias_text = str(alias or "").strip()
            if alias_text and alias_text not in aliases:
                aliases.append(alias_text)
        role_type = str(item.get("role_type") or "character").strip() or "character"
        profiles.append(
            {
                "character_id": str(item.get("character_id") or "").strip(),
                "display_name": display_name or canonical_name,
                "canonical_name": canonical_name or display_name,
                "aliases": aliases,
                "role_type": role_type,
            }
        )
    if not any("容遇" in [profile["canonical_name"], *profile.get("aliases", [])] for profile in profiles):
        profiles.insert(
            0,
            {
                "character_id": "fallback_lead",
                "display_name": "太奶奶",
                "canonical_name": "容遇",
                "aliases": ["太奶奶", "容玉", "荣遇"],
                "role_type": "lead",
            },
        )
    if not any(profile.get("role_type") == "family_group" for profile in profiles):
        profiles.append(
            {
                "character_id": "fallback_family_group",
                "display_name": "家族少爷",
                "canonical_name": "家族少爷",
                "aliases": ["少爷", "少爷们", "大少爷", "二少爷", "三少爷", "季家少爷"],
                "role_type": "family_group",
            }
        )
    return profiles


def _build_role_vocabulary(character_profiles: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for item in character_profiles:
        for candidate in [
            str(item.get("display_name") or "").strip(),
            str(item.get("canonical_name") or "").strip(),
            *[_alias.strip() for _alias in item.get("aliases", []) if isinstance(_alias, str)],
        ]:
            if candidate and candidate not in names:
                names.append(candidate)
    for required_name in ("太奶奶", "容遇"):
        if required_name not in names:
            names.append(required_name)
    return names


def _correct_text_by_roles(text: str, role_vocabulary: list[str]) -> str:
    corrected = str(text or "").strip()
    if not corrected:
        return ""
    replacements = {
        "容玉": "容遇",
        "荣遇": "容遇",
        "太奶": "太奶奶",
        "奶奶奶": "太奶奶",
        "季家少爷们": "家族少爷",
        "少爷们": "家族少爷",
    }
    for wrong, right in replacements.items():
        if right in role_vocabulary or right == "容遇":
            corrected = corrected.replace(wrong, right)
    return corrected


def _build_fused_media_text(
    *,
    transcript: str,
    ocr_cues: list[dict[str, Any]],
    role_vocabulary: list[str],
    speaker_turns: list[dict[str, Any]],
    speaker_role_map: list[dict[str, Any]],
) -> dict[str, Any]:
    screen_text = [
        str(item.get("text") or "").strip()
        for item in ocr_cues
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    ]
    speaker_preview = [
        f"{str(item.get('speaker_name') or item.get('speaker_id') or 'speaker')}: {str(item.get('text') or '')[:40]}"
        for item in speaker_turns[:4]
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    ]
    notes = [
        f"角色表：{'、'.join(role_vocabulary)}",
        f"ASR transcript 字数：{len(transcript)}",
        f"OCR cues 数量：{len(screen_text)}",
        f"说话人分段数量：{len(speaker_turns)}",
    ]
    return {
        "roleVocabulary": role_vocabulary,
        "correctedTranscriptPreview": transcript[:1000],
        "ocrTextPreview": screen_text[:5],
        "speakerTurnPreview": speaker_preview,
        "speakerRoleMap": speaker_role_map[:6],
        "notes": notes,
    }


def _normalize_identity_token(value: str) -> str:
    text = str(value or "").strip().lower()
    for token in (" ", "，", "。", "、", "：", ":", "-", "_", "【", "】", "(", ")", "（", "）"):
        text = text.replace(token, "")
    return text


def _collect_profile_aliases(profile: dict[str, Any]) -> list[str]:
    aliases: list[str] = []
    for candidate in [
        str(profile.get("display_name") or "").strip(),
        str(profile.get("canonical_name") or "").strip(),
        *[_alias for _alias in profile.get("aliases", []) if isinstance(_alias, str)],
    ]:
        alias_text = str(candidate or "").strip()
        if alias_text and alias_text not in aliases:
            aliases.append(alias_text)
    return sorted(aliases, key=len, reverse=True)


def _find_best_alias_match(blob: str, aliases: list[str]) -> str:
    text = str(blob or "")
    for alias in aliases:
        if alias and alias in text:
            return alias
    return ""


def _score_character_profile(
    profile: dict[str, Any],
    text: str,
    ocr_blob: str,
    speaker_id: str,
    speaker_label: str,
) -> tuple[str, int]:
    aliases = _collect_profile_aliases(profile)
    text_match = _find_best_alias_match(text, aliases)
    ocr_match = _find_best_alias_match(ocr_blob, aliases)
    label_match = _find_best_alias_match(speaker_label, aliases)
    speaker_match = _find_best_alias_match(speaker_id, aliases)
    matched_alias = label_match or speaker_match or text_match or ocr_match
    score = 0
    if label_match:
        score += 8
    if speaker_match:
        score += 6
    if text_match and _looks_like_self_identification(text, text_match):
        score += 5
    elif text_match:
        if _is_specific_alias(text_match):
            score += 5 if str(profile.get("role_type") or "").strip() == "family_group" else 4
        else:
            score += 1
    if ocr_match:
        score += 2 if _is_specific_alias(ocr_match) else 1
    if str(profile.get("role_type") or "").strip() == "family_group" and matched_alias:
        if _is_generic_group_alias(matched_alias):
            score += 1
    return matched_alias, score


def _looks_like_self_identification(text: str, alias: str) -> bool:
    value = str(text or "").replace(" ", "")
    role = str(alias or "").replace(" ", "")
    if not value or not role:
        return False
    markers = (f"我是{role}", f"我叫{role}", f"本少爷是{role}", f"本小姐是{role}")
    return any(marker in value for marker in markers)


def _is_generic_group_alias(alias: str) -> bool:
    text = str(alias or "").strip()
    if not text:
        return False
    generic_aliases = {
        "少爷",
        "少爷们",
        "家族少爷",
        "季家少爷",
        "围观群众",
        "群众",
        "旁观者",
    }
    if text in generic_aliases:
        return True
    return "群" in text and "号" not in text and len(text) <= 8


def _is_specific_alias(alias: str) -> bool:
    text = str(alias or "").strip()
    if not text:
        return False
    return not _is_generic_group_alias(text)


def _looks_like_crowd_line(
    speaker_turns: list[dict[str, Any]],
    index: int,
    speaker_id: str,
    ocr_blob: str,
) -> bool:
    current_text = ""
    for item in speaker_turns:
        if str(item.get("speaker_id") or "").strip() == speaker_id:
            current_text = str(item.get("text") or "").strip()
            break
    if not current_text:
        return False
    crowd_markers = (
        "快看",
        "怎么回事",
        "什么情况",
        "真的假的",
        "别吵",
        "有意思",
        "好帅",
        "太帅了",
        "围观",
        "来了",
        "哇",
        "啊",
        "哈哈",
        "笑死",
        "看她",
        "看他",
    )
    if any(marker in current_text for marker in crowd_markers):
        return True
    if any(marker in ocr_blob for marker in ("围观", "群众", "众人", "人群")):
        return True
    if len(current_text) <= 12 and index > 0:
        return True
    return False


def _build_speaker_turns(
    *,
    transcript: str,
    utterances: list[dict[str, Any]],
    role_vocabulary: list[str],
    character_profiles: list[dict[str, Any]],
    ocr_cues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(utterances[:40]):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        speaker_label = str(item.get("speaker_label") or "").strip()
        speaker_id = str(item.get("speaker_id") or speaker_label or f"speaker_{index % 2 + 1}").strip()
        normalized.append(
            {
                "speaker_id": speaker_id,
                "speaker_label": speaker_label,
                "start_ms": _safe_int(item.get("start_ms") or item.get("start_time"), 0, minimum=0),
                "end_ms": _safe_int(item.get("end_ms") or item.get("end_time"), 0, minimum=0),
                "text": _correct_text_by_roles(text, role_vocabulary),
                "reason": "ASR utterance 已保留说话人元数据" if str(item.get("speaker_id") or item.get("speaker_label") or "").strip() else "ASR utterance 未提供 speaker，按片段保留",
            }
        )
    if not normalized:
        chunks = [chunk.strip() for chunk in _split_dialogue(transcript) if chunk.strip()]
        if not chunks and transcript.strip():
            chunks = [transcript.strip()]
        for index, chunk in enumerate(chunks[:24]):
            speaker_id = "speaker_1" if len(chunks) == 1 else f"speaker_{index % 2 + 1}"
            normalized.append(
                {
                    "speaker_id": speaker_id,
                    "start_ms": 0,
                    "end_ms": 0,
                    "text": _correct_text_by_roles(chunk, role_vocabulary),
                    "reason": "基于文本分句构造的说话人片段",
                }
            )
    speaker_role_map = _infer_speaker_role_map(normalized, character_profiles, ocr_cues)
    role_lookup = {str(item.get("speaker_id") or "").strip(): item for item in speaker_role_map if isinstance(item, dict)}
    for item in normalized:
        speaker_id = str(item.get("speaker_id") or "").strip()
        binding = role_lookup.get(speaker_id, {})
        role_name = str(binding.get("role_name") or "").strip()
        canonical_role_name = str(binding.get("canonical_role_name") or role_name or speaker_id).strip()
        role_type = str(binding.get("role_type") or "unknown").strip() or "unknown"
        matched_alias = str(binding.get("matched_alias") or "").strip()
        if role_name and role_name != speaker_id:
            item["speaker_name"] = role_name
            item["speaker_role"] = canonical_role_name or role_name
            item["speaker_role_type"] = role_type
            if matched_alias and role_type not in {"crowd", "unknown", "crowd_like_group"}:
                item["speaker_alias"] = matched_alias
        else:
            item["speaker_name"] = speaker_id
            item["speaker_role"] = speaker_id
            item["speaker_role_type"] = "unknown"
    return normalized


def _infer_speaker_role_map(
    speaker_turns: list[dict[str, Any]],
    character_profiles: list[dict[str, Any]],
    ocr_cues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    unique_speakers: list[str] = []
    for item in speaker_turns:
        speaker_id = str(item.get("speaker_id") or "").strip()
        if speaker_id and speaker_id not in unique_speakers:
            unique_speakers.append(speaker_id)
    if not unique_speakers:
        return []

    ocr_texts = [
        str(item.get("text") or "").strip()
        for item in ocr_cues
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    ]
    ocr_blob = " ".join(ocr_texts)

    role_scoreboard: dict[str, list[dict[str, Any]]] = {speaker_id: [] for speaker_id in unique_speakers}
    for item in speaker_turns:
        speaker_id = str(item.get("speaker_id") or "").strip()
        speaker_label = str(item.get("speaker_label") or "").strip()
        text = str(item.get("text") or "").strip()
        if not speaker_id or not text:
            continue
        for profile in character_profiles:
            alias_hit, alias_score = _score_character_profile(profile, text, ocr_blob, speaker_id, speaker_label)
            if alias_score <= 0:
                continue
            role_scoreboard[speaker_id].append(
                {
                    "profile": profile,
                    "score": alias_score,
                    "matched_alias": alias_hit,
                }
            )

    group_counters: dict[str, int] = {"family_group": 0, "crowd": 0}
    bindings: list[dict[str, Any]] = []
    for index, speaker_id in enumerate(unique_speakers):
        candidates = sorted(role_scoreboard.get(speaker_id, []), key=lambda item: item["score"], reverse=True)
        best_candidate = candidates[0] if candidates else None
        best_profile = best_candidate["profile"] if best_candidate else None
        best_score = int(best_candidate["score"]) if best_candidate else 0
        matched_alias = str(best_candidate.get("matched_alias") or "") if best_candidate else ""
        reason = ""
        role_name = speaker_id
        canonical_role_name = speaker_id
        role_type = "unknown"
        confidence = 0.0
        mentioned_role_name = ""

        if best_profile and matched_alias:
            mentioned_role_name = str(best_profile.get("canonical_name") or best_profile.get("display_name") or "").strip()

        if best_profile and best_score >= 5:
            canonical_role_name = str(best_profile.get("canonical_name") or best_profile.get("display_name") or speaker_id).strip()
            role_type = str(best_profile.get("role_type") or "character").strip() or "character"
            display_name = str(best_profile.get("display_name") or canonical_role_name).strip() or canonical_role_name
            confidence = min(0.95, 0.35 + best_score * 0.12)
            if role_type == "family_group":
                if _is_generic_group_alias(matched_alias or display_name):
                    group_counters["family_group"] += 1
                    role_name = f"{display_name}{group_counters['family_group']}"
                    role_type = "crowd_like_group"
                    reason = f"ASR/OCR 命中家族群体线索 {matched_alias or display_name}"
                else:
                    role_name = matched_alias or canonical_role_name
                    role_type = "family_member"
                    reason = f"ASR/OCR 命中具体家庭成员 {role_name}"
            else:
                role_name = canonical_role_name
                if matched_alias and matched_alias != canonical_role_name:
                    reason = f"ASR/OCR 命中别名 {matched_alias}"
                else:
                    reason = f"ASR/OCR 命中角色名 {canonical_role_name}"
        elif _looks_like_crowd_line(speaker_turns, index, speaker_id, ocr_blob):
            group_counters["crowd"] += 1
            role_name = f"围观群众{group_counters['crowd']}"
            canonical_role_name = "围观群众"
            role_type = "crowd"
            reason = "未命中角色表且台词呈围观/群体特征"
            confidence = 0.25
        elif mentioned_role_name:
            reason = f"台词提及 {mentioned_role_name}，但缺少说话人身份证据"
            confidence = 0.1
        else:
            reason = "暂未识别到明确角色线索"
        bindings.append(
            {
                "speaker_id": speaker_id,
                "role_name": role_name,
                "canonical_role_name": canonical_role_name,
                "role_type": role_type,
                "matched_alias": matched_alias,
                "mentioned_role_name": mentioned_role_name,
                "confidence": round(confidence, 3),
                "reason": reason,
            }
        )
    return bindings


def _render_speaker_transcript(
    speaker_turns: list[dict[str, Any]],
    speaker_role_map: list[dict[str, Any]],
) -> str:
    role_lookup = {str(item.get("speaker_id") or "").strip(): item for item in speaker_role_map if isinstance(item, dict)}
    lines: list[str] = []
    for item in speaker_turns:
        speaker_id = str(item.get("speaker_id") or "").strip()
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        binding = role_lookup.get(speaker_id, {})
        speaker_name = str(binding.get("role_name") or item.get("speaker_name") or speaker_id).strip() or speaker_id
        lines.append(f"{speaker_name}：{text}")
    return "\n".join(lines).strip()


def _fallback_high_energy_lines(context: dict[str, Any]) -> list[dict[str, Any]]:
    audio_text = context["mediaText"]["audio"]
    transcript = str(
        audio_text.get("speakerTranscript")
        or audio_text.get("correctedTranscript")
        or audio_text.get("transcript")
        or ""
    )
    speaker_turns = audio_text.get("speakerTurns") if isinstance(audio_text.get("speakerTurns"), list) else []
    if speaker_turns:
        result: list[dict[str, Any]] = []
        for item in speaker_turns:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if 5 <= len(text) <= 42:
                label = str(item.get("speaker_name") or item.get("speaker_id") or "").strip() or "说话人"
                result.append(
                    {
                        "time_ms": _safe_int(item.get("start_ms"), 0, minimum=0),
                        "text": f"{label}：{text}",
                        "reason": "从说话人分段中抽取的高能台词",
                    }
                )
            if len(result) >= 3:
                break
        if result:
            return result
    chunks = _split_dialogue(transcript)
    result = []
    for chunk in chunks:
        if 5 <= len(chunk) <= 42:
            result.append({"time_ms": 0, "text": chunk, "reason": "从 ASR transcript 中抽取的高能台词"})
        if len(result) >= 3:
            break
    if result:
        return result
    summary = str(context["episode"].get("summary") or "")
    return [{"time_ms": 0, "text": summary, "reason": "ASR 不足时使用剧集摘要兜底"}] if summary else []


def _split_dialogue(text: str) -> list[str]:
    cleaned = text.replace("\r", " ").replace("\n", " ")
    chunks: list[str] = []
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
