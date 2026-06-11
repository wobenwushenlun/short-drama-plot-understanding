from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class OCRService:
    def analyze_frames(self, frame_items: list[dict[str, Any]]) -> dict[str, Any]:
        sidecar_cues = self._read_sidecar_cues(frame_items)
        if sidecar_cues:
            return {"status": "ok", "source": "sidecar_ocr", "cues": sidecar_cues}
        if not _ocr_enabled():
            return {"status": "ocr_disabled", "source": "none", "cues": []}
        rapidocr = self._load_rapidocr()
        if rapidocr is None:
            return {"status": "rapidocr_missing", "source": "none", "cues": []}

        cues: list[dict[str, Any]] = []
        for item in frame_items:
            image_path = Path(str(item.get("path") or ""))
            if not image_path.exists():
                continue
            try:
                result, _ = rapidocr(str(image_path))
            except Exception:
                continue
            text_parts: list[str] = []
            if isinstance(result, list):
                for record in result:
                    if not isinstance(record, (list, tuple)) or len(record) < 2:
                        continue
                    text = str(record[1] or "").strip()
                    if text:
                        text_parts.append(text)
            text = " ".join(text_parts).strip()
            if text:
                cues.append(
                    {
                        "time_ms": int(item.get("timeMs") or 0),
                        "text": text,
                        "cue_type": "onscreen_text",
                        "reason": "RapidOCR 从关键帧识别出的屏幕文字",
                    }
                )
        return {"status": "ok" if cues else "ocr_empty", "source": "rapidocr", "cues": cues}

    def _load_rapidocr(self):
        try:
            from rapidocr_onnxruntime import RapidOCR

            return RapidOCR()
        except Exception:
            pass
        try:
            from rapidocr import RapidOCR

            return RapidOCR()
        except Exception:
            return None

    def _read_sidecar_cues(self, frame_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cues: list[dict[str, Any]] = []
        for item in frame_items:
            image_path = Path(str(item.get("path") or ""))
            if not image_path.name:
                continue
            for candidate in _sidecar_candidates(image_path):
                if not candidate.exists():
                    continue
                cues.extend(_read_ocr_sidecar(candidate, int(item.get("timeMs") or 0)))
        return cues


def get_ocr_service() -> OCRService:
    return OCRService()


def _ocr_enabled() -> bool:
    return os.environ.get("AIGC_OCR_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _sidecar_candidates(image_path: Path) -> list[Path]:
    episode_id = image_path.parent.name
    repo_root = Path(__file__).resolve().parents[2]
    return [
        image_path.with_suffix(".txt"),
        image_path.with_suffix(".ocr.txt"),
        repo_root / "tmp" / "video_understanding_ocr" / episode_id / f"{image_path.stem}.txt",
        repo_root / "tmp" / "video_understanding_ocr" / episode_id / "ocr.json",
    ]


def _read_ocr_sidecar(path: Path, fallback_time_ms: int) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        try:
            parsed = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError:
            return []
        raw_items = parsed.get("cues") if isinstance(parsed, dict) else parsed
        if not isinstance(raw_items, list):
            return []
        cues: list[dict[str, Any]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            cues.append(
                {
                    "time_ms": int(item.get("time_ms") or item.get("timeMs") or fallback_time_ms),
                    "text": text,
                    "cue_type": str(item.get("cue_type") or "onscreen_text"),
                    "reason": str(item.get("reason") or "OCR 旁路证据"),
                }
            )
        return cues
    text = " ".join(line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip())
    if not text:
        return []
    return [
        {
            "time_ms": fallback_time_ms,
            "text": text,
            "cue_type": "onscreen_text",
            "reason": "OCR 旁路文本",
        }
    ]
