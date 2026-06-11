from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.content_catalog import (
    get_episode_file_path,
    get_episode_seeds,
    get_hls_root,
)
from backend.app.video_understanding_service import _find_ffmpeg_tool


def main() -> int:
    parser = argparse.ArgumentParser(description="为短剧剧集预处理 HLS 分片")
    parser.add_argument("--episode-id", default="", help="只处理指定 episodeId，默认处理前 5 集")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的 HLS 输出")
    args = parser.parse_args()

    episode_ids = [args.episode_id] if args.episode_id else [item["episode_id"] for item in get_episode_seeds()]
    ffmpeg = _find_ffmpeg_tool("ffmpeg")
    if ffmpeg is None:
        raise SystemExit("未找到 ffmpeg，请先安装或设置 AIGC_FFMPEG_DIR")

    hls_root = get_hls_root()
    hls_root.mkdir(parents=True, exist_ok=True)
    for episode_id in episode_ids:
        source = get_episode_file_path(episode_id)
        if source is None or not source.exists():
            print(f"SKIP {episode_id}: 视频文件不存在")
            continue
        output_dir = hls_root / episode_id
        index_path = output_dir / "index.m3u8"
        if index_path.exists() and not args.force:
            print(f"OK {episode_id}: 已存在 {index_path}")
            continue
        if output_dir.exists() and args.force:
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        segment_pattern = output_dir / "segment_%03d.ts"
        command = [
            str(ffmpeg),
            "-y",
            "-i",
            str(source),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-hls_time",
            "4",
            "-hls_playlist_type",
            "vod",
            "-hls_segment_filename",
            str(segment_pattern),
            str(index_path),
        ]
        completed = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
        if completed.returncode != 0:
            print(f"FAIL {episode_id}: {completed.stderr[-300:]}")
            continue
        print(f"OK {episode_id}: {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
