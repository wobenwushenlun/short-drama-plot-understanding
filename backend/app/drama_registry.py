from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BUNDLED_DRAMA_CONFIG_DIR = Path(__file__).resolve().parent / "dramas"
DRAMA_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_][a-zA-Z0-9_-]*$")


@dataclass(frozen=True)
class DramaConfig:
    drama_id: str
    title: str
    content_root: Path
    episode_count: int
    episode_id_prefix: str
    episode_file_pattern: str = "第{episode_no}集.mp4"
    episode_number_start: int = 1
    cover: str = ""
    cover_style: str = ""
    cover_badge: str = ""
    cover_hook: str = ""
    cover_palette: dict[str, str] | None = None
    cover_layers: dict[str, str] | None = None
    description: str = ""
    interaction_hint: str = ""
    episode_summaries: dict[int, str] | None = None
    episode_durations_ms: dict[int, int] | None = None
    tags: tuple[str, ...] = ()
    danmaku_evidence_path: Path | None = None

    @property
    def episode_ids(self) -> list[str]:
        return [f"{self.episode_id_prefix}{episode_no:02d}" for episode_no in range(1, self.episode_count + 1)]

    @property
    def latest_episode_no(self) -> int:
        return self.source_episode_no(self.episode_count)

    def contains_episode(self, episode_id: str) -> bool:
        return episode_id in set(self.episode_ids)

    def source_episode_no(self, logical_episode_no: int) -> int:
        return self.episode_number_start + logical_episode_no - 1

    def episode_summary_for(self, logical_episode_no: int) -> str:
        summaries = self.episode_summaries or {}
        return summaries.get(self.source_episode_no(logical_episode_no)) or summaries.get(logical_episode_no) or ""

    def episode_duration_for(self, logical_episode_no: int) -> int:
        durations = self.episode_durations_ms or {}
        return durations.get(self.source_episode_no(logical_episode_no)) or durations.get(logical_episode_no) or 0


@dataclass(frozen=True)
class DramaRegistry:
    configs: dict[str, DramaConfig]
    load_errors: list[dict[str, str]]

    def list_all(self) -> list[DramaConfig]:
        ordered_ids = sorted(self.configs, key=lambda drama_id: (drama_id != "tainai3", drama_id))
        return [self.configs[drama_id] for drama_id in ordered_ids]

    def get(self, drama_id: str) -> DramaConfig:
        config = self.configs.get(drama_id)
        if config is None:
            raise KeyError(drama_id)
        return config

    def find_by_episode_id(self, episode_id: str) -> DramaConfig:
        for config in self.configs.values():
            if config.contains_episode(episode_id):
                return config
        raise KeyError(episode_id)


def load_drama_registry() -> DramaRegistry:
    configs: dict[str, DramaConfig] = {}
    errors: list[dict[str, str]] = []
    for config_path in _iter_config_paths():
        try:
            config = _load_config(config_path)
        except ValueError as exc:
            errors.append({"path": str(config_path), "error": str(exc)})
            continue
        configs[config.drama_id] = config
    return DramaRegistry(configs=configs, load_errors=errors)


def _iter_config_paths() -> list[Path]:
    paths: list[Path] = []
    for directory in _config_dirs():
        if not directory.exists():
            continue
        paths.extend(sorted(directory.glob("*.json")))
    return paths


def _config_dirs() -> list[Path]:
    dirs = [BUNDLED_DRAMA_CONFIG_DIR]
    extra_dir = os.environ.get("AIGC_DRAMA_CONFIG_DIR", "").strip()
    if extra_dir:
        dirs.append(Path(extra_dir))
    return dirs


