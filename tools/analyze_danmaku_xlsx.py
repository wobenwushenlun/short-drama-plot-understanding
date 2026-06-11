from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_REL_PKG = "{http://schemas.openxmlformats.org/package/2006/relationships}"

REQUIRED_COLUMNS = {
    "drama": "剧名称",
    "group": "group_title",
    "offset": "发弹幕时刻相对于视频起始时间偏移量",
    "likes": "累计点赞数",
    "content": "弹幕内容",
}


@dataclass
class ParsedRow:
    drama: str
    group: str
    offset_seconds: float | None
    likes: int
    content_length: int
    has_question: bool
    has_exclamation: bool
    has_laugh: bool


@dataclass
class PendingRow:
    drama: str
    group: str
    raw_offset: Any
    likes: int
    content_length: int
    has_question: bool
    has_exclamation: bool
    has_laugh: bool


def main() -> None:
    parser = argparse.ArgumentParser(description="脱敏统计弹幕 xlsx，默认不输出原始弹幕内容。")
    parser.add_argument("--xlsx", type=Path, default=Path("assets/弹幕数据.xlsx"))
    parser.add_argument("--out", type=Path, default=Path("tmp/danmaku_analysis_report.md"))
    parser.add_argument("--json-out", type=Path, default=Path("tmp/danmaku_analysis_summary.json"))
    parser.add_argument("--bucket-seconds", type=int, default=10)
    parser.add_argument("--min-gap-seconds", type=int, default=25)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--privacy", choices=["strict", "named"], default="strict")
    args = parser.parse_args()

    rows, headers, offset_parse_info = load_danmaku_rows(args.xlsx)
    summary = analyze_rows(
        rows=rows,
        headers=headers,
        offset_parse_info=offset_parse_info,
        bucket_seconds=args.bucket_seconds,
        min_gap_seconds=args.min_gap_seconds,
        top_k=args.top_k,
        privacy=args.privacy,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_markdown(summary), encoding="utf-8")
    args.json_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report={args.out}")
    print(f"json={args.json_out}")


def load_danmaku_rows(path: Path) -> tuple[list[ParsedRow], list[str], dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with zipfile.ZipFile(path) as archive:
        shared_strings = read_shared_strings(archive)
        sheet_path = first_sheet_path(archive)
        raw_rows = iter_sheet_rows(archive, sheet_path, shared_strings)

    if not raw_rows:
        return [], [], {"numericScale": 1.0, "numericScaleLabel": "unknown"}
    headers = [normalize_text(value) for value in raw_rows[0]]
    index = resolve_column_index(headers)
    pending_rows: list[PendingRow] = []
    raw_offsets: list[Any] = []
    for raw in raw_rows[1:]:
        row = raw + [""] * max(0, len(headers) - len(raw))
        content = normalize_text(row[index["content"]])
        raw_offset = row[index["offset"]]
        raw_offsets.append(raw_offset)
        pending_rows.append(
            PendingRow(
                drama=normalize_text(row[index["drama"]]),
                group=normalize_text(row[index["group"]]),
                raw_offset=raw_offset,
                likes=parse_int(row[index["likes"]]),
                content_length=len(content),
                has_question=any(mark in content for mark in ("?", "？")),
                has_exclamation=any(mark in content for mark in ("!", "！")),
                has_laugh=bool(re.search(r"(哈{2,}|笑|hhh+|233)", content, re.IGNORECASE)),
            )
        )
    numeric_scale, numeric_scale_label = infer_numeric_offset_scale(raw_offsets)
    parsed_rows: list[ParsedRow] = []
    for row in pending_rows:
        parsed_rows.append(
            ParsedRow(
                drama=row.drama,
                group=row.group,
                offset_seconds=parse_offset_seconds(row.raw_offset, numeric_scale=numeric_scale),
                likes=row.likes,
                content_length=row.content_length,
                has_question=row.has_question,
                has_exclamation=row.has_exclamation,
                has_laugh=row.has_laugh,
            )
        )
    return parsed_rows, headers, {
        "numericScale": numeric_scale,
        "numericScaleLabel": numeric_scale_label,
    }


def read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values: list[str] = []
    for item in root.findall(f"{NS_MAIN}si"):
        parts = [node.text or "" for node in item.iter(f"{NS_MAIN}t")]
        values.append("".join(parts))
    return values


def first_sheet_path(archive: zipfile.ZipFile) -> str:
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    rels = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_by_id = {
        rel.attrib.get("Id", ""): rel.attrib.get("Target", "")
        for rel in rels.findall(f"{NS_REL_PKG}Relationship")
    }
    sheet = workbook.find(f"{NS_MAIN}sheets/{NS_MAIN}sheet")
    if sheet is None:
        raise ValueError("workbook has no sheet")
    rel_id = sheet.attrib.get(f"{NS_REL}id", "")
    target = rel_by_id.get(rel_id, "worksheets/sheet1.xml")
    if target.startswith("/"):
        return target.lstrip("/")
    return "xl/" + target.lstrip("/")


def iter_sheet_rows(
    archive: zipfile.ZipFile,
    sheet_path: str,
    shared_strings: list[str],
) -> list[list[str]]:
    root = ElementTree.fromstring(archive.read(sheet_path))
    rows: list[list[str]] = []
    for row_node in root.findall(f".//{NS_MAIN}row"):
        values_by_col: dict[int, str] = {}
        for cell in row_node.findall(f"{NS_MAIN}c"):
            ref = cell.attrib.get("r", "")
            col_index = column_index_from_ref(ref)
            values_by_col[col_index] = read_cell_value(cell, shared_strings)
        if not values_by_col:
            rows.append([])
            continue
        max_col = max(values_by_col)
        rows.append([values_by_col.get(index, "") for index in range(max_col + 1)])
    return rows


def read_cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.iter(f"{NS_MAIN}t"))
    value_node = cell.find(f"{NS_MAIN}v")
    if value_node is None or value_node.text is None:
        return ""
    raw = value_node.text
    if cell_type == "s":
        index = parse_int(raw)
        return shared_strings[index] if 0 <= index < len(shared_strings) else ""
    return raw


