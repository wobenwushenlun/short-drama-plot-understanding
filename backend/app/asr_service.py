from __future__ import annotations

import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_ASR_CONFIG_PATH = Path("asr_config.txt")
DEFAULT_ASR_API_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash"
DEFAULT_ASR_RESOURCE_ID = "volc.bigasr.auc_turbo"
DEFAULT_ASR_TIMEOUT_SECONDS = 45
DEFAULT_LOCAL_ASR_TIMEOUT_SECONDS = 300


@dataclass(frozen=True)
class ASRCredentials:
    api_key: str = ""
    app_id: str = ""
    access_key: str = ""
    resource_id: str = DEFAULT_ASR_RESOURCE_ID
    api_url: str = DEFAULT_ASR_API_URL
    local_engine: str = ""
    whisper_cpp_exe: str = ""
    whisper_cpp_model: str = ""
    local_command: str = ""
    source_path: str = ""


class ASRService:
    def __init__(self, credentials: ASRCredentials | None = None):
        self.credentials = credentials or load_asr_credentials()

    def recognize_file(self, audio_path: Path) -> dict[str, Any]:
        if not audio_path.exists():
            return _status("audio_missing", "音频文件不存在")
        sidecar_result = self._recognize_from_sidecar(audio_path)
        if sidecar_result is not None:
            return sidecar_result
        local_result = self._recognize_from_local_engine(audio_path)
        if local_result is not None:
            return local_result
        if not _asr_enabled():
            return _status("asr_disabled", "ASR 默认关闭，填写 key 后设置 AIGC_ASR_ENABLED=1 可启用")
        if not self.credentials.api_key and not (self.credentials.app_id and self.credentials.access_key):
            return _status("asr_key_missing", "未配置豆包语音 ASR key")

        start_ms = int(time.time() * 1000)
        try:
            payload = {
                "user": {
                    "uid": self.credentials.api_key or self.credentials.app_id or "aigc-shortplay",
                },
                "audio": {
                    "data": base64.b64encode(audio_path.read_bytes()).decode("ascii"),
                },
                "request": {
                    "model_name": "bigmodel",
                    "enable_itn": True,
                    "enable_punc": True,
                },
            }
            request = urllib.request.Request(
                self.credentials.api_url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=self._headers(),
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=DEFAULT_ASR_TIMEOUT_SECONDS) as response:
                body = json.loads(response.read().decode("utf-8"))
            result = body.get("result") if isinstance(body, dict) else {}
            text = str((result or {}).get("text") or "").strip()
            utterances = (result or {}).get("utterances") if isinstance(result, dict) else []
            return {
                "status": "ok" if text else "empty_result",
                "transcript": text,
                "source": "volc.bigasr.auc_turbo",
                "utterances": _normalize_utterances(utterances),
                "latency_ms": int(time.time() * 1000) - start_ms,
                "message": "",
            }
        except urllib.error.HTTPError as exc:
            return _status("asr_http_error", f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='ignore')[:200]}")
        except Exception as exc:  # pragma: no cover - 真实网络由运行环境决定
            return _status("asr_error", str(exc))

    def _recognize_from_sidecar(self, audio_path: Path) -> dict[str, Any] | None:
        for candidate in _sidecar_transcript_candidates(audio_path):
            if not candidate.exists():
                continue
            transcript = _read_transcript_file(candidate)
            if not transcript:
                continue
            return {
                "status": "ok",
                "transcript": transcript,
                "source": f"sidecar:{candidate.name}",
                "utterances": [],
                "latency_ms": 0,
                "message": "已读取本地旁路转写文件",
            }
        return None

    def _recognize_from_local_engine(self, audio_path: Path) -> dict[str, Any] | None:
        engine = self.credentials.local_engine.strip().lower()
        if engine in {"", "none", "disabled"}:
            return None
        if engine == "whisper_cpp":
            return self._recognize_with_whisper_cpp(audio_path)
        if engine == "command":
            return self._recognize_with_local_command(audio_path)
        return _status("local_asr_engine_unknown", f"未知本地 ASR 引擎：{engine}")

    def _recognize_with_whisper_cpp(self, audio_path: Path) -> dict[str, Any]:
        exe = Path(self.credentials.whisper_cpp_exe)
        model = Path(self.credentials.whisper_cpp_model)
        if not exe.exists() or not model.exists():
            return _status("local_asr_missing", "whisper.cpp 可执行文件或模型不存在")
        output_base = audio_path.with_suffix("")
        command = [
            str(exe),
            "-m",
            str(model),
            "-f",
            str(audio_path),
            "-l",
            "zh",
            "-mc",
            "0",
            "-sns",
            "-nt",
            "-nf",
            "-otxt",
            "-of",
            str(output_base),
        ]
        start_ms = int(time.time() * 1000)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=DEFAULT_LOCAL_ASR_TIMEOUT_SECONDS,
                check=False,
            )
            output_path = output_base.with_suffix(".txt")
            transcript = _read_transcript_file(output_path)
            if transcript:
                return {
                    "status": "ok",
                    "transcript": transcript,
                    "source": "whisper.cpp",
                    "utterances": [],
                    "latency_ms": int(time.time() * 1000) - start_ms,
                    "message": "",
                }
            message = (completed.stderr or completed.stdout or "whisper.cpp 未生成文本").strip()[:200]
            return _status("local_asr_empty", message)
        except Exception as exc:  # pragma: no cover - 本地命令依赖机器环境
            return _status("local_asr_error", str(exc))

    def _recognize_with_local_command(self, audio_path: Path) -> dict[str, Any]:
        template = self.credentials.local_command.strip()
        if not template:
            return _status("local_asr_missing", "未配置本地 ASR 命令")
        output_path = audio_path.with_name("local_asr_transcript.txt")
        command = template.replace("{audio}", str(audio_path)).replace("{output}", str(output_path))
        start_ms = int(time.time() * 1000)
        try:
            completed = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=DEFAULT_LOCAL_ASR_TIMEOUT_SECONDS,
                check=False,
            )
            transcript = _read_transcript_file(output_path) or (completed.stdout or "").strip()
            if transcript:
                return {
                    "status": "ok",
                    "transcript": transcript,
                    "source": "local_command",
                    "utterances": [],
                    "latency_ms": int(time.time() * 1000) - start_ms,
                    "message": "",
                }
            return _status("local_asr_empty", (completed.stderr or "本地 ASR 命令未生成文本").strip()[:200])
        except Exception as exc:  # pragma: no cover - 本地命令依赖机器环境
            return _status("local_asr_error", str(exc))

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "X-Api-Resource-Id": self.credentials.resource_id or DEFAULT_ASR_RESOURCE_ID,
            "X-Api-Request-Id": str(uuid4()),
            "X-Api-Sequence": "-1",
        }
        if self.credentials.api_key:
            headers["X-Api-Key"] = self.credentials.api_key
        else:
            headers["X-Api-App-Key"] = self.credentials.app_id
            headers["X-Api-Access-Key"] = self.credentials.access_key
        return headers


