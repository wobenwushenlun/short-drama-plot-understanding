from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.app.aigc_insert_service import DEFAULT_INSERT_DURATION_MS, get_aigc_insert_provider
from backend.app.cover_layers import build_cover_layers
from backend.app.danmaku_emotion_domain import build_danmaku_emotion_payload
from backend.app.drama_registry import DramaConfig, load_drama_registry
from backend.app.domain_utils import safe_int as _safe_int
from backend.app.evidence_graph import build_episode_evidence_graph_payload
from backend.app.interaction_components import apply_interaction_component_metadata
from backend.app.interaction_timeline import build_timed_event_from_timeline_item, build_timeline_items
from backend.app.quality_evaluation import build_quality_evaluation_report as build_quality_report_payload
from backend.app.runtime_sqlite_store import get_runtime_store
from backend.app.shareable_moments import (
    build_shareable_moment_from_node,
    format_saved_moment,
    normalize_incoming_moment,
    normalize_shareable_strategy,
    sort_shareable_moments,
)


DEFAULT_CONTENT_ROOT = Path("media/dramas/tainai3")
DEFAULT_HLS_ROOT = Path("tmp/hls")
DEFAULT_VIDEO_UNDERSTANDING_ROOT = Path("tmp/video_understanding_results")
DEFAULT_DRAMA_COVER_ASSET_ROOT = Path(__file__).resolve().parents[2] / "assets"
BUNDLED_DANMAKU_EVIDENCE_PATH = Path("backend/app/evidence/danmaku_hotspots.generated.json")
DEFAULT_DANMAKU_EVIDENCE_PATH = BUNDLED_DANMAKU_EVIDENCE_PATH
LEGACY_DANMAKU_EVIDENCE_PATH = Path("backend/app/evidence/tainai3_ep1_5_danmaku_hotspots.json")
DRAMA_COVER_ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
DRAMA_ID = "tainai3"
VIDEO_UNDERSTANDING_STORY_PROMPT_VERSION = "video.understanding/p1-story-summary"
STORY_SUMMARY_PROMPT_VERSION = "content.story_summary/p2-grounded-platform-copy"
STORY_SUMMARY_CACHE_FILE = "story_summaries.json"
STORY_SUMMARY_ATTEMPT_FILE = "story_summaries_attempt.json"
INTERACTION_CANDIDATE_REVIEW_FILE = "interaction_candidate_reviews.json"
STORY_SUMMARY_DRAMA_MIN_CHARS = 180
STORY_SUMMARY_DRAMA_MAX_CHARS = 520
STORY_SUMMARY_EPISODE_MIN_CHARS = 80
STORY_SUMMARY_EPISODE_MAX_CHARS = 280


DRAMA_PLOT_DESCRIPTION = (
    "1955年，容遇教授意外去世后醒来，竟穿到七十年后一位同名同姓的十八岁少女身上。"
    "昔日儿子已成纪家掌权人，她却被当成来路不明的闯入者。面对晚辈误会、家族内斗和外部危机，"
    "容遇一边隐藏穿越真相，一边用智慧与气场重新掌控纪家，把濒临失控的家族带回荣耀巅峰。"
)


EPISODE_DURATIONS_MS = {
    1: 245_840,
    2: 275_000,
    3: 254_440,
    4: 174_320,
    5: 133_000,
}


EPISODE_SUMMARIES = {
    1: "第1集｜1955年容遇教授意外身故，一睁眼却成了七十年后的十八岁少女。她被带到纪家后遭到质疑，只能先稳住局面，寻找自己与这个家族的真实联系。",
    2: "第2集｜纪家众人不相信眼前少女与太奶奶有关，试探和嘲讽不断升级。容遇没有正面摊牌，而是用判断力和气场让局面开始反转。",
    3: "第3集｜围绕容遇身份的线索继续浮出水面，纪家人的态度出现动摇。她在误解与逼问中抓住主动权，也让家族旧事露出新的破口。",
    4: "第4集｜冲突从口头质疑升级为正面对线，容遇的手腕逐渐压住场面。纪家内部压力被推到台前，新的反转也被推向临界点。",
    5: "第5集｜前几集埋下的人物关系和身份线索开始汇合，容遇在关键抉择前稳住局势。家族成员立场逐渐分化，更大的危机与打脸时刻即将到来。",
}


TECHNICAL_SUMMARY_MARKERS = (
    "ASR",
    "OCR",
    "关键帧",
    "融合理解",
    "视频理解",
    "识别",
    "证据",
    "互动",
    "AIGC",
    "P0",
    "P1",
    "prompt",
    "transcript",
    "speaker",
    "Speaker",
    "SPEAKER",
    "speaker_",
    "说话人",
    "台词识别",
    "角色表",
)


EPISODE_NODE_BLUEPRINTS: dict[str, list[dict[str, Any]]] = {
    "tainai3_ep01": [
        {
            "id": "n_044_character_entrance_reaction",
            "type": "REACTION_PULSE",
            "title": "容遇登场，你第一反应？",
            "subtitle": "抱臂凝重、气场压住全场，适合收集即时情绪反馈",
            "time_ms": 44_000,
            "style": "爽点气泡",
            "effect_text": "爽",
            "badge_text": "登场高能",
            "prompt_text": "点一下给这段气场加热度",
            "options": [
                ("handsome", "好帅"),
                ("aura", "这气场绝了"),
                ("interesting", "有意思，继续看"),
            ],
        },
        {
            "id": "n_123_profile_text_reaction",
            "type": "SCREEN_TEXT_REACTION",
            "title": "人物高光信息出现了",
            "subtitle": "科学院首席院士、国家终身成就奖等人物介绍文字出现，身份反差被放大",
            "time_ms": 123_000,
            "style": "身份放大镜",
            "effect_text": "强",
            "badge_text": "人物高光",
            "prompt_text": "这不是普通人设，选一个你最吃的点",
            "options": [
                ("legend", "履历太强"),
                ("hidden_identity", "原来有隐藏身份"),
                ("face_slap", "想看她打脸"),
            ],
        },
        {
            "id": "n_202_plot_hook_reaction",
            "type": "PLOT_EXPECTATION",
            "title": "接下来你最想看什么？",
            "subtitle": "家族逆袭主线即将加速，适合提前押注下一波爽点",
            "time_ms": 202_000,
            "style": "预判投票",
            "effect_text": "猜",
            "badge_text": "下一幕预测",
            "prompt_text": "提前押注下一波爽点",
            "options": [
                ("more_reversal", "继续反转"),
                ("identity_reveal", "身份揭晓"),
                ("family_conflict", "家族对线"),
            ],
        },
    ],
    "tainai3_ep02": [
        {
            "id": "n_038_ep02_crowd_mock",
            "type": "DANMAKU_REACTION",
            "title": "这波质疑你想怎么弹幕？",
            "subtitle": "围观者质疑升级，适合做同屏吐槽式互动",
            "time_ms": 38_000,
            "style": "弹幕冲浪",
            "effect_text": "怼",
            "badge_text": "弹幕上屏",
            "prompt_text": "选中后会生成同款弹幕反馈",
            "options": [
                ("let_her_speak", "让她说完"),
                ("too_noisy", "这群人太吵"),
                ("wait_reversal", "等反转"),
            ],
        },
        {
            "id": "n_118_ep02_counter_attack",
            "type": "CLIMAX_BOOST",
            "title": "反击开始，要不要加速？",
            "subtitle": "主角开始扭转局势，适合插入加速包式高能内容",
            "time_ms": 118_000,
            "style": "加速包",
            "effect_text": "燃",
            "badge_text": "高能加速包",
            "prompt_text": "模拟官方示例：点击后进入高能连剪解释",
            "options": [
                ("boost", "加速看反击"),
                ("slow_detail", "我要看细节"),
                ("save_power", "先攒一波爽点"),
            ],
            "ai_insert": {
                "type": "AIGC_ACCELERATION_PACK",
                "title": "反击高能连剪",
                "description": "占位：后续可接入 AIGC 生成的汽车加速/气势推进短片段。",
            },
        },
        {
            "id": "n_210_ep02_side_choice",
            "type": "SIDE_CHOICE",
            "title": "你现在站哪边？",
            "subtitle": "剧情冲突进入站队时刻，适合采集偏好用于后续讨论",
            "time_ms": 210_000,
            "style": "站队光环",
            "effect_text": "站",
            "badge_text": "阵营选择",
            "prompt_text": "这次选择会影响后续讨论卡视角",
            "options": [
                ("support_grandma", "支持太奶奶"),
                ("watch_family", "观察家族反应"),
                ("support_truth", "只站真相"),
            ],
        },
    ],
    "tainai3_ep03": [
        {
            "id": "n_052_ep03_identity_hint",
            "type": "SCREEN_TEXT_REACTION",
            "title": "身份线索又来了",
            "subtitle": "画面与台词继续暗示主角真实身份",
            "time_ms": 52_000,
            "style": "身份放大镜",
            "effect_text": "懂",
            "badge_text": "线索捕捉",
            "prompt_text": "你更相信哪条线索？",
            "options": [
                ("title_hint", "称号不简单"),
                ("tone_hint", "语气有底气"),
                ("people_hint", "众人反应露馅"),
            ],
        },
        {
            "id": "n_136_ep03_funny_cut",
            "type": "FUNNY_REACTION",
            "title": "这段有点好笑",
            "subtitle": "紧张冲突中出现反差反应，适合轻量搞笑按钮",
            "time_ms": 136_000,
            "style": "笑出鹅叫",
            "effect_text": "笑",
            "badge_text": "反差笑点",
            "prompt_text": "点一下，把这段变成笑点标记",
            "options": [
                ("goose_laugh", "笑出鹅叫"),
                ("awkward", "这也太尴尬"),
                ("again", "想重看这秒"),
            ],
        },
        {
            "id": "n_210_ep03_next_prediction",
            "type": "PLOT_EXPECTATION",
            "title": "下一秒谁会破防？",
            "subtitle": "反转前的节奏被拉满，适合做预测式互动",
            "time_ms": 210_000,
            "style": "预判投票",
            "effect_text": "爆",
            "badge_text": "破防预警",
            "prompt_text": "押一个马上破防的人",
            "options": [
                ("family_member", "家族成员"),
                ("outsider", "旁观者"),
                ("no_one", "还会再藏一手"),
            ],
        },
    ],
    "tainai3_ep04": [
        {
            "id": "n_030_ep04_pressure",
            "type": "REACTION_PULSE",
            "title": "压迫感上来了",
            "subtitle": "对峙画面集中，适合做情绪强度反馈",
            "time_ms": 30_000,
            "style": "爽点气泡",
            "effect_text": "压",
            "badge_text": "压迫感",
            "prompt_text": "这一幕你感受到几分压迫？",
            "options": [
                ("full_pressure", "压迫拉满"),
                ("calm", "她太稳了"),
                ("danger", "有危险味"),
            ],
        },
        {
            "id": "n_084_ep04_speed_pack",
            "type": "AIGC_INSERT",
            "title": "剧情提速，插入加速包？",
            "subtitle": "从试探进入直接推进，适合加一段气势插包",
            "time_ms": 84_000,
            "style": "加速包",
            "effect_text": "冲",
            "badge_text": "加速包",
            "prompt_text": "点加速，模拟生成一段高能推进内容",
            "options": [
                ("speed_up", "加速包"),
                ("original", "按原速看"),
                ("explain", "先解释局势"),
            ],
            "ai_insert": {
                "type": "AIGC_MOMENTUM_CLIP",
                "title": "局势推进动效",
                "description": "占位：后续可补一个 3-5 秒情绪推进片段。",
            },
        },
        {
            "id": "n_136_ep04_cliffhanger",
            "type": "CLIFFHANGER",
            "title": "这集结尾你要哪种钩子？",
            "subtitle": "结尾前收集用户对下一集的期待",
            "time_ms": 136_000,
            "style": "预判投票",
            "effect_text": "钩",
            "badge_text": "追更钩子",
            "prompt_text": "选一个最想看的下一集开场",
            "options": [
                ("truth_open", "真相开场"),
                ("face_slap_open", "打脸开场"),
                ("new_enemy", "新对手登场"),
            ],
        },
    ],
    "tainai3_ep05": [
        {
            "id": "n_026_ep05_recap",
            "type": "HISTORY_RECAP",
            "title": "前情线索要不要补一口？",
            "subtitle": "第五集承接前几集信息，适合触发前情复盘",
            "time_ms": 26_000,
            "style": "复盘卡",
            "effect_text": "补",
            "badge_text": "前情提要",
            "prompt_text": "点一下生成本集前情摘要",
            "options": [
                ("quick_recap", "30秒补剧情"),
                ("skip_recap", "不用，直接看"),
                ("character_recap", "只补人物关系"),
            ],
        },
        {
            "id": "n_074_ep05_team_up",
            "type": "SIDE_CHOICE",
            "title": "这一段你想给谁撑腰？",
            "subtitle": "站队结果会进入用户画像和讨论种子",
            "time_ms": 74_000,
            "style": "站队光环",
            "effect_text": "挺",
            "badge_text": "撑腰按钮",
            "prompt_text": "点一下，系统记录你的角色偏好",
            "options": [
                ("grandma", "太奶奶"),
                ("young_side", "年轻一辈"),
                ("neutral", "先中立观察"),
            ],
        },
        {
            "id": "n_112_ep05_comment",
            "type": "DANMAKU_REACTION",
            "title": "发一句不打断的即时评价",
            "subtitle": "轻量按钮代替手打评论，减少观看中断",
            "time_ms": 112_000,
            "style": "弹幕冲浪",
            "effect_text": "评",
            "badge_text": "一键弹幕",
            "prompt_text": "你的选择会沉淀到互动记录和讨论区",
            "options": [
                ("cool", "这段可以"),
                ("more", "还不够爽"),
                ("follow", "下一集继续"),
            ],
        },
    ],
}


