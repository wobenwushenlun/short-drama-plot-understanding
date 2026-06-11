from __future__ import annotations

import argparse
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


DRAMA_ALIASES = {
    "十八岁太奶奶驾到，重整家族荣耀第三部": {
        "drama_id": "tainai3",
        "episode_prefix": "tainai3_ep",
        "episode_number_start": 1,
    },
    "家里家外": {
        "drama_id": "jiali_jiawai",
        "episode_prefix": "jiali_jiawai_ep",
        "episode_number_start": 1,
    },
    "幸得相遇离婚时": {
        "drama_id": "xingde_xiangyu_lihunshi",
        "episode_prefix": "xingde_xiangyu_lihunshi_ep",
        "episode_number_start": 1,
    },
    "北派寻宝笔记": {
        "drama_id": "beipai_xunbao",
        "episode_prefix": "beipai_xunbao_ep",
        "episode_number_start": 63,
    },
}

REQUIRED_COLUMNS = {
    "drama": "剧名称",
    "group": "group_title",
    "offset": "发弹幕时刻相对于视频起始时间偏移量",
    "likes": "累计点赞数",
    "content": "弹幕内容",
}

STOP_WORDS = {
    "这个",
    "真的",
    "不是",
    "怎么",
    "什么",
    "一个",
    "一下",
    "哈哈",
    "哈哈哈",
    "啊啊",
    "就是",
    "感觉",
    "有人",
}

KEYWORD_RULES = [
    ("心疼", ("心疼", "委屈", "哭", "难受", "可怜")),
    ("愤怒", ("气人", "太气", "无语", "离谱", "恶心")),
    ("反转", ("反转", "打脸", "爽", "终于", "逆袭")),
    ("身份", ("身份", "太奶奶", "奶奶", "认出", "秘密")),
    ("站队", ("站", "支持", "女主", "男主", "相信")),
    ("悬疑", ("线索", "真相", "寻宝", "古玩", "假的", "真的")),
    ("情感", ("离婚", "相遇", "复合", "误会", "爱情")),
    ("家庭", ("家里", "家外", "亲情", "婆婆", "孩子", "家人")),
]

EMOTION_RULES = [
    ("心疼共情", ("心疼", "委屈", "哭", "难受", "可怜")),
    ("愤怒吐槽", ("气人", "太气", "无语", "离谱", "恶心")),
    ("爽感期待", ("反转", "打脸", "爽", "逆袭", "终于")),
    ("悬念推理", ("线索", "真相", "寻宝", "古玩", "身份", "秘密")),
    ("站队讨论", ("站", "支持", "女主", "男主", "相信")),
]


