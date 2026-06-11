from __future__ import annotations

from typing import Any


HIGHLIGHT_STRATEGY_LABELS = {
    "heat_score_desc_v1": "热度优先",
    "episode_spread_v1": "分集均衡",
    "recent_episode_v1": "近期优先",
    "interaction_first": "互动优先",
    "danmaku_first": "弹幕优先",
    "ai_evidence_first": "AI 证据优先",
    "hybrid": "混合策略",
}


def build_operations_dashboard_payload(
    *,
    summary: dict[str, Any],
    profile: dict[str, Any],
    trend: list[dict[str, Any]],
    highlight_strategies: list[dict[str, Any]],
    agnes_generation: dict[str, Any] | None = None,
    generated_at_ms: int,
) -> dict[str, Any]:
    overview = _build_operations_overview(summary, profile)
    return {
        "storage": summary["storage"],
        "dramaId": str(summary.get("dramaId") or ""),
        "episodeId": summary["episodeId"],
        "generatedAtMs": generated_at_ms,
        "overview": overview,
        "watch": summary["watch"],
        "interaction": summary["interaction"],
        "insertPlayback": summary["insertPlayback"],
        "playback": summary["playback"],
        "ai": summary["ai"],
        "trend": trend,
        "trendSummary": build_operations_trend_summary(trend, highlight_strategies, overview),
        "hotNodes": summary["interaction"]["nodes"][:5],
        "highlightStrategies": highlight_strategies,
        "agnesGeneration": agnes_generation or build_agnes_generation_report([]),
        "profile": {
            "interestTags": profile["interestTags"],
            "interestTagDistribution": profile["interestTagDistribution"],
            "recommendReason": profile["recommendReason"],
            "topNodes": profile["topNodes"],
        },
    }