def get_content_root() -> Path:
    env_path = os.environ.get("AIGC_CONTENT_ROOT")
    if env_path:
        return Path(env_path)
    return DEFAULT_CONTENT_ROOT


def _episode_no_from_id(episode_id: str) -> int | None:
    match = re.search(r"ep0*(\d+)$", episode_id, re.IGNORECASE)
    if match is None:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _read_json_document(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return document if isinstance(document, dict) else None


def _with_public_media_url(request_base_url: str | None, value: str) -> str:
    media_url = str(value or "").strip()
    if not media_url:
        return ""
    if re.match(r"^https?://", media_url, re.IGNORECASE):
        return media_url
    if media_url.startswith("/") and request_base_url:
        return f"{request_base_url.rstrip('/')}{media_url}"
    return media_url


def _normalize_cover_layer_urls(
    cover_layers: dict[str, Any],
    request_base_url: str | None,
) -> dict[str, Any]:
    normalized = dict(cover_layers)
    if "portrait_url" in normalized:
        normalized["portrait_url"] = _with_public_media_url(
            request_base_url,
            str(normalized.get("portrait_url") or ""),
        )
    return normalized


def get_drama_cover_asset_path(asset_name: str) -> Path | None:
    clean_name = str(asset_name or "").strip()
    if not clean_name or clean_name != Path(clean_name).name:
        return None
    if "/" in clean_name or "\\" in clean_name:
        return None
    asset_path = DEFAULT_DRAMA_COVER_ASSET_ROOT / clean_name
    if asset_path.suffix.lower() not in DRAMA_COVER_ALLOWED_SUFFIXES:
        return None
    try:
        asset_path.resolve().relative_to(DEFAULT_DRAMA_COVER_ASSET_ROOT.resolve())
    except ValueError:
        return None
    return asset_path


def _story_summary_cache_path(drama_id: str = DRAMA_ID) -> Path:
    return DEFAULT_VIDEO_UNDERSTANDING_ROOT / drama_id / STORY_SUMMARY_CACHE_FILE


def _story_summary_attempt_path(drama_id: str = DRAMA_ID) -> Path:
    return DEFAULT_VIDEO_UNDERSTANDING_ROOT / drama_id / STORY_SUMMARY_ATTEMPT_FILE


def _story_summary_episode_ids(drama_id: str = DRAMA_ID) -> list[str]:
    try:
        return load_drama_registry().get(drama_id).episode_ids
    except KeyError:
        if drama_id == DRAMA_ID:
            return [f"tainai3_ep{episode_no:02d}" for episode_no in range(1, 6)]
        return []


def _read_story_summary_cache(drama_id: str = DRAMA_ID) -> dict[str, Any]:
    document = _read_json_document(_story_summary_cache_path(drama_id))
    if not document or document.get("prompt_version") != STORY_SUMMARY_PROMPT_VERSION:
        return {}
    result = document.get("result")
    if not isinstance(result, dict):
        return {}

    raw_drama_description = _clean_user_facing_summary(
        str(result.get("drama_description") or result.get("description") or "").strip(),
        strip_episode_label=True,
        max_chars=STORY_SUMMARY_DRAMA_MAX_CHARS,
    )
    episodes = _normalize_story_summary_episodes(result.get("episodes"), drama_id=drama_id)
    drama_description = _ensure_story_summary_minimums(
        drama_id=drama_id,
        drama_description=raw_drama_description,
        episodes=episodes,
    )
    episodes = {
        episode_id: _ensure_episode_summary_minimum(
            summary=summary,
            drama_id=drama_id,
            episode_id=episode_id,
            drama_description=drama_description,
        )
        for episode_id, summary in episodes.items()
    }
    if not drama_description and not episodes:
        return {}
    return {
        "drama_description": drama_description,
        "episodes": episodes,
        "status": str(document.get("status") or ""),
        "model": document.get("model") if isinstance(document.get("model"), dict) else {},
        "generated_at_ms": int(document.get("generated_at_ms") or 0),
    }


def _normalize_story_summary_episodes(raw_episodes: Any, drama_id: str = DRAMA_ID) -> dict[str, str]:
    episodes: dict[str, str] = {}
    if isinstance(raw_episodes, dict):
        iterator = raw_episodes.items()
    elif isinstance(raw_episodes, list):
        iterator = (
            (str(item.get("episode_id") or item.get("episodeId") or "").strip(), item.get("summary"))
            for item in raw_episodes
            if isinstance(item, dict)
        )
    else:
        return episodes

    valid_episode_ids = set(_story_summary_episode_ids(drama_id))
    for raw_episode_id, raw_summary in iterator:
        episode_id = str(raw_episode_id or "").strip()
        if episode_id not in valid_episode_ids:
            continue
        summary = _clean_user_facing_summary(
            str(raw_summary or ""),
            strip_episode_label=False,
            max_chars=STORY_SUMMARY_EPISODE_MAX_CHARS,
        )
        if summary:
            episodes[episode_id] = summary
    return episodes


def _clean_user_facing_summary(
    summary: str,
    *,
    strip_episode_label: bool,
    max_chars: int,
) -> str:
    normalized = re.sub(r"\s+", " ", str(summary or "")).strip(" ，。；;")
    if strip_episode_label:
        normalized = _strip_episode_summary_label(normalized)
    if not _is_user_facing_plot_summary(normalized):
        return ""
    normalized = _trim_summary(normalized, max_chars).strip(" ，。；;")
    return f"{normalized}。" if normalized and normalized[-1] not in "。！？!?" else normalized


def _ensure_story_summary_minimums(
    *,
    drama_id: str,
    drama_description: str,
    episodes: dict[str, str],
) -> str:
    if len(drama_description) >= STORY_SUMMARY_DRAMA_MIN_CHARS:
        return drama_description
    expanded = _expand_drama_description(drama_id, drama_description, list(episodes.values()))
    return _clean_user_facing_summary(
        expanded,
        strip_episode_label=True,
        max_chars=STORY_SUMMARY_DRAMA_MAX_CHARS,
    )


def _ensure_episode_summary_minimum(
    *,
    summary: str,
    drama_id: str,
    episode_id: str,
    drama_description: str,
) -> str:
    if len(summary) >= STORY_SUMMARY_EPISODE_MIN_CHARS:
        return summary
    expanded = _expand_episode_summary(
        summary=summary,
        drama_id=drama_id,
        episode_id=episode_id,
        drama_description=drama_description,
    )
    return _clean_user_facing_summary(
        expanded,
        strip_episode_label=False,
        max_chars=STORY_SUMMARY_EPISODE_MAX_CHARS,
    )


def _expand_drama_description(drama_id: str, description: str, episode_summaries: list[str]) -> str:
    base = description.strip()
    try:
        config = load_drama_registry().get(drama_id)
        title = config.title
        tags = "、".join(config.tags[:3])
    except KeyError:
        title = "十八岁太奶奶驾到，重整家族荣耀第三部" if drama_id == DRAMA_ID else "这部短剧"
        tags = "家族、逆袭、短剧" if drama_id == DRAMA_ID else ""
    clean_episodes = [
        _strip_episode_summary_label(item).strip().rstrip("。")
        for item in episode_summaries
        if str(item).strip()
    ]
    episode_focus = "；".join(clean_episodes[:3])
    if not base:
        base = f"《{title}》围绕{tags or '人物关系、核心冲突和剧情反转'}展开。"
    additions = [
        f"从已接入的前几集来看，故事重点落在{episode_focus}。" if episode_focus else "",
        f"整体气质偏向{tags}，适合围绕人物立场、关键线索和情绪共鸣持续推进。" if tags else "",
        "后续看点集中在冲突升级、关系变化和关键选择带来的反转上，人物会在不断逼近的压力中暴露真实立场。",
    ]
    return " ".join([base, *[item for item in additions if item]]).strip()


def _expand_episode_summary(
    *,
    summary: str,
    drama_id: str,
    episode_id: str,
    drama_description: str,
) -> str:
    episode_no = _episode_no_from_id(episode_id) or 0
    base = _strip_episode_summary_label(summary).strip()
    if not base:
        base = f"本集继续推进{_short_drama_subject(drama_id)}的核心冲突。"
    expanded = f"{base.rstrip('。')}。{_episode_summary_tail(drama_id, episode_no)}"
    if len(expanded) < STORY_SUMMARY_EPISODE_MIN_CHARS:
        expanded = f"{expanded}{_episode_summary_extra_tail(drama_id, episode_no)}"
    if len(expanded) < STORY_SUMMARY_EPISODE_MIN_CHARS:
        expanded = f"{expanded}追看动力也继续累积。"
    return expanded


def _episode_summary_tail(drama_id: str, episode_no: int) -> str:
    subject = _short_drama_subject(drama_id)
    if "情感" in subject or "都市" in subject:
        return "情绪拉扯在对话和沉默里继续加深，人物关系也因此留下新的转折空间。"
    if "寻宝" in subject or "悬疑" in subject or "古玩" in subject:
        return "线索真假仍未完全落定，人物之间的试探让下一步行动更有悬念。"
    if "家庭" in subject or "现实" in subject:
        return "家庭立场和现实压力继续交织，后续矛盾会顺着这一刻继续发酵。"
    if episode_no > 1:
        return "它承接前面的铺垫，把人物立场和矛盾压力继续推高。"
    return "开篇先交代人物处境和主要矛盾，为后续反转留下追看动力。"


def _episode_summary_extra_tail(drama_id: str, episode_no: int) -> str:
    subject = _short_drama_subject(drama_id)
    if "情感" in subject or "都市" in subject:
        return "观众能从细节里看到双方关系的裂痕，也会期待下一次相遇如何改写局面。"
    if "寻宝" in subject or "悬疑" in subject or "古玩" in subject:
        return "观众会跟随角色继续判断线索价值，等待隐藏秘密进一步浮出水面。"
    if "家庭" in subject or "现实" in subject:
        return "观众能看到每个人的顾虑和委屈，也会期待这场家事如何继续失控。"
    if episode_no > 1:
        return "观众会继续关注谁先露出破绽，以及下一轮对峙会把局势推向哪里。"
    return "观众可以先抓住人物关系和矛盾入口，再顺着后续剧情看反转如何持续展开。"


def _short_drama_subject(drama_id: str) -> str:
    try:
        config = load_drama_registry().get(drama_id)
        if config.tags:
            return "、".join(config.tags[:2])
        return config.title
    except KeyError:
        return "剧情"


def _trim_summary(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    clipped = text[:max_chars].rstrip()
    for punctuation in ("。", "！", "？", "；", ";"):
        index = clipped.rfind(punctuation)
        if index >= max_chars * 0.55:
            return clipped[: index + 1]
    return clipped.rstrip(" ，。；;") + "…"


def _build_static_drama_seed() -> dict[str, Any]:
    return {
        "drama_id": DRAMA_ID,
        "title": "十八岁太奶奶驾到，重整家族荣耀第三部",
        "cover_url": "",
        "cover_style": "family_reversal_poster",
        "cover_badge": "高能逆袭",
        "cover_hook": "十八岁外表，太奶奶气场回归纪家",
        "cover_palette": {
            "primary": "#25130F",
            "secondary": "#8A4F22",
            "accent": "#F8D36D",
        },
        "cover_layers": {
            "portrait_url": "",
            "identity_label": "身份反转",
            "heat_label": "178.8万人想看",
            "share_hint": "生成同款打卡图",
        },
        "description": _ensure_story_summary_minimums(
            drama_id=DRAMA_ID,
            drama_description=DRAMA_PLOT_DESCRIPTION,
            episodes={
                f"tainai3_ep{episode_no:02d}": summary
                for episode_no, summary in EPISODE_SUMMARIES.items()
            },
        ),
        "tags": ["家族", "逆袭", "短剧"],
        "latest_episode_no": 5,
        "interaction_hint": "剧情简介已预生成并缓存，播放时直接加载",
        "characters": [
            {
                "character_id": "char_grandma",
                "name": "太奶奶",
                "canonical_name": "容遇",
                "aliases": ["太奶奶", "容玉", "荣遇"],
                "role_type": "lead",
                "avatar_url": "",
            },
            {
                "character_id": "char_grandson",
                "name": "家族少爷",
                "canonical_name": "家族少爷",
                "aliases": ["少爷", "少爷们", "大少爷", "二少爷", "三少爷", "季家少爷"],
                "role_type": "family_group",
                "avatar_url": "",
            },
        ],
    }


def _build_static_episode_seed(episode_no: int) -> dict[str, Any]:
    episode_id = f"tainai3_ep{episode_no:02d}"
    return {
        "episode_id": episode_id,
        "episode_no": episode_no,
        "title": f"第{episode_no}集",
        "duration_ms": EPISODE_DURATIONS_MS[episode_no],
        "file_name": f"第{episode_no}集.mp4",
        "summary": _ensure_episode_summary_minimum(
            summary=EPISODE_SUMMARIES[episode_no],
            drama_id=DRAMA_ID,
            episode_id=episode_id,
            drama_description=DRAMA_PLOT_DESCRIPTION,
        ),
    }


def _build_registry_drama_seed(
    config: DramaConfig,
    *,
    request_base_url: str | None = None,
) -> dict[str, Any]:
    story_cache = _read_story_summary_cache(config.drama_id)
    cached_drama_description = str(story_cache.get("drama_description") or "").strip()
    cover_url = _with_public_media_url(request_base_url, config.cover)
    cover_layers = dict(
        config.cover_layers
        or {
            "identity_label": config.cover_badge or "新剧接入",
            "heat_label": "待视频理解预热",
            "share_hint": "",
        }
    )
    if not str(cover_layers.get("portrait_url") or "").strip():
        cover_layers["portrait_url"] = config.cover
    cover_layers = _normalize_cover_layer_urls(cover_layers, request_base_url)
    return {
        "drama_id": config.drama_id,
        "title": config.title,
        "cover_url": cover_url,
        "cover_style": config.cover_style or "registry_ingest_poster",
        "cover_badge": config.cover_badge or "新剧接入",
        "cover_hook": config.cover_hook or "等待视频理解生成专属爽点",
        "cover_palette": config.cover_palette
        or {
            "primary": "#182033",
            "secondary": "#465A87",
            "accent": "#F2C96D",
        },
        "cover_layers": cover_layers,
        "description": cached_drama_description
        or config.description
        or f"{config.title} 已接入短剧注册表，可通过视频理解预热生成剧情简介和互动节点。",
        "tags": list(config.tags),
        "latest_episode_no": config.latest_episode_no,
        "interaction_hint": (
            "剧情简介已预生成并缓存，播放时直接加载"
            if cached_drama_description
            else config.interaction_hint or "新短剧已接入内容目录，完成视频理解预热后可生成互动时间线"
        ),
        "characters": [],
    }


def _build_registry_episode_seed(
    config: DramaConfig,
    episode_no: int,
    *,
    request_base_url: str | None = None,
) -> dict[str, Any]:
    episode_id = f"{config.episode_id_prefix}{episode_no:02d}"
    source_episode_no = config.source_episode_no(episode_no)
    summary, _ = _resolve_episode_summary_with_source(
        episode_id,
        request_base_url=request_base_url,
        ensure_generated=False,
        drama_id=config.drama_id,
    )
    return {
        "episode_id": episode_id,
        "episode_no": source_episode_no,
        "logical_episode_no": episode_no,
        "title": f"第{source_episode_no}集",
        "duration_ms": config.episode_duration_for(episode_no),
        "file_name": _format_episode_file_name(config, episode_no),
        "summary": summary or config.episode_summary_for(episode_no) or "本集已接入内容目录，等待视频理解生成剧情简介。",
        "content_root": config.content_root,
        "drama_id": config.drama_id,
    }


def _format_episode_file_name(config: DramaConfig, episode_no: int) -> str:
    source_episode_no = config.source_episode_no(episode_no)
    try:
        return config.episode_file_pattern.format(
            episode_no=episode_no,
            episodeNo=episode_no,
            logical_episode_no=episode_no,
            logicalEpisodeNo=episode_no,
            source_episode_no=source_episode_no,
            sourceEpisodeNo=source_episode_no,
        )
    except (KeyError, IndexError, ValueError):
        return f"第{source_episode_no}集.mp4"


def build_drama_registry_status() -> dict[str, Any]:
    registry = load_drama_registry()
    items: list[dict[str, Any]] = []
    for config in registry.list_all():
        missing_episode_files: list[dict[str, Any]] = []
        media_ready_count = 0
        for episode_no, episode_id in enumerate(config.episode_ids, start=1):
            file_name = _format_episode_file_name(config, episode_no)
            source_episode_no = config.source_episode_no(episode_no)
            if (config.content_root / file_name).exists():
                media_ready_count += 1
            else:
                missing_episode_files.append(
                    {
                        "episode_id": episode_id,
                        "episode_no": source_episode_no,
                        "logical_episode_no": episode_no,
                        "file_name": file_name,
                    }
                )
        ready = config.content_root.exists() and not missing_episode_files
        items.append(
            {
                "drama_id": config.drama_id,
                "title": config.title,
                "episode_count": config.episode_count,
                "episode_number_start": config.episode_number_start,
                "latest_episode_no": config.latest_episode_no,
                "episode_ids": config.episode_ids,
                "content_root_exists": config.content_root.exists(),
                "media_ready_count": media_ready_count,
                "missing_episode_files": missing_episode_files,
                "ready": ready,
            }
        )
    load_errors = [
        {
            "file_name": Path(str(error.get("path") or "")).name,
            "error": str(error.get("error") or ""),
        }
        for error in registry.load_errors
    ]
    return {
        "total_count": len(items),
        "ready_count": sum(1 for item in items if item["ready"]),
        "items": items,
        "load_errors": load_errors,
        "load_error_count": len(load_errors),
    }


def _load_video_understanding_envelope(
    episode_id: str,
    *,
    request_base_url: str | None = None,
    ensure_generated: bool = False,
) -> dict[str, Any] | None:
    try:
        drama_id = load_drama_registry().find_by_episode_id(episode_id).drama_id
    except KeyError:
        drama_id = DRAMA_ID
    for file_name in ("latest_success.json", "understanding.json"):
        document = _read_json_document(DEFAULT_VIDEO_UNDERSTANDING_ROOT / drama_id / episode_id / file_name)
        if document is None:
            document = _read_json_document(DEFAULT_VIDEO_UNDERSTANDING_ROOT / episode_id / file_name)
        if document is None:
            continue
        envelope = document.get("envelope")
        if isinstance(envelope, dict):
            result = envelope.get("result")
            if (
                document.get("prompt_version")
                and document.get("prompt_version") != VIDEO_UNDERSTANDING_STORY_PROMPT_VERSION
                and isinstance(result, dict)
                and not any(result.get(key) for key in ("story_summary", "plot_summary", "synopsis"))
            ):
                continue
            return envelope

    if not ensure_generated or not request_base_url:
        return None

    try:
        from backend.app.video_understanding_service import get_video_understanding_service

        envelope = get_video_understanding_service().analyze_episode(
            {
                "episodeId": episode_id,
                "dramaId": drama_id,
                "forceRefresh": False,
            },
            request_base_url,
        )
    except Exception:
        return None

    return envelope if isinstance(envelope, dict) else None


def _resolve_episode_summary(
    episode_id: str,
    *,
    request_base_url: str | None = None,
    ensure_generated: bool = False,
) -> str:
    summary, _ = _resolve_episode_summary_with_source(
        episode_id,
        request_base_url=request_base_url,
        ensure_generated=ensure_generated,
    )
    return summary


def _resolve_episode_summary_with_source(
    episode_id: str,
    *,
    request_base_url: str | None = None,
    ensure_generated: bool = False,
    drama_id: str = DRAMA_ID,
) -> tuple[str, bool]:
    story_cache = _read_story_summary_cache(drama_id)
    cached_episode_summaries = story_cache.get("episodes") if isinstance(story_cache.get("episodes"), dict) else {}
    cached_summary = str(cached_episode_summaries.get(episode_id) or "").strip()
    drama_description = str((story_cache.get("drama_description") if isinstance(story_cache, dict) else "") or "")
    if not drama_description and drama_id == DRAMA_ID:
        drama_description = DRAMA_PLOT_DESCRIPTION
    if cached_summary:
        return _ensure_episode_summary_minimum(
            summary=cached_summary,
            drama_id=drama_id,
            episode_id=episode_id,
            drama_description=drama_description,
        ), True

    envelope = _load_video_understanding_envelope(
        episode_id,
        request_base_url=request_base_url,
        ensure_generated=ensure_generated,
    )
    if envelope is not None:
        result = envelope.get("result")
        if isinstance(result, dict):
            summary = _extract_user_facing_story_summary(result)
            if summary:
                return _ensure_episode_summary_minimum(
                    summary=summary,
                    drama_id=drama_id,
                    episode_id=episode_id,
                    drama_description=drama_description,
                ), True

    if drama_id != DRAMA_ID:
        return "", False

    episode_no = _episode_no_from_id(episode_id)
    if episode_no is None:
        return "", False
    return _ensure_episode_summary_minimum(
        summary=str(EPISODE_SUMMARIES.get(episode_no, "")).strip(),
        drama_id=drama_id,
        episode_id=episode_id,
        drama_description=drama_description,
    ), False


def _extract_user_facing_story_summary(result: dict[str, Any]) -> str:
    for key in ("story_summary", "plot_summary", "synopsis", "summary"):
        summary = str(result.get(key) or "").strip()
        if summary and _is_user_facing_plot_summary(summary):
            return summary
    segments = result.get("segments")
    if isinstance(segments, list) and segments:
        first_segment = segments[0]
        if isinstance(first_segment, dict):
            summary = str(first_segment.get("story_summary") or first_segment.get("dialogue_summary") or "").strip()
            if summary and _is_user_facing_plot_summary(summary):
                return summary
    return ""


def _is_user_facing_plot_summary(summary: str) -> bool:
    normalized = summary.strip()
    if not normalized:
        return False
    return not any(marker in normalized for marker in TECHNICAL_SUMMARY_MARKERS)


def _build_drama_description_from_summaries(summaries: list[str]) -> str:
    cleaned = [
        _strip_episode_summary_label(summary).strip().rstrip("。")
        for summary in summaries
        if summary and summary.strip()
    ]
    if not cleaned:
        return DRAMA_PLOT_DESCRIPTION
    core_conflict = "被晚辈质疑身份、在试探中逐步掌控纪家局面"
    if any("外部" in summary or "危机" in summary for summary in cleaned):
        core_conflict = "在身份误会、家族内斗和外部危机之间重新夺回主动权"
    return (
        "1955年，容遇教授意外身故后醒来，发现自己穿到了七十年后的同名十八岁少女身上。"
        f"她以年轻外表回到早已物是人非的纪家，却要面对{core_conflict}。"
        "这部短剧主打穿越身份反差、家族逆袭和连续打脸爽点，容遇既要找回亲情，也要把纪家重新带回荣耀巅峰。"
    )


def _strip_episode_summary_label(summary: str) -> str:
    return re.sub(r"^第\s*\d+\s*集\s*[｜|]\s*", "", summary.strip())


def warm_story_summary_cache(
    request_base_url: str | None = None,
    *,
    force_refresh: bool = False,
    drama_id: str = DRAMA_ID,
) -> dict[str, Any]:
    cached = _read_story_summary_cache(drama_id)
    if cached and not force_refresh:
        return cached

    base_url = (request_base_url or os.environ.get("AIGC_PUBLIC_BASE_URL") or "http://127.0.0.1:8000").strip()
    episode_items = _collect_story_summary_inputs(base_url, drama_id=drama_id)
    fallback_result = _build_local_story_summary_result(episode_items, drama_id=drama_id)
    status = "degraded"
    degrade_reason = "远端模型不可用，已使用本地平台文案兜底"
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    model_info: dict[str, Any] = {
        "provider": "local",
        "model_name": "local-story-summary-rule",
        "endpoint_id": "",
        "base_url": "",
    }
    result = fallback_result
    latency_ms = 0

    prompt_context = {
        "drama": {
            "dramaId": drama_id,
            "title": (get_drama_by_id(drama_id, base_url) or _build_static_drama_seed())["title"],
            "baseDescription": (get_drama_by_id(drama_id, base_url) or {}).get("description") or DRAMA_PLOT_DESCRIPTION,
        },
        "episode_summaries": episode_items,
        "request": {
            "dramaId": drama_id,
            "style": "短剧平台剧情简介",
            "rules": [
                "整剧简介必须重写为整部剧主线概括，不能逐集罗列或拼接单集简介",
                "单集简介必须只写当前集剧情，不要出现 speaker、ASR、OCR、关键帧、识别、证据、模型等词",
                "不得新增输入中没有出现的职业、技能、人物关系或剧情设定",
                "文案面向观众展示，允许悬念和爽点表达，但不要技术解释",
            ],
        },
    }

    try:
        from backend.app.ai_service import get_ai_service

        ai_service = get_ai_service()
        model_info = ai_service._model_info()
        start_ms = int(time.time() * 1000)
        if not ai_service._remote_model_enabled():
            degrade_reason = "远端模型默认关闭，已使用本地平台文案兜底"
        else:
            messages = _build_story_summary_messages(prompt_context)
            response = ai_service._call_chat_completion_best_effort(
                capability="content.story_summary",
                messages=messages,
                max_tokens=1200,
                temperature=0.28,
            )
            parsed = ai_service._parse_model_result(response)
            if parsed is None:
                raw_text = ai_service._extract_model_text(response)
                if not raw_text:
                    raise ValueError("invalid model response")
                parsed = {"drama_description": raw_text}
            result = _normalize_story_summary_result(parsed, fallback_result, drama_id=drama_id)
            status = "ok"
            degrade_reason = ""
            usage = ai_service._extract_usage(response)
        latency_ms = int(time.time() * 1000) - start_ms
        envelope = ai_service._decorate_response(
            capability="content.story_summary",
            result=result,
            status=status,
            latency_ms=latency_ms,
            usage=usage,
            cache_hit=False,
            model_info=model_info,
            degrade_reason=degrade_reason or None,
        )
        ai_service._append_audit(
            capability="content.story_summary",
            payload=prompt_context,
            envelope=envelope,
            prompt_version=STORY_SUMMARY_PROMPT_VERSION,
        )
        result = _normalize_story_summary_result(envelope.get("result", result), fallback_result, drama_id=drama_id)
        model_info = envelope.get("model", model_info) if isinstance(envelope.get("model"), dict) else model_info
    except Exception as exc:
        degrade_reason = str(exc) or degrade_reason
        latency_ms = max(latency_ms, 0)
        result = fallback_result

    document = _write_story_summary_cache(
        result=result,
        fallback_result=fallback_result,
        status=status,
        model_info=model_info,
        usage=usage,
        latency_ms=latency_ms,
        degrade_reason=degrade_reason,
        drama_id=drama_id,
    )
    return _normalize_story_summary_cache_document(document, drama_id=drama_id)


def _collect_story_summary_inputs(request_base_url: str, drama_id: str = DRAMA_ID) -> list[dict[str, Any]]:
    episode_items: list[dict[str, Any]] = []
    try:
        config = load_drama_registry().get(drama_id)
    except KeyError:
        config = load_drama_registry().get(DRAMA_ID)
    for episode_no, episode_id in enumerate(config.episode_ids, start=1):
        summary = ""
        envelope = _load_video_understanding_envelope(
            episode_id,
            request_base_url=request_base_url,
            ensure_generated=False,
        )
        if envelope is not None:
            result = envelope.get("result")
            if isinstance(result, dict):
                summary = _extract_user_facing_story_summary(result)
        if not summary:
            if drama_id == DRAMA_ID:
                summary = str(EPISODE_SUMMARIES.get(episode_no, "")).strip()
            else:
                summary = str(
                    _build_registry_episode_seed(config, episode_no, request_base_url=request_base_url).get("summary")
                    or ""
                ).strip()
        episode_items.append(
            {
                "episode_id": episode_id,
                "episode_no": episode_no,
                "title": f"第{episode_no}集",
                "summary": _clean_user_facing_summary(
                    summary,
                    strip_episode_label=False,
                    max_chars=STORY_SUMMARY_EPISODE_MAX_CHARS,
                ),
            }
        )
    return episode_items


def _build_local_story_summary_result(episode_items: list[dict[str, Any]], drama_id: str = DRAMA_ID) -> dict[str, Any]:
    summaries = [
        str(item.get("summary") or "").strip()
        for item in episode_items
        if str(item.get("summary") or "").strip()
    ]
    return {
        "drama_description": _build_drama_description_from_summaries(summaries),
        "episodes": [
            {
                "episode_id": str(item.get("episode_id") or f"tainai3_ep{int(item.get('episode_no') or 1):02d}"),
                "summary": _clean_user_facing_summary(
                    str(item.get("summary") or ""),
                    strip_episode_label=False,
                    max_chars=STORY_SUMMARY_EPISODE_MAX_CHARS,
                ),
            }
            for item in episode_items
        ],
    }


def _build_story_summary_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "你是短剧平台剧情文案编辑。只输出 JSON，不要 Markdown，不要解释。"
                "整剧简介要像短剧详情页介绍，重写整部剧主线，不能把每集简介拼接起来。"
                "每集简介要像选集页简介，只概括当前集剧情和悬念。"
                "只能使用输入里已有的人物、能力和剧情信息，不要自行补充医术、商业、复仇等未出现设定。"
                "禁止出现 speaker、ASR、OCR、关键帧、识别、证据、模型、对话识别等技术词。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "task": "content.story_summary",
                    "prompt_version": STORY_SUMMARY_PROMPT_VERSION,
                    "output_schema": {
                        "drama_description": "string，180-260字，整部剧总剧情介绍",
                        "episodes": [
                            {
                                "episode_id": "string",
                                "summary": "string，80-140字，当前集剧情介绍",
                            }
                        ],
                    },
                    "context": context,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        },
    ]