def _load_config(path: Path) -> DramaConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid json: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("config must be an object")

    drama_id = _required_text(raw, "dramaId")
    if not DRAMA_ID_PATTERN.match(drama_id):
        raise ValueError("dramaId must use letters, numbers, dash or underscore")
    title = _required_text(raw, "title")
    content_root = Path(_required_text(raw, "contentRoot"))
    episode_count = _required_int(raw, "episodeCount")
    if episode_count <= 0:
        raise ValueError("episodeCount must be positive")
    episode_number_start = _optional_positive_int(raw, "episodeNumberStart", default=1)
    episode_id_prefix = _required_text(raw, "episodeIdPrefix")
    tags = tuple(str(item).strip() for item in raw.get("tags", []) if str(item).strip())
    danmaku_path_text = str(raw.get("danmakuEvidencePath") or "").strip()
    return DramaConfig(
        drama_id=drama_id,
        title=title,
        content_root=content_root,
        episode_count=episode_count,
        episode_id_prefix=episode_id_prefix,
        episode_number_start=episode_number_start,
        episode_file_pattern=str(raw.get("episodeFilePattern") or "第{episode_no}集.mp4").strip()
        or "第{episode_no}集.mp4",
        cover=str(raw.get("cover") or "").strip(),
        cover_style=str(raw.get("coverStyle") or "").strip(),
        cover_badge=str(raw.get("coverBadge") or "").strip(),
        cover_hook=str(raw.get("coverHook") or "").strip(),
        cover_palette=_parse_cover_palette(raw.get("coverPalette")),
        cover_layers=_parse_text_map(raw.get("coverLayers")),
        description=str(raw.get("description") or "").strip(),
        interaction_hint=str(raw.get("interactionHint") or "").strip(),
        episode_summaries=_parse_episode_summaries(raw.get("episodeSummaries"), episode_number_start),
        episode_durations_ms=_parse_episode_durations(raw.get("episodeDurationsMs"), episode_number_start),
        tags=tags,
        danmaku_evidence_path=Path(danmaku_path_text) if danmaku_path_text else None,
    )


def _required_text(raw: dict[str, Any], key: str) -> str:
    value = str(raw.get(key) or "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    return value


def _required_int(raw: dict[str, Any], key: str) -> int:
    try:
        return int(raw.get(key))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer") from exc


def _optional_positive_int(raw: dict[str, Any], key: str, *, default: int) -> int:
    if raw.get(key) in (None, ""):
        return default
    try:
        value = int(raw.get(key))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{key} must be positive")
    return value


def _parse_cover_palette(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    palette = {
        key: str(value.get(key) or "").strip()
        for key in ("primary", "secondary", "accent")
        if str(value.get(key) or "").strip()
    }
    return palette or None


def _parse_text_map(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    result = {
        str(key).strip(): str(raw_value).strip()
        for key, raw_value in value.items()
        if str(key).strip()
    }
    return result or None


def _parse_episode_summaries(value: Any, episode_number_start: int) -> dict[int, str] | None:
    summaries: dict[int, str] = {}
    if isinstance(value, dict):
        for raw_episode_no, raw_summary in value.items():
            try:
                episode_no = int(raw_episode_no)
            except (TypeError, ValueError):
                continue
            summary = str(raw_summary or "").strip()
            if summary:
                summaries[episode_no] = summary
    elif isinstance(value, list):
        for index, item in enumerate(value, start=1):
            if isinstance(item, dict):
                raw_episode_no = item.get("episodeNo") or item.get("episode_no")
                try:
                    episode_no = int(raw_episode_no) if raw_episode_no not in (None, "") else episode_number_start + index - 1
                except (TypeError, ValueError):
                    episode_no = episode_number_start + index - 1
                summary = str(item.get("summary") or "").strip()
            else:
                episode_no = episode_number_start + index - 1
                summary = str(item or "").strip()
            if summary:
                summaries[episode_no] = summary
    return summaries or None


def _parse_episode_durations(value: Any, episode_number_start: int) -> dict[int, int] | None:
    durations: dict[int, int] = {}
    if isinstance(value, dict):
        for raw_episode_no, raw_duration in value.items():
            try:
                episode_no = int(raw_episode_no)
                duration_ms = int(raw_duration)
            except (TypeError, ValueError):
                continue
            if duration_ms > 0:
                durations[episode_no] = duration_ms
    elif isinstance(value, list):
        for index, raw_duration in enumerate(value, start=1):
            try:
                duration_ms = int(raw_duration)
            except (TypeError, ValueError):
                continue
            if duration_ms > 0:
                durations[episode_number_start + index - 1] = duration_ms
    return durations or None
