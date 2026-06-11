from __future__ import annotations

from typing import Any

from backend.app.content_catalog import (
    build_danmaku_emotion_report,
    build_interaction_nodes,
    build_shareable_moments,
)
from backend.app.domain_utils import safe_int


CHECKIN_CARD_PROMPT_VERSION = "agnes.checkin_card/v2-style-template"

CHECKIN_CARD_STYLE_TEMPLATES: dict[str, dict[str, Any]] = {
    "short_drama_poster": {
        "label": "短剧通用海报",
        "aliases": {"poster", "default", "short_drama_poster"},
        "visual_prompt": "竖版短剧宣发海报，人物关系居中，标题醒目，整体像手机端短剧封面。",
        "color_prompt": "暖金和深红作为主色，保留商业短剧的强冲突质感。",
        "avoid_prompt": "不要做成单一身份揭露、单一打脸冲突或考古寻宝风。",
    },
    "family_glory": {
        "label": "家族荣耀逆袭",
        "aliases": {"family_glory", "family_counter_attack", "家族荣耀逆袭"},
        "visual_prompt": "豪门家族大厅、金色家徽、主角气场压制全场，突出从被轻视到掌控局面的逆袭感。",
        "color_prompt": "金色、酒红、深木色，画面有家族权力和仪式感。",
        "avoid_prompt": "不要做成街头打斗、悬疑寻宝或纯甜宠风。",
    },
    "face_slap": {
        "label": "打脸爽点",
        "aliases": {"face_slap", "counter_attack", "打脸爽点"},
        "visual_prompt": "冲突对峙构图，前景是强势反击姿态，背景用速度线和高亮字幕强化爽点爆发。",
        "color_prompt": "高对比冷暖撞色，动作感强，保留短视频爆点字幕空间。",
        "avoid_prompt": "不要做成安静合照、温情家庭照或静态证件照。",
    },
    "identity_reveal": {
        "label": "身份揭露",
        "aliases": {"identity_reveal", "identity", "身份揭露"},
        "visual_prompt": "人物半身特写叠加身份线索光效，画面有揭开真相的悬念和反转仪式感。",
        "color_prompt": "冷蓝暗调配金色线索光，突出秘密、档案、身份反差。",
        "avoid_prompt": "不要使用豪门大厅群像，不要做成普通婚庆海报。",
    },
    "reversal_scene": {
        "label": "反转名场面",
        "aliases": {"reversal_scene", "plot_twist", "reversal", "反转名场面"},
        "visual_prompt": "高反差戏剧光，画面中形成前后局势翻转的对比，强调名场面和继续观看欲。",
        "color_prompt": "一半压抑暗色、一半强光反击，形成明显前后反转对照。",
        "avoid_prompt": "不要做成平铺直叙的普通剧照或无冲突合影。",
    },
}


def build_checkin_card_context(
    *,
    request_base_url: str,
    drama: dict[str, Any],
    episode: dict[str, Any],
    moment_id: str,
    style: str,
) -> dict[str, Any]:
    episode_id = str(episode["episode_id"])
    style_id, style_template = _resolve_checkin_card_style(style)
    shareable_payload = build_shareable_moments(request_base_url, str(drama["drama_id"]))
    moments = shareable_payload.get("items", []) if isinstance(shareable_payload, dict) else []
    selected_moment = next(
        (
            item
            for item in moments
            if isinstance(item, dict)
            and (not moment_id or str(item.get("momentId") or "") == moment_id)
            and str(item.get("episodeId") or "") == episode_id
        ),
        {},
    )
    danmaku = build_danmaku_emotion_report(episode_id) or {}
    resonance_items = danmaku.get("items") if isinstance(danmaku.get("items"), list) else []
    top_resonance = resonance_items[0] if resonance_items else {}
    title = str(selected_moment.get("title") or f"第{episode.get('episode_no')}集打卡").strip()
    return {
        "dramaId": str(drama["drama_id"]),
        "dramaTitle": str(drama["title"]),
        "episodeId": episode_id,
        "episodeNo": int(episode.get("episode_no") or 0),
        "episodeTitle": str(episode.get("title") or ""),
        "episodeSummary": str(episode.get("summary") or ""),
        "title": title[:40],
        "hookText": str(selected_moment.get("hookText") or "").strip()[:80],
        "heatScore": safe_int(selected_moment.get("heatScore"), 0, minimum=0, maximum=100),
        "emotion": str(top_resonance.get("emotion") or "").strip(),
        "keywords": top_resonance.get("keywords") if isinstance(top_resonance.get("keywords"), list) else [],
        "characters": _build_checkin_character_summary(drama),
        "interactionHooks": _build_checkin_interaction_hooks(request_base_url, episode_id),
        "style": style_id,
        "styleLabel": str(style_template.get("label") or style_id),
        "stylePrompt": str(style_template.get("visual_prompt") or ""),
        "styleColorPrompt": str(style_template.get("color_prompt") or ""),
        "styleAvoidPrompt": str(style_template.get("avoid_prompt") or ""),
    }