def _normalize_story_summary_result(
    parsed: dict[str, Any],
    fallback: dict[str, Any],
    drama_id: str = DRAMA_ID,
) -> dict[str, Any]:
    result = parsed.get("result") if isinstance(parsed.get("result"), dict) else parsed
    if not isinstance(result, dict):
        result = {}
    fallback_description = str(fallback.get("drama_description") or DRAMA_PLOT_DESCRIPTION).strip()
    drama_description = _clean_user_facing_summary(
        str(
            result.get("drama_description")
            or result.get("dramaDescription")
            or result.get("description")
            or ""
        ),
        strip_episode_label=True,
        max_chars=STORY_SUMMARY_DRAMA_MAX_CHARS,
    )
    episode_map = _normalize_story_summary_episodes(
        result.get("episodes")
        or result.get("episode_summaries")
        or result.get("episodeSummaries"),
        drama_id=drama_id,
    )
    fallback_episode_map = _normalize_story_summary_episodes(fallback.get("episodes"), drama_id=drama_id)
    for episode_id, fallback_summary in fallback_episode_map.items():
        episode_map.setdefault(episode_id, fallback_summary)
    episode_ids = _story_summary_episode_ids(drama_id)
    normalized_description = _ensure_story_summary_minimums(
        drama_id=drama_id,
        drama_description=drama_description or fallback_description,
        episodes=episode_map,
    )
    normalized_episode_map = {
        episode_id: _ensure_episode_summary_minimum(
            summary=episode_map.get(
                episode_id,
                str(EPISODE_SUMMARIES.get(_episode_no_from_id(episode_id) or 0, "")),
            ),
            drama_id=drama_id,
            episode_id=episode_id,
            drama_description=normalized_description,
        )
        for episode_id in episode_ids
    }
    return {
        "drama_description": normalized_description,
        "episodes": [
            {
                "episode_id": episode_id,
                "summary": normalized_episode_map.get(episode_id, ""),
            }
            for episode_id in episode_ids
        ],
    }


