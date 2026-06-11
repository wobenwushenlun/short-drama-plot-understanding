import pytest
from httpx import ASGITransport, AsyncClient


def _assert_keys(payload: dict, required: dict[str, type | tuple[type, ...]]) -> None:
    missing = [key for key in required if key not in payload]
    assert not missing, f"missing keys: {missing}"
    for key, expected_type in required.items():
        assert isinstance(payload[key], expected_type), f"{key} expected {expected_type}, got {type(payload[key])}"


class ContractFakeAIService:
    def story_continuation(self, payload: dict[str, object], request_base_url: str):
        return {
            "capability": "story.continuation",
            "status": "ok",
            "cached": False,
            "latency_ms": 17,
            "model": {"provider": "fake", "model_name": "contract-video"},
            "result": {
                "continuation_title": "契约续写",
                "continuation_summary": "纪容遇继续追查身份线索，新的家族冲突被引爆。",
                "generated_asset": {
                    "provider": {"name": "agnes-video", "mode": "remote"},
                    "mediaUrl": "http://test/media/generated-assets/contract-continuation.mp4",
                    "mediaType": "video/mp4",
                    "remoteAttempt": {"status": "ok", "latencyMs": 17, "degradeReason": ""},
                    "assetCache": {
                        "cacheStatus": "cached",
                        "remoteUrl": "https://cdn.example.test/contract-continuation.mp4",
                        "localUrl": "http://test/media/generated-assets/contract-continuation.mp4",
                        "mediaUrl": "http://test/media/generated-assets/contract-continuation.mp4",
                    },
                },
            },
            "artifact": {"successVersion": 1},
        }

    def checkin_card(self, payload: dict[str, object], request_base_url: str):
        return {
            "capability": "agnes.checkin_card",
            "status": "ok",
            "cached": False,
            "latency_ms": 11,
            "model": {"provider": "agnes", "model_name": "contract-image"},
            "result": {
                "title": "反转打卡",
                "prompt": "家族荣耀逆袭名场面，身份揭露，强冲突短剧海报。",
                "imageUrl": "http://test/media/generated-assets/checkin.png",
                "provider": "agnes",
                "status": "ok",
                "latencyMs": 11,
                "degradeReason": "",
                "assetCache": {
                    "cacheStatus": "cached",
                    "remoteUrl": "https://cdn.example.test/checkin.png",
                    "localUrl": "http://test/media/generated-assets/checkin.png",
                    "mediaUrl": "http://test/media/generated-assets/checkin.png",
                },
            },
            "artifact": {"successVersion": 1},
        }


@pytest.mark.asyncio
async def test_timed_events_contract_keeps_standard_schema_and_legacy_compatibility():
    from backend.app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        timed_resp = await ac.get("/episodes/tainai3_ep02/timed-events")
        legacy_resp = await ac.get("/episodes/tainai3_ep02/interaction-nodes")

    assert timed_resp.status_code == 200
    assert legacy_resp.status_code == 200
    data = timed_resp.json()["data"]
    _assert_keys(
        data,
        {
            "timelineSchemaVersion": str,
            "events": list,
            "nodes": list,
            "eventCount": int,
            "evidenceGraph": dict,
        },
    )
    assert data["timelineSchemaVersion"] == "1.1"
    assert data["eventCount"] == len(data["events"])
    event = data["events"][0]
    _assert_keys(
        event,
        {
            "eventId": str,
            "episodeId": str,
            "startMs": int,
            "endMs": int,
            "componentType": str,
            "visualStyle": str,
            "placement": str,
            "safeArea": dict,
            "maxLines": int,
            "analyticsKey": str,
            "evidenceRefs": list,
            "generationSource": str,
            "confidence": (int, float),
            "reviewStatus": str,
            "payloadHash": str,
            "payload": dict,
        },
    )
    assert len(event["payloadHash"]) == 16
    assert event["payload"]["componentType"] == event["componentType"]
    assert legacy_resp.json()["data"]["timelineSchemaVersion"] == "1.0"


