from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from backend.app.agnes_client import AgnesClient
from backend.app.aigc_insert_service import get_aigc_insert_provider
from backend.app.ai_artifact_store import attach_artifact_state
from backend.app.ai_checkin_card import (
    CHECKIN_CARD_PROMPT_VERSION,
    build_checkin_card_context,
    build_checkin_card_prompt,
    fallback_checkin_card,
)
from backend.app.domain_utils import safe_int as _safe_int
from backend.app.generated_asset_store import cache_remote_generated_asset
from backend.app.content_catalog import (
    build_interaction_nodes,
    get_drama_by_id,
    get_episode_by_id,
    list_home_items,
    list_interaction_records,
)
from backend.app.runtime_sqlite_store import get_runtime_store
from backend.app.user_activity_store import list_watch_history


DEFAULT_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL_CONFIG_FILE = "model_apikey.txt"
DEFAULT_AUDIT_PATH = Path("tmp/ai_audit.jsonl")
DEFAULT_CACHE_TTL_SECONDS = 300
DEFAULT_TIMEOUT_SECONDS = 45
DEFAULT_MODEL_WAIT_SECONDS = 50
DEFAULT_REMOTE_MODEL_ENABLED = True

CONTENT_RECAP_PROMPT_VERSION = "content.recap/v2-video-fusion"
INTERACTION_FEEDBACK_PROMPT_VERSION = "interaction.feedback/v1"
TAG_EXTRACT_PROMPT_VERSION = "tag.extract/v1"
DISCUSSION_SEED_PROMPT_VERSION = "discussion.seed/v1"
STORY_CONTINUATION_PROMPT_VERSION = "story.continuation/v1"
HISTORY_RECAP_PROMPT_VERSION = "history.recap/v1"
RECOMMEND_HOME_PROMPT_VERSION = "recommend.home/v1"
CREATIVE_PROMPT_REFINE_VERSION = "creative.prompt.refine/v1"

MODERATION_RISK_PATTERNS: dict[str, list[str]] = {
    "self_harm": [
        "自杀",
        "割腕",
        "轻生",
        "不想活了",
    ],
    "violence": [
        "杀了你",
        "砍死",
        "碎尸",
        "暴力",
    ],
    "sexual": [
        "裸露",
        "性爱",
        "强奷",
        "性暗示",
    ],
    "abuse": [
        "去死",
        "废物",
        "傻逼",
        "滚开",
    ],
}

_MODEL_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ai-model")


@dataclass(frozen=True)
class ArkCredentials:
    endpoint_id: str
    api_key: str
    base_url: str = DEFAULT_ARK_BASE_URL
    source_path: str = ""


@dataclass
class CacheEntry:
    expires_at_ms: int
    value: dict[str, Any]