def _write_story_summary_cache(
    *,
    result: dict[str, Any],
    fallback_result: dict[str, Any],
    status: str,
    model_info: dict[str, Any],
    usage: dict[str, int],
    latency_ms: int,
    degrade_reason: str,
    drama_id: str = DRAMA_ID,
) -> dict[str, Any]:
    generated_at_ms = int(time.time() * 1000)
    document = {
        "schema_version": "1.0",
        "prompt_version": STORY_SUMMARY_PROMPT_VERSION,
        "generated_at_ms": generated_at_ms,
        "status": status,
        "model": model_info,
        "usage": usage,
        "latency_ms": max(int(latency_ms), 0),
        "degrade_reason": degrade_reason if status != "ok" else "",
        "result": _normalize_story_summary_result(result, fallback_result, drama_id=drama_id),
    }
    cache_path = _story_summary_cache_path(drama_id)
    attempt_path = _story_summary_attempt_path(drama_id)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    attempt_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    existing_success = _read_story_summary_cache(drama_id)
    if status == "ok" or not existing_success:
        cache_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
        return document
    existing_document = _read_json_document(cache_path)
    return existing_document if existing_document is not None else document


def _normalize_story_summary_cache_document(document: dict[str, Any], drama_id: str = DRAMA_ID) -> dict[str, Any]:
    normalized = _read_story_summary_cache(drama_id)
    if normalized:
        return normalized
    result = document.get("result") if isinstance(document.get("result"), dict) else {}
    return {
        "drama_description": str(result.get("drama_description") or DRAMA_PLOT_DESCRIPTION),
        "episodes": _normalize_story_summary_episodes(result.get("episodes"), drama_id=drama_id),
        "status": str(document.get("status") or ""),
        "model": document.get("model") if isinstance(document.get("model"), dict) else {},
        "generated_at_ms": int(document.get("generated_at_ms") or 0),
    }


def _story_summary_document_status(
    document: dict[str, Any] | None,
    source: str,
    drama_id: str = DRAMA_ID,
) -> dict[str, Any]:
    if not isinstance(document, dict):
        return {
            "source": source,
            "status": "missing",
            "generated_at": 0,
            "generated_at_ms": 0,
            "model_name": "",
            "latency_ms": 0,
            "degrade_reason": "",
            "drama_description": "",
            "episodes": [],
        }
    result = document.get("result") if isinstance(document.get("result"), dict) else {}
    model = document.get("model") if isinstance(document.get("model"), dict) else {}
    raw_drama_description = _clean_user_facing_summary(
        str(result.get("drama_description") or result.get("description") or ""),
        strip_episode_label=True,
        max_chars=STORY_SUMMARY_DRAMA_MAX_CHARS,
    )
    episode_map = _normalize_story_summary_episodes(result.get("episodes"), drama_id=drama_id)
    drama_description = _ensure_story_summary_minimums(
        drama_id=drama_id,
        drama_description=raw_drama_description,
        episodes=episode_map,
    )
    episode_map = {
        episode_id: _ensure_episode_summary_minimum(
            summary=summary,
            drama_id=drama_id,
            episode_id=episode_id,
            drama_description=drama_description,
        )
        for episode_id, summary in episode_map.items()
    }
    if not drama_description or not episode_map:
        return {
            "source": source,
            "status": "missing",
            "generated_at": 0,
            "generated_at_ms": 0,
            "model_name": "",
            "latency_ms": 0,
            "degrade_reason": "",
            "drama_description": "",
            "episodes": [],
        }
    episode_ids = _story_summary_episode_ids(drama_id)
    return {
        "source": source,
        "status": str(document.get("status") or "unknown"),
        "generated_at": int(document.get("generated_at_ms") or 0),
        "generated_at_ms": int(document.get("generated_at_ms") or 0),
        "model_name": str(model.get("model_name") or model.get("provider") or ""),
        "latency_ms": int(document.get("latency_ms") or 0),
        "degrade_reason": str(document.get("degrade_reason") or ""),
        "drama_description": drama_description,
        "episodes": [
            {
                "episode_id": episode_id,
                "episode_no": _episode_no_from_id(episode_id) or index,
                "summary": episode_map.get(episode_id, ""),
            }
            for index, episode_id in enumerate(episode_ids, start=1)
            if episode_map.get(episode_id, "")
        ],
    }