@pytest.mark.asyncio
async def test_evidence_graph_contract_supports_time_filtered_xray():
    from backend.app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/episodes/tainai3_ep01/evidence-graph", params={"timeMs": 44000})

    assert resp.status_code == 200
    data = resp.json()["data"]
    _assert_keys(
        data,
        {
            "schemaVersion": str,
            "episodeId": str,
            "focusTimeMs": int,
            "sourceStatus": str,
            "evidenceSources": list,
            "nodeCount": int,
            "evidenceCount": int,
            "relationCount": int,
            "storyFacets": dict,
            "explanations": list,
            "nodes": list,
            "evidence": list,
            "relations": list,
        },
    )
    assert data["episodeId"] == "tainai3_ep01"
    assert data["nodes"], "X-Ray 至少要能解释一个互动节点"
    node = data["nodes"][0]
    _assert_keys(
        node,
        {
            "nodeId": str,
            "eventId": str,
            "title": str,
            "timeMs": int,
            "componentType": str,
            "generationSource": str,
            "reviewStatus": str,
            "confidence": (int, float),
            "evidenceRefs": list,
            "resolvedEvidenceRefs": list,
            "whyText": str,
        },
    )
    if node["generationSource"] != "manual":
        assert node["evidenceRefs"], "非人工节点必须保留证据引用"
    assert data["explanations"], "X-Ray 必须提供剧情语义解释"
    _assert_keys(
        data["explanations"][0],
        {
            "nodeId": str,
            "title": str,
            "storyTags": list,
            "audienceResonance": str,
            "evidenceSummary": str,
            "explainText": str,
            "confidence": (int, float),
        },
    )
    relation = data["relations"][0]
    _assert_keys(relation, {"fromNodeId": str, "toEvidenceRef": str, "relationType": str, "timeDeltaMs": int})


@pytest.mark.asyncio
async def test_generation_tasks_contract_preserves_last_success(monkeypatch, tmp_path):
    from backend.app.main import app
    from backend.app.runtime_sqlite_store import reset_runtime_store_for_tests
    import backend.app.api.routes.ai as ai_routes

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    reset_runtime_store_for_tests()
    monkeypatch.setattr(ai_routes, "get_ai_service", lambda: ContractFakeAIService())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        create_resp = await ac.post(
            "/ai/generation/tasks",
            json={"taskType": "story_continuation_video", "dramaId": "tainai3", "episodeId": "tainai3_ep01"},
        )
        task_id = create_resp.json()["data"]["taskId"]
        query_resp = await ac.get(f"/ai/generation/tasks/{task_id}")

    assert create_resp.status_code == 200
    assert query_resp.status_code == 200
    task = query_resp.json()["data"]
    _assert_keys(
        task,
        {
            "taskId": str,
            "taskType": str,
            "dramaId": str,
            "episodeId": str,
            "status": str,
            "provider": str,
            "modelName": str,
            "mediaUrl": str,
            "mediaType": str,
            "latencyMs": int,
            "degradeReason": str,
            "result": dict,
            "createdAtMs": int,
            "updatedAtMs": int,
            "lastSuccess": dict,
        },
    )
    assert task["status"] == "succeeded"
    assert task["result"]["assetCache"]["cacheStatus"] == "cached"
    assert task["lastSuccess"]["taskId"] == task["taskId"]
    assert task["lastSuccess"]["mediaUrl"] == task["mediaUrl"]
    assert task["lastSuccess"]["assetCache"]["localUrl"] == task["mediaUrl"]


