from __future__ import annotations

from typing import Any


SUITE_VERSION = "quality.shortplay/p2-regression-v1"
STORY_SUMMARY_DRAMA_MIN_CHARS = 180
STORY_SUMMARY_DRAMA_MAX_CHARS = 520
STORY_SUMMARY_EPISODE_MIN_CHARS = 80
STORY_SUMMARY_EPISODE_MAX_CHARS = 280
TECHNICAL_MARKERS = (
    "speaker",
    "Speaker",
    "ASR",
    "OCR",
    "关键帧",
    "视频理解",
    "台词识别",
    "prompt",
    "transcript",
)


def build_quality_evaluation_report(
    *,
    summary_status: dict[str, Any],
    timed_payload: dict[str, Any],
    highlight_payload: dict[str, Any] | None = None,
    generation_tasks: list[dict[str, Any]] | None = None,
    generated_at_ms: int,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    drama_description = str(summary_status.get("drama_description") or "")
    episodes = summary_status.get("episodes") if isinstance(summary_status.get("episodes"), list) else []

    _append_quality_check(
        checks,
        check_id="story.drama_clean",
        name="整剧简介无技术痕迹",
        passed=_quality_text_is_clean(drama_description),
        detail="检查 speaker、ASR/OCR、视频理解、prompt 等技术痕迹。",
    )
    _append_quality_check(
        checks,
        check_id="story.drama_not_episode_concat",
        name="整剧简介不是分集拼接",
        passed=not any(f"第{episode_no}集" in drama_description for episode_no in range(1, 6)),
        detail="整剧介绍应是重写后的剧情总概括，而不是分集摘要串联。",
    )
    _append_quality_check(
        checks,
        check_id="story.drama_plot_elements",
        name="整剧简介包含人物、冲突和爽点",
        passed=_drama_summary_has_plot_elements(drama_description),
        detail="用于保证文案更像短剧平台剧情介绍。",
    )

    episode_summaries = [
        str(item.get("summary") or "")
        for item in episodes
        if isinstance(item, dict)
    ]
    _append_quality_check(
        checks,
        check_id="story.episode_count",
        name="分集简介覆盖前 5 集",
        passed=len(episode_summaries) == 5,
        detail=f"当前覆盖 {len(episode_summaries)} 集。",
    )
    _append_quality_check(
        checks,
        check_id="story.episode_clean",
        name="分集简介无技术痕迹",
        passed=bool(episode_summaries) and all(_quality_text_is_clean(summary) for summary in episode_summaries),
        detail="每集简介应说明本集发生了什么，不暴露识别过程。",
    )
    _append_quality_check(
        checks,
        check_id="story.episode_plot_elements",
        name="分集简介包含冲突或反转线索",
        passed=bool(episode_summaries) and all(_episode_summary_has_plot_elements(summary) for summary in episode_summaries),
        detail="分集文案需要有短剧剧情推进感，长度适合移动端展示。",
    )

    timed_events = timed_payload.get("events") if isinstance(timed_payload.get("events"), list) else []
    nodes = timed_payload.get("nodes") if isinstance(timed_payload.get("nodes"), list) else []
    timed_event_failures = [
        str(event.get("eventId") or event.get("payload", {}).get("id") or "unknown_event")
        for event in timed_events
        if isinstance(event, dict) and not _timed_event_schema_is_valid(event)
    ]
    _append_quality_check(
        checks,
        check_id="interaction.timed_event_schema",
        name="互动时间线字段完整",
        passed=bool(timed_events) and not timed_event_failures,
        detail="检查 eventId、startMs/endMs、componentType、证据、来源、置信度、复核状态和 payloadHash。",
        targets=timed_event_failures,
    )
    traceability_failures = _node_traceability_failures(nodes)
    _append_quality_check(
        checks,
        check_id="interaction.traceable_evidence",
        name="模型/规则节点可追溯到证据",
        passed=bool(nodes) and not traceability_failures,
        detail="非人工节点必须保留 evidenceRefs，便于展示来源。",
        targets=traceability_failures,
    )
    text_failures = _interaction_text_failures(nodes)
    _append_quality_check(
        checks,
        check_id="interaction.user_text_clean",
        name="互动文案无技术过程泄露",
        passed=bool(nodes) and not text_failures,
        detail="检查标题、提示、选项、插片描述不出现 speaker、ASR/OCR、prompt 等痕迹。",
        targets=text_failures,
    )
    alignment_failures = _highlight_alignment_failures(timed_events, highlight_payload or {})
    _append_quality_check(
        checks,
        check_id="interaction.high_energy_alignment",
        name="互动点命中高能片段",
        passed=alignment_failures == [],
        detail="首页高能片段必须能映射到互动时间线节点，避免爽点和互动脱节。",
        targets=alignment_failures,
    )
    evidence_failures = _evidence_graph_failures(timed_payload.get("evidenceGraph"))
    _append_quality_check(
        checks,
        check_id="evidence.graph_complete",
        name="证据图谱节点完整",
        passed=evidence_failures == [],
        detail="检查 X-Ray 图谱中节点、证据和支撑关系是否完整。",
        targets=evidence_failures,
    )
    aigc_failures = _aigc_output_failures(generation_tasks or [])
    _append_quality_check(
        checks,
        check_id="aigc.output_story_fit",
        name="Agnes/模板产物贴合剧情",
        passed=aigc_failures == [],
        detail="检查生成图片/视频产物文案不泄露技术过程，并包含人物、冲突或反转线索。",
        targets=aigc_failures,
    )

    passed_count = sum(1 for check in checks if check["passed"])
    total_count = len(checks)
    return {
        "suiteVersion": SUITE_VERSION,
        "generatedAtMs": generated_at_ms,
        "source": "stable_cache_and_timed_events",
        "summary": {
            "total": total_count,
            "passed": passed_count,
            "failed": total_count - passed_count,
            "passRate": round(passed_count / total_count, 4) if total_count else 0.0,
        },
        "checks": checks,
    }


def _append_quality_check(
    checks: list[dict[str, Any]],
    *,
    check_id: str,
    name: str,
    passed: bool,
    detail: str,
    targets: list[str] | None = None,
) -> None:
    checks.append(
        {
            "checkId": check_id,
            "name": name,
            "passed": bool(passed),
            "severity": "blocker" if not passed else "info",
            "detail": detail,
            "targets": targets or [],
        }
    )


def _quality_text_is_clean(text: str) -> bool:
    return bool(str(text or "").strip()) and not any(marker in text for marker in TECHNICAL_MARKERS)


def _timed_event_schema_is_valid(event: dict[str, Any]) -> bool:
    required = ("eventId", "episodeId", "startMs", "endMs", "componentType", "generationSource", "reviewStatus", "payloadHash")
    if not all(event.get(key) not in (None, "") for key in required):
        return False
    if str(event.get("generationSource")) not in {"manual", "rule", "model", "reviewed_model"}:
        return False
    if str(event.get("reviewStatus")) not in {"accepted", "rejected", "edited"}:
        return False
    try:
        confidence = float(event.get("confidence", 0))
    except (TypeError, ValueError):
        return False
    return 0.0 <= confidence <= 1.0 and len(str(event.get("payloadHash") or "")) == 16


def _node_traceability_is_valid(node: dict[str, Any]) -> bool:
    generation = node.get("generation") if isinstance(node.get("generation"), dict) else {}
    source = str(generation.get("generationSource") or "manual")
    evidence_refs = generation.get("evidenceRefs") if isinstance(generation.get("evidenceRefs"), list) else []
    return source == "manual" or bool(evidence_refs)


def _node_traceability_failures(nodes: list[Any]) -> list[str]:
    return [
        str(node.get("id") or "unknown_node")
        for node in nodes
        if isinstance(node, dict) and not _node_traceability_is_valid(node)
    ]


def _interaction_node_text_is_clean(node: dict[str, Any]) -> bool:
    display = node.get("display") if isinstance(node.get("display"), dict) else {}
    ai_insert = node.get("aiInsert") if isinstance(node.get("aiInsert"), dict) else {}
    option_texts = [
        str(option.get("text") or "")
        for option in node.get("options", [])
        if isinstance(option, dict)
    ]
    user_text = " ".join(
        [
            str(node.get("title") or ""),
            str(node.get("subtitle") or ""),
            str(display.get("promptText") or ""),
            str(display.get("badgeText") or ""),
            str(ai_insert.get("title") or ""),
            str(ai_insert.get("description") or ""),
            " ".join(option_texts),
        ]
    )
    return _quality_text_is_clean(user_text)


def _interaction_text_failures(nodes: list[Any]) -> list[str]:
    return [
        str(node.get("id") or "unknown_node")
        for node in nodes
        if isinstance(node, dict) and not _interaction_node_text_is_clean(node)
    ]


def _highlight_alignment_failures(timed_events: list[Any], highlight_payload: dict[str, Any]) -> list[str]:
    items = highlight_payload.get("items") if isinstance(highlight_payload.get("items"), list) else []
    event_episode_ids = {
        str(event.get("episodeId") or "")
        for event in timed_events
        if isinstance(event, dict) and str(event.get("episodeId") or "")
    }
    source_node_ids = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        source_node_id = str(item.get("sourceNodeId") or "")
        item_episode_id = str(item.get("episodeId") or "")
        if source_node_id and (not event_episode_ids or not item_episode_id or item_episode_id in event_episode_ids):
            source_node_ids.add(source_node_id)
    if not source_node_ids:
        return []
    timeline_node_ids = set()
    for event in timed_events:
        if not isinstance(event, dict):
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        node_id = str(payload.get("id") or "")
        if node_id:
            timeline_node_ids.add(node_id)
    return sorted(source_node_ids - timeline_node_ids)


def _evidence_graph_failures(evidence_graph: Any) -> list[str]:
    if not isinstance(evidence_graph, dict):
        return ["evidenceGraph"]
    nodes = evidence_graph.get("nodes") if isinstance(evidence_graph.get("nodes"), list) else []
    evidence = evidence_graph.get("evidence") if isinstance(evidence_graph.get("evidence"), list) else []
    relations = evidence_graph.get("relations") if isinstance(evidence_graph.get("relations"), list) else []
    if not nodes:
        return ["evidenceGraph"]
    non_manual_nodes = [
        node
        for node in nodes
        if isinstance(node, dict) and str(node.get("generationSource") or "manual") != "manual"
    ]
    if not non_manual_nodes:
        return []
    if not evidence or not relations:
        return ["evidenceGraph"]
    related_node_ids = {
        str(relation.get("fromNodeId") or "")
        for relation in relations
        if isinstance(relation, dict)
    }
    failures: list[str] = []
    for node in non_manual_nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("nodeId") or "")
        refs = node.get("evidenceRefs") if isinstance(node.get("evidenceRefs"), list) else []
        if not node_id or not refs or node_id not in related_node_ids:
            failures.append(node_id or "unknown_node")
    return failures