def build_story_summary_cache_status(
    request_base_url: str | None = None,
    drama_id: str = DRAMA_ID,
) -> dict[str, Any]:
    success_document = _read_json_document(_story_summary_cache_path(drama_id))
    attempt_document = _read_json_document(_story_summary_attempt_path(drama_id))
    current = _story_summary_document_status(success_document, "latest_success", drama_id=drama_id)
    if current["status"] == "missing":
        fallback_result = _build_local_story_summary_result(
            _collect_story_summary_inputs(
                (request_base_url or os.environ.get("AIGC_PUBLIC_BASE_URL") or "http://127.0.0.1:8000").strip(),
                drama_id=drama_id,
            ),
            drama_id=drama_id,
        )
        current = _story_summary_document_status(
            {
                "prompt_version": STORY_SUMMARY_PROMPT_VERSION,
                "status": "local_fallback",
                "generated_at_ms": 0,
                "model": {"model_name": "local-story-summary-rule"},
                "latency_ms": 0,
                "degrade_reason": "尚未生成缓存，当前展示本地平台文案兜底",
                "result": fallback_result,
            },
            "local_fallback",
            drama_id=drama_id,
        )
    latest_attempt = _story_summary_document_status(attempt_document, "latest_attempt", drama_id=drama_id)
    return {
        "drama_id": drama_id,
        "prompt_version": STORY_SUMMARY_PROMPT_VERSION,
        **current,
        "latest_attempt": latest_attempt,
        "cache_policy": {
            "success_result_versioned": True,
            "degraded_attempt_does_not_override_success": True,
            "success_file": STORY_SUMMARY_CACHE_FILE,
            "attempt_file": STORY_SUMMARY_ATTEMPT_FILE,
        },
    }


def refresh_story_summary_cache(request_base_url: str | None = None, drama_id: str = DRAMA_ID) -> dict[str, Any]:
    warm_story_summary_cache(request_base_url, force_refresh=True, drama_id=drama_id)
    return build_story_summary_cache_status(request_base_url, drama_id=drama_id)


def build_quality_evaluation_report(request_base_url: str | None = None) -> dict[str, Any]:
    summary_status = build_story_summary_cache_status(request_base_url)
    timed_payload = build_timed_events(request_base_url or "", "tainai3_ep01") or {}
    highlight_payload = build_home_highlight_feed(request_base_url or "", size=6, strategy="heat_score_desc_v1") or {}
    generation_tasks = [
        task
        for task in (
            get_runtime_store().get_latest_success_generation_task("story_continuation_video", "tainai3_ep01"),
            get_runtime_store().get_latest_success_generation_task("checkin_card", "tainai3_ep01"),
        )
        if task is not None
    ]
    return build_quality_report_payload(
        summary_status=summary_status,
        timed_payload=timed_payload,
        highlight_payload=highlight_payload,
        generation_tasks=generation_tasks,
        generated_at_ms=int(time.time() * 1000),
    )


def _build_drama_seed(
    *,
    request_base_url: str | None = None,
    ensure_generated: bool = False,
) -> dict[str, Any]:
    drama = _build_static_drama_seed()
    story_cache = _read_story_summary_cache()
    cached_drama_description = str(story_cache.get("drama_description") or "").strip()
    if cached_drama_description:
        drama["description"] = cached_drama_description
        drama["interaction_hint"] = "剧情简介已预生成并缓存，播放时直接加载"
        return drama

    episode_summaries: list[str] = []
    has_cached_summary = False
    for episode_no in range(1, 6):
        summary, summary_from_cache = _resolve_episode_summary_with_source(
            f"tainai3_ep{episode_no:02d}",
            request_base_url=request_base_url,
            ensure_generated=ensure_generated,
        )
        episode_summaries.append(summary)
        has_cached_summary = has_cached_summary or summary_from_cache
    if has_cached_summary:
        generated_description = _build_drama_description_from_summaries(episode_summaries)
        if generated_description:
            drama["description"] = generated_description
        drama["interaction_hint"] = "剧情简介已预生成并缓存，播放时直接加载"
    return drama


def _build_episode_seed(
    episode_no: int,
    *,
    request_base_url: str | None = None,
    ensure_generated: bool = False,
) -> dict[str, Any]:
    episode = _build_static_episode_seed(episode_no)
    summary = _resolve_episode_summary(
        episode["episode_id"],
        request_base_url=request_base_url,
        ensure_generated=ensure_generated,
    )
    if summary:
        episode["summary"] = summary
    return episode


def get_drama_seed(
    request_base_url: str | None = None,
    ensure_generated: bool = False,
) -> dict[str, Any]:
    return _build_drama_seed(
        request_base_url=request_base_url,
        ensure_generated=ensure_generated,
    )


def get_episode_seeds(
    request_base_url: str | None = None,
    ensure_generated: bool = False,
) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    for episode_no in range(1, 6):
        episodes.append(
            _build_episode_seed(
                episode_no,
                request_base_url=request_base_url,
                ensure_generated=ensure_generated,
            )
        )
    return episodes


def warm_video_understanding_cache(
    request_base_url: str | None = None,
    episode_ids: list[str] | None = None,
) -> list[str]:
    base_url = (request_base_url or os.environ.get("AIGC_PUBLIC_BASE_URL") or "http://127.0.0.1:8000").strip()
    if not base_url:
        base_url = "http://127.0.0.1:8000"
    target_episode_ids = episode_ids or [f"tainai3_ep{episode_no:02d}" for episode_no in range(1, 6)]
    try:
        from backend.app.video_understanding_service import get_video_understanding_service
    except Exception:
        return []

    service = get_video_understanding_service()
    warmed_episode_ids: list[str] = []
    for episode_id in target_episode_ids:
        try:
            service.analyze_episode(
                {
                    "episodeId": episode_id,
                    "dramaId": DRAMA_ID,
                    "forceRefresh": False,
                },
                base_url,
            )
            warmed_episode_ids.append(episode_id)
        except Exception:
            continue
    try:
        warm_story_summary_cache(base_url)
    except Exception:
        pass
    return warmed_episode_ids


def _with_play_url(request_base_url: str, episode_id: str) -> str:
    return f"{request_base_url.rstrip('/')}/media/episodes/{episode_id}"


def _with_hls_url(request_base_url: str, episode_id: str) -> str:
    return f"{request_base_url.rstrip('/')}/media/hls/{episode_id}/index.m3u8"


def list_home_items(request_base_url: str, size: int = 10) -> list[dict[str, Any]]:
    profile = get_runtime_store().build_user_profile()
    items: list[dict[str, Any]] = []
    for config in load_drama_registry().list_all():
        drama = (
            get_drama_seed(request_base_url=request_base_url, ensure_generated=False)
            if config.drama_id == DRAMA_ID
            else _build_registry_drama_seed(config, request_base_url=request_base_url)
        )
        first_episode_id = config.episode_ids[0] if config.episode_ids else ""
        content_source = "cache" if config.drama_id == DRAMA_ID and _read_story_summary_cache() else "backend"
        if config.drama_id != DRAMA_ID:
            content_source = "registry"
        items.append(
            {
                "drama_id": drama["drama_id"],
                "title": drama["title"],
                "cover_url": drama["cover_url"],
                "cover_style": drama["cover_style"],
                "cover_badge": drama["cover_badge"],
                "cover_hook": drama["cover_hook"],
                "cover_palette": drama["cover_palette"],
                "cover_layers": build_cover_layers(drama, request_base_url, primary_drama_id=DRAMA_ID),
                "description": drama["description"],
                "tags": drama["tags"],
                "latest_episode_no": drama["latest_episode_no"],
                "interaction_hint": drama["interaction_hint"],
                "play_url": _with_play_url(request_base_url, first_episode_id),
                "content_source": content_source,
                "recommend_reason": str(profile.get("recommendReason") or "基于观看和互动行为推荐"),
            }
        )
    return items[: max(size, 0)]




def get_drama_by_id(
    drama_id: str,
    request_base_url: str | None = None,
    ensure_generated: bool = False,
) -> dict[str, Any] | None:
    try:
        config = load_drama_registry().get(drama_id)
    except KeyError:
        return None
    if config.drama_id != DRAMA_ID:
        return _build_registry_drama_seed(config, request_base_url=request_base_url)
    return get_drama_seed(
        request_base_url=request_base_url,
        ensure_generated=ensure_generated,
    )


def list_episodes(drama_id: str, request_base_url: str) -> list[dict[str, Any]] | None:
    try:
        config = load_drama_registry().get(drama_id)
    except KeyError:
        return None
    if config.drama_id != DRAMA_ID:
        return [
            {
                "episode_id": episode["episode_id"],
                "episode_no": episode["episode_no"],
                "title": episode["title"],
                "duration_ms": episode["duration_ms"],
                "summary": episode["summary"],
                "play_url": _with_play_url(request_base_url, episode["episode_id"]),
            }
            for episode in (
                _build_registry_episode_seed(config, episode_no, request_base_url=request_base_url)
                for episode_no in range(1, config.episode_count + 1)
            )
        ]
    episodes: list[dict[str, Any]] = []
    for episode in get_episode_seeds(request_base_url=request_base_url, ensure_generated=False):
        episodes.append(
            {
                "episode_id": episode["episode_id"],
                "episode_no": episode["episode_no"],
                "title": episode["title"],
                "duration_ms": episode["duration_ms"],
                "summary": episode["summary"],
                "play_url": _with_play_url(request_base_url, episode["episode_id"]),
            }
        )
    return episodes


def get_episode_by_id(
    episode_id: str,
    request_base_url: str | None = None,
    ensure_generated: bool = False,
) -> dict[str, Any] | None:
    try:
        config = load_drama_registry().find_by_episode_id(episode_id)
    except KeyError:
        return None
    if config.drama_id != DRAMA_ID:
        episode_no = _episode_no_from_id(episode_id)
        if episode_no is None or episode_no < 1 or episode_no > config.episode_count:
            return None
        return _build_registry_episode_seed(config, episode_no, request_base_url=request_base_url)
    for episode in get_episode_seeds(request_base_url=request_base_url, ensure_generated=ensure_generated):
        if episode["episode_id"] == episode_id:
            return episode
    return None


def get_episode_file_path(episode_id: str) -> Path | None:
    episode = get_episode_by_id(episode_id)
    if episode is None:
        return None
    content_root = episode.get("content_root")
    root = Path(content_root) if content_root else get_content_root()
    return root / str(episode["file_name"])


def get_hls_root() -> Path:
    env_path = os.environ.get("AIGC_HLS_ROOT", "").strip()
    return Path(env_path) if env_path else DEFAULT_HLS_ROOT


def get_hls_asset_path(episode_id: str, asset_name: str) -> Path | None:
    if get_episode_by_id(episode_id) is None:
        return None
    if "/" in asset_name or "\\" in asset_name or asset_name in {"", ".", ".."}:
        return None
    asset_path = get_hls_root() / episode_id / asset_name
    try:
        asset_path.resolve().relative_to((get_hls_root() / episode_id).resolve())
    except ValueError:
        return None
    return asset_path


def get_hls_index_path(episode_id: str) -> Path | None:
    return get_hls_asset_path(episode_id, "index.m3u8")


def build_play_response(request_base_url: str, episode_id: str) -> dict[str, Any] | None:
    episode = get_episode_by_id(episode_id)
    if episode is None:
        return None
    hls_index = get_hls_index_path(episode_id)
    hls_available = bool(hls_index and hls_index.exists())
    hls_url = _with_hls_url(request_base_url, episode["episode_id"])
    return {
        "episode_id": episode["episode_id"],
        "episode_no": episode["episode_no"],
        "title": episode["title"],
        "duration_ms": episode["duration_ms"],
        "play_url": _with_play_url(request_base_url, episode["episode_id"]),
        "hls_url": hls_url,
        "hls_available": hls_available,
        "preferred_play_url": hls_url if hls_available else _with_play_url(request_base_url, episode["episode_id"]),
        "expire_at_ms": 1_900_000_000_000,
    }


def build_interaction_nodes(request_base_url: str, episode_id: str) -> dict[str, Any] | None:
    episode = get_episode_by_id(episode_id)
    if episode is None:
        return None
    drama_id = str(episode.get("drama_id") or DRAMA_ID)
    drama = get_drama_by_id(drama_id) or get_drama_seed()
    play_url = _with_play_url(request_base_url, episode_id)
    nodes = _build_episode_nodes(episode_id, str(request_base_url), str(episode["summary"]))
    if _should_publish_reviewed_danmaku():
        nodes.extend(_build_reviewed_danmaku_nodes(episode_id))
    for node in nodes:
        apply_interaction_component_metadata(node, episode_id)
    nodes.sort(key=lambda item: int(item.get("trigger", {}).get("timeMs", 0) or 0))
    generation_pipeline = _build_interaction_generation_pipeline(episode_id, nodes)
    nodes = [
        node
        for node in nodes
        if str(node.get("generation", {}).get("reviewStatus") or "accepted") != "rejected"
    ]
    for node in nodes:
        apply_interaction_component_metadata(node, episode_id)
    timeline_items = build_timeline_items(nodes)
    _sync_interaction_generation_counts(generation_pipeline, len(nodes), len(timeline_items))
    return {
        "schemaVersion": "1.0",
        "timelineSchemaVersion": "1.0",
        "drama": {
            "dramaId": drama["drama_id"],
            "title": drama["title"],
        },
        "episode": {
            "episodeId": episode["episode_id"],
            "episodeNo": episode["episode_no"],
            "durationMs": episode["duration_ms"],
            "playUrl": play_url,
        },
        "globalPolicy": {
            "maxNodesPerEpisode": 4,
            "minIntervalMs": 25_000,
            "maxShowsPerNodePerUser": 2,
            "defaultDisplayMode": "SOFT",
            "defaultTimeoutMs": 7_000,
        },
        "generationPipeline": generation_pipeline,
        "candidateNodes": generation_pipeline["candidateNodes"],
        "timeline_items": timeline_items,
        "nodes": nodes,
    }