@pytest.mark.asyncio
async def test_operations_dashboard_contract_exposes_trends_and_ab_metrics(monkeypatch, tmp_path):
    from backend.app.main import app
    from backend.app.runtime_sqlite_store import reset_runtime_store_for_tests

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    reset_runtime_store_for_tests()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(
            "/analytics/events",
            json={
                "events": [
                    {
                        "eventName": "home_highlight_impression",
                        "screenName": "home",
                        "dramaId": "tainai3",
                        "episodeId": "tainai3_ep01",
                        "nodeId": "moment_001",
                        "clientTsMs": 1_780_000_000_000,
                        "properties": {
                            "selectionStrategy": "hybrid",
                            "rank": 1,
                            "heatScore": 92,
                        },
                    },
                    {
                        "eventName": "home_highlight_click",
                        "screenName": "home",
                        "dramaId": "tainai3",
                        "episodeId": "tainai3_ep01",
                        "nodeId": "moment_001",
                        "clientTsMs": 1_780_000_000_100,
                        "properties": {"selectionStrategy": "hybrid"},
                    },
                    {
                        "eventName": "video_start",
                        "screenName": "player",
                        "dramaId": "tainai3",
                        "episodeId": "tainai3_ep01",
                        "nodeId": "",
                        "clientTsMs": 1_780_000_000_200,
                        "properties": {"startupMs": 480},
                    },
                ]
            },
        )
        resp = await ac.get("/dashboard/operations", params={"episode_id": "tainai3_ep01"})

    assert resp.status_code == 200
    data = resp.json()["data"]
    _assert_keys(
        data,
        {
            "storage": dict,
            "episodeId": str,
            "overview": dict,
            "trend": list,
            "trendSummary": dict,
            "hotNodes": list,
            "highlightStrategies": list,
            "agnesGeneration": dict,
            "profile": dict,
        },
    )
    overview = data["overview"]
    _assert_keys(
        overview,
        {
            "interactionCtr": (int, float),
            "insertPlaybackCompletionRate": (int, float),
            "aiSuccessRate": (int, float),
            "aiDegradedRate": (int, float),
            "aiP95LatencyMs": int,
            "startupSuccessRate": (int, float),
            "startupP95Ms": int,
            "playbackErrorCount": int,
            "fullscreenExitCount": int,
            "continueWatchCount": int,
        },
    )
    trend_point = data["trend"][0]
    _assert_keys(
        trend_point,
        {
            "day": str,
            "interactionCtr": (int, float),
            "insertPlaybackCompletionRate": (int, float),
            "startupSuccessRate": (int, float),
            "aiSuccessRate": (int, float),
            "aiDegradedRate": (int, float),
            "aiP95LatencyMs": int,
        },
    )
    strategy = next(item for item in data["highlightStrategies"] if item["selectionStrategy"] == "hybrid")
    _assert_keys(
        strategy,
        {
            "selectionStrategy": str,
            "label": str,
            "impressions": int,
            "clicks": int,
            "ctr": (int, float),
            "jumps": int,
            "jumpRate": (int, float),
            "completionRate": (int, float),
            "saveRate": (int, float),
            "averageHeatScore": (int, float),
        },
    )
    assert strategy["impressions"] == 1
    assert strategy["clicks"] == 1


@pytest.mark.asyncio
async def test_analytics_event_contract_rejects_invalid_payload_and_accepts_stable_names(monkeypatch, tmp_path):
    from backend.app.main import app
    from backend.app.runtime_sqlite_store import reset_runtime_store_for_tests

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    reset_runtime_store_for_tests()

    stable_events = [
        "interaction_exposure",
        "interaction_click",
        "interaction_skip",
        "insert_playback_complete",
        "video_start",
        "playback_error",
        "fullscreen_exit",
        "continue_watch",
        "agnes_image_generate_success",
        "agnes_video_generate_degraded",
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        invalid_resp = await ac.post("/analytics/events", json={"events": "bad"})
        valid_resp = await ac.post(
            "/analytics/events",
            json={
                "events": [
                    {
                        "eventName": name,
                        "screenName": "contract_smoke",
                        "dramaId": "tainai3",
                        "episodeId": "tainai3_ep01",
                        "nodeId": "node_contract",
                        "progressMs": 1000,
                        "clientTsMs": 1_780_000_001_000 + index,
                        "properties": {"schemaVersion": "analytics.shortplay/v1"},
                    }
                    for index, name in enumerate(stable_events)
                ]
            },
        )
        summary_resp = await ac.get("/analytics/summary", params={"episode_id": "tainai3_ep01"})

    assert invalid_resp.status_code == 400
    assert valid_resp.status_code == 200
    assert len(valid_resp.json()["data"]["accepted_ids"]) == len(stable_events)
    summary = summary_resp.json()["data"]
    _assert_keys(summary, {"storage": dict, "interaction": dict, "playback": dict, "ai": dict})
    _assert_keys(
        summary["playback"],
        {
            "errorCount": int,
            "fullscreenExitCount": int,
            "continueWatchCount": int,
            "videoStartAttempts": int,
            "startupP95Ms": int,
        },
    )