def load_asr_credentials(config_path: Path | None = None) -> ASRCredentials:
    path = config_path or DEFAULT_ASR_CONFIG_PATH
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            normalized = line.replace("：", ":")
            if ":" not in normalized:
                continue
            key, value = normalized.split(":", 1)
            values[key.strip().upper()] = value.strip()
    return ASRCredentials(
        api_key=os.environ.get("AIGC_ASR_API_KEY", "").strip() or values.get("APIKEY", ""),
        app_id=os.environ.get("AIGC_ASR_APP_ID", "").strip() or values.get("APPID", ""),
        access_key=os.environ.get("AIGC_ASR_ACCESS_KEY", "").strip() or values.get("ACCESSKEY", ""),
        resource_id=os.environ.get("AIGC_ASR_RESOURCE_ID", "").strip() or values.get("RESOURCE_ID", DEFAULT_ASR_RESOURCE_ID),
        api_url=os.environ.get("AIGC_ASR_API_URL", "").strip() or values.get("API_URL", DEFAULT_ASR_API_URL),
        local_engine=os.environ.get("AIGC_LOCAL_ASR_ENGINE", "").strip() or values.get("LOCAL_ENGINE", ""),
        whisper_cpp_exe=os.environ.get("AIGC_WHISPER_CPP_EXE", "").strip() or values.get("WHISPER_CPP_EXE", ""),
        whisper_cpp_model=os.environ.get("AIGC_WHISPER_CPP_MODEL", "").strip() or values.get("WHISPER_CPP_MODEL", ""),
        local_command=os.environ.get("AIGC_LOCAL_ASR_COMMAND", "").strip() or values.get("LOCAL_COMMAND", ""),
        source_path=str(path) if path.exists() else "",
    )


def get_asr_service() -> ASRService:
    return ASRService()


def _asr_enabled() -> bool:
    return os.environ.get("AIGC_ASR_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _status(status: str, message: str) -> dict[str, Any]:
    return {
        "status": status,
        "transcript": "",
        "source": "none",
        "utterances": [],
        "latency_ms": 0,
        "message": message,
    }


def _normalize_utterances(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    utterances: list[dict[str, Any]] = []
    for item in value[:20]:
        if not isinstance(item, dict):
            continue
        speaker_id = _normalize_speaker_value(
            item.get("speaker_id")
            or item.get("speakerId")
            or item.get("speaker")
            or item.get("spk")
        )
        speaker_label = _normalize_speaker_value(
            item.get("speaker_name")
            or item.get("speakerName")
            or item.get("role")
            or item.get("role_name")
        )
        utterances.append(
            {
                "start_ms": int(item.get("start_time") or 0),
                "end_ms": int(item.get("end_time") or 0),
                "text": str(item.get("text") or "").strip(),
                "speaker_id": speaker_id,
                "speaker_label": speaker_label,
            }
        )
    return utterances


def _normalize_speaker_value(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"speaker_{int(value)}"
    text = str(value or "").strip()
    return text


def _sidecar_transcript_candidates(audio_path: Path) -> list[Path]:
    episode_id = audio_path.parent.name
    repo_root = Path(__file__).resolve().parents[2]
    return [
        audio_path.with_name("transcript.txt"),
        audio_path.with_name("transcript.srt"),
        audio_path.with_name("transcript.vtt"),
        audio_path.with_name("local_asr_transcript.txt"),
        repo_root / "tmp" / "video_understanding_transcripts" / episode_id / "transcript.txt",
        repo_root / "tmp" / "video_understanding_transcripts" / f"{episode_id}.txt",
        repo_root / "assets" / "transcripts" / f"{episode_id}.txt",
        repo_root / "assets" / "transcripts" / f"{episode_id}.srt",
    ]


def _read_transcript_file(path: Path) -> str:
    if not path.exists():
        return ""
    if path.suffix.lower() == ".json":
        try:
            parsed = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            return ""
        if isinstance(parsed, dict):
            return str(parsed.get("transcript") or parsed.get("text") or "").strip()
        return ""
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.isdigit() or "-->" in line or line.upper() == "WEBVTT":
            continue
        lines.append(line)
    return " ".join(lines).strip()