def build_highlight_strategy_report(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for event in events:
        properties = event.get("properties") if isinstance(event.get("properties"), dict) else {}
        strategy = str(
            properties.get("selectionStrategy")
            or properties.get("selection_strategy")
            or "unknown"
        ).strip() or "unknown"
        bucket = buckets.setdefault(
            strategy,
            {
                "selectionStrategy": strategy,
                "impressions": 0,
                "clicks": 0,
                "jumps": 0,
                "playCompleted": 0,
                "saved": 0,
                "rankSamples": [],
                "heatSamples": [],
                "momentIds": set(),
                "latestAtMs": 0,
            },
        )
        event_name = str(event.get("eventName") or "")
        if event_name == "home_highlight_impression":
            bucket["impressions"] += 1
        elif event_name == "home_highlight_click":
            bucket["clicks"] += 1
        elif event_name == "home_highlight_jump":
            bucket["jumps"] += 1
        elif event_name == "home_highlight_play_complete":
            bucket["playCompleted"] += 1
        elif event_name == "moment_save":
            bucket["saved"] += 1
        if event_name in {"home_highlight_impression", "home_highlight_click"}:
            rank = _property_int(properties, "rank")
            if rank > 0:
                bucket["rankSamples"].append(rank)
            heat_score = _property_int(properties, "heatScore", "heat_score")
            if heat_score > 0:
                bucket["heatSamples"].append(heat_score)
        moment_id = str(properties.get("momentId") or properties.get("moment_id") or "").strip()
        if moment_id:
            bucket["momentIds"].add(moment_id)
        bucket["latestAtMs"] = max(int(bucket["latestAtMs"]), int(event.get("clientTsMs") or 0))

    result: list[dict[str, Any]] = []
    for strategy, bucket in buckets.items():
        impressions = int(bucket["impressions"])
        clicks = int(bucket["clicks"])
        jumps = int(bucket["jumps"])
        play_completed = int(bucket["playCompleted"])
        saved = int(bucket["saved"])
        rank_samples = [int(value) for value in bucket["rankSamples"]]
        heat_samples = [int(value) for value in bucket["heatSamples"]]
        result.append(
            {
                "selectionStrategy": strategy,
                "label": highlight_strategy_label(strategy),
                "impressions": impressions,
                "clicks": clicks,
                "ctr": round(clicks / impressions, 4) if impressions else 0.0,
                "jumps": jumps,
                "jumpRate": round(jumps / clicks, 4) if clicks else 0.0,
                "playCompleted": play_completed,
                "completionRate": round(play_completed / clicks, 4) if clicks else 0.0,
                "saved": saved,
                "saveRate": round(saved / clicks, 4) if clicks else 0.0,
                "averageRank": round(sum(rank_samples) / len(rank_samples), 2) if rank_samples else 0.0,
                "averageHeatScore": round(sum(heat_samples) / len(heat_samples), 2) if heat_samples else 0.0,
                "uniqueMomentCount": len(bucket["momentIds"]),
                "latestAtMs": int(bucket["latestAtMs"]),
            }
        )
    return sorted(
        result,
        key=lambda item: (-float(item["ctr"]), -int(item["clicks"]), str(item["selectionStrategy"])),
    )


def build_agnes_generation_report(events: list[dict[str, Any]]) -> dict[str, Any]:
    image = _empty_agnes_generation_bucket()
    video = _empty_agnes_generation_bucket()
    latest_at_ms = 0
    local_template_fallback_count = 0

    for event in events:
        event_name = str(event.get("eventName") or "")
        if not event_name.startswith("agnes_"):
            continue
        bucket = image if "_image_" in event_name else video if "_video_" in event_name else None
        if bucket is None:
            continue
        properties = event.get("properties") if isinstance(event.get("properties"), dict) else {}
        latest_at_ms = max(latest_at_ms, int(event.get("clientTsMs") or 0))
        provider = str(properties.get("provider") or "").lower()
        if event_name.endswith("_start"):
            bucket["starts"] += 1
        elif event_name.endswith("_success"):
            bucket["success"] += 1
            _append_agnes_latency(bucket, properties)
        elif event_name.endswith("_degraded"):
            bucket["degraded"] += 1
            _append_agnes_latency(bucket, properties)
        if "template" in provider or provider in {"local", "local_fallback"}:
            local_template_fallback_count += 1

    image_report = _finalize_agnes_generation_bucket(image)
    video_report = _finalize_agnes_generation_bucket(video)
    total_starts = image_report["starts"] + video_report["starts"]
    total_success = image_report["success"] + video_report["success"]
    total_degraded = image_report["degraded"] + video_report["degraded"]
    latency_samples = image["latencySamples"] + video["latencySamples"]
    attempts = total_success + total_degraded
    return {
        "totalStarts": total_starts,
        "totalSuccess": total_success,
        "totalDegraded": total_degraded,
        "successRate": round(total_success / attempts, 4) if attempts else 0.0,
        "degradedRate": round(total_degraded / attempts, 4) if attempts else 0.0,
        "p95LatencyMs": _percentile95(latency_samples),
        "localTemplateFallbackCount": local_template_fallback_count,
        "latestAtMs": latest_at_ms,
        "image": image_report,
        "video": video_report,
    }


def _empty_agnes_generation_bucket() -> dict[str, Any]:
    return {
        "starts": 0,
        "success": 0,
        "degraded": 0,
        "latencySamples": [],
    }


def _append_agnes_latency(bucket: dict[str, Any], properties: dict[str, Any]) -> None:
    latency_ms = _property_int(properties, "latencyMs", "latency_ms")
    if latency_ms > 0:
        bucket["latencySamples"].append(latency_ms)


def _finalize_agnes_generation_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
    starts = int(bucket["starts"])
    success = int(bucket["success"])
    degraded = int(bucket["degraded"])
    attempts = success + degraded
    return {
        "starts": starts,
        "success": success,
        "degraded": degraded,
        "successRate": round(success / attempts, 4) if attempts else 0.0,
        "degradedRate": round(degraded / attempts, 4) if attempts else 0.0,
        "p95LatencyMs": _percentile95(bucket["latencySamples"]),
    }


def highlight_strategy_label(strategy: str) -> str:
    return HIGHLIGHT_STRATEGY_LABELS.get(strategy, strategy or "未知策略")


def build_operations_trend_summary(
    trend: list[dict[str, Any]],
    highlight_strategies: list[dict[str, Any]],
    overview: dict[str, Any],
) -> dict[str, Any]:
    active_days = [
        point
        for point in trend
        if int(point.get("interactionImpressions") or 0)
        or int(point.get("interactionSubmits") or 0)
        or int(point.get("videoStartAttempts") or 0)
        or int(point.get("aiAttemptCount") or 0)
    ]
    best_ctr_day = max(active_days, key=lambda point: float(point.get("interactionCtr") or 0), default={})
    best_strategy = max(
        highlight_strategies,
        key=lambda item: (float(item.get("ctr") or 0), int(item.get("clicks") or 0)),
        default={},
    )
    risk_notes = _build_dashboard_risk_notes(overview, highlight_strategies)
    return {
        "activeDayCount": len(active_days),
        "bestCtrDay": str(best_ctr_day.get("label") or ""),
        "bestCtr": float(best_ctr_day.get("interactionCtr") or 0.0),
        "bestStrategy": str(best_strategy.get("selectionStrategy") or ""),
        "bestStrategyLabel": str(best_strategy.get("label") or ""),
        "bestStrategyCtr": float(best_strategy.get("ctr") or 0.0),
        "qualityStatus": "warning" if _has_dashboard_warning(risk_notes) else "healthy",
        "riskNotes": risk_notes,
    }


def _build_operations_overview(summary: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "interactionCtr": summary["interaction"]["ctr"],
        "interactionImpressions": summary["interaction"]["impressions"],
        "interactionSubmits": summary["interaction"]["submits"],
        "insertPlaybackCompletionRate": summary["insertPlayback"]["completionRate"],
        "insertPlaybackStarts": summary["insertPlayback"]["starts"],
        "insertPlaybackCompleted": summary["insertPlayback"]["completed"],
        "aiSuccessRate": summary["ai"]["successRate"],
        "aiDegradedRate": summary["ai"]["degradedRate"],
        "aiP95LatencyMs": summary["ai"]["p95LatencyMs"],
        "watchEpisodeCount": summary["watch"]["episodeCount"],
        "watchCompletedCount": summary["watch"]["completedCount"],
        "interactionCount": summary["interaction"]["submits"],
        "videoStartAttempts": summary["playback"]["videoStartAttempts"],
        "firstFrameRendered": summary["playback"]["firstFrameRendered"],
        "startupSuccessRate": summary["playback"]["startupSuccessRate"],
        "startupFailureRate": summary["playback"]["startupFailureRate"],
        "playbackErrorCount": summary["playback"]["errorCount"],
        "fullscreenExitCount": summary["playback"]["fullscreenExitCount"],
        "continueWatchCount": summary["playback"]["continueWatchCount"],
        "exitBeforeStartCount": summary["playback"]["exitBeforeStartCount"],
        "rebufferCount": summary["playback"]["rebufferCount"],
        "rebufferTotalMs": summary["playback"]["rebufferTotalMs"],
        "startupP50Ms": summary["playback"]["startupP50Ms"],
        "startupP95Ms": summary["playback"]["startupP95Ms"],
        "rebufferP95Ms": summary["playback"]["rebufferP95Ms"],
        "savedMomentCount": profile["savedMomentCount"],
        "eventCount": profile["eventCount"],
    }


def _build_dashboard_risk_notes(
    overview: dict[str, Any],
    highlight_strategies: list[dict[str, Any]],
) -> list[str]:
    risk_notes: list[str] = []
    if float(overview.get("aiDegradedRate") or 0) >= 0.2:
        risk_notes.append("AI 降级率偏高，优先检查模型超时和缓存命中")
    if float(overview.get("startupFailureRate") or 0) >= 0.1:
        risk_notes.append("起播失败率偏高，优先检查播放源和首帧耗时")
    if float(overview.get("interactionCtr") or 0) < 0.05 and int(overview.get("interactionImpressions") or 0) > 0:
        risk_notes.append("互动 CTR 偏低，优先调整节点文案或安全区位置")
    if highlight_strategies and not any(float(item.get("ctr") or 0) > 0 for item in highlight_strategies):
        risk_notes.append("高能策略有曝光但无点击，需要调整封面文案和排序")
    if not risk_notes:
        risk_notes.append("核心指标处于可演示状态，可继续积累样本对比策略")
    return risk_notes


def _has_dashboard_warning(risk_notes: list[str]) -> bool:
    return any("偏高" in note or "偏低" in note or "无点击" in note for note in risk_notes)


def _property_int(properties: dict[str, Any], *names: str) -> int:
    for name in names:
        value = properties.get(name)
        try:
            return max(int(float(value)), 0)
        except (TypeError, ValueError):
            continue
    return 0


def _percentile95(values: list[int]) -> int:
    if not values:
        return 0
    sorted_values = sorted(int(value) for value in values)
    index = max(0, min(len(sorted_values) - 1, int(round((len(sorted_values) - 1) * 0.95))))
    return sorted_values[index]
