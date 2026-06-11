from __future__ import annotations

import hashlib
import json
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from backend.app.runtime_sqlite_store import get_runtime_store


def attach_artifact_state(
    *,
    capability: str,
    payload: dict[str, Any],
    envelope: dict[str, Any],
    prompt_version: str,
    restore_last_success: bool = True,
) -> None:
    result = envelope.get("result")
    if not isinstance(result, dict):
        return
    identity = _build_artifact_identity(capability, payload)
    stored = get_runtime_store().register_ai_attempt(
        capability=capability,
        scope_key=identity["scope_key"],
        prompt_version=prompt_version,
        drama_id=identity["drama_id"],
        episode_id=identity["episode_id"],
        node_id=identity["node_id"],
        status=str(envelope.get("status") or ""),
        source=_resolve_artifact_source(envelope),
        result=result,
        model_name=str(envelope.get("model", {}).get("model_name") or ""),
        cached=bool(envelope.get("cached", envelope.get("cache_hit", False))),
        latency_ms=int(envelope.get("latency_ms") or 0),
        degrade_reason=str(envelope.get("degrade_reason") or ""),
        restore_last_success=restore_last_success,
    )
    restored = bool(stored.get("artifact", {}).get("restored_from_last_success"))
    display_result = _normalize_restored_result_urls(
        stored["result"],
        request_base_url=str(payload.get("requestBaseUrl") or payload.get("request_base_url") or ""),
        restored=restored,
    )
    envelope["result"] = _prefer_current_generated_asset(display_result, result, restored=restored)
    envelope["artifact"] = stored["artifact"]


def _build_artifact_identity(capability: str, payload: dict[str, Any]) -> dict[str, str]:
    drama = payload.get("drama") if isinstance(payload.get("drama"), dict) else {}
    episode = payload.get("episode") if isinstance(payload.get("episode"), dict) else {}
    interaction = payload.get("interaction") if isinstance(payload.get("interaction"), dict) else {}
    node = payload.get("node") if isinstance(payload.get("node"), dict) else {}
    option = payload.get("option") if isinstance(payload.get("option"), dict) else {}
    request = payload.get("request") if isinstance(payload.get("request"), dict) else {}
    interaction_node = interaction.get("node") if isinstance(interaction.get("node"), dict) else {}
    interaction_option = interaction.get("option") if isinstance(interaction.get("option"), dict) else {}
    drama_id = str(
        drama.get("dramaId")
        or payload.get("dramaId")
        or request.get("dramaId")
        or ""
    ).strip()
    episode_id = str(episode.get("episodeId") or payload.get("episodeId") or "").strip()
    node_id = str(
        node.get("id")
        or interaction_node.get("id")
        or interaction.get("nodeId")
        or payload.get("nodeId")
        or ""
    ).strip()
    option_id = str(
        option.get("id")
        or interaction_option.get("id")
        or interaction.get("optionId")
        or payload.get("optionId")
        or ""
    ).strip()
    parts = [
        part
        for part in (
            f"drama={drama_id}" if drama_id else "",
            f"episode={episode_id}" if episode_id else "",
            f"node={node_id}" if node_id else "",
            f"option={option_id}" if option_id else "",
        )
        if part
    ]
    scope = "|".join(parts) if parts else f"payload={_hash_json(payload)}"
    return {
        "scope_key": f"{capability}|{scope}",
        "drama_id": drama_id,
        "episode_id": episode_id,
        "node_id": node_id,
    }


def _resolve_artifact_source(envelope: dict[str, Any]) -> str:
    if bool(envelope.get("cached", envelope.get("cache_hit", False))):
        return "memory_cache"
    status = str(envelope.get("status") or "")
    provider = str(envelope.get("model", {}).get("provider") or "")
    if status == "ok":
        return "remote_model" if provider not in {"rule", "local"} else "local_rule"
    if status == "blocked":
        return "local_rule"
    return "local_fallback"


def _normalize_restored_result_urls(result: dict[str, Any], *, request_base_url: str, restored: bool) -> dict[str, Any]:
    if not restored or not request_base_url:
        return result
    return _rewrite_local_media_urls(result, request_base_url)


def _rewrite_local_media_urls(value: Any, request_base_url: str, *, key: str = "") -> Any:
    if isinstance(value, dict):
        return {item_key: _rewrite_local_media_urls(item_value, request_base_url, key=item_key) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [_rewrite_local_media_urls(item, request_base_url, key=key) for item in value]
    if isinstance(value, str) and key != "remoteUrl":
        return _rewrite_local_media_url(value, request_base_url)
    return value


def _rewrite_local_media_url(url: str, request_base_url: str) -> str:
    parsed = urlsplit(url)
    if parsed.path not in ("", "/") and parsed.path.startswith(("/media/aigc-inserts/", "/media/generated-assets/")):
        base = urlsplit(request_base_url)
        return urlunsplit((base.scheme, base.netloc, parsed.path, parsed.query, parsed.fragment))
    return url


def _prefer_current_generated_asset(
    restored_result: dict[str, Any],
    current_result: dict[str, Any],
    *,
    restored: bool,
) -> dict[str, Any]:
    if not restored:
        return restored_result
    current_asset = current_result.get("generated_asset")
    if not isinstance(current_asset, dict) or not str(current_asset.get("mediaUrl") or "").strip():
        return restored_result
    merged = dict(restored_result)
    merged["generated_asset"] = current_asset
    return merged


def _hash_json(data: Any) -> str:
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