def build_checkin_card_prompt(context: dict[str, Any]) -> str:
    keywords = "、".join(str(item) for item in context.get("keywords", [])[:4] if str(item).strip())
    characters = "、".join(str(item) for item in context.get("characters", [])[:4] if str(item).strip())
    interaction_hooks = "；".join(str(item) for item in context.get("interactionHooks", [])[:3] if str(item).strip())
    user_intent = context.get("userCreativeIntent") if isinstance(context.get("userCreativeIntent"), dict) else {}
    prompt_refinement = context.get("promptRefinement") if isinstance(context.get("promptRefinement"), dict) else {}
    return "\n".join(
        item
        for item in [
            "生成一张竖版短剧打卡海报，比例 9:16，适合手机分享。",
            f"内部episodeId：{context['episodeId']}",
            f"风格模板（最高优先级）：{context['styleLabel']}。",
            f"视觉构图：{context['stylePrompt']}",
            f"色彩与氛围：{context['styleColorPrompt']}" if context.get("styleColorPrompt") else "",
            f"本风格禁止：{context['styleAvoidPrompt']}" if context.get("styleAvoidPrompt") else "",
            f"剧名：{context['dramaTitle']}",
            f"分集：第{context['episodeNo']}集 {context['episodeTitle']}",
            f"剧情概括：{context['episodeSummary']}",
            f"人物关系：{characters}" if characters else "",
            f"互动爽点：{interaction_hooks}" if interaction_hooks else "",
            f"高能标题：{context['title']}",
            f"钩子文案：{context['hookText']}" if context.get("hookText") else "",
            f"观众情绪：{context['emotion']}" if context.get("emotion") else "",
            f"关键词：{keywords}" if keywords else "",
            f"用户希望：{user_intent.get('userIntent')}" if user_intent.get("userIntent") else "",
            f"用户期望结局：{user_intent.get('desiredEnding')}" if user_intent.get("desiredEnding") else "",
            f"用户画面方向：{user_intent.get('visualDirection')}" if user_intent.get("visualDirection") else "",
            f"语言模型优化意图：{prompt_refinement.get('intentSummary')}" if prompt_refinement.get("intentSummary") else "",
            f"剧情方向优化：{prompt_refinement.get('storyDirection')}" if prompt_refinement.get("storyDirection") else "",
            f"海报补充提示：{prompt_refinement.get('imagePromptAddon')}" if prompt_refinement.get("imagePromptAddon") else "",
            f"负向约束：{prompt_refinement.get('negativePrompt')}" if prompt_refinement.get("negativePrompt") else "",
            "画面要求：严格按所选风格模板生成，风格差异要明显；保留醒目的打卡标题和短剧爽点文案。",
            "禁止出现说话人编号、识别技术词、技术流程、水印、真实用户弹幕原文。",
        ]
        if item
    )


def fallback_checkin_card(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": context["title"],
        "subtitle": f"第{context['episodeNo']}集 · {context['episodeTitle']}",
        "hookText": context.get("hookText") or context.get("episodeSummary") or "这一集的高能爽点已记录。",
        "style": context.get("style") or "short_drama_poster",
        "styleLabel": context.get("styleLabel") or "短剧通用海报",
        "source": "local_fallback",
    }


def _resolve_checkin_card_style(style: str) -> tuple[str, dict[str, Any]]:
    normalized = str(style or "").strip() or "short_drama_poster"
    lowered = normalized.lower()
    for style_id, template in CHECKIN_CARD_STYLE_TEMPLATES.items():
        aliases = {str(alias).lower() for alias in template.get("aliases", set())}
        if lowered == style_id.lower() or lowered in aliases:
            return style_id, template
    return "short_drama_poster", CHECKIN_CARD_STYLE_TEMPLATES["short_drama_poster"]


def _build_checkin_character_summary(drama: dict[str, Any]) -> list[str]:
    characters = drama.get("characters") if isinstance(drama.get("characters"), list) else []
    result: list[str] = []
    for character in characters[:4]:
        if not isinstance(character, dict):
            continue
        name = str(character.get("canonical_name") or character.get("name") or "").strip()
        role_type = str(character.get("role_type") or "").strip()
        if name:
            result.append(f"{name}（{role_type or '角色'}）")
    return result


def _build_checkin_interaction_hooks(request_base_url: str, episode_id: str) -> list[str]:
    payload = build_interaction_nodes(request_base_url, episode_id) or {}
    nodes = payload.get("nodes") if isinstance(payload.get("nodes"), list) else []
    hooks: list[str] = []
    for node in nodes[:3]:
        if not isinstance(node, dict):
            continue
        title = str(node.get("title") or "").strip()
        prompt_text = str(node.get("promptText") or node.get("subtitle") or "").strip()
        component_type = str(node.get("componentType") or "").strip()
        if title:
            detail = title
            if prompt_text:
                detail += f"：{prompt_text[:36]}"
            if component_type:
                detail += f"（{component_type}）"
            hooks.append(detail)
    return hooks
