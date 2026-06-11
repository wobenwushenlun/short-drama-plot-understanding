from __future__ import annotations

from typing import Any


def build_cover_layers(
    drama: dict[str, Any],
    request_base_url: str,
    *,
    primary_drama_id: str,
    primary_portrait_episode_id: str = "tainai3_ep01",
) -> dict[str, Any]:
    layers = drama.get("cover_layers") if isinstance(drama.get("cover_layers"), dict) else {}
    portrait_url = str(layers.get("portrait_url") or "").strip()
    if not portrait_url and str(drama.get("drama_id") or "") == primary_drama_id:
        portrait_url = (
            f"{request_base_url.rstrip('/')}/media/video-understanding-frames/"
            f"{primary_portrait_episode_id}/poster_portrait.jpg"
        )
    return {
        "portrait_url": portrait_url,
        "identity_label": _layer_text(layers, "identity_label", "身份反转"),
        "heat_label": _layer_text(layers, "heat_label", "高能热播"),
        "latest_label": _layer_text(layers, "latest_label", _latest_label(drama)),
        "share_hint": _layer_text(layers, "share_hint", "生成同款打卡图"),
    }


def _layer_text(layers: dict[str, Any], key: str, default: str) -> str:
    if key in layers:
        return str(layers.get(key) or "").strip()
    return default


def _latest_label(drama: dict[str, Any]) -> str:
    try:
        latest_episode_no = int(drama.get("latest_episode_no") or 0)
    except (TypeError, ValueError):
        latest_episode_no = 0
    return f"更新至第{latest_episode_no}集" if latest_episode_no > 0 else ""
