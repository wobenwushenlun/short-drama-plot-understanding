from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from analyze_danmaku_xlsx import (
    first_sheet_path,
    format_seconds,
    infer_numeric_offset_scale,
    iter_sheet_rows,
    normalize_text,
    parse_int,
    parse_offset_seconds,
    percentile,
    read_shared_strings,
    resolve_column_index,
    safe_ratio,
)


TARGET_DRAMA = "十八岁太奶奶驾到，重整家族荣耀第三部"

EMOTION_LEXICON = {
    "爽感/打脸": ("爽", "解气", "打脸", "反杀", "逆袭", "霸气", "牛", "燃", "过瘾"),
    "愤怒/厌恶": ("气", "恶心", "坏", "讨厌", "无语", "离谱", "太过分", "坏人"),
    "心疼/共情": ("心疼", "可怜", "哭", "泪", "难受", "委屈", "惨"),
    "笑点/轻松": ("哈哈", "笑死", "笑", "233", "hhh"),
    "疑问/悬念": ("?", "？", "怎么", "为什么", "谁", "啥", "真相", "不是"),
    "期待/催更": ("期待", "下集", "更新", "赶紧", "快点", "想看"),
    "震惊/反转": ("啊", "卧槽", "震惊", "居然", "反转", "没想到", "？！", "!?"),
}

STOP_TERMS = {
    "这个",
    "那个",
    "就是",
    "什么",
    "不是",
    "真的",
    "怎么",
    "这么",
    "一下",
    "一个",
    "没有",
    "还是",
    "感觉",
    "现在",
    "可以",
    "哈哈哈",
}


@dataclass
class Event:
    episode: int
    group: str
    offset_seconds: float
    likes: int
    content: str


def main() -> None:
    parser = argparse.ArgumentParser(description="分析目标短剧前 5 集弹幕热区，并抽取对应视频帧。")
    parser.add_argument("--xlsx", type=Path, default=None)
    parser.add_argument("--target-drama", default=TARGET_DRAMA)
    parser.add_argument("--video-dir", type=Path, default=Path(TARGET_DRAMA))
    parser.add_argument("--episode-count", type=int, default=5)
    parser.add_argument("--bucket-seconds", type=int, default=10)
    parser.add_argument("--top-windows", type=int, default=5)
    parser.add_argument("--extract-windows", type=int, default=2)
    parser.add_argument("--min-gap-seconds", type=int, default=20)
    parser.add_argument("--ffmpeg", type=Path, default=Path("tools/ffmpeg/bin/ffmpeg.exe"))
    parser.add_argument("--out", type=Path, default=Path("tmp/tainai3_ep1_5_danmaku_scene_report.md"))
    parser.add_argument("--json-out", type=Path, default=Path("tmp/tainai3_ep1_5_danmaku_scene_summary.json"))
    parser.add_argument("--frames-dir", type=Path, default=Path("tmp/tainai3_ep1_5_scene_frames"))
    args = parser.parse_args()

    xlsx_path = args.xlsx or find_default_xlsx()
    events, parse_info = load_target_events(xlsx_path, args.target_drama, args.episode_count)
    summary = analyze_events(
        events=events,
        target_drama=args.target_drama,
        parse_info=parse_info,
        bucket_seconds=args.bucket_seconds,
        top_windows=args.top_windows,
        min_gap_seconds=args.min_gap_seconds,
    )
    extract_scene_frames(
        summary=summary,
        video_dir=args.video_dir,
        frames_dir=args.frames_dir,
        ffmpeg=args.ffmpeg,
        extract_windows=args.extract_windows,
        bucket_seconds=args.bucket_seconds,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_report(summary), encoding="utf-8")
    args.json_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report={args.out}")
    print(f"json={args.json_out}")
    print(f"contactSheet={summary.get('contactSheet', '')}")


def find_default_xlsx() -> Path:
    candidates = [path for path in Path("assets").glob("*.xlsx") if not path.name.startswith("~$")]
    if not candidates:
        raise FileNotFoundError("assets 下没有可用 xlsx 文件")
    return max(candidates, key=lambda path: path.stat().st_size)