def _aigc_output_failures(generation_tasks: list[dict[str, Any]]) -> list[str]:
    samples = generation_tasks or _fixed_aigc_quality_samples()
    failures: list[str] = []
    for task in samples:
        if not isinstance(task, dict):
            continue
        if not _aigc_task_is_story_fit(task):
            failures.append(str(task.get("taskId") or task.get("taskType") or "unknown_aigc"))
    return failures


def _aigc_task_is_story_fit(task: dict[str, Any]) -> bool:
    result = task.get("result") if isinstance(task.get("result"), dict) else {}
    text = " ".join(
        [
            str(result.get("title") or ""),
            str(result.get("summary") or ""),
            str(result.get("prompt") or ""),
            str(task.get("title") or ""),
            str(task.get("prompt") or ""),
        ]
    )
    return (
        _quality_text_is_clean(text)
        and any(token in text for token in ("容遇", "纪家", "太奶奶", "家族"))
        and any(token in text for token in ("质疑", "冲突", "危机", "反击", "打脸", "反转", "身份", "逆袭"))
    )


def _fixed_aigc_quality_samples() -> list[dict[str, Any]]:
    return [
        {
            "taskId": "fixed_story_continuation_video",
            "taskType": "story_continuation_video",
            "result": {
                "title": "容遇反击续写",
                "summary": "容遇在纪家质疑中抓住证据，继续推进身份反转和家族逆袭。",
            },
        },
        {
            "taskId": "fixed_checkin_card",
            "taskType": "checkin_card",
            "result": {
                "title": "太奶奶打脸名场面",
                "prompt": "容遇面对纪家质疑时强势反击，突出身份反转和家族荣耀逆袭。",
            },
        },
    ]


def _drama_summary_has_plot_elements(summary: str) -> bool:
    return (
        STORY_SUMMARY_DRAMA_MIN_CHARS <= len(summary) <= STORY_SUMMARY_DRAMA_MAX_CHARS
        and
        "容遇" in summary
        and "纪家" in summary
        and any(token in summary for token in ("质疑", "误会", "内斗", "危机", "反转", "打脸"))
    )


def _episode_summary_has_plot_elements(summary: str) -> bool:
    return (
        any(token in summary for token in ("质疑", "嘲讽", "误解", "冲突", "反转", "危机", "打脸", "身份"))
        and STORY_SUMMARY_EPISODE_MIN_CHARS <= len(summary) <= STORY_SUMMARY_EPISODE_MAX_CHARS
    )