def build_timed_events(request_base_url: str, episode_id: str) -> dict[str, Any] | None:
    payload = build_interaction_nodes(request_base_url, episode_id)
    if payload is None:
        return None
    events = [
        build_timed_event_from_timeline_item(episode_id, item)
        for item in payload.get("timeline_items", [])
        if isinstance(item, dict)
    ]
    timed_payload = {
        **payload,
        "schemaVersion": "1.1",
        "timelineSchemaVersion": "1.1",
        "events": events,
        "eventCount": len(events),
    }
    timed_payload["evidenceGraph"] = build_episode_evidence_graph_payload(
        episode_id=episode_id,
        timed_payload=timed_payload,
        evidence_context=_load_interaction_generation_evidence(episode_id),
    )
    return timed_payload


def build_evidence_graph(
    request_base_url: str,
    episode_id: str,
    time_ms: int | None = None,
) -> dict[str, Any] | None:
    timed_payload = build_timed_events(request_base_url, episode_id)
    if timed_payload is None:
        return None
    return build_episode_evidence_graph_payload(
        episode_id=episode_id,
        timed_payload=timed_payload,
        evidence_context=_load_interaction_generation_evidence(episode_id),
        focus_time_ms=time_ms,
    )


def build_interaction_candidate_review_queue(request_base_url: str, episode_id: str) -> dict[str, Any] | None:
    payload = build_interaction_nodes(request_base_url, episode_id)
    if payload is None:
        return None
    candidates = payload.get("candidateNodes", [])
    return {
        "episodeId": episode_id,
        "items": candidates if isinstance(candidates, list) else [],
        "reviewPolicy": {
            "acceptedStatuses": ["accepted", "edited"],
            "rejectedCandidatesHiddenFromTimeline": True,
        },
    }


