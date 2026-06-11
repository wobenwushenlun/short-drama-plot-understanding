from __future__ import annotations

from typing import Any


PROFILE_TAG_RULES = (
    ("打脸反转", ("打脸", "反转", "逆袭", "质疑", "危机", "冲突")),
    ("身份悬念", ("身份", "隐藏", "真相", "关系")),
    ("高能爽点", ("高能", "爽", "排面", "气场", "反击")),
    ("轻松笑点", ("笑", "破防", "搞笑", "尴尬", "医生")),
    ("站队偏好", ("站队", "撑腰", "支持", "先查", "先护")),
)


def derive_profile_tags(texts: list[str]) -> list[str]:
    joined = " ".join(texts)
    return [label for label, tokens in PROFILE_TAG_RULES if any(token in joined for token in tokens)]


def build_profile_tag_distribution(texts: list[str]) -> list[dict[str, Any]]:
    distribution: list[dict[str, Any]] = []
    for label, tokens in PROFILE_TAG_RULES:
        count = sum(1 for text in texts if any(token in text for token in tokens))
        if count:
            distribution.append({"tag": label, "count": count})
    return distribution


def build_profile_reason(tags: list[str], saved_moment_count: int, interaction_count: int) -> list[str]:
    parts: list[str] = []
    if "打脸反转" in tags:
        parts.append("偏好打脸反转")
    elif "身份悬念" in tags:
        parts.append("偏好身份悬念")
    elif "高能爽点" in tags:
        parts.append("偏好高能爽点")
    elif "轻松笑点" in tags:
        parts.append("偏好轻松笑点")
    if "站队偏好" in tags:
        parts.append("对站队互动有参与")
    if saved_moment_count > 0:
        parts.append(f"已收藏{saved_moment_count}个高能片段")
    if interaction_count > 0:
        parts.append(f"累计{interaction_count}次互动")
    if not parts:
        parts.append("基于观看、互动和收藏行为推荐")
    return parts