def build_danmaku_evidence(source_path: Path, output_path: Path, *, top_n: int = 4, window_seconds: int = 15) -> dict[str, Any]:
    rows = _read_xlsx_rows(source_path)
    if not rows:
        payload = _empty_payload()
        _write_json(output_path, payload)
        return payload
    header = [str(value).strip() for value in rows[0]]
    indexes = _resolve_column_indexes(header)
    buckets: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows[1:]:
        item = _normalize_row(row, indexes)
        if item is None:
            continue
        bucket_ms = int(item["offset_ms"] // (window_seconds * 1000) * (window_seconds * 1000))
        buckets[item["episode_id"]][bucket_ms].append(item)

    episodes: dict[str, Any] = {}
    for episode_id, episode_buckets in sorted(buckets.items()):
        ranked = sorted(
            (
                _build_hotspot(episode_id, start_ms, items, window_seconds)
                for start_ms, items in episode_buckets.items()
                if items
            ),
            key=lambda item: (-item["heatScore"], item["timeMs"]),
        )[:top_n]
        if not ranked:
            continue
        episodes[episode_id] = {
            "candidates": [item["candidate"] for item in ranked],
            "publishedNodes": [
                item["publishedNode"]
                for item in ranked
                if item["publishedNode"]["timeMs"] >= window_seconds * 1000
            ],
            "hotspots": [item["hotspot"] for item in ranked],
        }

    payload = {
        "schemaVersion": "1.1",
        "source": "danmaku_excel_aggregate",
        "privacy": {
            "rawContentExported": False,
            "rawRowsExported": False,
            "wordAggregationOnly": True,
        },
        "windowSeconds": window_seconds,
        "episodes": episodes,
    }
    _write_json(output_path, payload)
    return payload


def _empty_payload() -> dict[str, Any]:
    return {
        "schemaVersion": "1.1",
        "source": "danmaku_excel_aggregate",
        "privacy": {"rawContentExported": False, "rawRowsExported": False, "wordAggregationOnly": True},
        "windowSeconds": 15,
        "episodes": {},
    }


def _read_xlsx_rows(path: Path) -> list[list[Any]]:
    with zipfile.ZipFile(path) as zf:
        shared_strings = _read_shared_strings(zf)
        sheet_name = _first_sheet_name(zf)
        root = ET.fromstring(zf.read(sheet_name))
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows: list[list[Any]] = []
    for row in root.findall(".//m:sheetData/m:row", ns):
        values: dict[int, Any] = {}
        for cell in row.findall("m:c", ns):
            ref = str(cell.attrib.get("r") or "")
            col_index = _column_index(ref)
            if col_index < 0:
                continue
            values[col_index] = _cell_value(cell, shared_strings, ns)
        if values:
            max_col = max(values)
            rows.append([values.get(index, "") for index in range(max_col + 1)])
    return rows


def _read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    values = []
    for item in root.findall("m:si", ns):
        values.append("".join(text.text or "" for text in item.findall(".//m:t", ns)))
    return values


def _first_sheet_name(zf: zipfile.ZipFile) -> str:
    for name in zf.namelist():
        if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
            return name
    raise ValueError("xlsx has no worksheet")


def _column_index(ref: str) -> int:
    match = re.match(r"([A-Z]+)", ref)
    if match is None:
        return -1
    result = 0
    for char in match.group(1):
        result = result * 26 + (ord(char) - ord("A") + 1)
    return result - 1


def _cell_value(cell: ET.Element, shared_strings: list[str], ns: dict[str, str]) -> Any:
    value = cell.find("m:v", ns)
    raw = value.text if value is not None else ""
    if cell.attrib.get("t") == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return ""
    if cell.attrib.get("t") == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//m:t", ns))
    try:
        number = float(raw)
    except (TypeError, ValueError):
        return raw or ""
    return int(number) if math.isfinite(number) and number.is_integer() else number


def _resolve_column_indexes(header: list[str]) -> dict[str, int]:
    indexes: dict[str, int] = {}
    for key, column_name in REQUIRED_COLUMNS.items():
        try:
            indexes[key] = header.index(column_name)
        except ValueError as exc:
            raise ValueError(f"missing required column: {column_name}") from exc
    return indexes


def _normalize_row(row: list[Any], indexes: dict[str, int]) -> dict[str, Any] | None:
    drama_title = _safe_cell(row, indexes["drama"])
    mapping = DRAMA_ALIASES.get(drama_title)
    if mapping is None:
        return None
    source_episode_no = _extract_episode_no(_safe_cell(row, indexes["group"]))
    if source_episode_no is None:
        return None
    logical_episode_no = source_episode_no - int(mapping["episode_number_start"]) + 1
    if logical_episode_no < 1 or logical_episode_no > 5:
        return None
    offset_ms = _offset_to_ms(_safe_cell(row, indexes["offset"]))
    if offset_ms < 0:
        return None
    return {
        "drama_title": drama_title,
        "drama_id": mapping["drama_id"],
        "episode_id": f"{mapping['episode_prefix']}{logical_episode_no:02d}",
        "source_episode_no": source_episode_no,
        "offset_ms": offset_ms,
        "likes": _safe_int(_safe_cell(row, indexes["likes"])),
        "content": _safe_cell(row, indexes["content"]),
    }


def _safe_cell(row: list[Any], index: int) -> str:
    return str(row[index] if index < len(row) else "").strip()


def _extract_episode_no(text: str) -> int | None:
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else None


def _offset_to_ms(text: str) -> int:
    if ":" in text:
        parts = [float(part) for part in text.split(":") if part != ""]
        seconds = 0.0
        for part in parts:
            seconds = seconds * 60 + part
        return int(seconds * 1000)
    try:
        value = float(text)
    except ValueError:
        return -1
    return int(value if value > 10_000 else value * 1000)


def _safe_int(text: str) -> int:
    try:
        return max(0, int(float(text)))
    except ValueError:
        return 0


def _build_hotspot(episode_id: str, start_ms: int, items: list[dict[str, Any]], window_seconds: int) -> dict[str, Any]:
    end_ms = start_ms + window_seconds * 1000
    comment_count = len(items)
    like_intensity = sum(int(item["likes"]) for item in items)
    keywords = _extract_keywords([str(item["content"]) for item in items])
    emotion = _infer_emotion(keywords)
    interaction = _suggest_interaction(emotion, keywords)
    heat_score = min(100, int(round(comment_count * 8 + math.log1p(like_intensity) * 12)))
    suffix = f"{start_ms // 1000:03d}"
    candidate_id = f"danmaku_{episode_id}_{suffix}"
    evidence_refs = [f"danmaku_bucket:{episode_id}:{suffix}"]
    reason = f"{_format_time(start_ms)}-{_format_time(end_ms)} 聚合弹幕 {comment_count} 条、点赞 {like_intensity}；关键词：{'、'.join(keywords)}。"
    candidate = {
        "candidateId": candidate_id,
        "timeMs": start_ms,
        "type": interaction["type"],
        "question": interaction["question"],
        "reason": reason,
        "options": interaction["options"],
        "evidenceRefs": evidence_refs,
        "confidence": round(min(0.96, 0.62 + heat_score / 300), 3),
        "reviewStatus": "accepted",
    }
    published_node = {
        "id": f"n_{suffix}_{episode_id}_danmaku",
        "candidateId": candidate_id,
        "timeMs": start_ms,
        "type": interaction["type"],
        "title": interaction["title"],
        "subtitle": f"真实弹幕热区：{comment_count} 条互动，{like_intensity} 点赞",
        "style": interaction["style"],
        "effectText": interaction["effectText"],
        "badgeText": interaction["badgeText"],
        "promptText": interaction["promptText"],
        "options": [{"id": f"choice_{index + 1}", "text": option} for index, option in enumerate(interaction["options"])],
    }
    hotspot = {
        "hotspotId": candidate_id,
        "episodeId": episode_id,
        "startMs": start_ms,
        "endMs": end_ms,
        "timeMs": start_ms,
        "keywords": keywords,
        "emotion": emotion,
        "commentIntensity": comment_count,
        "likeIntensity": like_intensity,
        "heatScore": heat_score,
        "suggestedComponentType": interaction["componentType"],
        "suggestedInteraction": interaction["label"],
        "evidenceRefs": evidence_refs,
    }
    return {"candidate": candidate, "publishedNode": published_node, "hotspot": hotspot, "heatScore": heat_score, "timeMs": start_ms}


def _extract_keywords(contents: list[str]) -> list[str]:
    joined = " ".join(contents)
    keyword_scores: Counter[str] = Counter()
    for label, tokens in KEYWORD_RULES:
        score = sum(joined.count(token) for token in tokens)
        if score:
            keyword_scores[label] += score
    for word in re.findall(r"[\u4e00-\u9fff]{2,6}", joined):
        if word in STOP_WORDS:
            continue
        keyword_scores[word] += 1
    keywords = [word for word, _ in keyword_scores.most_common(4)]
    return keywords or ["观众共鸣"]


def _infer_emotion(keywords: list[str]) -> str:
    joined = " ".join(keywords)
    for label, tokens in EMOTION_RULES:
        if any(token in joined for token in tokens):
            return label
    return "共鸣讨论"


def _suggest_interaction(emotion: str, keywords: list[str]) -> dict[str, Any]:
    if emotion == "心疼共情":
        return {
            "type": "DANMAKU_REACTION",
            "componentType": "DANMAKU_STICKER",
            "label": "共情弹幕贴纸",
            "title": "这一刻观众开始心疼",
            "question": "看到这里你最想发哪句弹幕？",
            "options": ["太心疼了", "先别误会她", "等她反击"],
            "style": "共情弹幕",
            "effectText": "疼",
            "badgeText": "心疼热区",
            "promptText": "来自真实弹幕共鸣的轻互动",
        }
    if emotion == "愤怒吐槽":
        return {
            "type": "REACTION_PULSE",
            "componentType": "REACTION_STICKER",
            "label": "吐槽反应贴纸",
            "title": "弹幕吐槽集中爆发",
            "question": "这一段你想怎么吐槽？",
            "options": ["太气人了", "等反转", "站出来怼"],
            "style": "吐槽气泡",
            "effectText": "怼",
            "badgeText": "吐槽热区",
            "promptText": "用一键反应承接观众情绪",
        }
    if emotion in {"爽感期待", "悬念推理"}:
        return {
            "type": "PLOT_EXPECTATION",
            "componentType": "CHOICE_CARD",
            "label": "剧情预判卡",
            "title": "观众开始预判反转",
            "question": "你觉得下一步会怎么反转？",
            "options": ["身份揭开", "当场打脸", "线索反转"],
            "style": "反转预判",
            "effectText": "猜",
            "badgeText": "高能预警",
            "promptText": "把热区讨论转成剧情选择",
        }
    return {
        "type": "DANMAKU_REACTION",
        "componentType": "DANMAKU_STICKER",
        "label": "弹幕共鸣贴纸",
        "title": f"弹幕聚焦：{keywords[0]}",
        "question": "这一幕你更想表达什么？",
        "options": ["继续看", "有点上头", "想看后续"],
        "style": "弹幕共鸣",
        "effectText": "热",
        "badgeText": "共鸣热区",
        "promptText": "基于真实弹幕热区生成",
    }


def _format_time(ms: int) -> str:
    total_seconds = ms // 1000
    return f"{total_seconds // 60:02d}:{total_seconds % 60:02d}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="生成脱敏弹幕热区证据 JSON")
    parser.add_argument("--source", type=Path, default=Path("assets/弹幕数据.xlsx"))
    parser.add_argument("--output", type=Path, default=Path("backend/app/evidence/danmaku_hotspots.generated.json"))
    parser.add_argument("--top-n", type=int, default=4)
    parser.add_argument("--window-seconds", type=int, default=15)
    args = parser.parse_args()
    payload = build_danmaku_evidence(args.source, args.output, top_n=args.top_n, window_seconds=args.window_seconds)
    print(json.dumps({"output": str(args.output), "episodeCount": len(payload["episodes"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