def review_interaction_candidate(candidate_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    episode_id = str(payload.get("episodeId") or payload.get("episode_id") or "").strip()
    review_status = str(payload.get("reviewStatus") or payload.get("review_status") or "").strip()
    if not candidate_id or not episode_id or review_status not in {"accepted", "rejected", "edited"}:
        return None
    reviews = _read_interaction_candidate_reviews()
    review_item = {
        "candidateId": candidate_id,
        "episodeId": episode_id,
        "reviewStatus": review_status,
        "editedQuestion": str(payload.get("editedQuestion") or payload.get("edited_question") or "").strip(),
        "editedOptions": [
            str(item).strip()
            for item in payload.get("editedOptions", [])
            if str(item).strip()
        ]
        if isinstance(payload.get("editedOptions"), list)
        else [],
        "reviewNote": str(payload.get("reviewNote") or payload.get("review_note") or "").strip(),
        "reviewedAtMs": int(time.time() * 1000),
    }
    episode_reviews = reviews.setdefault(episode_id, {})
    if isinstance(episode_reviews, dict):
        episode_reviews[candidate_id] = review_item
    _write_interaction_candidate_reviews(reviews)
    return review_item


def build_danmaku_emotion_report(episode_id: str) -> dict[str, Any] | None:
    episode = get_episode_by_id(episode_id)
    if episode is None:
        return None
    evidence = _load_danmaku_episode_evidence(episode_id)
    return build_danmaku_emotion_payload(
        episode_id=episode_id,
        episode=episode,
        evidence=evidence,
    )


def find_interaction_node(
    episode_id: str,
    node_id: str,
    request_base_url: str = "http://localhost:8000",
) -> dict[str, Any] | None:
    payload = build_interaction_nodes(request_base_url, episode_id)
    if payload is None:
        return None
    for node in payload["nodes"]:
        if node["id"] == node_id:
            return node
    return None


def build_shareable_moments(
    request_base_url: str,
    drama_id: str = DRAMA_ID,
    selection_strategy: str = "heat_score_desc_v1",
) -> dict[str, Any] | None:
    drama = get_drama_by_id(drama_id)
    if drama is None:
        return None
    selection_strategy = normalize_shareable_strategy(selection_strategy)
    moments: list[dict[str, Any]] = []
    episode_ids = _story_summary_episode_ids(drama_id)
    for episode_id in episode_ids:
        episode = get_episode_by_id(episode_id)
        payload = build_interaction_nodes(request_base_url, episode_id)
        if episode is None or payload is None:
            continue
        for node in payload["nodes"]:
            moments.append(
                build_shareable_moment_from_node(
                    request_base_url=request_base_url,
                    drama_id=drama_id,
                    episode=episode,
                    node=node,
                    selection_strategy=selection_strategy,
                    play_url=_with_play_url(request_base_url, str(episode["episode_id"])),
                )
            )
    moments = sort_shareable_moments(moments, selection_strategy)
    return {
        "dramaId": drama_id,
        "selectionStrategy": selection_strategy,
        "items": moments,
    }


def build_home_highlight_feed(
    request_base_url: str,
    size: int = 6,
    strategy: str = "heat_score_desc_v1",
    drama_id: str = "",
) -> dict[str, Any] | None:
    strategy = normalize_shareable_strategy(strategy)
    target_drama_ids = [drama_id] if drama_id else [config.drama_id for config in load_drama_registry().list_all()]
    items: list[dict[str, Any]] = []
    for target_drama_id in target_drama_ids:
        payload = build_shareable_moments(request_base_url, target_drama_id, strategy)
        if payload is None:
            continue
        payload_items = payload.get("items") if isinstance(payload.get("items"), list) else []
        items.extend(payload_items)
    if drama_id and not items:
        return None
    items = sort_shareable_moments(items, strategy)
    selected_items = items[: max(size, 0)]
    return {
        "dramaId": drama_id or "all",
        "feedType": "high_energy_moment",
        "selectionStrategy": strategy,
        "abTest": {
            "enabled": strategy in {"interaction_first", "danmaku_first", "ai_evidence_first", "hybrid"},
            "strategy": strategy,
            "metrics": ["impression", "click", "jump", "play_complete", "save"],
        },
        "strategyEvaluation": _build_highlight_strategy_evaluation(strategy, selected_items),
        "items": selected_items,
    }


def _build_highlight_strategy_evaluation(strategy: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    heat_scores = [_safe_int(item.get("heatScore"), 0, minimum=0) for item in items]
    source_counts: dict[str, int] = {}
    for item in items:
        source = str(item.get("source") or "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
    return {
        "selectionStrategy": strategy,
        "strategyLabel": _highlight_strategy_label(strategy),
        "sampleSize": len(items),
        "averageHeatScore": round(sum(heat_scores) / len(heat_scores), 2) if heat_scores else 0,
        "evidenceMix": [
            {"source": source, "count": count}
            for source, count in sorted(source_counts.items(), key=lambda pair: (-pair[1], pair[0]))
        ],
        "metricPlan": ["CTR=点击/曝光", "完播率=片段播放完成/开始", "收藏率=收藏/点击", "跳转率=进入播放/曝光"],
        "interpretation": _highlight_strategy_interpretation(strategy, items),
    }


def _highlight_strategy_label(strategy: str) -> str:
    return {
        "heat_score_desc_v1": "热度优先",
        "episode_spread_v1": "分集均衡",
        "recent_episode_v1": "最新优先",
        "interaction_first": "互动优先",
        "danmaku_first": "弹幕共鸣优先",
        "ai_evidence_first": "AI 证据优先",
        "hybrid": "混合策略",
    }.get(strategy, strategy)


def _highlight_strategy_interpretation(strategy: str, items: list[dict[str, Any]]) -> str:
    if not items:
        return "当前没有可评测片段，等待互动节点或弹幕热区预热。"
    if strategy == "danmaku_first":
        return "优先验证观众共鸣热区是否能提升点击和收藏。"
    if strategy == "ai_evidence_first":
        return "优先验证多模态证据支撑的高能点是否更稳定。"
    if strategy == "interaction_first":
        return "优先验证互动节点驱动的跳转和完播效果。"
    if strategy == "hybrid":
        return "综合热度、证据和分集覆盖，适合答辩默认展示。"
    return "作为基线策略，用于和 A/B 策略对照。"


def save_shareable_moment(payload: dict[str, Any]) -> dict[str, Any] | None:
    drama_id = str(payload.get("dramaId") or payload.get("drama_id") or DRAMA_ID).strip() or DRAMA_ID
    moment = normalize_incoming_moment(
        payload,
        drama_id=drama_id,
        valid_episode_ids=set(_story_summary_episode_ids(drama_id)),
        now_ms=int(time.time() * 1000),
    )
    if moment is None:
        return None
    saved = get_runtime_store().save_moment(moment)
    return format_saved_moment(saved, drama_id=drama_id, play_url="")


def list_saved_shareable_moments(request_base_url: str, drama_id: str = DRAMA_ID) -> dict[str, Any]:
    rows = get_runtime_store().list_saved_moments(drama_id)
    return {
        "dramaId": drama_id,
        "items": [
            format_saved_moment(
                row,
                drama_id=drama_id,
                play_url=_with_play_url(request_base_url, str(row.get("episode_id") or ""))
                if request_base_url and row.get("episode_id")
                else "",
            )
            for row in rows
        ],
    }


def _build_episode_nodes(episode_id: str, request_base_url: str, episode_summary: str = "") -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    blueprints = EPISODE_NODE_BLUEPRINTS.get(episode_id) or _build_registry_episode_blueprints(episode_id, episode_summary)
    for blueprint in blueprints:
        options = [
            {"id": option_id, "text": option_text}
            for option_id, option_text in blueprint["options"]
        ]
        node: dict[str, Any] = {
            "id": blueprint["id"],
            "type": blueprint["type"],
            "title": blueprint["title"],
            "subtitle": blueprint["subtitle"],
            "trigger": {
                "event": "TIMECODE",
                "timeMs": blueprint["time_ms"],
            },
            "display": {
                "mode": "SOFT",
                "timeoutMs": 7_000,
                "allowSkip": True,
                "skipText": "继续看",
                "layout": "BOTTOM_CARD",
                "style": blueprint["style"],
                "effectText": blueprint["effect_text"],
                "badgeText": blueprint["badge_text"],
                "promptText": blueprint["prompt_text"],
            },
            "options": options,
            "result": {
                "showAggregate": True,
                "aggregateMode": "PERCENT",
                "copywriting": {
                    "afterSubmit": f"已记录「{blueprint['badge_text']}」互动，后续用于剧情讨论和推荐偏好"
                },
            },
        }
        if "ai_insert" in blueprint:
            ai_insert = dict(blueprint["ai_insert"])
            generated_asset = get_aigc_insert_provider().build_insert(
                episode_id=episode_id,
                node=node,
                episode_summary=episode_summary,
                request_base_url=request_base_url,
            )
            ai_insert["generatedAsset"] = generated_asset
            node["aiInsert"] = ai_insert
            _attach_aigc_insert_branch(node, generated_asset)
        nodes.append(node)
    return nodes


def _build_registry_episode_blueprints(episode_id: str, episode_summary: str) -> list[dict[str, Any]]:
    episode = get_episode_by_id(episode_id)
    if episode is None:
        return []
    duration_ms = _safe_int(episode.get("duration_ms"), 180_000, minimum=60_000)
    drama = get_drama_by_id(str(episode.get("drama_id") or DRAMA_ID)) or {}
    title = str(drama.get("title") or episode.get("title") or "短剧")
    summary = str(episode_summary or episode.get("summary") or "").strip()
    theme = str(drama.get("interaction_hint") or "围绕剧情选择和情绪共鸣设计互动").strip()
    points = [
        (0.18, "opening_reaction", "这一幕你更想站哪边？", "开场冲突已经出现，适合收集第一反应", "立场选择"),
        (0.50, "middle_prediction", "接下来你觉得会怎么反转？", "剧情推进到关键段落，适合做预判互动", "剧情预判"),
        (0.82, "ending_hook", "这一集结尾你最想继续看什么？", "结尾前收集追更期待，服务下一集推荐", "追更钩子"),
    ]
    options = [
        [("support_lead", "支持主角"), ("watch_more", "继续观察"), ("expect_reversal", "等一个反转")],
        [("truth", "真相揭开"), ("conflict", "冲突升级"), ("new_clue", "出现新线索")],
        [("next_episode", "马上看下一集"), ("highlight", "收藏这个爽点"), ("discuss", "想看大家怎么说")],
    ]
    return [
        {
            "id": f"n_{episode_id}_{suffix}",
            "type": "PLOT_EXPECTATION" if index != 0 else "REACTION_PULSE",
            "title": question,
            "subtitle": f"{subtitle}。{theme}",
            "time_ms": int(duration_ms * ratio),
            "style": style,
            "effect_text": "热",
            "badge_text": style,
            "prompt_text": summary[:48] or f"{title}第{episode.get('episode_no')}集互动点",
            "options": options[index],
        }
        for index, (ratio, suffix, question, subtitle, style) in enumerate(points)
    ]


def _build_reviewed_danmaku_nodes(episode_id: str) -> list[dict[str, Any]]:
    evidence = _load_danmaku_episode_evidence(episode_id)
    published = evidence.get("publishedNodes") if isinstance(evidence, dict) else []
    if not isinstance(published, list):
        return []
    nodes: list[dict[str, Any]] = []
    for item in published:
        if not isinstance(item, dict):
            continue
        options = item.get("options")
        if not isinstance(options, list) or not options:
            continue
        nodes.append(
            {
                "id": str(item.get("id") or ""),
                "type": str(item.get("type") or "DANMAKU_REACTION"),
                "title": str(item.get("title") or ""),
                "subtitle": str(item.get("subtitle") or ""),
                "trigger": {"event": "TIMECODE", "timeMs": _safe_int(item.get("timeMs"), 0, minimum=0)},
                "display": {
                    "mode": "SOFT",
                    "timeoutMs": 7_000,
                    "allowSkip": True,
                    "skipText": "继续看",
                    "layout": "BOTTOM_CARD",
                    "style": str(item.get("style") or "弹幕冲浪"),
                    "effectText": str(item.get("effectText") or "热"),
                    "badgeText": str(item.get("badgeText") or "弹幕共鸣"),
                    "promptText": str(item.get("promptText") or "来自真实热区的互动选择"),
                },
                "options": [
                    {"id": str(option.get("id") or ""), "text": str(option.get("text") or "")}
                    for option in options
                    if isinstance(option, dict)
                ],
                "generationCandidateId": str(item.get("candidateId") or ""),
            }
        )
    return [node for node in nodes if node["id"] and node["options"]]


def _build_interaction_generation_pipeline(episode_id: str, nodes: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = _load_interaction_generation_evidence(episode_id)
    candidates = _build_evidence_candidates(episode_id, evidence, nodes)
    for node in nodes:
        trigger_ms = int(node.get("trigger", {}).get("timeMs", 0) or 0)
        requested_candidate_id = str(node.pop("generationCandidateId", "") or "")
        closest = next(
            (item for item in candidates if item.get("candidateId") == requested_candidate_id),
            None,
        ) or min(candidates, key=lambda item: abs(int(item.get("timeMs", 0)) - trigger_ms), default=None)
        has_machine_evidence = bool(closest and closest.get("source") != "manual_seed")
        is_reviewed_candidate = bool(requested_candidate_id and closest)
        offset_ms = abs(int(closest.get("timeMs", 0)) - trigger_ms) if closest else 0
        confidence = float(closest.get("confidence", 0.55)) if closest else 0.55
        if has_machine_evidence and not is_reviewed_candidate:
            confidence = max(0.3, confidence - min(offset_ms / 100_000, 0.35))
        candidate_status = str(closest.get("reviewStatus") or "") if closest else ""
        review_status = (
            candidate_status
            if candidate_status in {"accepted", "rejected", "edited"}
            else ("accepted" if is_reviewed_candidate or not has_machine_evidence else "edited")
        )
        node["generation"] = {
            "pipeline": "AI_ASSISTED_REVIEW",
            "evidenceRefs": closest.get("evidenceRefs", []) if closest else [],
            "evidence_refs": closest.get("evidenceRefs", []) if closest else [],
            "generationSource": (
                "reviewed_model" if has_machine_evidence else "manual"
            ),
            "generation_source": (
                "reviewed_model" if has_machine_evidence else "manual"
            ),
            "confidence": round(confidence, 3),
            "reviewStatus": review_status,
            "review_status": review_status,
            "candidateId": str(closest.get("candidateId") or "") if closest else "",
            "evidenceSource": str(closest.get("source") or "manual_seed") if closest else "manual_seed",
            "timeOffsetMs": offset_ms,
        }
    has_evidence = bool(evidence.get("sources"))
    return {
        "pipelineVersion": "1.1",
        "mode": "AI_ASSISTED_REVIEW",
        "sourceStatus": "evidence_ready" if has_evidence else "seed_fallback",
        "evidenceSources": evidence.get("sources", []),
        "evidenceCatalog": evidence.get("references", []),
        "stages": [
            {
                "name": "evidence_extraction",
                "status": "ready" if has_evidence else "fallback",
                "sources": evidence.get("sources", []),
            },
            {
                "name": "candidate_generation",
                "status": "ready",
                "count": len(candidates),
            },
            {
                "name": "human_confirmation",
                "status": "confirmed",
                "count": len(nodes),
            },
            {
                "name": "timeline_publish",
                "status": "published",
                "count": len(nodes),
            },
        ],
        "candidateNodes": candidates,
        "candidateNodeCount": len(candidates),
        "confirmedNodeCount": len(nodes),
    }


def _sync_interaction_generation_counts(
    generation_pipeline: dict[str, Any],
    confirmed_count: int,
    timeline_item_count: int,
) -> None:
    generation_pipeline["confirmedNodeCount"] = confirmed_count
    generation_pipeline["timelineItemCount"] = timeline_item_count
    for stage in generation_pipeline.get("stages", []):
        if not isinstance(stage, dict):
            continue
        if stage.get("name") == "human_confirmation":
            stage["count"] = confirmed_count
        elif stage.get("name") == "timeline_publish":
            stage["count"] = timeline_item_count


def _load_interaction_generation_evidence(episode_id: str) -> dict[str, Any]:
    path = DEFAULT_VIDEO_UNDERSTANDING_ROOT / episode_id / "understanding.json"
    document: dict[str, Any] = {}
    if path.exists():
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            document = {}
    result = ((document.get("envelope") or {}).get("result") or {}) if isinstance(document, dict) else {}
    audio_text = result.get("audio_text") if isinstance(result.get("audio_text"), dict) else {}
    sources: list[str] = []
    references: list[dict[str, Any]] = []
    if str(audio_text.get("transcript") or audio_text.get("corrected_transcript") or "").strip():
        sources.append("ASR")
        turns = audio_text.get("speaker_turns") if isinstance(audio_text.get("speaker_turns"), list) else []
        if turns:
            references.extend(
                {
                    "refId": f"asr_segment:{episode_id}:{index:02d}",
                    "kind": "asr_segment",
                    "timeMs": _safe_int(turn.get("start_ms"), 0, minimum=0),
                }
                for index, turn in enumerate(turns, start=1)
                if isinstance(turn, dict)
            )
    if isinstance(result.get("screen_text_cues"), list) and result["screen_text_cues"]:
        sources.append("OCR")
        references.extend(
            {
                "refId": f"ocr_cue:{episode_id}:{index:02d}",
                "kind": "ocr_cue",
                "timeMs": _safe_int(cue.get("time_ms"), 0, minimum=0),
            }
            for index, cue in enumerate(result["screen_text_cues"], start=1)
            if isinstance(cue, dict)
        )
    frame_assets = ((document.get("assets") or {}).get("frames") or []) if isinstance(document, dict) else []
    if isinstance(frame_assets, list) and frame_assets:
        sources.append("KEYFRAME")
        references.extend(
            {
                "refId": f"frame:{episode_id}:{index:02d}",
                "kind": "frame",
                "timeMs": _safe_int(frame.get("timeMs"), 0, minimum=0),
            }
            for index, frame in enumerate(frame_assets, start=1)
            if isinstance(frame, dict)
        )
    danmaku = _load_danmaku_episode_evidence(episode_id)
    if danmaku:
        sources.extend(["DANMAKU_AGGREGATE", "REVIEWED_FRAME"])
    return {
        "sources": list(dict.fromkeys(sources)),
        "result": result,
        "references": references,
        "frames": frame_assets if isinstance(frame_assets, list) else [],
        "danmaku": danmaku,
    }


def _build_evidence_candidates(episode_id: str, evidence: dict[str, Any], nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_candidates = evidence.get("result", {}).get("interaction_candidates")
    candidates: list[dict[str, Any]] = []
    if isinstance(raw_candidates, list):
        for index, candidate in enumerate(raw_candidates, start=1):
            if not isinstance(candidate, dict):
                continue
            question = str(candidate.get("question") or "").strip()
            if not question:
                continue
            candidates.append(
                {
                    "candidateId": f"evidence_candidate_{index:02d}",
                    "timeMs": _safe_int(candidate.get("time_ms"), 0, minimum=0),
                    "type": str(candidate.get("type") or "INTERACTION"),
                    "question": question,
                    "reason": str(candidate.get("reason") or "").strip(),
                    "options": [
                        str(item).strip()
                        for item in candidate.get("options", [])
                        if str(item).strip()
                    ],
                    "source": "ASR_OCR_KEYFRAME",
                    "evidenceRefs": _match_evidence_refs(
                        evidence.get("references", []),
                        _safe_int(candidate.get("time_ms"), 0, minimum=0),
                    ),
                    "confidence": 0.76,
                    "reviewStatus": "pending",
                }
            )
    danmaku_candidates = evidence.get("danmaku", {}).get("candidates", [])
    if isinstance(danmaku_candidates, list):
        for item in danmaku_candidates:
            if not isinstance(item, dict):
                continue
            candidates.append(
                {
                    "candidateId": str(item.get("candidateId") or ""),
                    "timeMs": _safe_int(item.get("timeMs"), 0, minimum=0),
                    "type": str(item.get("type") or "DANMAKU_REACTION"),
                    "question": str(item.get("question") or ""),
                    "reason": str(item.get("reason") or ""),
                    "options": [str(option) for option in item.get("options", [])],
                    "source": "DANMAKU_FRAME_REVIEW",
                    "evidenceRefs": [str(ref) for ref in item.get("evidenceRefs", [])],
                    "confidence": float(item.get("confidence") or 0.0),
                    "reviewStatus": str(item.get("reviewStatus") or "pending"),
                }
            )
    if candidates:
        return _attach_candidate_orchestration_advice(_apply_candidate_reviews(episode_id, candidates))
    seed_candidates = [
        {
            "candidateId": f"seed_candidate_{index:02d}",
            "timeMs": int(node.get("trigger", {}).get("timeMs", 0) or 0),
            "type": str(node.get("type") or "INTERACTION"),
            "question": str(node.get("title") or ""),
            "reason": str(node.get("subtitle") or ""),
            "options": [
                str(option.get("text") or "")
                for option in node.get("options", [])
                if str(option.get("text") or "").strip()
            ],
            "source": "manual_seed",
            "evidenceRefs": [],
            "confidence": 0.55,
            "reviewStatus": "accepted",
        }
        for index, node in enumerate(nodes, start=1)
    ]
    return _attach_candidate_orchestration_advice(_apply_candidate_reviews(episode_id, seed_candidates))


def _attach_candidate_orchestration_advice(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **candidate,
            "orchestrationAdvice": _build_candidate_orchestration_advice(candidate),
        }
        for candidate in candidates
    ]


def _build_candidate_orchestration_advice(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate_type = str(candidate.get("type") or "").upper()
    review_status = str(candidate.get("reviewStatus") or "pending")
    evidence_refs = [str(ref) for ref in candidate.get("evidenceRefs", []) if str(ref).strip()]
    if "DANMAKU" in candidate_type or str(candidate.get("source") or "").startswith("DANMAKU"):
        component_type = "plot_hint_card"
        visual_style = "audience_resonance"
        placement = "center_end"
        max_lines = 2
    elif "CHOICE" in candidate_type or len(candidate.get("options", [])) >= 2:
        component_type = "choice_card"
        visual_style = "family_reversal"
        placement = "bottom_sheet"
        max_lines = 3
    else:
        component_type = "sticker"
        visual_style = "high_energy_pulse"
        placement = "center_start"
        max_lines = 2
    return {
        "recommendedComponentType": component_type,
        "visualStyle": visual_style,
        "placement": placement,
        "safeArea": {
            "avoidTopTitle": True,
            "avoidRightActions": True,
            "avoidBottomControls": True,
            "avoidDanmakuLayer": True,
        },
        "maxLines": max_lines,
        "analyticsKey": f"candidate_{component_type}_{str(candidate.get('candidateId') or 'unknown')}",
        "evidenceSummary": f"已绑定 {len(evidence_refs)} 条证据" if evidence_refs else "人工种子候选，待补充多模态证据",
        "publishEligible": review_status in {"accepted", "edited"},
    }


def _interaction_candidate_review_path() -> Path:
    return DEFAULT_VIDEO_UNDERSTANDING_ROOT / DRAMA_ID / INTERACTION_CANDIDATE_REVIEW_FILE


def _read_interaction_candidate_reviews() -> dict[str, Any]:
    document = _read_json_document(_interaction_candidate_review_path())
    return document if isinstance(document, dict) else {}


def _write_interaction_candidate_reviews(reviews: dict[str, Any]) -> None:
    path = _interaction_candidate_review_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(reviews, ensure_ascii=False, indent=2), encoding="utf-8")


def _apply_candidate_reviews(episode_id: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reviews = _read_interaction_candidate_reviews().get(episode_id, {})
    if not isinstance(reviews, dict):
        return candidates
    for candidate in candidates:
        review = reviews.get(str(candidate.get("candidateId") or ""))
        if not isinstance(review, dict):
            continue
        review_status = str(review.get("reviewStatus") or "")
        if review_status in {"accepted", "rejected", "edited"}:
            candidate["reviewStatus"] = review_status
        edited_question = str(review.get("editedQuestion") or "").strip()
        if edited_question:
            candidate["question"] = edited_question
        edited_options = review.get("editedOptions")
        if isinstance(edited_options, list) and edited_options:
            candidate["options"] = [str(item) for item in edited_options if str(item).strip()]
        candidate["reviewedAtMs"] = int(review.get("reviewedAtMs") or 0)
        candidate["reviewNote"] = str(review.get("reviewNote") or "")
    return candidates


def _load_danmaku_episode_evidence(episode_id: str) -> dict[str, Any]:
    raw_path = os.environ.get("AIGC_DANMAKU_EVIDENCE_PATH", "").strip()
    for path in _danmaku_evidence_paths(episode_id, raw_path):
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        episodes = payload.get("episodes") if isinstance(payload, dict) else {}
        item = episodes.get(episode_id) if isinstance(episodes, dict) else {}
        if isinstance(item, dict) and item:
            return item
    return {}


def _danmaku_evidence_paths(episode_id: str, raw_path: str = "") -> list[Path]:
    paths: list[Path] = []
    if raw_path:
        return [Path(raw_path)]
    paths.append(DEFAULT_DANMAKU_EVIDENCE_PATH)
    if DEFAULT_DANMAKU_EVIDENCE_PATH == BUNDLED_DANMAKU_EVIDENCE_PATH:
        try:
            config = load_drama_registry().find_by_episode_id(episode_id)
        except KeyError:
            config = None
        if config is not None and config.danmaku_evidence_path is not None:
            paths.append(config.danmaku_evidence_path)
        paths.append(LEGACY_DANMAKU_EVIDENCE_PATH)
    deduped: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def _should_publish_reviewed_danmaku() -> bool:
    raw_value = os.environ.get("AIGC_PUBLISH_REVIEWED_DANMAKU", "").strip().lower()
    if not raw_value:
        return True
    return raw_value not in {"0", "false", "no", "off"}


def _match_evidence_refs(references: list[dict[str, Any]], time_ms: int) -> list[str]:
    matches: list[str] = []
    for kind in ("frame", "asr_segment", "ocr_cue"):
        same_kind = [item for item in references if item.get("kind") == kind]
        closest = min(
            same_kind,
            key=lambda item: abs(_safe_int(item.get("timeMs"), 0) - time_ms),
            default=None,
        )
        if closest and abs(_safe_int(closest.get("timeMs"), 0) - time_ms) <= 15_000:
            matches.append(str(closest.get("refId") or ""))
    return [item for item in matches if item]


def _attach_aigc_insert_branch(node: dict[str, Any], generated_asset: dict[str, Any]) -> None:
    media_url = str(generated_asset.get("mediaUrl") or "").strip()
    playback = generated_asset.get("playback")
    if not media_url or not isinstance(playback, dict):
        return
    options = node.get("options")
    if not isinstance(options, list) or not options:
        return
    branch = {
        "segmentId": str(playback.get("segmentId") or generated_asset.get("assetId") or node.get("id") or ""),
        "startMs": _safe_int(playback.get("startMs"), 0, minimum=0),
        "endMs": _safe_int(playback.get("endMs"), DEFAULT_INSERT_DURATION_MS, minimum=0),
        "returnSeekMs": _safe_int(playback.get("returnSeekMs"), _safe_int(node.get("trigger", {}).get("timeMs"), 0, minimum=0), minimum=0),
        "mediaUrl": media_url,
        "mediaType": str(generated_asset.get("mediaType") or ""),
        "playbackMode": str(playback.get("mode") or "REPLACE_MAIN"),
    }
    options[0]["branch"] = branch


def submit_interaction_answer(
    payload: dict[str, Any],
    request_base_url: str = "http://localhost:8000",
) -> dict[str, Any] | None:
    episode_id = str(payload.get("episodeId", ""))
    node_id = str(payload.get("nodeId", ""))
    answer = payload.get("answer")
    if not isinstance(answer, dict):
        return None

    node = find_interaction_node(episode_id, node_id, request_base_url)
    if node is None:
        return None

    option_id = str(answer.get("optionId", ""))
    selected_option = None
    for option in node.get("options", []):
        if option.get("id") == option_id:
            selected_option = option
            break
    if selected_option is None:
        return None

    record_id = f"ir_{uuid4().hex}"
    record = {
        "record_id": record_id,
        "submit_id": payload.get("submitId") or record_id,
        "drama_id": payload.get("dramaId", DRAMA_ID),
        "episode_id": episode_id,
        "node_id": node_id,
        "node_title": str(node.get("title", "")),
        "option_id": option_id,
        "option_text": str(selected_option.get("text", "")),
        "trigger_ms": payload.get("triggerMs", 0),
        "created_at_ms": int(time.time() * 1000),
    }
    record = get_runtime_store().save_interaction_record(record)

    node_type = str(node.get("type", ""))
    feedback_text = _build_feedback_text(node_type, node_id, option_id)
    result: dict[str, Any] = {
        "recordId": record["record_id"],
        "feedback": {
            "mode": "template",
            "text": feedback_text,
        },
        "reward": {
            "growthValue": 5,
            "points": 2,
        },
        "derivedTags": [
            {
                "tagId": "interaction.intent.choice",
                "score": 0.8,
                "source": "rule",
            }
        ],
        "aggregate": _build_aggregate(node_id),
        "nextAction": {
            "type": "CONTINUE",
        },
    }

    branch = selected_option.get("branch")
    if isinstance(branch, dict):
        result["nextAction"] = {
            "type": "BRANCH_SEGMENT",
            "segment": branch,
        }

    return result


def list_interaction_records(episode_id: str | None = None) -> list[dict[str, Any]]:
    return get_runtime_store().list_interaction_records(episode_id)


def build_interaction_insights(episode_id: str) -> dict[str, Any] | None:
    episode = get_episode_by_id(episode_id)
    interaction_payload = build_interaction_nodes("http://localhost:8000", episode_id)
    if episode is None or interaction_payload is None:
        return None

    records = list_interaction_records(episode_id)
    record_counts: dict[tuple[str, str], int] = {}
    node_record_counts: dict[str, int] = {}
    for record in records:
        node_id = str(record.get("node_id") or "")
        option_id = str(record.get("option_id") or "")
        if not node_id or not option_id:
            continue
        record_counts[(node_id, option_id)] = record_counts.get((node_id, option_id), 0) + 1
        node_record_counts[node_id] = node_record_counts.get(node_id, 0) + 1

    heat_nodes: list[dict[str, Any]] = []
    for node in interaction_payload["nodes"]:
        node_id = str(node["id"])
        display = node.get("display", {})
        style = str(display.get("style") or "")
        base_aggregate = _build_aggregate(node_id)
        options: list[dict[str, Any]] = []
        option_total = 0
        for option in node.get("options", []):
            option_id = str(option.get("id") or "")
            base_count = int(base_aggregate.get(option_id, 0))
            live_count = record_counts.get((node_id, option_id), 0)
            count = base_count + live_count * 8
            option_total += count
            options.append(
                {
                    "optionId": option_id,
                    "optionText": str(option.get("text") or ""),
                    "count": count,
                    "liveCount": live_count,
                    "percent": 0,
                }
            )

        if option_total > 0:
            for option in options:
                option["percent"] = round(option["count"] * 100 / option_total)

        live_node_count = node_record_counts.get(node_id, 0)
        heat_score = min(100, _style_base_heat(style) + live_node_count * 8)
        heat_nodes.append(
            {
                "nodeId": node_id,
                "title": str(node.get("title") or ""),
                "style": style,
                "effectText": str(display.get("effectText") or ""),
                "badgeText": str(display.get("badgeText") or ""),
                "triggerMs": int(node.get("trigger", {}).get("timeMs", 0)),
                "heatScore": heat_score,
                "totalCount": option_total,
                "liveCount": live_node_count,
                "options": options,
            }
        )

    peak_node = max(heat_nodes, key=lambda item: int(item.get("heatScore", 0)), default=None)
    return {
        "episodeId": episode_id,
        "durationMs": episode["duration_ms"],
        "totalInteractions": sum(item["liveCount"] for item in heat_nodes),
        "nodeCount": len(heat_nodes),
        "peakNodeId": peak_node["nodeId"] if peak_node else "",
        "peakNodeTitle": peak_node["title"] if peak_node else "",
        "crowdSummary": _build_crowd_summary(heat_nodes, records),
        "nodes": heat_nodes,
    }


def _style_base_heat(style: str) -> int:
    return {
        "加速包": 84,
        "爽点气泡": 80,
        "笑出鹅叫": 78,
        "弹幕冲浪": 74,
        "站队光环": 72,
        "身份放大镜": 68,
        "预判投票": 66,
        "复盘卡": 62,
    }.get(style, 60)


def _build_crowd_summary(nodes: list[dict[str, Any]], records: list[dict[str, Any]]) -> str:
    if not nodes:
        return "暂无互动节点，无法生成群体反馈。"
    peak_node = max(nodes, key=lambda item: int(item.get("heatScore", 0)))
    live_count = sum(int(item.get("liveCount", 0)) for item in nodes)
    if live_count > 0:
        return f"已有 {live_count} 次本地互动反馈，当前热度最高的是「{peak_node['badgeText'] or peak_node['title']}」。"
    return f"当前基于剧情节点预估群体反馈，「{peak_node['badgeText'] or peak_node['title']}」最容易触发互动。"


def _build_feedback_text(node_type: str, node_id: str, option_id: str) -> str:
    node = find_interaction_node("tainai3_ep01", node_id)
    if node is None:
        for episode in get_episode_seeds():
            node = find_interaction_node(episode["episode_id"], node_id)
            if node is not None:
                break
    if node is not None:
        display = node.get("display", {})
        option_text = ""
        for option in node.get("options", []):
            if option.get("id") == option_id:
                option_text = str(option.get("text", ""))
                break
        effect = str(display.get("effectText") or "记")
        badge = str(display.get("badgeText") or "互动")
        if node.get("aiInsert"):
            return f"已触发「{badge}」：{effect}！你选择了「{option_text}」，后续可替换为真实 AIGC 插入片段。"
        return f"已上屏「{badge}」：{effect}！你选择了「{option_text}」，系统会把这次反应写入偏好和讨论卡。"
    if node_type == "REACTION_PULSE":
        if option_id == "handsome":
            return "已记录「好帅」反应，后续讨论会更偏人物魅力和登场气场。"
        if option_id == "aura":
            return "已记录你对角色气场的关注，后续会推荐更多强势名场面。"
        return "已记录你觉得有意思，系统会继续观察你的剧情兴趣。"
    if node_type == "SCREEN_TEXT_REACTION":
        return "已记录你对人物介绍文字的兴趣，后续会强化身份线索和角色高光。"
    if node_type == "PLOT_EXPECTATION":
        return "已记录你的爽点期待，后续会用于互动偏好和推荐判断。"
    return "已记录你的即时反馈，继续观看剧情。"


def _build_aggregate(node_id: str) -> dict[str, int]:
    for blueprints in EPISODE_NODE_BLUEPRINTS.values():
        for blueprint in blueprints:
            if blueprint["id"] == node_id:
                option_ids = [item[0] for item in blueprint["options"]]
                presets = [43, 34, 23]
                return {
                    option_id: presets[index] if index < len(presets) else max(5, 20 - index * 3)
                    for index, option_id in enumerate(option_ids)
                }
    if node_id == "n_044_character_entrance_reaction":
        return {"handsome": 46, "aura": 41, "interesting": 13}
    if node_id == "n_123_profile_text_reaction":
        return {"legend": 39, "hidden_identity": 35, "face_slap": 26}
    if node_id == "n_202_plot_hook_reaction":
        return {"more_reversal": 33, "identity_reveal": 37, "family_conflict": 30}
    return {}