def load_target_events(path: Path, target_drama: str, episode_count: int) -> tuple[list[Event], dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = read_shared_strings(archive)
        sheet_path = first_sheet_path(archive)
        raw_rows = iter_sheet_rows(archive, sheet_path, shared_strings)
    if not raw_rows:
        return [], {"xlsx": str(path), "numericScale": 1.0, "numericScaleLabel": "unknown"}

    headers = [normalize_text(value) for value in raw_rows[0]]
    index = resolve_column_index(headers)
    matched_rows: list[list[str]] = []
    raw_offsets: list[Any] = []
    for raw in raw_rows[1:]:
        row = raw + [""] * max(0, len(headers) - len(raw))
        if normalize_text(row[index["drama"]]) != target_drama:
            continue
        episode = parse_episode_number(row[index["group"]])
        if episode is None or episode < 1 or episode > episode_count:
            continue
        matched_rows.append(row)
        raw_offsets.append(row[index["offset"]])

    numeric_scale, numeric_scale_label = infer_numeric_offset_scale(raw_offsets)
    events: list[Event] = []
    for row in matched_rows:
        offset = parse_offset_seconds(row[index["offset"]], numeric_scale=numeric_scale)
        episode = parse_episode_number(row[index["group"]])
        if offset is None or episode is None:
            continue
        events.append(
            Event(
                episode=episode,
                group=normalize_text(row[index["group"]]),
                offset_seconds=offset,
                likes=parse_int(row[index["likes"]]),
                content=normalize_text(row[index["content"]]),
            )
        )
    return events, {
        "xlsx": str(path),
        "numericScale": numeric_scale,
        "numericScaleLabel": numeric_scale_label,
        "matchedRows": len(events),
    }


def parse_episode_number(value: Any) -> int | None:
    text = normalize_text(value)
    match = re.search(r"第\s*(\d+)\s*集", text)
    return int(match.group(1)) if match else None


def analyze_events(
    *,
    events: list[Event],
    target_drama: str,
    parse_info: dict[str, Any],
    bucket_seconds: int,
    top_windows: int,
    min_gap_seconds: int,
) -> dict[str, Any]:
    by_episode: dict[int, list[Event]] = defaultdict(list)
    for event in events:
        by_episode[event.episode].append(event)

    episodes = []
    for episode in sorted(by_episode):
        episode_events = by_episode[episode]
        buckets = build_episode_buckets(episode_events, bucket_seconds)
        top = select_hot_windows(buckets, top_windows, min_gap_seconds)
        episodes.append(
            {
                "episode": episode,
                "group": episode_events[0].group if episode_events else f"第{episode}集",
                "eventCount": len(episode_events),
                "likeSum": sum(event.likes for event in episode_events),
                "zeroLikeRate": safe_ratio(sum(1 for event in episode_events if event.likes == 0), len(episode_events)),
                "topWindows": top,
            }
        )
    return {
        "privacy": {
            "rawContentExported": False,
            "rawRowsExported": False,
            "wordAggregationOnly": True,
        },
        "targetDrama": target_drama,
        "timeParsing": parse_info,
        "bucketSeconds": bucket_seconds,
        "episodes": episodes,
    }


def build_episode_buckets(events: list[Event], bucket_seconds: int) -> dict[int, dict[str, Any]]:
    buckets: dict[int, dict[str, Any]] = defaultdict(lambda: {"events": [], "count": 0, "likes": 0})
    for event in events:
        start = int(event.offset_seconds // bucket_seconds) * bucket_seconds
        buckets[start]["events"].append(event)
        buckets[start]["count"] += 1
        buckets[start]["likes"] += event.likes

    max_count = max((bucket["count"] for bucket in buckets.values()), default=1) or 1
    max_likes = max((bucket["likes"] for bucket in buckets.values()), default=1) or 1
    result = {}
    for start, bucket in buckets.items():
        items = bucket["events"]
        score = 0.6 * bucket["count"] / max_count + 0.4 * bucket["likes"] / max_likes
        result[start] = {
            "startSeconds": start,
            "endSeconds": start + bucket_seconds,
            "timeRange": f"{format_seconds(start)}-{format_seconds(start + bucket_seconds)}",
            "count": bucket["count"],
            "likeSum": bucket["likes"],
            "score": round(score, 4),
            "terms": top_terms(items, limit=8),
            "emotions": top_emotions(items, limit=3),
            "questionRate": safe_ratio(sum(1 for event in items if "?" in event.content or "？" in event.content), len(items)),
            "exclamationRate": safe_ratio(sum(1 for event in items if "!" in event.content or "！" in event.content), len(items)),
            "laughRate": safe_ratio(sum(1 for event in items if re.search(r"哈{2,}|笑|233|hhh+", event.content, re.IGNORECASE)), len(items)),
        }
    return result


def select_hot_windows(
    buckets: dict[int, dict[str, Any]],
    limit: int,
    min_gap_seconds: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for _, item in sorted(buckets.items(), key=lambda pair: pair[1]["score"], reverse=True):
        if any(abs(item["startSeconds"] - old["startSeconds"]) < min_gap_seconds for old in selected):
            continue
        selected.append({key: value for key, value in item.items() if key != "events"})
        if len(selected) >= limit:
            break
    return sorted(selected, key=lambda item: item["startSeconds"])


def top_terms(events: list[Event], limit: int) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for event in events:
        counter.update(extract_terms(event.content))

    selected: list[dict[str, Any]] = []
    for term, count in sorted(counter.items(), key=lambda pair: (pair[1], len(pair[0])), reverse=True):
        if term in STOP_TERMS or count < 2:
            continue
        if any(term in old["term"] and count <= old["count"] * 1.2 for old in selected):
            continue
        if any(old["term"] in term and old["count"] <= count * 1.2 for old in selected):
            selected = [old for old in selected if not (old["term"] in term and old["count"] <= count * 1.2)]
        selected.append({"term": term, "count": count})
        if len(selected) >= limit:
            break
    return selected


def extract_terms(text: str) -> list[str]:
    terms: list[str] = []
    compact = re.sub(r"\s+", "", text)
    for words in EMOTION_LEXICON.values():
        for word in words:
            if word in compact:
                terms.append(word)
    for token in re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", compact):
        if re.fullmatch(r"[A-Za-z0-9]+", token):
            if len(token) >= 2:
                terms.append(token.lower())
            continue
        if len(token) <= 4:
            terms.append(token)
        for size in (2, 3, 4):
            if len(token) < size:
                continue
            for index in range(0, len(token) - size + 1):
                gram = token[index : index + size]
                if gram not in STOP_TERMS:
                    terms.append(gram)
    return terms


def top_emotions(events: list[Event], limit: int) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for event in events:
        compact = re.sub(r"\s+", "", event.content)
        for label, words in EMOTION_LEXICON.items():
            if any(word in compact for word in words):
                counter[label] += 1
    total = len(events)
    return [
        {"emotion": label, "count": count, "rate": round(count / total, 4) if total else 0.0}
        for label, count in counter.most_common(limit)
    ]


def extract_scene_frames(
    *,
    summary: dict[str, Any],
    video_dir: Path,
    frames_dir: Path,
    ffmpeg: Path,
    extract_windows: int,
    bucket_seconds: int,
) -> None:
    frames_dir.mkdir(parents=True, exist_ok=True)
    if not ffmpeg.exists():
        summary["frameExtractionError"] = f"ffmpeg not found: {ffmpeg}"
        return

    extracted: list[dict[str, Any]] = []
    for episode in summary["episodes"]:
        video_path = video_dir / f"第{episode['episode']}集.mp4"
        if not video_path.exists():
            episode["frameError"] = f"video not found: {video_path}"
            continue
        windows = sorted(episode["topWindows"], key=lambda item: item["score"], reverse=True)[:extract_windows]
        for window in sorted(windows, key=lambda item: item["startSeconds"]):
            offsets = frame_offsets(window["startSeconds"], bucket_seconds)
            frame_paths: list[str] = []
            for index, second in enumerate(offsets, start=1):
                frame_path = frames_dir / f"ep{episode['episode']:02d}_{window['startSeconds']:04d}_{index}.jpg"
                run_ffmpeg_frame(ffmpeg, video_path, frame_path, second)
                if frame_path.exists():
                    frame_paths.append(str(frame_path))
            window["framePaths"] = frame_paths
            extracted.append(
                {
                    "episode": episode["episode"],
                    "timeRange": window["timeRange"],
                    "score": window["score"],
                    "count": window["count"],
                    "likeSum": window["likeSum"],
                    "framePaths": frame_paths,
                }
            )
    if extracted:
        sheet_path = frames_dir / "contact_sheet.jpg"
        make_contact_sheet(extracted, sheet_path)
        summary["contactSheet"] = str(sheet_path)
    summary["extractedFrames"] = extracted


def frame_offsets(start_seconds: int, bucket_seconds: int) -> list[float]:
    if bucket_seconds <= 4:
        return [start_seconds + max(bucket_seconds / 2, 0.5)]
    return [
        start_seconds + 1.5,
        start_seconds + bucket_seconds / 2,
        max(start_seconds + bucket_seconds - 1.5, start_seconds + 0.5),
    ]


def run_ffmpeg_frame(ffmpeg: Path, video_path: Path, frame_path: Path, second: float) -> None:
    command = [
        str(ffmpeg),
        "-y",
        "-ss",
        f"{second:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(frame_path),
    ]
    subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def make_contact_sheet(items: list[dict[str, Any]], out_path: Path) -> None:
    thumb_w, thumb_h = 420, 236
    label_h = 36
    columns = 3
    rows = sum(math.ceil(len(item["framePaths"]) / columns) for item in items)
    rows = max(rows, 1)
    sheet = Image.new("RGB", (thumb_w * columns, rows * (thumb_h + label_h)), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    row_offset = 0
    for item in items:
        label = f"EP{item['episode']:02d} {item['timeRange']} score={item['score']} count={item['count']} likes={item['likeSum']}"
        for index, frame in enumerate(item["framePaths"]):
            image = Image.open(frame).convert("RGB")
            image.thumbnail((thumb_w, thumb_h))
            x = (index % columns) * thumb_w
            y = row_offset * (thumb_h + label_h) + label_h
            sheet.paste(image, (x, y))
            draw.text((x + 4, y - label_h + 4), label, fill=(0, 0, 0), font=font)
        row_offset += math.ceil(max(len(item["framePaths"]), 1) / columns)
    sheet.save(out_path, quality=92)


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# 《十八岁太奶奶驾到，重整家族荣耀第三部》前 5 集弹幕热区分析",
        "",
        "## 隐私边界",
        "",
        f"- 原始弹幕内容导出：{summary['privacy']['rawContentExported']}",
        f"- 原始逐行记录导出：{summary['privacy']['rawRowsExported']}",
        f"- 仅输出聚合词频：{summary['privacy']['wordAggregationOnly']}",
        f"- 时间数值解析：{summary['timeParsing']['numericScaleLabel']}，scale={summary['timeParsing']['numericScale']}",
        "",
        "## 分集热区",
        "",
    ]
    for episode in summary["episodes"]:
        lines.extend(
            [
                f"### 第 {episode['episode']} 集",
                "",
                f"- 弹幕数：{episode['eventCount']}",
                f"- 点赞和：{episode['likeSum']}",
                f"- 0 赞占比：{episode['zeroLikeRate']}",
                "",
                "| 时间窗 | 热度分 | 弹幕数 | 点赞和 | 聚合高频词 | 主要情绪 |",
                "| --- | ---: | ---: | ---: | --- | --- |",
            ]
        )
        for window in episode["topWindows"]:
            terms = "、".join(f"{item['term']}({item['count']})" for item in window["terms"][:6]) or "-"
            emotions = "、".join(f"{item['emotion']}({item['rate']})" for item in window["emotions"]) or "-"
            lines.append(
                f"| {window['timeRange']} | {window['score']} | {window['count']} | "
                f"{window['likeSum']} | {terms} | {emotions} |"
            )
        lines.append("")
    if summary.get("contactSheet"):
        lines.extend(["## 抽帧索引", "", f"- contact sheet：{summary['contactSheet']}", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    main()