def column_index_from_ref(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha()).upper()
    value = 0
    for char in letters:
        value = value * 26 + (ord(char) - ord("A") + 1)
    return max(value - 1, 0)


def resolve_column_index(headers: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for key, column_name in REQUIRED_COLUMNS.items():
        try:
            result[key] = headers.index(column_name)
        except ValueError as exc:
            raise ValueError(f"missing required column: {column_name}") from exc
    return result


def analyze_rows(
    *,
    rows: list[ParsedRow],
    headers: list[str],
    offset_parse_info: dict[str, Any],
    bucket_seconds: int,
    min_gap_seconds: int,
    top_k: int,
    privacy: str,
) -> dict[str, Any]:
    if bucket_seconds <= 0:
        raise ValueError("--bucket-seconds must be positive")
    valid_time_rows = [row for row in rows if row.offset_seconds is not None]
    offsets = [float(row.offset_seconds) for row in valid_time_rows]
    likes = [row.likes for row in rows]
    lengths = [row.content_length for row in rows]
    bucket_stats = build_bucket_stats(valid_time_rows, bucket_seconds)
    group_stats = build_group_stats(valid_time_rows, privacy)
    candidates = select_candidate_windows(
        bucket_stats=bucket_stats,
        min_gap_seconds=min_gap_seconds,
        limit=top_k,
    )
    return {
        "privacy": {
            "mode": privacy,
            "rawContentExported": False,
            "rawRowsExported": False,
            "nameMasking": privacy == "strict",
        },
        "columns": {
            "requiredFound": REQUIRED_COLUMNS,
            "sourceColumnCount": len(headers),
        },
        "timeParsing": offset_parse_info,
        "dataset": {
            "rowCount": len(rows),
            "validTimeRowCount": len(valid_time_rows),
            "dramaCount": len({row.drama for row in rows if row.drama}),
            "groupCount": len({row.group for row in rows if row.group}),
            "missingTimeRate": safe_ratio(len(rows) - len(valid_time_rows), len(rows)),
        },
        "time": numeric_summary(offsets, unit="seconds"),
        "likes": {
            **numeric_summary(likes, unit="count"),
            "zeroLikeRate": safe_ratio(sum(1 for value in likes if value == 0), len(likes)),
            "top1PercentLikeShare": top_share(likes, 0.01),
            "top5PercentLikeShare": top_share(likes, 0.05),
        },
        "contentShape": {
            **numeric_summary(lengths, unit="chars"),
            "questionRate": safe_ratio(sum(1 for row in rows if row.has_question), len(rows)),
            "exclamationRate": safe_ratio(sum(1 for row in rows if row.has_exclamation), len(rows)),
            "laughSignalRate": safe_ratio(sum(1 for row in rows if row.has_laugh), len(rows)),
        },
        "groups": group_stats[:top_k],
        "hotBucketsByCount": top_buckets(bucket_stats, key="count", limit=top_k),
        "hotBucketsByLikes": top_buckets(bucket_stats, key="likes", limit=top_k),
        "interactionCandidateWindows": candidates,
        "projectGuidance": build_project_guidance(
            rows=rows,
            candidates=candidates,
            bucket_seconds=bucket_seconds,
            min_gap_seconds=min_gap_seconds,
        ),
    }


def build_bucket_stats(rows: list[ParsedRow], bucket_seconds: int) -> dict[int, dict[str, Any]]:
    stats: dict[int, dict[str, Any]] = defaultdict(
        lambda: {
            "bucketSeconds": bucket_seconds,
            "count": 0,
            "likes": 0,
            "questions": 0,
            "exclamations": 0,
        }
    )
    for row in rows:
        if row.offset_seconds is None:
            continue
        bucket_start = int(row.offset_seconds // bucket_seconds) * bucket_seconds
        stats[bucket_start]["count"] += 1
        stats[bucket_start]["likes"] += row.likes
        stats[bucket_start]["questions"] += int(row.has_question)
        stats[bucket_start]["exclamations"] += int(row.has_exclamation)
    return dict(stats)


def build_group_stats(rows: list[ParsedRow], privacy: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[ParsedRow]] = defaultdict(list)
    for row in rows:
        grouped[row.group or "UNKNOWN"].append(row)
    ordered = sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)
    return [
        {
            "group": mask_name(name, "分组", index, privacy),
            "count": len(items),
            "likeSum": sum(item.likes for item in items),
            "avgOffsetSeconds": round(statistics.mean(item.offset_seconds for item in items if item.offset_seconds is not None), 2),
        }
        for index, (name, items) in enumerate(ordered, start=1)
    ]


def top_buckets(bucket_stats: dict[int, dict[str, Any]], *, key: str, limit: int) -> list[dict[str, Any]]:
    ordered = sorted(bucket_stats.items(), key=lambda item: (item[1][key], item[1]["count"]), reverse=True)
    return [format_bucket(start, stat) for start, stat in ordered[:limit]]


def select_candidate_windows(
    *,
    bucket_stats: dict[int, dict[str, Any]],
    min_gap_seconds: int,
    limit: int,
) -> list[dict[str, Any]]:
    if not bucket_stats:
        return []
    max_count = max(stat["count"] for stat in bucket_stats.values()) or 1
    max_likes = max(stat["likes"] for stat in bucket_stats.values()) or 1
    ranked = []
    for start, stat in bucket_stats.items():
        score = 0.65 * stat["count"] / max_count + 0.35 * stat["likes"] / max_likes
        ranked.append((start, score, stat))
    selected: list[tuple[int, float, dict[str, Any]]] = []
    for start, score, stat in sorted(ranked, key=lambda item: item[1], reverse=True):
        if any(abs(start - old_start) < min_gap_seconds for old_start, _, _ in selected):
            continue
        selected.append((start, score, stat))
        if len(selected) >= limit:
            break
    return [
        {
            **format_bucket(start, stat),
            "score": round(score, 4),
            "suggestedNodeType": suggest_node_type(stat),
        }
        for start, score, stat in sorted(selected, key=lambda item: item[0])
    ]


def format_bucket(start: int, stat: dict[str, Any]) -> dict[str, Any]:
    end = start + int(stat.get("bucketSeconds", 10) or 10)
    return {
        "startSeconds": start,
        "timeRange": f"{format_seconds(start)}-{format_seconds(end)}",
        "count": int(stat["count"]),
        "likeSum": int(stat["likes"]),
        "questionCount": int(stat["questions"]),
        "exclamationCount": int(stat["exclamations"]),
    }


def suggest_node_type(stat: dict[str, Any]) -> str:
    count = int(stat.get("count", 0))
    questions = int(stat.get("questions", 0))
    exclamations = int(stat.get("exclamations", 0))
    if questions >= max(2, count * 0.12):
        return "PLOT_EXPECTATION"
    if exclamations >= max(2, count * 0.18):
        return "REACTION_PULSE"
    return "DANMAKU_REACTION"


def build_project_guidance(
    *,
    rows: list[ParsedRow],
    candidates: list[dict[str, Any]],
    bucket_seconds: int,
    min_gap_seconds: int,
) -> list[str]:
    guidance = [
        f"互动节点候选可从 {len(candidates)} 个高热时间窗里筛选，当前最小间隔按 {min_gap_seconds}s 控制，符合项目 globalPolicy 的节点间隔约束。",
        f"建议将后端证据流水线里的候选节点生成窗口从固定秒点扩展为 {bucket_seconds}s 热区聚合，再由人工确认写入 timeline_items。",
    ]
    if candidates:
        guidance.append(
            "优先把 Top 热区对齐到播放器互动触发点；不需要暴露原始弹幕文本，也能用密度、点赞和问号/感叹号比例解释为什么这里值得互动。"
        )
    like_values = [row.likes for row in rows]
    if top_share(like_values, 0.05) >= 0.5:
        guidance.append("点赞集中度较高，推荐在热区排序中加入 likeSum 或点赞分位，避免只按弹幕条数选择节点。")
    avg_length = statistics.mean([row.content_length for row in rows]) if rows else 0
    if avg_length <= 12:
        guidance.append("弹幕平均长度偏短，Android 侧更适合一键短文案、弹幕按钮和轻反馈，不宜要求用户输入长文本。")
    else:
        guidance.append("弹幕平均长度不低，可以在互动反馈里增加评论快捷回填和讨论种子承接。")
    return guidance


def numeric_summary(values: list[float | int], *, unit: str) -> dict[str, Any]:
    clean = [float(value) for value in values if value is not None and not math.isnan(float(value))]
    if not clean:
        return {"unit": unit, "count": 0}
    ordered = sorted(clean)
    return {
        "unit": unit,
        "count": len(clean),
        "min": round(ordered[0], 4),
        "p25": round(percentile(ordered, 0.25), 4),
        "median": round(percentile(ordered, 0.5), 4),
        "p75": round(percentile(ordered, 0.75), 4),
        "p90": round(percentile(ordered, 0.9), 4),
        "max": round(ordered[-1], 4),
        "mean": round(statistics.mean(ordered), 4),
    }


def percentile(ordered: list[float], q: float) -> float:
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return ordered[low]
    weight = pos - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def top_share(values: list[int], fraction: float) -> float:
    clean = sorted((max(int(value), 0) for value in values), reverse=True)
    total = sum(clean)
    if total <= 0 or not clean:
        return 0.0
    top_n = max(1, int(math.ceil(len(clean) * fraction)))
    return round(sum(clean[:top_n]) / total, 4)


def safe_ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def infer_numeric_offset_scale(values: list[Any]) -> tuple[float, str]:
    numeric_values: list[float] = []
    for value in values:
        text = normalize_text(value)
        if re.fullmatch(r"\d+(\.\d+)?", text):
            numeric_values.append(float(text))
    if not numeric_values:
        return 1.0, "clock"
    ordered = sorted(numeric_values)
    median = percentile(ordered, 0.5)
    p90 = percentile(ordered, 0.9)
    if median >= 1000 and p90 >= 10000:
        return 0.001, "milliseconds"
    return 1.0, "seconds"


def parse_offset_seconds(value: Any, *, numeric_scale: float = 1.0) -> float | None:
    text = normalize_text(value)
    if not text:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text) * numeric_scale
    match = re.fullmatch(r"(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)", text)
    if match:
        hours = float(match.group(1) or 0)
        minutes = float(match.group(2) or 0)
        seconds = float(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds
    return None


def parse_int(value: Any) -> int:
    text = normalize_text(value)
    if not text:
        return 0
    try:
        return max(int(float(text)), 0)
    except ValueError:
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else 0


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def mask_name(name: str, prefix: str, index: int, privacy: str) -> str:
    if privacy == "named":
        return name
    return f"{prefix}#{index:02d}"


def format_seconds(seconds: int | float) -> str:
    seconds_int = int(seconds)
    minutes, sec = divmod(seconds_int, 60)
    return f"{minutes:02d}:{sec:02d}"


def render_markdown(summary: dict[str, Any]) -> str:
    lines: list[str] = [
        "# 弹幕数据脱敏统计分析",
        "",
        "## 隐私边界",
        "",
        f"- 原始弹幕内容导出：{summary['privacy']['rawContentExported']}",
        f"- 原始逐行记录导出：{summary['privacy']['rawRowsExported']}",
        f"- 名称脱敏：{summary['privacy']['nameMasking']}",
        f"- 时间数值解析：{summary['timeParsing']['numericScaleLabel']}，scale={summary['timeParsing']['numericScale']}",
        "",
        "## 数据概览",
        "",
        f"- 总记录数：{summary['dataset']['rowCount']}",
        f"- 有效时间记录数：{summary['dataset']['validTimeRowCount']}",
        f"- 剧名称数量：{summary['dataset']['dramaCount']}",
        f"- group_title 数量：{summary['dataset']['groupCount']}",
        f"- 时间缺失率：{summary['dataset']['missingTimeRate']}",
        "",
        "## 时间与互动强度",
        "",
        render_summary_line("时间偏移", summary["time"]),
        render_summary_line("点赞数", summary["likes"]),
        f"- 0 赞占比：{summary['likes']['zeroLikeRate']}",
        f"- Top 1% 点赞占比：{summary['likes']['top1PercentLikeShare']}",
        f"- Top 5% 点赞占比：{summary['likes']['top5PercentLikeShare']}",
        "",
        "## 文本形态（不含原文）",
        "",
        render_summary_line("弹幕长度", summary["contentShape"]),
        f"- 问号占比：{summary['contentShape']['questionRate']}",
        f"- 感叹号占比：{summary['contentShape']['exclamationRate']}",
        f"- 笑点信号占比：{summary['contentShape']['laughSignalRate']}",
        "",
        "## Top 热区（按弹幕量）",
        "",
        render_bucket_table(summary["hotBucketsByCount"]),
        "",
        "## Top 热区（按点赞量）",
        "",
        render_bucket_table(summary["hotBucketsByLikes"]),
        "",
        "## 建议互动节点候选窗",
        "",
        render_candidate_table(summary["interactionCandidateWindows"]),
        "",
        "## 对当前项目的指导意义",
        "",
    ]
    lines.extend(f"- {item}" for item in summary["projectGuidance"])
    lines.append("")
    return "\n".join(lines)


def render_summary_line(title: str, stat: dict[str, Any]) -> str:
    if not stat.get("count"):
        return f"- {title}：无可用数据"
    return (
        f"- {title}：median={stat['median']} {stat['unit']}，"
        f"p90={stat['p90']}，mean={stat['mean']}，max={stat['max']}"
    )


def render_bucket_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return "无可用热区。"
    lines = ["| 时间窗 | 条数 | 点赞和 | 问号数 | 感叹号数 |", "| --- | ---: | ---: | ---: | ---: |"]
    for item in items:
        lines.append(
            f"| {item['timeRange']} | {item['count']} | {item['likeSum']} | "
            f"{item['questionCount']} | {item['exclamationCount']} |"
        )
    return "\n".join(lines)


def render_candidate_table(items: list[dict[str, Any]]) -> str:
    if not items:
        return "无可用候选窗。"
    lines = ["| 时间窗 | 分数 | 建议节点类型 | 条数 | 点赞和 |", "| --- | ---: | --- | ---: | ---: |"]
    for item in items:
        lines.append(
            f"| {item['timeRange']} | {item['score']} | {item['suggestedNodeType']} | "
            f"{item['count']} | {item['likeSum']} |"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