class AIService:
    def __init__(self, credentials: ArkCredentials, audit_path: Path | None = None):
        self.credentials = credentials
        self.audit_path = audit_path or DEFAULT_AUDIT_PATH
        self._cache: dict[str, CacheEntry] = {}
        self._cache_lock = threading.Lock()
        self._audit_lock = threading.Lock()

    @classmethod
    def from_environment(cls) -> "AIService":
        return cls(load_ark_credentials(), resolve_audit_path())

    def reset_runtime_state(self) -> None:
        with self._cache_lock:
            self._cache.clear()

    def content_recap(self, payload: dict[str, Any], request_base_url: str) -> dict[str, Any]:
        drama_id = str(payload.get("dramaId", "")).strip()
        episode_id = str(payload.get("episodeId", "")).strip()
        if not episode_id:
            raise ValueError("episodeId is required")
        if not drama_id:
            drama_id = "tainai3"

        drama = get_drama_by_id(drama_id)
        episode = get_episode_by_id(episode_id)
        if drama is None or episode is None:
            raise ValueError("episode or drama not found")

        interaction_payload = build_interaction_nodes(request_base_url, episode_id)
        video_evidence = _load_video_understanding_evidence(episode_id, drama_id=drama_id)
        watch_history = list_watch_history(3)
        recent_records = list_interaction_records(episode_id)[0:3]
        prompt_context = {
            "drama": {
                "dramaId": drama["drama_id"],
                "title": drama["title"],
                "description": drama["description"],
                "tags": drama["tags"],
                "characters": drama.get("characters", []),
                "interaction_hint": drama.get("interaction_hint", ""),
            },
            "episode": {
                "episodeId": episode["episode_id"],
                "episodeNo": episode["episode_no"],
                "title": episode["title"],
                "summary": episode["summary"],
                "durationMs": episode["duration_ms"],
            },
            "interaction": {
                "hint": drama["interaction_hint"],
                "nodes": interaction_payload["nodes"] if interaction_payload else [],
                "recentRecords": recent_records,
            },
            "videoEvidence": video_evidence,
            "history": watch_history,
            "request": {
                "includeDiscussionSeeds": bool(payload.get("includeDiscussionSeeds", True)),
                "locale": str(payload.get("locale", "zh-CN")),
            },
        }
        cache_key = self._make_cache_key(
            "content.recap",
            {
                "prompt_version": CONTENT_RECAP_PROMPT_VERSION,
                "context": prompt_context,
            },
        )
        cached = self._get_cache(cache_key)
        if cached is not None:
            envelope = self._decorate_response(
                capability="content.recap",
                result=cached["result"],
                status=cached["status"],
                latency_ms=0,
                usage=cached["usage"],
                cache_hit=True,
                model_info=cached["model"],
            )
            self._append_audit(
                capability="content.recap",
                payload=prompt_context,
                envelope=envelope,
                prompt_version=CONTENT_RECAP_PROMPT_VERSION,
            )
            return envelope

        start_ms = _now_ms()
        messages = [
            {
                "role": "system",
                "content": (
                    "你是短剧剧情摘要与理解助手。"
                    "只输出 JSON，不要 Markdown，不要解释。"
                    "请围绕 summary、highlights、character_focus、discussion_seeds、continue_reason 组织结果，字段内容保持简短。"
                    "如果 context.videoEvidence 中有 ASR transcript、OCR 屏幕文字或融合摘要，必须优先使用这些证据生成摘要。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "content.recap",
                        "prompt_version": CONTENT_RECAP_PROMPT_VERSION,
                        "output_schema": {
                            "summary": "string",
                            "highlights": ["string"],
                            "character_focus": ["string"],
                            "discussion_seeds": ["string"],
                            "continue_reason": "string",
                        },
                        "context": prompt_context,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ]
        if not self._remote_model_enabled():
            result = self._fallback_content_recap(prompt_context)
            status = "degraded"
            degrade_reason = "远端模型默认关闭，已使用本地兜底"
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        else:
            try:
                response = self._call_chat_completion_best_effort(
                    capability="content.recap",
                    messages=messages,
                    max_tokens=260,
                    temperature=0.25,
                )
                parsed = self._parse_model_result(response)
                if parsed is None:
                    raw_text = self._extract_model_text(response)
                    if not raw_text:
                        raise ValueError("invalid model response")
                    parsed = {"summary": raw_text}
                result = self._normalize_content_recap_result(parsed, prompt_context)
                status = "ok"
                degrade_reason = ""
                usage = self._extract_usage(response)
            except Exception as exc:  # pragma: no cover - fallback is exercised by tests
                result = self._fallback_content_recap(prompt_context)
                status = "degraded"
                degrade_reason = str(exc)
                usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        model_info = self._model_info()
        envelope = self._decorate_response(
            capability="content.recap",
            result=result,
            status=status,
            latency_ms=_now_ms() - start_ms,
            usage=usage,
            cache_hit=False,
            model_info=model_info,
            degrade_reason=degrade_reason or None,
        )
        self._set_cache(
            cache_key,
            {
                "result": result,
                "status": status,
                "usage": usage,
                "model": model_info,
            },
            ttl_seconds=self._cache_ttl_seconds(),
        )
        self._append_audit(
            capability="content.recap",
            payload=prompt_context,
            envelope=envelope,
            prompt_version=CONTENT_RECAP_PROMPT_VERSION,
        )
        return envelope

    def interaction_feedback(self, payload: dict[str, Any], request_base_url: str) -> dict[str, Any]:
        drama_id = str(payload.get("dramaId", "")).strip()
        episode_id = str(payload.get("episodeId", "")).strip()
        node_id = str(payload.get("nodeId", "")).strip()
        option_id = str(payload.get("optionId", "")).strip()
        if not episode_id or not node_id or not option_id:
            raise ValueError("episodeId, nodeId and optionId are required")
        if not drama_id:
            drama_id = "tainai3"

        interaction_payload = build_interaction_nodes(request_base_url, episode_id)
        if interaction_payload is None:
            raise ValueError("episode not found")
        node = next((item for item in interaction_payload["nodes"] if item["id"] == node_id), None)
        if node is None:
            raise ValueError("node not found")
        option = next((item for item in node.get("options", []) if item.get("id") == option_id), None)
        if option is None:
            raise ValueError("option not found")

        drama_context = get_drama_by_id(drama_id) or {}
        prompt_context = {
            "drama": {
                "dramaId": drama_context.get("drama_id", interaction_payload["drama"]["dramaId"]),
                "title": drama_context.get("title", interaction_payload["drama"]["title"]),
                "description": drama_context.get("description", ""),
                "tags": drama_context.get("tags", []),
                "characters": drama_context.get("characters", []),
                "interaction_hint": drama_context.get("interaction_hint", ""),
            },
            "episode": interaction_payload["episode"],
            "node": {
                "id": node["id"],
                "type": node["type"],
                "title": node["title"],
                "subtitle": node["subtitle"],
                "triggerMs": node["trigger"]["timeMs"],
                "displayMode": node["display"]["mode"],
            },
            "option": {
                "id": option["id"],
                "text": option["text"],
                "branch": option.get("branch"),
            },
            "userContext": {
                "answerText": str(payload.get("answerText", "")).strip(),
                "sceneSummary": str(payload.get("sceneSummary", "")).strip(),
                "userProfileTags": payload.get("userProfileTags") or [],
            },
        }
        cache_key = self._make_cache_key(
            "interaction.feedback",
            {
                "prompt_version": INTERACTION_FEEDBACK_PROMPT_VERSION,
                "context": prompt_context,
            },
        )
        cached = self._get_cache(cache_key)
        if cached is not None:
            envelope = self._decorate_response(
                capability="interaction.feedback",
                result=cached["result"],
                status=cached["status"],
                latency_ms=0,
                usage=cached["usage"],
                cache_hit=True,
                model_info=cached["model"],
            )
            self._append_audit(
                capability="interaction.feedback",
                payload=prompt_context,
                envelope=envelope,
                prompt_version=INTERACTION_FEEDBACK_PROMPT_VERSION,
            )
            return envelope

        start_ms = _now_ms()
        messages = [
            {
                "role": "system",
                "content": (
                    "你是短剧互动反馈助手。"
                    "只输出 JSON，不要 Markdown，不要解释。"
                    "请围绕 feedback_text、selection_explanation、followup_question、derived_tags 组织结果，字段内容保持简短。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "interaction.feedback",
                        "prompt_version": INTERACTION_FEEDBACK_PROMPT_VERSION,
                        "output_schema": {
                            "feedback_text": "string",
                            "selection_explanation": "string",
                            "followup_question": "string",
                            "derived_tags": [
                                {
                                    "tag_id": "string",
                                    "score": 0.0,
                                }
                            ],
                        },
                        "context": prompt_context,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ]
        if not self._remote_model_enabled():
            result = self._fallback_interaction_feedback(prompt_context)
            status = "degraded"
            degrade_reason = "远端模型默认关闭，已使用本地兜底"
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        else:
            try:
                response = self._call_chat_completion_best_effort(
                    capability="interaction.feedback",
                    messages=messages,
                    max_tokens=220,
                    temperature=0.3,
                )
                parsed = self._parse_model_result(response)
                if parsed is None:
                    raw_text = self._extract_model_text(response)
                    if not raw_text:
                        raise ValueError("invalid model response")
                    parsed = {
                        "feedback_text": raw_text,
                        "selection_explanation": "模型已根据本次选择生成反馈。",
                        "followup_question": "如果换一个选择，你觉得剧情会如何变化？",
                    }
                result = self._normalize_interaction_feedback_result(parsed, prompt_context)
                status = "ok"
                degrade_reason = ""
                usage = self._extract_usage(response)
            except Exception as exc:  # pragma: no cover - fallback is exercised by tests
                result = self._fallback_interaction_feedback(prompt_context)
                status = "degraded"
                degrade_reason = str(exc)
                usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        model_info = self._model_info()
        envelope = self._decorate_response(
            capability="interaction.feedback",
            result=result,
            status=status,
            latency_ms=_now_ms() - start_ms,
            usage=usage,
            cache_hit=False,
            model_info=model_info,
            degrade_reason=degrade_reason or None,
        )
        self._set_cache(
            cache_key,
            {
                "result": result,
                "status": status,
                "usage": usage,
                "model": model_info,
            },
            ttl_seconds=self._cache_ttl_seconds(),
        )
        self._append_audit(
            capability="interaction.feedback",
            payload=prompt_context,
            envelope=envelope,
            prompt_version=INTERACTION_FEEDBACK_PROMPT_VERSION,
        )
        return envelope

    def tag_extract(self, payload: dict[str, Any], request_base_url: str) -> dict[str, Any]:
        drama_id = str(payload.get("dramaId", "")).strip()
        episode_id = str(payload.get("episodeId", "")).strip()
        if not episode_id:
            raise ValueError("episodeId is required")
        if not drama_id:
            drama_id = "tainai3"

        drama = get_drama_by_id(drama_id)
        episode = get_episode_by_id(episode_id)
        if drama is None or episode is None:
            raise ValueError("episode or drama not found")

        interaction_payload = build_interaction_nodes(request_base_url, episode_id)
        prompt_context = {
            "drama": {
                "dramaId": drama["drama_id"],
                "title": drama["title"],
                "description": drama["description"],
                "tags": drama["tags"],
                "characters": drama.get("characters", []),
                "interaction_hint": drama.get("interaction_hint", ""),
            },
            "episode": {
                "episodeId": episode["episode_id"],
                "episodeNo": episode["episode_no"],
                "title": episode["title"],
                "summary": episode["summary"],
            },
            "interaction": {
                "nodeId": str(payload.get("nodeId", "")).strip(),
                "optionId": str(payload.get("optionId", "")).strip(),
                "answerText": str(payload.get("answerText", "")).strip(),
                "sceneSummary": str(payload.get("sceneSummary", "")).strip(),
                "nodeHint": interaction_payload["nodes"] if interaction_payload else [],
            },
            "userContext": {
                "userProfileTags": payload.get("userProfileTags") or [],
                "history": list_watch_history(3),
            },
        }
        cache_key = self._make_cache_key(
            "tag.extract",
            {
                "prompt_version": TAG_EXTRACT_PROMPT_VERSION,
                "context": prompt_context,
            },
        )
        cached = self._get_cache(cache_key)
        if cached is not None:
            envelope = self._decorate_response(
                capability="tag.extract",
                result=cached["result"],
                status=cached["status"],
                latency_ms=0,
                usage=cached["usage"],
                cache_hit=True,
                model_info=cached["model"],
            )
            self._append_audit(
                capability="tag.extract",
                payload=prompt_context,
                envelope=envelope,
                prompt_version=TAG_EXTRACT_PROMPT_VERSION,
            )
            return envelope

        start_ms = _now_ms()
        messages = [
            {
                "role": "system",
                "content": (
                    "你是短剧标签抽取助手。"
                    "只输出 JSON，不要 Markdown，不要解释。"
                    "请围绕 content_tags、interaction_tags、user_profile_tag_updates 组织结果，字段内容保持简短。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "tag.extract",
                        "prompt_version": TAG_EXTRACT_PROMPT_VERSION,
                        "output_schema": {
                            "content_tags": [
                                {
                                    "tag_id": "string",
                                    "score": 0.0,
                                }
                            ],
                            "interaction_tags": [
                                {
                                    "tag_id": "string",
                                    "score": 0.0,
                                }
                            ],
                            "user_profile_tag_updates": [
                                {
                                    "tag_id": "string",
                                    "delta": 0.0,
                                }
                            ],
                        },
                        "context": prompt_context,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ]
        if not self._remote_model_enabled():
            result = self._fallback_tag_extract(prompt_context)
            status = "degraded"
            degrade_reason = "远端模型默认关闭，已使用本地兜底"
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        else:
            try:
                response = self._call_chat_completion_best_effort(
                    capability="tag.extract",
                    messages=messages,
                    max_tokens=220,
                    temperature=0.2,
                )
                parsed = self._parse_model_result(response)
                if parsed is None:
                    raise ValueError("invalid model response")
                result = self._normalize_tag_extract_result(parsed, prompt_context)
                status = "ok"
                degrade_reason = ""
                usage = self._extract_usage(response)
            except Exception as exc:  # pragma: no cover - fallback is exercised by tests
                result = self._fallback_tag_extract(prompt_context)
                status = "degraded"
                degrade_reason = str(exc)
                usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        model_info = self._model_info()
        envelope = self._decorate_response(
            capability="tag.extract",
            result=result,
            status=status,
            latency_ms=_now_ms() - start_ms,
            usage=usage,
            cache_hit=False,
            model_info=model_info,
            degrade_reason=degrade_reason or None,
        )
        self._set_cache(
            cache_key,
            {
                "result": result,
                "status": status,
                "usage": usage,
                "model": model_info,
            },
            ttl_seconds=self._cache_ttl_seconds(),
        )
        self._append_audit(
            capability="tag.extract",
            payload=prompt_context,
            envelope=envelope,
            prompt_version=TAG_EXTRACT_PROMPT_VERSION,
        )
        return envelope

    def moderation_check(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = str(
            payload.get("text")
            or payload.get("content")
            or payload.get("message")
            or ""
        ).strip()
        if not text:
            raise ValueError("text is required")

        matched_keywords: list[str] = []
        risk_flags: list[str] = []
        for risk_name, patterns in MODERATION_RISK_PATTERNS.items():
            for pattern in patterns:
                if pattern in text:
                    matched_keywords.append(pattern)
                    risk_flags.append(risk_name)
                    break

        decision = "allow"
        block_reason = ""
        if risk_flags:
            decision = "block"
            block_reason = "内容包含风险关键词"

        result = {
            "decision": decision,
            "risk_flags": sorted(set(risk_flags)),
            "matched_keywords": matched_keywords,
            "review_text": text[:200],
        }
        envelope = {
            "status": "blocked" if decision == "block" else "ok",
            "result": result,
            "model": {
                "provider": "rule",
                "model_name": "local-moderation-rule",
                "base_url": "",
                "endpoint_id": "",
            },
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "latency_ms": 0,
            "cache_hit": False,
            "block_reason": block_reason,
        }
        self._append_audit(
            capability="moderation.check",
            payload={"text_hash": _sha256_text(text), "length": len(text)},
            envelope=envelope,
            prompt_version="moderation.check/v1",
        )
        return envelope

    def discussion_seed(self, payload: dict[str, Any], request_base_url: str) -> dict[str, Any]:
        drama_id = str(payload.get("dramaId", "")).strip() or "tainai3"
        episode_id = str(payload.get("episodeId", "")).strip()
        node_id = str(payload.get("nodeId", "")).strip()
        option_id = str(payload.get("optionId", "")).strip()
        if not episode_id:
            raise ValueError("episodeId is required")

        drama = get_drama_by_id(drama_id)
        episode = get_episode_by_id(episode_id)
        interaction_payload = build_interaction_nodes(request_base_url, episode_id)
        if drama is None or episode is None or interaction_payload is None:
            raise ValueError("episode or drama not found")

        selected_node = next(
            (item for item in interaction_payload["nodes"] if item["id"] == node_id),
            interaction_payload["nodes"][0] if interaction_payload["nodes"] else {},
        )
        selected_option = {}
        if selected_node:
            selected_option = next(
                (item for item in selected_node.get("options", []) if item.get("id") == option_id),
                selected_node.get("options", [{}])[0] if selected_node.get("options") else {},
            )
        prompt_context = {
            "drama": {
                "dramaId": drama["drama_id"],
                "title": drama["title"],
                "description": drama["description"],
                "tags": drama["tags"],
                "characters": drama.get("characters", []),
            },
            "episode": {
                "episodeId": episode["episode_id"],
                "episodeNo": episode["episode_no"],
                "title": episode["title"],
                "summary": episode["summary"],
            },
            "interaction": {
                "node": selected_node,
                "option": selected_option,
                "selectionText": str(
                    payload.get("selectionText")
                    or payload.get("answerText")
                    or selected_option.get("text", "")
                ).strip(),
                "recentRecords": list_interaction_records(episode_id)[0:5],
            },
            "history": list_watch_history(5),
        }
        cache_key = self._make_cache_key(
            "discussion.seed",
            {"prompt_version": DISCUSSION_SEED_PROMPT_VERSION, "context": prompt_context},
        )
        cached = self._get_cache(cache_key)
        if cached is not None:
            envelope = self._decorate_response(
                capability="discussion.seed",
                result=cached["result"],
                status=cached["status"],
                latency_ms=0,
                usage=cached["usage"],
                cache_hit=True,
                model_info=cached["model"],
            )
            self._append_audit(
                capability="discussion.seed",
                payload=prompt_context,
                envelope=envelope,
                prompt_version=DISCUSSION_SEED_PROMPT_VERSION,
            )
            return envelope

        start_ms = _now_ms()
        messages = [
            {
                "role": "system",
                "content": (
                    "你是短剧社区讨论运营助手。"
                    "只输出 JSON，不要 Markdown，不要解释。"
                    "请围绕 discussion_questions、character_perspectives、next_episode_predictions、alternate_choice_topics、share_text 组织结果。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "discussion.seed",
                        "prompt_version": DISCUSSION_SEED_PROMPT_VERSION,
                        "output_schema": {
                            "discussion_questions": ["string"],
                            "character_perspectives": [{"name": "string", "question": "string"}],
                            "next_episode_predictions": ["string"],
                            "alternate_choice_topics": ["string"],
                            "share_text": "string",
                        },
                        "context": prompt_context,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ]
        if not self._remote_model_enabled():
            result = self._fallback_discussion_seed(prompt_context)
            status = "degraded"
            degrade_reason = "远端模型默认关闭，已使用本地兜底"
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        else:
            try:
                response = self._call_chat_completion_best_effort(
                    capability="discussion.seed",
                    messages=messages,
                    max_tokens=520,
                    temperature=0.35,
                )
                parsed = self._parse_model_result(response)
                if parsed is None:
                    raw_text = self._extract_model_text(response)
                    if not raw_text or _looks_like_jsonish(raw_text):
                        raise ValueError("invalid model response")
                    parsed = {"discussion_questions": [raw_text]}
                result = self._normalize_discussion_seed_result(parsed, prompt_context)
                status = "ok"
                degrade_reason = ""
                usage = self._extract_usage(response)
            except Exception as exc:  # pragma: no cover - fallback is exercised by tests
                result = self._fallback_discussion_seed(prompt_context)
                status = "degraded"
                degrade_reason = str(exc)
                usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        model_info = self._model_info()
        envelope = self._decorate_response(
            capability="discussion.seed",
            result=result,
            status=status,
            latency_ms=_now_ms() - start_ms,
            usage=usage,
            cache_hit=False,
            model_info=model_info,
            degrade_reason=degrade_reason or None,
        )
        self._set_cache(
            cache_key,
            {"result": result, "status": status, "usage": usage, "model": model_info},
            ttl_seconds=self._cache_ttl_seconds(),
        )
        self._append_audit(
            capability="discussion.seed",
            payload=prompt_context,
            envelope=envelope,
            prompt_version=DISCUSSION_SEED_PROMPT_VERSION,
        )
        return envelope

    def story_continuation(self, payload: dict[str, Any], request_base_url: str) -> dict[str, Any]:
        drama_id = str(payload.get("dramaId", "")).strip() or "tainai3"
        episode_id = str(payload.get("episodeId", "")).strip()
        user_intent = _sanitize_user_creative_text(payload.get("userIntent"))
        desired_ending = _sanitize_user_creative_text(payload.get("desiredEnding"))
        visual_direction = _sanitize_user_creative_text(payload.get("visualDirection"))
        if not episode_id:
            raise ValueError("episodeId is required")

        drama = get_drama_by_id(drama_id)
        episode = get_episode_by_id(episode_id)
        if drama is None or episode is None:
            raise ValueError("episode or drama not found")

        prompt_context = {
            "drama": {
                "dramaId": drama["drama_id"],
                "title": drama["title"],
                "description": drama["description"],
                "characters": drama.get("characters", []),
            },
            "episode": {
                "episodeId": episode["episode_id"],
                "episodeNo": episode["episode_no"],
                "title": episode["title"],
                "summary": episode["summary"],
                "durationMs": episode["duration_ms"],
            },
            "videoEvidence": _load_video_understanding_evidence(episode_id),
            "recentInteractions": list_interaction_records(episode_id)[0:5],
            "userCreativeIntent": {
                "userIntent": user_intent,
                "desiredEnding": desired_ending,
                "visualDirection": visual_direction,
            },
            "requestBaseUrl": request_base_url,
        }
        prompt_refinement = self._refine_creative_prompt(prompt_context, target="video")
        prompt_context["promptRefinement"] = prompt_refinement
        cache_key = self._make_cache_key(
            "story.continuation",
            {
                "prompt_version": STORY_CONTINUATION_PROMPT_VERSION,
                "request_base_url": request_base_url,
                "context": prompt_context,
            },
        )
        cached = self._get_cache(cache_key)
        if cached is not None:
            envelope = self._decorate_response(
                capability="story.continuation",
                result=cached["result"],
                status=cached["status"],
                latency_ms=0,
                usage=cached["usage"],
                cache_hit=True,
                model_info=cached["model"],
            )
            self._append_audit(
                capability="story.continuation",
                payload=prompt_context,
                envelope=envelope,
                prompt_version=STORY_CONTINUATION_PROMPT_VERSION,
            )
            return envelope

        start_ms = _now_ms()
        messages = [
            {
                "role": "system",
                "content": (
                    "你是互动短剧的下一幕编剧。基于本集摘要、ASR/OCR证据与角色信息，"
                    "生成承接结尾但不冒充原剧正片的三秒幻想续写预演。"
                    "只输出 JSON，不要 Markdown，不要解释。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "story.continuation",
                        "prompt_version": STORY_CONTINUATION_PROMPT_VERSION,
                        "output_schema": {
                            "continuation_title": "string",
                            "continuation_summary": "string",
                            "scene_direction": "string",
                            "dialogue_lines": ["string"],
                            "viewer_hook": "string",
                        },
                        "context": prompt_context,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ]
        if not self._remote_model_enabled():
            result = self._fallback_story_continuation(prompt_context)
            status = "degraded"
            degrade_reason = "远端模型默认关闭，已使用本地兜底"
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        else:
            try:
                response = self._call_chat_completion_best_effort(
                    capability="story.continuation",
                    messages=messages,
                    max_tokens=480,
                    temperature=0.6,
                )
                parsed = self._parse_model_result(response)
                if parsed is None:
                    raise ValueError("invalid model response")
                result = self._normalize_story_continuation_result(parsed, prompt_context)
                status = "ok"
                degrade_reason = ""
                usage = self._extract_usage(response)
            except Exception as exc:  # pragma: no cover - 网络与远端模型异常走降级路径
                result = self._fallback_story_continuation(prompt_context)
                status = "degraded"
                degrade_reason = str(exc)
                usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        result["prompt_refinement"] = _snake_case_prompt_refinement(prompt_refinement)

        clip_id = f"continuation_{episode_id}_{_hash_json(result)[:10]}"
        result["generated_asset"] = get_aigc_insert_provider().build_insert(
            episode_id=episode_id,
            node={
                "id": clip_id,
                "title": result["continuation_title"],
                "generatedTitle": result["continuation_title"],
                "generatedHighEnergyLine": result["dialogue_lines"][0],
                "generatedSubtitle": result["scene_direction"],
                "badgeText": "AI 生成 · 下一幕预演",
                "progressText": "续写展开",
                "playbackMode": "POST_EPISODE_CONTINUATION",
                "trigger": {"timeMs": episode["duration_ms"]},
                "userIntent": user_intent,
                "desiredEnding": desired_ending,
                "visualDirection": visual_direction,
                "creativePrompt": prompt_refinement,
            },
            episode_summary=result["continuation_summary"],
            request_base_url=request_base_url,
        )
        model_info = self._model_info()
        envelope = self._decorate_response(
            capability="story.continuation",
            result=result,
            status=status,
            latency_ms=_now_ms() - start_ms,
            usage=usage,
            cache_hit=False,
            model_info=model_info,
            degrade_reason=degrade_reason or None,
        )
        self._set_cache(
            cache_key,
            {"result": result, "status": status, "usage": usage, "model": model_info},
            ttl_seconds=self._cache_ttl_seconds(),
        )
        self._append_audit(
            capability="story.continuation",
            payload=prompt_context,
            envelope=envelope,
            prompt_version=STORY_CONTINUATION_PROMPT_VERSION,
        )
        return envelope

    def history_recap(self, payload: dict[str, Any], request_base_url: str) -> dict[str, Any]:
        size = _safe_int(payload.get("size"), 5, minimum=1, maximum=20)
        drama_id = str(payload.get("dramaId", "")).strip()
        raw_history = list_watch_history(size)
        if drama_id:
            raw_history = [item for item in raw_history if str(item.get("drama_id", "")) == drama_id]

        history_items = []
        for record in raw_history:
            episode = get_episode_by_id(str(record.get("episode_id", ""))) or {}
            drama = get_drama_by_id(str(record.get("drama_id", ""))) or get_drama_by_id("tainai3") or {}
            duration_ms = _safe_int(record.get("duration_ms"), int(episode.get("duration_ms", 0) or 0))
            progress_ms = _safe_int(record.get("progress_ms"), 0)
            history_items.append(
                {
                    "drama_id": record.get("drama_id", drama.get("drama_id", "")),
                    "drama_title": drama.get("title", ""),
                    "episode_id": record.get("episode_id", ""),
                    "episode_title": episode.get("title", ""),
                    "episode_summary": episode.get("summary", ""),
                    "progress_ms": progress_ms,
                    "duration_ms": duration_ms,
                    "is_completed": bool(record.get("is_completed", False)),
                    "progress_text": _format_progress_text(progress_ms, duration_ms),
                }
            )

        prompt_context = {"history": history_items, "request": {"size": size, "dramaId": drama_id}}
        cache_key = self._make_cache_key(
            "history.recap",
            {"prompt_version": HISTORY_RECAP_PROMPT_VERSION, "context": prompt_context},
        )
        cached = self._get_cache(cache_key)
        if cached is not None:
            envelope = self._decorate_response(
                capability="history.recap",
                result=cached["result"],
                status=cached["status"],
                latency_ms=0,
                usage=cached["usage"],
                cache_hit=True,
                model_info=cached["model"],
            )
            self._append_audit(
                capability="history.recap",
                payload=prompt_context,
                envelope=envelope,
                prompt_version=HISTORY_RECAP_PROMPT_VERSION,
            )
            return envelope

        start_ms = _now_ms()
        messages = [
            {
                "role": "system",
                "content": (
                    "你是短剧续播助手。"
                    "只输出 JSON，不要 Markdown，不要解释。"
                    "请围绕 items、summary、next_episode_id、continue_reason 组织结果，帮助用户快速回到上次观看位置。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "history.recap",
                        "prompt_version": HISTORY_RECAP_PROMPT_VERSION,
                        "output_schema": {
                            "items": [
                                {
                                    "episode_id": "string",
                                    "episode_title": "string",
                                    "progress_text": "string",
                                    "recap": "string",
                                    "continue_reason": "string",
                                    "suggested_action": "string",
                                }
                            ],
                            "summary": "string",
                            "next_episode_id": "string",
                            "continue_reason": "string",
                        },
                        "context": prompt_context,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ]
        if not self._remote_model_enabled():
            result = self._fallback_history_recap(prompt_context)
            status = "degraded"
            degrade_reason = "远端模型默认关闭，已使用本地兜底"
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        else:
            try:
                response = self._call_chat_completion_best_effort(
                    capability="history.recap",
                    messages=messages,
                    max_tokens=480,
                    temperature=0.25,
                )
                parsed = self._parse_model_result(response)
                if parsed is None:
                    raw_text = self._extract_model_text(response)
                    if not raw_text or _looks_like_jsonish(raw_text):
                        raise ValueError("invalid model response")
                    parsed = {"summary": raw_text}
                result = self._normalize_history_recap_result(parsed, prompt_context)
                status = "ok"
                degrade_reason = ""
                usage = self._extract_usage(response)
            except Exception as exc:  # pragma: no cover - fallback is exercised by tests
                result = self._fallback_history_recap(prompt_context)
                status = "degraded"
                degrade_reason = str(exc)
                usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        model_info = self._model_info()
        envelope = self._decorate_response(
            capability="history.recap",
            result=result,
            status=status,
            latency_ms=_now_ms() - start_ms,
            usage=usage,
            cache_hit=False,
            model_info=model_info,
            degrade_reason=degrade_reason or None,
        )
        self._set_cache(
            cache_key,
            {"result": result, "status": status, "usage": usage, "model": model_info},
            ttl_seconds=self._cache_ttl_seconds(),
        )
        self._append_audit(
            capability="history.recap",
            payload=prompt_context,
            envelope=envelope,
            prompt_version=HISTORY_RECAP_PROMPT_VERSION,
        )
        return envelope

    def recommend_home(self, payload: dict[str, Any], request_base_url: str) -> dict[str, Any]:
        size = _safe_int(payload.get("size"), 5, minimum=1, maximum=20)
        drama_id = str(payload.get("dramaId", "")).strip()
        candidates = list_home_items(request_base_url, size)
        if drama_id:
            candidates = [item for item in candidates if str(item.get("drama_id", "")) == drama_id]
        prompt_context = {
            "candidates": candidates,
            "history": list_watch_history(10),
            "interactionRecords": list_interaction_records(None)[0:10],
            "request": {"size": size, "dramaId": drama_id},
        }
        cache_key = self._make_cache_key(
            "recommend.home",
            {"prompt_version": RECOMMEND_HOME_PROMPT_VERSION, "context": prompt_context},
        )
        cached = self._get_cache(cache_key)
        if cached is not None:
            envelope = self._decorate_response(
                capability="recommend.home",
                result=cached["result"],
                status=cached["status"],
                latency_ms=0,
                usage=cached["usage"],
                cache_hit=True,
                model_info=cached["model"],
            )
            self._append_audit(
                capability="recommend.home",
                payload=prompt_context,
                envelope=envelope,
                prompt_version=RECOMMEND_HOME_PROMPT_VERSION,
            )
            return envelope

        start_ms = _now_ms()
        messages = [
            {
                "role": "system",
                "content": (
                    "你是短剧首页推荐解释助手。"
                    "只输出 JSON，不要 Markdown，不要解释。"
                    "请围绕 items、strategy、personalization_signals 组织结果，推荐理由要结合互动和观看行为。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "recommend.home",
                        "prompt_version": RECOMMEND_HOME_PROMPT_VERSION,
                        "output_schema": {
                            "items": [
                                {
                                    "drama_id": "string",
                                    "title": "string",
                                    "rank": 1,
                                    "reason": "string",
                                    "score": 0.0,
                                    "tags": ["string"],
                                }
                            ],
                            "strategy": "string",
                            "personalization_signals": ["string"],
                        },
                        "context": prompt_context,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ]
        if not self._remote_model_enabled():
            result = self._fallback_recommend_home(prompt_context)
            status = "degraded"
            degrade_reason = "远端模型默认关闭，已使用本地兜底"
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        else:
            try:
                response = self._call_chat_completion_best_effort(
                    capability="recommend.home",
                    messages=messages,
                    max_tokens=420,
                    temperature=0.25,
                )
                parsed = self._parse_model_result(response)
                if parsed is None:
                    raw_text = self._extract_model_text(response)
                    if not raw_text or _looks_like_jsonish(raw_text):
                        raise ValueError("invalid model response")
                    parsed = {"strategy": raw_text}
                result = self._normalize_recommend_home_result(parsed, prompt_context)
                status = "ok"
                degrade_reason = ""
                usage = self._extract_usage(response)
            except Exception as exc:  # pragma: no cover - fallback is exercised by tests
                result = self._fallback_recommend_home(prompt_context)
                status = "degraded"
                degrade_reason = str(exc)
                usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        model_info = self._model_info()
        envelope = self._decorate_response(
            capability="recommend.home",
            result=result,
            status=status,
            latency_ms=_now_ms() - start_ms,
            usage=usage,
            cache_hit=False,
            model_info=model_info,
            degrade_reason=degrade_reason or None,
        )
        self._set_cache(
            cache_key,
            {"result": result, "status": status, "usage": usage, "model": model_info},
            ttl_seconds=self._cache_ttl_seconds(),
        )
        self._append_audit(
            capability="recommend.home",
            payload=prompt_context,
            envelope=envelope,
            prompt_version=RECOMMEND_HOME_PROMPT_VERSION,
        )
        return envelope

    def agnes_status(self) -> dict[str, Any]:
        return AgnesClient().status()

    def checkin_card(self, payload: dict[str, Any], request_base_url: str) -> dict[str, Any]:
        drama_id = str(payload.get("dramaId") or "tainai3").strip()
        episode_id = str(payload.get("episodeId") or "").strip()
        moment_id = str(payload.get("momentId") or "").strip()
        style = str(payload.get("style") or "short_drama_poster").strip() or "short_drama_poster"
        user_intent = _sanitize_user_creative_text(payload.get("userIntent"))
        desired_ending = _sanitize_user_creative_text(payload.get("desiredEnding"))
        visual_direction = _sanitize_user_creative_text(payload.get("visualDirection"))
        if not episode_id:
            raise ValueError("episodeId is required")
        drama = get_drama_by_id(drama_id)
        episode = get_episode_by_id(episode_id)
        if drama is None or episode is None:
            raise ValueError("episode or drama not found")

        prompt_context = build_checkin_card_context(
            request_base_url=request_base_url,
            drama=drama,
            episode=episode,
            moment_id=moment_id,
            style=style,
        )
        prompt_context["userCreativeIntent"] = {
            "userIntent": user_intent,
            "desiredEnding": desired_ending,
            "visualDirection": visual_direction,
        }
        prompt_refinement = self._refine_creative_prompt(prompt_context, target="image")
        prompt_context["promptRefinement"] = prompt_refinement
        prompt = build_checkin_card_prompt(prompt_context)
        start_ms = _now_ms()
        agnes = AgnesClient()
        image_result = agnes.generate_image(prompt, size="1024x1024", n=1)
        remote_image_url = str(image_result.get("media_url") or "")
        asset_cache = (
            cache_remote_generated_asset(
                remote_url=remote_image_url,
                media_type="image/png",
                request_base_url=request_base_url,
                asset_hint=f"checkin_card_{drama_id}_{episode_id}_{style}",
            )
            if image_result.get("status") == "ok" and remote_image_url
            else {}
        )
        status = "ok" if image_result.get("status") == "ok" and remote_image_url else "degraded"
        degrade_reason = "" if status == "ok" else str(image_result.get("degrade_reason") or "agnes image unavailable")
        latency_ms = _safe_int(image_result.get("latency_ms"), _now_ms() - start_ms, minimum=0)
        result = {
            "title": prompt_context["title"],
            "prompt": prompt,
            "imageUrl": str(asset_cache.get("mediaUrl") or remote_image_url),
            "remoteImageUrl": remote_image_url,
            "assetCache": asset_cache,
            "provider": "agnes" if status == "ok" else "local_fallback",
            "status": status,
            "latencyMs": latency_ms,
            "degradeReason": degrade_reason,
            "style": prompt_context["style"],
            "styleLabel": prompt_context["styleLabel"],
            "promptRefinement": prompt_refinement,
            "episodeId": episode_id,
            "momentId": moment_id,
        }
        if status != "ok":
            result["fallbackCard"] = fallback_checkin_card(prompt_context)
        envelope = self._decorate_response(
            capability="agnes.image.checkin",
            result=result,
            status=status,
            latency_ms=latency_ms,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            cache_hit=False,
            model_info={
                "provider": "agnes",
                "model_name": agnes.credentials.image_model,
                "source_path": getattr(agnes.credentials, "source", ""),
            },
            degrade_reason=degrade_reason or None,
        )
        self._append_audit(
            capability="agnes.image.checkin",
            payload=prompt_context,
            envelope=envelope,
            prompt_version=CHECKIN_CARD_PROMPT_VERSION,
            restore_last_success=False,
        )
        return envelope

    def _call_chat_completion(
        self,
        capability: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
        json_mode: bool = True,
    ) -> dict[str, Any]:
        body = {
            "model": self.credentials.endpoint_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        curl_error: RuntimeError | None = None
        if shutil.which("curl.exe") is not None:
            try:
                return self._call_chat_completion_with_curl(capability, body)
            except RuntimeError as exc:
                curl_error = exc

        request = urlrequest.Request(
            f"{self.credentials.base_url.rstrip('/')}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.credentials.api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlrequest.urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
                response_text = response.read().decode("utf-8")
        except urlerror.HTTPError as exc:  # pragma: no cover - exercised in fallback scenarios
            response_text = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{capability} 请求失败: HTTP {exc.code} {response_text}") from exc
        except Exception as exc:  # pragma: no cover - exercised in fallback scenarios
            prefix = f"{curl_error}; " if curl_error is not None else ""
            raise RuntimeError(f"{capability} 请求失败: {prefix}{exc}") from exc

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{capability} 响应不是有效 JSON") from exc

    def _call_chat_completion_with_curl(self, capability: str, body: dict[str, Any]) -> dict[str, Any]:
        command = [
            "curl.exe",
            "-s",
            "--max-time",
            str(DEFAULT_TIMEOUT_SECONDS),
            "-X",
            "POST",
            f"{self.credentials.base_url.rstrip('/')}/chat/completions",
            "-H",
            "Content-Type: application/json",
            "-H",
            f"Authorization: Bearer {self.credentials.api_key}",
            "--data-binary",
            "@-",
        ]
        try:
            completed = subprocess.run(
                command,
                input=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=DEFAULT_TIMEOUT_SECONDS + 2,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:  # pragma: no cover - network dependent
            raise RuntimeError(f"{capability} curl 请求超时") from exc

        response_text = completed.stdout.decode("utf-8", errors="replace")
        error_text = completed.stderr.decode("utf-8", errors="replace")
        if completed.returncode != 0:
            raise RuntimeError(f"{capability} curl 请求失败({completed.returncode}): {error_text or response_text}")

        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{capability} curl 响应不是有效 JSON: {response_text[:300]}") from exc

        if isinstance(parsed, dict) and parsed.get("error"):
            raise RuntimeError(f"{capability} 模型返回错误: {parsed.get('error')}")
        return parsed

    def _call_chat_completion_best_effort(
        self,
        capability: str,
        messages: list[dict[str, str]],
        *,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        future = _MODEL_EXECUTOR.submit(
            self._call_chat_completion,
            capability,
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=True,
        )
        try:
            return future.result(timeout=self._model_wait_seconds())
        except RuntimeError as exc:
            if not _looks_response_format_unsupported(str(exc)):
                raise
            fallback_future = _MODEL_EXECUTOR.submit(
                self._call_chat_completion,
                capability,
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                json_mode=False,
            )
            try:
                return fallback_future.result(timeout=self._model_wait_seconds())
            except FutureTimeoutError as timeout_exc:
                raise TimeoutError(f"{capability} 模型调用超时") from timeout_exc
        except FutureTimeoutError as exc:
            raise TimeoutError(f"{capability} 模型调用超时") from exc

    def _model_info(self) -> dict[str, str]:
        return {
            "provider": "volcengine-ark",
            "model_name": self.credentials.endpoint_id,
            "endpoint_id": self.credentials.endpoint_id,
            "base_url": self.credentials.base_url,
            "source_path": self.credentials.source_path,
        }

    def _decorate_response(
        self,
        *,
        capability: str,
        result: dict[str, Any],
        status: str,
        latency_ms: int,
        usage: dict[str, int],
        cache_hit: bool,
        model_info: dict[str, Any],
        degrade_reason: str | None = None,
        block_reason: str | None = None,
    ) -> dict[str, Any]:
        data = {
            "capability": capability,
            "status": status,
            "cached": cache_hit,
            "model": model_info,
            "usage": usage,
            "latency_ms": latency_ms,
            "result": result,
        }
        if degrade_reason:
            data["degrade_reason"] = degrade_reason
        if block_reason:
            data["block_reason"] = block_reason
        return data

    def _fallback_content_recap(self, context: dict[str, Any]) -> dict[str, Any]:
        episode = context["episode"]
        drama = context["drama"]
        nodes = context["interaction"]["nodes"]
        video_evidence = context.get("videoEvidence", {})
        evidence_summary = str(video_evidence.get("summary") or "").strip()
        transcript = str(video_evidence.get("transcript") or "").strip()
        ocr_texts = [
            str(item.get("text") or "").strip()
            for item in video_evidence.get("screenTextCues", [])
            if isinstance(item, dict) and str(item.get("text") or "").strip()
        ]
        highlights = [
            f"本集标题：{episode['title']}",
            f"主线简介：{episode['summary']}",
        ]
        if transcript:
            highlights.append(f"ASR台词证据：{transcript[:80]}")
        if ocr_texts:
            highlights.append(f"OCR屏幕文字：{'；'.join(ocr_texts[:2])[:80]}")
        if nodes:
            highlights.append(f"本集包含 {len(nodes)} 个互动节点，可围绕选择结果展开讨论。")
        seeds = [
            "如果你站在主角视角，会不会做出同样的选择？",
            "这个选择对后续关系线意味着什么？",
        ]
        if context["history"]:
            seeds.append("结合最近观看记录，这一集最值得补看的冲突点是什么？")
        return {
            "drama_id": drama["dramaId"],
            "episode_id": episode["episodeId"],
            "summary": evidence_summary or f"{drama['title']} 的 {episode['title']} 主要围绕 {episode['summary']} 展开。",
            "highlights": highlights,
            "character_focus": [item["name"] for item in context["drama"].get("characters", [])] if context["drama"].get("characters") else [],
            "discussion_seeds": seeds,
            "continue_reason": "这一集已经建立了关键冲突，继续观看可以看到互动选择如何影响剧情走向。",
        }

    def _normalize_content_recap_result(self, parsed: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        result = parsed.get("result") if isinstance(parsed.get("result"), dict) else parsed
        summary = str(result.get("summary") or "").strip()
        if not summary:
            evidence_summary = str(context.get("videoEvidence", {}).get("summary") or "").strip()
            summary = evidence_summary or f"{context['drama']['title']} 的 {context['episode']['title']} 主要围绕 {context['episode']['summary']} 展开。"
        evidence_highlights = _video_evidence_highlights(context.get("videoEvidence", {}))
        return {
            "drama_id": context["drama"]["dramaId"],
            "episode_id": context["episode"]["episodeId"],
            "summary": summary,
            "highlights": _ensure_string_list(result.get("highlights"), fallback=[
                *(evidence_highlights or [context["episode"]["summary"]]),
            ]),
            "character_focus": _ensure_string_list(result.get("character_focus"), fallback=[
                item["name"] for item in context["drama"].get("characters", [])
            ]),
            "discussion_seeds": _ensure_string_list(result.get("discussion_seeds"), fallback=[
                "如果你是主角，你会怎么选？",
                "这一幕之后最可能发生什么？",
            ]),
            "continue_reason": str(
                result.get("continue_reason")
                or "继续观看可以看到互动选择对剧情的后续影响。"
            ).strip(),
        }

    def _fallback_interaction_feedback(self, context: dict[str, Any]) -> dict[str, Any]:
        node = context["node"]
        option = context["option"]
        base_text = f"你选择了「{option['text']}」，系统已经记录这次倾向。"
        if node["type"] == "REACTION_PULSE":
            selection_explanation = "这是人物登场的即时评价，会用于判断你对角色魅力和名场面的兴趣。"
            followup_question = "这个角色刚出场时，最吸引你的是颜值、气场还是反差感？"
        elif node["type"] == "SCREEN_TEXT_REACTION":
            selection_explanation = "这是画面文字触发的互动，会用于识别你对人物设定和隐藏身份线的兴趣。"
            followup_question = "你更想继续挖这个角色的履历，还是看她马上反击？"
        elif node["type"] == "PLOT_EXPECTATION":
            selection_explanation = "这是剧情爽点偏好反馈，会影响后续讨论和推荐解释。"
            followup_question = "接下来你最期待身份揭晓、继续反转还是家族对线？"
        else:
            selection_explanation = "这是一次轻量互动，更适合用来观察你的剧情偏好。"
            followup_question = "如果站在旁观者视角，你会如何解释这个选择？"
        return {
            "feedback_text": base_text,
            "selection_explanation": selection_explanation,
            "followup_question": followup_question,
            "derived_tags": [
                {
                    "tag_id": "interaction.intent.choice",
                    "score": 0.8,
                    "source": "rule",
                }
            ],
        }

    def _normalize_interaction_feedback_result(self, parsed: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        result = parsed.get("result") if isinstance(parsed.get("result"), dict) else parsed
        feedback_text = str(result.get("feedback_text") or result.get("feedback") or "").strip()
        if not feedback_text:
            feedback_text = f"你选择了「{context['option']['text']}」，系统已经记录这次倾向。"
        return {
            "feedback_text": feedback_text,
            "selection_explanation": str(
                result.get("selection_explanation")
                or "系统已经根据你的选择更新了偏好信号。"
            ).strip(),
            "followup_question": str(
                result.get("followup_question")
                or "如果换成另一种选择，你觉得人物关系会怎么变？"
            ).strip(),
            "derived_tags": _ensure_tag_list(
                result.get("derived_tags"),
                fallback=[
                    {
                        "tag_id": "interaction.intent.choice",
                        "score": 0.8,
                        "source": "rule",
                    }
                ],
            ),
        }

    def _fallback_tag_extract(self, context: dict[str, Any]) -> dict[str, Any]:
        node_id = str(context["interaction"].get("nodeId", "")).strip()
        option_id = str(context["interaction"].get("optionId", "")).strip()
        content_tags = [
            {
                "tag_id": "content.genre.short_drama",
                "score": 0.9,
                "source": "rule",
            },
            {
                "tag_id": "content.trope.interactive_choice",
                "score": 0.82,
                "source": "rule",
            },
        ]
        if node_id == "n_123_profile_text_reaction":
            content_tags.append(
                {
                    "tag_id": "content.trope.hidden_identity",
                    "score": 0.88,
                    "source": "rule",
                }
            )
        interaction_tags = [
            {
                "tag_id": "interaction.intent.choice",
                "score": 0.85,
                "source": "rule",
            },
            {
                "tag_id": f"interaction.option.{option_id or 'unknown'}",
                "score": 0.6,
                "source": "rule",
            },
        ]
        user_updates = [
            {
                "tag_id": "user.tendency.engagement.interactive",
                "delta": 0.05,
                "source": "rule",
            }
        ]
        return {
            "content_tags": content_tags,
            "interaction_tags": interaction_tags,
            "user_profile_tag_updates": user_updates,
        }

    def _normalize_tag_extract_result(self, parsed: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        result = parsed.get("result") if isinstance(parsed.get("result"), dict) else parsed
        return {
            "content_tags": _ensure_tag_list(
                result.get("content_tags"),
                fallback=[
                    {
                        "tag_id": "content.genre.short_drama",
                        "score": 0.9,
                        "source": "rule",
                    }
                ],
            ),
            "interaction_tags": _ensure_tag_list(
                result.get("interaction_tags"),
                fallback=[
                    {
                        "tag_id": "interaction.intent.choice",
                        "score": 0.85,
                        "source": "rule",
                    }
                ],
            ),
            "user_profile_tag_updates": _ensure_profile_updates(
                result.get("user_profile_tag_updates"),
                fallback=[
                    {
                        "tag_id": "user.tendency.engagement.interactive",
                        "delta": 0.05,
                        "source": "rule",
                    }
                ],
            ),
        }

    def _fallback_discussion_seed(self, context: dict[str, Any]) -> dict[str, Any]:
        episode = context["episode"]
        option_text = str(context["interaction"].get("selectionText") or "").strip()
        characters = context["drama"].get("characters", [])
        selected_text = f"围绕「{option_text}」" if option_text else "围绕当前互动"
        return {
            "episode_id": episode["episodeId"],
            "discussion_questions": [
                f"{selected_text}，你觉得主角最真实的动机是什么？",
                "如果这一幕换一个选择，人物关系会向哪个方向变化？",
                "这一集埋下的最大反转线索是什么？",
            ],
            "character_perspectives": [
                {
                    "name": item.get("name", "角色"),
                    "question": f"站在{item.get('name', '角色')}视角，这个选择值不值得？",
                }
                for item in characters[:3]
            ],
            "next_episode_predictions": [
                "下一集可能会揭示本次选择背后的代价。",
                "家族关系线会因为站队结果出现新的冲突。",
            ],
            "alternate_choice_topics": [
                "如果选择另一条分支，剧情节奏会更激进还是更稳妥？",
                "你更想看高风险推进还是缓慢试探？",
            ],
            "share_text": f"我刚看完{episode['title']}，这个互动选择很适合拉朋友一起讨论。",
        }

    def _normalize_discussion_seed_result(self, parsed: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        result = parsed.get("result") if isinstance(parsed.get("result"), dict) else parsed
        fallback = self._fallback_discussion_seed(context)
        character_perspectives: list[dict[str, str]] = []
        raw_perspectives = result.get("character_perspectives")
        if isinstance(raw_perspectives, list):
            for item in raw_perspectives:
                if isinstance(item, dict):
                    name = str(item.get("name") or item.get("character") or "").strip()
                    question = str(item.get("question") or item.get("text") or "").strip()
                    if name or question:
                        character_perspectives.append(
                            {
                                "name": name or "角色",
                                "question": question or "你会如何理解这个角色的选择？",
                            }
                        )
                elif isinstance(item, str) and item.strip():
                    character_perspectives.append({"name": "角色", "question": item.strip()})
        return {
            "episode_id": context["episode"]["episodeId"],
            "discussion_questions": _ensure_string_list(
                result.get("discussion_questions"),
                fallback=fallback["discussion_questions"],
            ),
            "character_perspectives": character_perspectives or fallback["character_perspectives"],
            "next_episode_predictions": _ensure_string_list(
                result.get("next_episode_predictions"),
                fallback=fallback["next_episode_predictions"],
            ),
            "alternate_choice_topics": _ensure_string_list(
                result.get("alternate_choice_topics"),
                fallback=fallback["alternate_choice_topics"],
            ),
            "share_text": str(result.get("share_text") or fallback["share_text"]).strip(),
        }

    def _fallback_story_continuation(self, context: dict[str, Any]) -> dict[str, Any]:
        episode = context["episode"]
        characters = context["drama"].get("characters", [])
        lead_name = str(characters[0].get("canonical_name") or characters[0].get("name") or "容遇") if characters else "容遇"
        return {
            "episode_id": episode["episodeId"],
            "continuation_title": "未完的反击",
            "continuation_summary": (
                f"{episode['title']}落幕后，{lead_name}没有退让，反而当众提出一份能改写家族局面的证据，"
                "众人的站队被迫重新洗牌。"
            ),
            "scene_direction": "门厅灯光骤暗，证据文件被推到桌面中央",
            "dialogue_lines": [
                f"{lead_name}：现在，该把真正的答案说清楚了。",
                "众人：这份证据到底证明了什么？",
            ],
            "viewer_hook": "如果由你决定，下一幕先公开证据还是先逼问幕后人？",
        }

    def _normalize_story_continuation_result(self, parsed: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        result = parsed.get("result") if isinstance(parsed.get("result"), dict) else parsed
        fallback = self._fallback_story_continuation(context)
        return {
            "episode_id": context["episode"]["episodeId"],
            "continuation_title": str(result.get("continuation_title") or result.get("title") or fallback["continuation_title"]).strip(),
            "continuation_summary": str(result.get("continuation_summary") or result.get("summary") or fallback["continuation_summary"]).strip(),
            "scene_direction": str(result.get("scene_direction") or fallback["scene_direction"]).strip(),
            "dialogue_lines": _ensure_string_list(result.get("dialogue_lines"), fallback=fallback["dialogue_lines"])[:3],
            "viewer_hook": str(result.get("viewer_hook") or fallback["viewer_hook"]).strip(),
        }

    def _refine_creative_prompt(self, context: dict[str, Any], *, target: str) -> dict[str, Any]:
        raw_intent = context.get("userCreativeIntent") if isinstance(context.get("userCreativeIntent"), dict) else {}
        user_intent = _sanitize_user_creative_text(raw_intent.get("userIntent"))
        desired_ending = _sanitize_user_creative_text(raw_intent.get("desiredEnding"))
        visual_direction = _sanitize_user_creative_text(raw_intent.get("visualDirection"))
        if not any([user_intent, desired_ending, visual_direction]):
            return _empty_prompt_refinement()

        fallback = _fallback_prompt_refinement(
            user_intent=user_intent,
            desired_ending=desired_ending,
            visual_direction=visual_direction,
        )
        if not self._remote_model_enabled():
            fallback["status"] = "degraded"
            fallback["degradeReason"] = "远端模型默认关闭，已直接使用用户意图"
            return fallback

        messages = [
            {
                "role": "system",
                "content": (
                    "你是短剧 AIGC 创作提示词编排器。把用户想看的方向改写成适合生图/生视频模型的稳定提示词，"
                    "必须贴合当前剧情和人物关系，不泄露 ASR/OCR、弹幕原文、技术流程或密钥。只输出 JSON。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task": "creative.prompt.refine",
                        "prompt_version": CREATIVE_PROMPT_REFINE_VERSION,
                        "target": target,
                        "output_schema": {
                            "intent_summary": "string",
                            "story_direction": "string",
                            "image_prompt_addon": "string",
                            "video_prompt_addon": "string",
                            "negative_prompt": "string",
                            "safety_notes": ["string"],
                        },
                        "user_intent": {
                            "userIntent": user_intent,
                            "desiredEnding": desired_ending,
                            "visualDirection": visual_direction,
                        },
                        "context": {
                            "drama": context.get("drama") or {
                                "title": context.get("dramaTitle"),
                            },
                            "episode": context.get("episode") or {
                                "episodeId": context.get("episodeId"),
                                "episodeNo": context.get("episodeNo"),
                                "title": context.get("episodeTitle"),
                                "summary": context.get("episodeSummary"),
                            },
                            "style": context.get("styleLabel") or context.get("style"),
                            "interactionHooks": context.get("interactionHooks", []),
                            "keywords": context.get("keywords", []),
                        },
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ]
        try:
            response = self._call_chat_completion_best_effort(
                capability="creative.prompt.refine",
                messages=messages,
                max_tokens=420,
                temperature=0.45,
            )
            parsed = self._parse_model_result(response)
            if parsed is None:
                raise ValueError("invalid creative prompt response")
            return _normalize_prompt_refinement(
                parsed,
                fallback=fallback,
                user_intent=user_intent,
                desired_ending=desired_ending,
                visual_direction=visual_direction,
            )
        except Exception as exc:  # pragma: no cover - 远端模型异常走降级路径
            fallback["status"] = "degraded"
            fallback["degradeReason"] = str(exc)
            return fallback

    def _fallback_history_recap(self, context: dict[str, Any]) -> dict[str, Any]:
        history = context.get("history", [])
        items = []
        for item in history:
            episode_title = str(item.get("episode_title") or item.get("episode_id") or "短剧")
            summary = str(item.get("episode_summary") or "这一集已经记录了观看进度。")
            items.append(
                {
                    "episode_id": str(item.get("episode_id") or ""),
                    "episode_title": episode_title,
                    "progress_text": str(item.get("progress_text") or "暂无进度"),
                    "recap": summary,
                    "continue_reason": "从上次位置继续可以接上互动节点和剧情冲突。",
                    "suggested_action": "继续播放",
                }
            )
        if not items:
            return {
                "items": [],
                "summary": "暂无观看历史，可以先从第 1 集开始体验互动剧情。",
                "next_episode_id": "tainai3_ep01",
                "continue_reason": "第 1 集包含完整的播放和互动验证链路。",
            }
        return {
            "items": items,
            "summary": f"已找到 {len(items)} 条观看记录，建议从最近未完成的剧集继续。",
            "next_episode_id": items[0]["episode_id"],
            "continue_reason": items[0]["continue_reason"],
        }

    def _normalize_history_recap_result(self, parsed: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        result = parsed.get("result") if isinstance(parsed.get("result"), dict) else parsed
        fallback = self._fallback_history_recap(context)
        items: list[dict[str, str]] = []
        raw_items = result.get("items")
        if isinstance(raw_items, list):
            fallback_by_episode = {
                item["episode_id"]: item
                for item in fallback["items"]
                if item.get("episode_id")
            }
            for raw_item in raw_items:
                if not isinstance(raw_item, dict):
                    continue
                episode_id = str(raw_item.get("episode_id") or raw_item.get("episodeId") or "").strip()
                base = fallback_by_episode.get(episode_id, {})
                items.append(
                    {
                        "episode_id": episode_id or str(base.get("episode_id", "")),
                        "episode_title": str(raw_item.get("episode_title") or base.get("episode_title", "")).strip(),
                        "progress_text": str(raw_item.get("progress_text") or base.get("progress_text", "")).strip(),
                        "recap": str(raw_item.get("recap") or base.get("recap", "")).strip(),
                        "continue_reason": str(
                            raw_item.get("continue_reason") or base.get("continue_reason", "")
                        ).strip(),
                        "suggested_action": str(
                            raw_item.get("suggested_action") or base.get("suggested_action", "继续播放")
                        ).strip(),
                    }
                )
        return {
            "items": items or fallback["items"],
            "summary": str(result.get("summary") or fallback["summary"]).strip(),
            "next_episode_id": str(result.get("next_episode_id") or fallback["next_episode_id"]).strip(),
            "continue_reason": str(result.get("continue_reason") or fallback["continue_reason"]).strip(),
        }

    def _fallback_recommend_home(self, context: dict[str, Any]) -> dict[str, Any]:
        candidates = context.get("candidates", [])
        items = []
        for index, candidate in enumerate(candidates, start=1):
            items.append(
                {
                    "drama_id": str(candidate.get("drama_id") or ""),
                    "title": str(candidate.get("title") or ""),
                    "rank": index,
                    "reason": "该内容包含互动节点，适合继续验证短剧互动体验。",
                    "score": max(0.5, 0.95 - (index - 1) * 0.05),
                    "tags": candidate.get("tags", []),
                }
            )
        signals = ["内容含互动选择", "结合最近观看进度"]
        if context.get("interactionRecords"):
            signals.append("参考了最近互动记录")
        return {
            "items": items,
            "strategy": "优先推荐可完成播放、互动、反馈闭环的短剧内容。",
            "personalization_signals": signals,
        }

    def _normalize_recommend_home_result(self, parsed: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        result = parsed.get("result") if isinstance(parsed.get("result"), dict) else parsed
        fallback = self._fallback_recommend_home(context)
        fallback_by_drama = {
            item["drama_id"]: item
            for item in fallback["items"]
            if item.get("drama_id")
        }
        items: list[dict[str, Any]] = []
        raw_items = result.get("items")
        if isinstance(raw_items, list):
            for index, raw_item in enumerate(raw_items, start=1):
                if not isinstance(raw_item, dict):
                    continue
                drama_id = str(raw_item.get("drama_id") or raw_item.get("dramaId") or "").strip()
                base = fallback_by_drama.get(drama_id, {})
                title = str(raw_item.get("title") or base.get("title", "")).strip()
                if not drama_id and not title:
                    continue
                items.append(
                    {
                        "drama_id": drama_id or str(base.get("drama_id", "")),
                        "title": title,
                        "rank": _safe_int(raw_item.get("rank"), index, minimum=1, maximum=100),
                        "reason": str(raw_item.get("reason") or base.get("reason", "适合继续观看。")).strip(),
                        "score": float(raw_item.get("score", base.get("score", 0.7)) or 0.7),
                        "tags": _ensure_string_list(raw_item.get("tags"), fallback=base.get("tags", [])),
                    }
                )
        return {
            "items": items or fallback["items"],
            "strategy": str(result.get("strategy") or fallback["strategy"]).strip(),
            "personalization_signals": _ensure_string_list(
                result.get("personalization_signals"),
                fallback=fallback["personalization_signals"],
            ),
        }

    def _append_audit(
        self,
        *,
        capability: str,
        payload: dict[str, Any],
        envelope: dict[str, Any],
        prompt_version: str,
        restore_last_success: bool = True,
    ) -> None:
        self._attach_artifact_state(
            capability=capability,
            payload=payload,
            envelope=envelope,
            prompt_version=prompt_version,
            restore_last_success=restore_last_success,
        )
        audit_record = {
            "trace_id": f"ai_{hashlib.sha256((capability + str(time.time())).encode('utf-8')).hexdigest()[:16]}",
            "capability": capability,
            "prompt_version": prompt_version,
            "payload_hash": _hash_json(payload),
            "result_hash": _hash_json(envelope.get("result", {})),
            "status": envelope.get("status", ""),
            "model_name": envelope.get("model", {}).get("model_name", ""),
            "provider": envelope.get("model", {}).get("provider", ""),
            "latency_ms": envelope.get("latency_ms", 0),
            "usage": envelope.get("usage", {}),
            "cache_hit": envelope.get("cached", False),
            "degrade_reason": envelope.get("degrade_reason", ""),
            "block_reason": envelope.get("block_reason", ""),
            "artifact": envelope.get("artifact", {}),
            "created_at_ms": _now_ms(),
        }
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_lock:
            with self.audit_path.open("a", encoding="utf-8") as file_obj:
                file_obj.write(json.dumps(audit_record, ensure_ascii=False, separators=(",", ":")))
                file_obj.write("\n")

    def _attach_artifact_state(
        self,
        *,
        capability: str,
        payload: dict[str, Any],
        envelope: dict[str, Any],
        prompt_version: str,
        restore_last_success: bool = True,
    ) -> None:
        attach_artifact_state(
            capability=capability,
            payload=payload,
            envelope=envelope,
            prompt_version=prompt_version,
            restore_last_success=restore_last_success,
        )

    def _cache_ttl_seconds(self) -> int:
        raw = os.environ.get("AIGC_AI_CACHE_TTL_SECONDS")
        if not raw:
            return DEFAULT_CACHE_TTL_SECONDS
        try:
            ttl = int(raw)
        except ValueError:
            return DEFAULT_CACHE_TTL_SECONDS
        return max(ttl, 1)

    def _model_wait_seconds(self) -> int:
        raw = os.environ.get("AIGC_AI_MODEL_WAIT_SECONDS")
        if not raw:
            return DEFAULT_MODEL_WAIT_SECONDS
        try:
            wait_seconds = int(raw)
        except ValueError:
            return DEFAULT_MODEL_WAIT_SECONDS
        return max(wait_seconds, 1)

    def _remote_model_enabled(self) -> bool:
        raw = os.environ.get("AIGC_AI_REMOTE_MODEL", "").strip().lower()
        if not raw:
            return DEFAULT_REMOTE_MODEL_ENABLED
        return raw in {"1", "true", "yes", "on"}

    def _get_cache(self, cache_key: str) -> dict[str, Any] | None:
        now_ms = _now_ms()
        with self._cache_lock:
            entry = self._cache.get(cache_key)
            if entry is None:
                return None
            if entry.expires_at_ms <= now_ms:
                self._cache.pop(cache_key, None)
                return None
            return entry.value

    def _set_cache(self, cache_key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        if str(value.get("status") or "") != "ok":
            return
        with self._cache_lock:
            self._cache[cache_key] = CacheEntry(
                expires_at_ms=_now_ms() + ttl_seconds * 1000,
                value=value,
            )

    def _make_cache_key(self, capability: str, payload: dict[str, Any]) -> str:
        return f"{capability}:{_hash_json(payload)}"

    def _extract_usage(self, response: dict[str, Any]) -> dict[str, int]:
        usage = response.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    def _parse_model_result(self, response: dict[str, Any]) -> dict[str, Any] | None:
        content = self._extract_model_text(response)
        if not content:
            return None
        return _load_jsonish(content)

    def _extract_model_text(self, response: dict[str, Any]) -> str:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""
        message = first.get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            content = "".join(
                str(item.get("text", "")) if isinstance(item, dict) else str(item)
                for item in content
            )
        if not isinstance(content, str):
            return ""
        return content.strip()


@lru_cache(maxsize=1)
def get_ai_service() -> AIService:
    return AIService.from_environment()


def reset_ai_runtime_for_tests() -> None:
    get_ai_service.cache_clear()


def load_ark_credentials() -> ArkCredentials:
    env_api_key = os.environ.get("ARK_API_KEY", "").strip()
    env_endpoint_id = (
        os.environ.get("ARK_ENDPOINT_ID", "").strip()
        or os.environ.get("ARK_MODEL", "").strip()
        or os.environ.get("ARK_MODEL_ID", "").strip()
    )
    env_base_url = os.environ.get("ARK_BASE_URL", DEFAULT_ARK_BASE_URL).strip() or DEFAULT_ARK_BASE_URL
    if env_api_key and env_endpoint_id:
        return ArkCredentials(
            endpoint_id=env_endpoint_id,
            api_key=env_api_key,
            base_url=env_base_url,
            source_path="env",
        )

    for candidate in _candidate_config_paths():
        if not candidate.exists():
            continue
        parsed = _parse_model_config_text(candidate.read_text(encoding="utf-8-sig", errors="ignore"))
        endpoint_id = parsed.get("endpoint_id", "").strip()
        api_key = parsed.get("api_key", "").strip()
        if endpoint_id and api_key:
            return ArkCredentials(
                endpoint_id=endpoint_id,
                api_key=api_key,
                base_url=env_base_url,
                source_path=str(candidate),
            )

    raise RuntimeError(
        "未找到火山方舟配置，请在 model_apikey.txt 中提供 EP/APIKEY，"
        "或设置 ARK_ENDPOINT_ID 与 ARK_API_KEY 环境变量。"
    )


def resolve_audit_path() -> Path:
    raw = os.environ.get("AIGC_AI_AUDIT_PATH", "").strip()
    if raw:
        return Path(raw)
    return DEFAULT_AUDIT_PATH


def _candidate_config_paths() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        Path(os.environ.get("AIGC_MODEL_CONFIG_PATH", "").strip()) if os.environ.get("AIGC_MODEL_CONFIG_PATH") else None,
        Path.cwd() / DEFAULT_MODEL_CONFIG_FILE,
        repo_root / DEFAULT_MODEL_CONFIG_FILE,
        Path.cwd() / "model_config.txt",
        repo_root / "model_config.txt",
    ]
    return [candidate for candidate in candidates if candidate is not None]


def _load_video_understanding_evidence(episode_id: str, drama_id: str = "tainai3") -> dict[str, Any]:
    root = Path(os.environ.get("AIGC_VIDEO_UNDERSTANDING_ROOT", "tmp/video_understanding_results"))
    path = next(
        (
            candidate
            for candidate in (
                root / drama_id / episode_id / "understanding.json",
                root / episode_id / "understanding.json",
            )
            if candidate.exists()
        ),
        None,
    )
    if path is None:
        return {"status": "missing", "summary": "", "transcript": "", "speakerTranscript": "", "speakerTurns": [], "screenTextCues": [], "highEnergyLines": []}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "unreadable", "summary": "", "transcript": "", "speakerTranscript": "", "speakerTurns": [], "screenTextCues": [], "highEnergyLines": []}
    result = ((document.get("envelope") or {}).get("result") or {}) if isinstance(document, dict) else {}
    audio_text = result.get("audio_text") if isinstance(result.get("audio_text"), dict) else {}
    transcript = str(
        audio_text.get("speaker_transcript")
        or audio_text.get("speakerTranscript")
        or audio_text.get("corrected_transcript")
        or audio_text.get("correctedTranscript")
        or audio_text.get("transcript")
        or ""
    ).strip()
    speaker_turns = audio_text.get("speaker_turns") if isinstance(audio_text.get("speaker_turns"), list) else []
    return {
        "status": "ok",
        "summary": str(result.get("summary") or "").strip(),
        "story_summary": str(result.get("story_summary") or result.get("plot_summary") or result.get("synopsis") or "").strip(),
        "transcript": transcript[:1200],
        "speakerTranscript": transcript[:1200],
        "speakerTurns": speaker_turns[:12],
        "screenTextCues": result.get("screen_text_cues") if isinstance(result.get("screen_text_cues"), list) else [],
        "highEnergyLines": result.get("high_energy_lines") if isinstance(result.get("high_energy_lines"), list) else [],
        "sourcePath": str(path),
    }


def _video_evidence_highlights(video_evidence: Any) -> list[str]:
    if not isinstance(video_evidence, dict) or video_evidence.get("status") != "ok":
        return []
    highlights = []
    transcript = str(video_evidence.get("transcript") or "").strip()
    if transcript:
        highlights.append(f"ASR台词证据：{transcript[:80]}")
    screen_texts = [
        str(item.get("text") or "").strip()
        for item in video_evidence.get("screenTextCues", [])
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    ]
    if screen_texts:
        highlights.append(f"OCR屏幕文字：{'；'.join(screen_texts[:2])[:80]}")
    speaker_turns = []
    for item in video_evidence.get("speakerTurns", []):
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        speaker_turns.append(f"{str(item.get('speaker_name') or item.get('speaker_id') or 'speaker').strip()}：{text}")
        if len(speaker_turns) >= 2:
            break
    if speaker_turns:
        highlights.append(f"说话人分段：{' / '.join(speaker_turns)[:100]}")
    high_lines = []
    for item in video_evidence.get("highEnergyLines", []):
        text = str(item.get("text") if isinstance(item, dict) else item).strip()
        if text:
            high_lines.append(text)
    if high_lines:
        highlights.append(f"高能台词：{high_lines[0][:80]}")
    return highlights


def _parse_model_config_text(text: str) -> dict[str, str]:
    endpoint_id = ""
    api_key = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if re.match(r"^(EP|Endpoint|MODEL)\s*[:：]", line, flags=re.IGNORECASE):
            endpoint_id = re.split(r"[:：]", line, maxsplit=1)[1].strip()
            continue
        if re.match(r"^(APIKEY|API_KEY|KEY)\s*[:：]", line, flags=re.IGNORECASE):
            api_key = re.split(r"[:：]", line, maxsplit=1)[1].strip()
            continue
    return {
        "endpoint_id": endpoint_id,
        "api_key": api_key,
    }


def _hash_json(data: Any) -> str:
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_jsonish(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None

    candidates = [stripped]
    fenced = _strip_code_fence(stripped)
    if fenced:
        candidates.append(fenced)
    bracketed = _extract_first_json_object(stripped)
    if bracketed:
        candidates.append(bracketed)
    repaired = _repair_json_text(bracketed or stripped)
    if repaired:
        candidates.append(repaired)

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, str):
            nested = parsed.strip()
            if nested and nested != candidate and _looks_like_jsonish(nested):
                nested_parsed = _load_jsonish(nested)
                if nested_parsed is not None:
                    return nested_parsed
    return None


def _repair_json_text(text: str) -> str | None:
    candidate = text.strip()
    if not candidate:
        return None
    candidate = _strip_code_fence(candidate) or candidate
    candidate = _extract_first_json_object(candidate) or candidate
    candidate = (
        candidate.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("：", ":")
        .replace("，", ",")
    )
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError:
        pass

    try:
        import ast

        parsed = ast.literal_eval(candidate)
    except (SyntaxError, ValueError):
        return None
    if isinstance(parsed, dict):
        return json.dumps(parsed, ensure_ascii=False)
    return None


def _looks_response_format_unsupported(message: str) -> bool:
    lowered = message.lower()
    return "response_format" in lowered and any(
        keyword in lowered
        for keyword in ("unsupported", "not support", "invalid", "unknown", "不支持", "无效")
    )


def _strip_code_fence(text: str) -> str | None:
    if not text.startswith("```"):
        return None
    lines = text.splitlines()
    if len(lines) < 3:
        return None
    if lines[0].startswith("```") and lines[-1].startswith("```"):
        return "\n".join(lines[1:-1]).strip()
    return None


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    return text[start : end + 1]


def _looks_like_jsonish(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith("{") or stripped.startswith("```") or "\"result\"" in stripped


def _ensure_string_list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = str(item.get("text") or item.get("title") or item.get("value") or "").strip()
            else:
                text = str(item).strip()
            if text:
                result.append(text)
        if result:
            return result
    return fallback


def _sanitize_user_creative_text(value: Any, *, max_length: int = 160) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    for term in ["api_key", "apikey", "secret", "ASR", "OCR", "speaker1", "Speaker 1"]:
        text = text.replace(term, "")
    return text[:max_length].strip()


def _empty_prompt_refinement() -> dict[str, Any]:
    return {
        "status": "disabled",
        "source": "none",
        "intentSummary": "",
        "storyDirection": "",
        "imagePromptAddon": "",
        "videoPromptAddon": "",
        "negativePrompt": "",
        "safetyNotes": [],
        "degradeReason": "",
    }


def _fallback_prompt_refinement(
    *,
    user_intent: str,
    desired_ending: str,
    visual_direction: str,
) -> dict[str, Any]:
    parts = [item for item in [user_intent, desired_ending, visual_direction] if item]
    summary = "；".join(parts)
    story_direction = desired_ending or user_intent
    visual = visual_direction or user_intent
    return {
        "status": "degraded",
        "source": "user_input",
        "intentSummary": summary[:120],
        "storyDirection": story_direction[:160],
        "imagePromptAddon": visual[:180],
        "videoPromptAddon": "，".join(item for item in [story_direction, visual] if item)[:220],
        "negativePrompt": "不要出现技术流程、识别字幕、水印、真实用户弹幕原文",
        "safetyNotes": ["用户意图已做长度限制和技术词清理"],
        "degradeReason": "",
    }


def _normalize_prompt_refinement(
    parsed: dict[str, Any],
    *,
    fallback: dict[str, Any],
    user_intent: str,
    desired_ending: str,
    visual_direction: str,
) -> dict[str, Any]:
    result = parsed.get("result") if isinstance(parsed.get("result"), dict) else parsed
    normalized = {
        "status": "ok",
        "source": "model",
        "intentSummary": str(
            result.get("intent_summary")
            or result.get("intentSummary")
            or fallback.get("intentSummary")
            or user_intent
        ).strip()[:140],
        "storyDirection": str(
            result.get("story_direction")
            or result.get("storyDirection")
            or fallback.get("storyDirection")
            or desired_ending
        ).strip()[:220],
        "imagePromptAddon": str(
            result.get("image_prompt_addon")
            or result.get("imagePromptAddon")
            or fallback.get("imagePromptAddon")
            or visual_direction
        ).strip()[:260],
        "videoPromptAddon": str(
            result.get("video_prompt_addon")
            or result.get("videoPromptAddon")
            or fallback.get("videoPromptAddon")
            or desired_ending
        ).strip()[:300],
        "negativePrompt": str(
            result.get("negative_prompt")
            or result.get("negativePrompt")
            or fallback.get("negativePrompt")
            or ""
        ).strip()[:220],
        "safetyNotes": _ensure_string_list(
            result.get("safety_notes") or result.get("safetyNotes"),
            fallback=list(fallback.get("safetyNotes") or []),
        )[:4],
        "degradeReason": "",
    }
    if not any(
        [
            normalized["intentSummary"],
            normalized["storyDirection"],
            normalized["imagePromptAddon"],
            normalized["videoPromptAddon"],
        ]
    ):
        return fallback
    return normalized


def _snake_case_prompt_refinement(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": str(value.get("status") or ""),
        "source": str(value.get("source") or ""),
        "intent_summary": str(value.get("intentSummary") or ""),
        "story_direction": str(value.get("storyDirection") or ""),
        "image_prompt_addon": str(value.get("imagePromptAddon") or ""),
        "video_prompt_addon": str(value.get("videoPromptAddon") or ""),
        "negative_prompt": str(value.get("negativePrompt") or ""),
        "safety_notes": value.get("safetyNotes") if isinstance(value.get("safetyNotes"), list) else [],
        "degrade_reason": str(value.get("degradeReason") or ""),
    }


def _ensure_tag_list(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(value, list):
        result: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, str):
                tag_id = item.strip()
                if tag_id:
                    result.append({"tag_id": tag_id, "score": 0.6, "source": "llm"})
                continue
            if isinstance(item, dict):
                tag_id = str(item.get("tag_id") or item.get("id") or "").strip()
                if not tag_id:
                    continue
                result.append(
                    {
                        "tag_id": tag_id,
                        "score": float(item.get("score", 0.6) or 0.6),
                        "source": str(item.get("source") or "llm"),
                    }
                )
        if result:
            return result
    return fallback


def _ensure_profile_updates(value: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(value, list):
        result: list[dict[str, Any]] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            tag_id = str(item.get("tag_id") or "").strip()
            if not tag_id:
                continue
            result.append(
                {
                    "tag_id": tag_id,
                    "delta": float(item.get("delta", 0.05) or 0.05),
                    "source": str(item.get("source") or "llm"),
                }
            )
        if result:
            return result
    return fallback


def _format_progress_text(progress_ms: int, duration_ms: int) -> str:
    if duration_ms <= 0:
        return "暂无进度"
    ratio = max(0.0, min(float(progress_ms) / float(duration_ms), 1.0))
    return f"已看到 {int(ratio * 100)}%"


def _now_ms() -> int:
    return int(time.time() * 1000)
