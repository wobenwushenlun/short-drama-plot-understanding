from __future__ import annotations

from typing import Any


def apply_interaction_component_metadata(node: dict[str, Any], episode_id: str) -> None:
    node_id = str(node.get("id") or "")
    display = node.setdefault("display", {})
    if not isinstance(display, dict):
        display = {}
        node["display"] = display
    visual_style = str(display.get("style") or "高光互动")
    component_type = resolve_interaction_component_type(str(node.get("type") or ""), visual_style)
    analytics_key = f"interaction_component.{episode_id}.{node_id}"
    placement = resolve_interaction_placement(component_type, visual_style)
    safe_area = build_interaction_safe_area(component_type, placement)
    max_lines = 1 if component_type in {"REACTION_STICKER", "DANMAKU_STICKER"} else 2
    display["componentType"] = component_type
    display["visualStyle"] = visual_style
    display["analyticsKey"] = analytics_key
    display["placement"] = placement
    display["safeArea"] = safe_area
    display["maxLines"] = max_lines
    if not isinstance(node.get("result"), dict):
        node["result"] = {
            "showAggregate": True,
            "aggregateMode": "PERCENT",
            "copywriting": {
                "afterSubmit": f"已记录「{str(display.get('badgeText') or visual_style)}」互动，后续用于剧情讨论和推荐偏好"
            },
        }
    node["componentType"] = component_type
    node["visualStyle"] = visual_style
    node["analyticsKey"] = analytics_key
    node["placement"] = placement
    node["safeArea"] = safe_area
    node["maxLines"] = max_lines


def resolve_interaction_component_type(node_type: str, visual_style: str) -> str:
    normalized_type = node_type.upper()
    if "DANMAKU" in normalized_type or visual_style == "弹幕冲浪":
        return "DANMAKU_STICKER"
    if "AIGC" in normalized_type or "BOOST" in normalized_type or visual_style == "加速包":
        return "AIGC_CARD"
    if normalized_type in {"PLOT_EXPECTATION", "SIDE_CHOICE"} or visual_style in {"预判投票", "站队光环"}:
        return "CHOICE_CARD"
    if "SCREEN_TEXT" in normalized_type or visual_style in {"身份放大镜", "复盘卡"}:
        return "EVIDENCE_CARD"
    return "REACTION_STICKER"


def resolve_interaction_placement(component_type: str, visual_style: str) -> str:
    if component_type == "DANMAKU_STICKER":
        return "TOP_CENTER"
    if component_type == "REACTION_STICKER":
        return "CENTER_START" if visual_style == "笑出鹅叫" else "CENTER_END"
    if component_type == "AIGC_CARD":
        return "CENTER"
    if component_type == "EVIDENCE_CARD":
        return "CENTER_START"
    return "BOTTOM_CENTER"


def build_interaction_safe_area(component_type: str, placement: str) -> dict[str, Any]:
    avoid_right_rail = placement.endswith("END")
    avoid_danmaku = placement.startswith("TOP") or component_type == "DANMAKU_STICKER"
    avoid_progress = placement.startswith("BOTTOM") or component_type in {"CHOICE_CARD", "AIGC_CARD"}
    return {
        "topDp": 72 if avoid_danmaku else 24,
        "bottomDp": 88 if avoid_progress else 24,
        "startDp": 16,
        "endDp": 84 if avoid_right_rail else 16,
        "avoidRightRail": avoid_right_rail,
        "avoidDanmaku": avoid_danmaku,
        "avoidProgressBar": avoid_progress,
    }
