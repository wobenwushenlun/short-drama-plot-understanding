from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.drama_registry import BUNDLED_DRAMA_CONFIG_DIR, DRAMA_ID_PATTERN


def main() -> int:
    parser = argparse.ArgumentParser(description="生成新短剧注册表配置，便于后续接入更多素材")
    parser.add_argument("--registry-dir", default=str(BUNDLED_DRAMA_CONFIG_DIR), help="注册表 JSON 输出目录")
    parser.add_argument("--drama-id", required=True, help="短剧唯一 ID，只允许字母、数字、下划线和短横线")
    parser.add_argument("--title", required=True, help="短剧标题")
    parser.add_argument("--content-root", required=True, help="短剧素材根目录")
    parser.add_argument("--episode-count", required=True, type=int, help="剧集数量")
    parser.add_argument("--episode-id-prefix", required=True, help="分集 ID 前缀，例如 tainai3_ep")
    parser.add_argument("--episode-file-pattern", default="第{episode_no}集.mp4", help="分集文件名模板，支持 {episode_no}")
    parser.add_argument("--cover", default="", help="封面图片 URL 或本地路径")
    parser.add_argument("--cover-style", default="", help="封面风格说明")
    parser.add_argument("--cover-badge", default="", help="封面角标")
    parser.add_argument("--cover-hook", default="", help="封面钩子文案")
    parser.add_argument("--tags", default="", help="标签，使用逗号分隔")
    parser.add_argument("--danmaku-evidence-path", default="", help="已脱敏弹幕证据 JSON 路径")
    parser.add_argument("--force", action="store_true", help="覆盖已有同名配置")
    args = parser.parse_args()

    try:
        config = _build_config(args)
        output_path = _write_config(Path(args.registry_dir), config, force=args.force)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(f"OK {config['dramaId']}: {output_path}")
    return 0


def _build_config(args: argparse.Namespace) -> dict[str, object]:
    drama_id = str(args.drama_id).strip()
    if not DRAMA_ID_PATTERN.match(drama_id):
        raise ValueError("dramaId must use letters, numbers, dash or underscore")
    if not str(args.title).strip():
        raise ValueError("title is required")
    if not str(args.content_root).strip():
        raise ValueError("contentRoot is required")
    if int(args.episode_count) <= 0:
        raise ValueError("episodeCount must be positive")
    if not str(args.episode_id_prefix).strip():
        raise ValueError("episodeIdPrefix is required")

    config: dict[str, object] = {
        "dramaId": drama_id,
        "title": str(args.title).strip(),
        "contentRoot": str(Path(str(args.content_root).strip())),
        "episodeCount": int(args.episode_count),
        "episodeIdPrefix": str(args.episode_id_prefix).strip(),
        "episodeFilePattern": str(args.episode_file_pattern or "第{episode_no}集.mp4").strip()
        or "第{episode_no}集.mp4",
        "cover": str(args.cover or "").strip(),
        "tags": _parse_tags(str(args.tags or "")),
    }

    optional_fields = {
        "coverStyle": args.cover_style,
        "coverBadge": args.cover_badge,
        "coverHook": args.cover_hook,
        "danmakuEvidencePath": args.danmaku_evidence_path,
    }
    for key, value in optional_fields.items():
        text = str(value or "").strip()
        if text:
            config[key] = text
    return config


def _parse_tags(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _write_config(registry_dir: Path, config: dict[str, object], *, force: bool) -> Path:
    registry_dir.mkdir(parents=True, exist_ok=True)
    drama_id = str(config["dramaId"])
    output_path = registry_dir / f"{drama_id}.json"
    if output_path.exists() and not force:
        raise ValueError(f"{output_path} already exists; use --force to overwrite")
    output_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


if __name__ == "__main__":
    raise SystemExit(main())
