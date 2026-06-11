import time

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_watch_progress_and_history():
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        progress_resp = await ac.post(
            "/watch/progress",
            json={
                "dramaId": "tainai3",
                "episodeId": "tainai3_ep01",
                "progressMs": 45000,
                "durationMs": 245000,
                "isCompleted": False,
                "clientTsMs": 1900000000000,
            },
        )
        history_resp = await ac.get("/user/history", params={"size": 10})

    assert progress_resp.status_code == 200
    assert history_resp.status_code == 200
    assert history_resp.json()["data"]["items"][0]["episode_id"] == "tainai3_ep01"


@pytest.mark.asyncio
async def test_analytics_events_accept_batch():
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/analytics/events",
            json={
                "events": [
                    {
                        "eventId": "evt_001",
                        "eventName": "page_view",
                        "screenName": "home",
                        "dramaId": "tainai3",
                        "clientTsMs": 1900000000000,
                    },
                    {
                        "eventId": "evt_002",
                        "eventName": "click",
                        "screenName": "detail",
                        "episodeId": "tainai3_ep01",
                        "clientTsMs": 1900000001000,
                    },
                ]
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["accepted_ids"] == ["evt_001", "evt_002"]


@pytest.mark.asyncio
async def test_sqlite_runtime_summary_persists_feedback_loop(monkeypatch, tmp_path):
    from backend.app.main import app
    from backend.app.runtime_sqlite_store import reset_runtime_store_for_tests

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    reset_runtime_store_for_tests()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        nodes_resp = await ac.get("/episodes/tainai3_ep01/interaction-nodes")
        node = nodes_resp.json()["data"]["nodes"][0]
        option = node["options"][0]
        await ac.post(
            "/analytics/events",
            json={
                "events": [
                    {
                        "eventId": "impression_001",
                        "eventName": "interaction_impression",
                        "screenName": "player",
                        "dramaId": "tainai3",
                        "episodeId": "tainai3_ep01",
                        "nodeId": node["id"],
                        "progressMs": node["trigger"]["timeMs"],
                        "clientTsMs": 1_900_000_000_000,
                        "properties": {"nodeTitle": node["title"]},
                    }
                    ,
                    {
                        "eventId": "start_001",
                        "eventName": "insert_play_start",
                        "screenName": "player",
                        "dramaId": "tainai3",
                        "episodeId": "tainai3_ep01",
                        "nodeId": node["id"],
                        "clientTsMs": 1_900_000_000_010,
                    },
                    {
                        "eventId": "complete_001",
                        "eventName": "insert_play_complete",
                        "screenName": "player",
                        "dramaId": "tainai3",
                        "episodeId": "tainai3_ep01",
                        "nodeId": node["id"],
                        "clientTsMs": 1_900_000_000_020,
                    },
                    {
                        "eventId": "error_001",
                        "eventName": "playback_error",
                        "screenName": "player",
                        "dramaId": "tainai3",
                        "episodeId": "tainai3_ep01",
                        "nodeId": node["id"],
                        "clientTsMs": 1_900_000_000_030,
                    },
                    {
                        "eventId": "fullscreen_001",
                        "eventName": "fullscreen_exit",
                        "screenName": "player",
                        "dramaId": "tainai3",
                        "episodeId": "tainai3_ep01",
                        "clientTsMs": 1_900_000_000_040,
                    },
                    {
                        "eventId": "continue_001",
                        "eventName": "continue_watch",
                        "screenName": "player",
                        "dramaId": "tainai3",
                        "episodeId": "tainai3_ep01",
                        "clientTsMs": 1_900_000_000_050,
                    },
                ]
            },
        )
        await ac.post(
            "/watch/progress",
            json={
                "dramaId": "tainai3",
                "episodeId": "tainai3_ep01",
                "progressMs": 66_000,
                "durationMs": 245_840,
                "isCompleted": False,
            },
        )
        await ac.post(
            "/interaction/submit",
            json={
                "submitId": "summary_submit_001",
                "dramaId": "tainai3",
                "episodeId": "tainai3_ep01",
                "nodeId": node["id"],
                "triggerMs": node["trigger"]["timeMs"],
                "answer": {"optionId": option["id"]},
            },
        )
        summary_resp = await ac.get("/analytics/summary", params={"episode_id": "tainai3_ep01"})

    reset_runtime_store_for_tests()
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        history_resp = await ac.get("/user/history", params={"size": 5})

    data = summary_resp.json()["data"]
    assert data["storage"] == {"engine": "sqlite", "persistent": True}
    assert data["interaction"]["impressions"] == 1
    assert data["interaction"]["submits"] == 1
    assert data["interaction"]["ctr"] > 0
    assert data["interaction"]["nodeHeat"]
    assert data["interaction"]["nodes"][0]["choices"]
    assert data["insertPlayback"]["starts"] == 1
    assert data["insertPlayback"]["completed"] == 1
    assert data["playback"]["errorCount"] == 1
    assert data["playback"]["fullscreenExitCount"] == 1
    assert data["playback"]["continueWatchCount"] == 1
    assert history_resp.json()["data"]["items"][0]["last_progress_ms"] == 66_000


@pytest.mark.asyncio
async def test_user_profile_and_home_recommend_reason_use_sqlite(monkeypatch, tmp_path):
    from backend.app.main import app
    from backend.app.runtime_sqlite_store import reset_runtime_store_for_tests
    import backend.app.content_catalog as content_catalog

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)
    monkeypatch.setattr(content_catalog, "DEFAULT_DANMAKU_EVIDENCE_PATH", tmp_path / "missing.json")
    reset_runtime_store_for_tests()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        nodes_resp = await ac.get("/episodes/tainai3_ep02/interaction-nodes")
        node = next(item for item in nodes_resp.json()["data"]["nodes"] if item["type"] == "SIDE_CHOICE")
        option = node["options"][0]
        await ac.post(
            "/watch/progress",
            json={
                "dramaId": "tainai3",
                "episodeId": "tainai3_ep02",
                "progressMs": 84000,
                "durationMs": 275000,
                "isCompleted": False,
            },
        )
        await ac.post(
            "/analytics/events",
            json={
                "events": [
                    {
                        "eventId": "profile_impression_001",
                        "eventName": "interaction_impression",
                        "screenName": "home",
                        "dramaId": "tainai3",
                        "episodeId": "tainai3_ep02",
                        "nodeId": node["id"],
                        "clientTsMs": 1900000000000,
                    }
                ]
            },
        )
        await ac.post(
            "/interaction/submit",
            json={
                "submitId": "profile_submit_001",
                "dramaId": "tainai3",
                "episodeId": "tainai3_ep02",
                "nodeId": node["id"],
                "triggerMs": node["trigger"]["timeMs"],
                "answer": {"optionId": option["id"]},
            },
        )
        moments_resp = await ac.get("/dramas/tainai3/shareable-moments")
        moment = moments_resp.json()["data"]["items"][0]
        await ac.post(
            "/moments/save",
            json={
                **moment,
                "clientTsMs": 1900000000100,
            },
        )
        profile_resp = await ac.get("/user/profile")
        home_resp = await ac.get("/home/recommend")

    profile = profile_resp.json()["data"]
    home_item = home_resp.json()["data"]["items"][0]
    assert profile["storage"] == {"engine": "sqlite", "persistent": True}
    assert profile["savedMomentCount"] == 1
    assert profile["interactionCount"] == 1
    assert "高能切片偏好" in profile["interestTags"]
    assert "站队偏好" in profile["interestTags"]
    assert profile["recommendReason"]
    assert home_item["recommend_reason"] == profile["recommendReason"]


@pytest.mark.asyncio
async def test_operations_dashboard_uses_sqlite_metrics(monkeypatch, tmp_path):
    from backend.app.main import app
    from backend.app.runtime_sqlite_store import get_runtime_store, reset_runtime_store_for_tests
    import backend.app.content_catalog as content_catalog

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)
    monkeypatch.setattr(content_catalog, "DEFAULT_DANMAKU_EVIDENCE_PATH", tmp_path / "missing.json")
    reset_runtime_store_for_tests()
    store = get_runtime_store()
    now_ms = int(time.time() * 1000)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        nodes_resp = await ac.get("/episodes/tainai3_ep03/interaction-nodes")
        node = next(item for item in nodes_resp.json()["data"]["nodes"] if item.get("options"))
        option = node["options"][0]
        await ac.post(
            "/watch/progress",
            json={
                "dramaId": "tainai3",
                "episodeId": "tainai3_ep03",
                "progressMs": 88_000,
                "durationMs": 275_000,
                "isCompleted": True,
            },
        )
        await ac.post(
            "/analytics/events",
            json={
                "events": [
                        {
                            "eventId": "dashboard_impression_001",
                            "eventName": "interaction_impression",
                            "screenName": "player",
                            "dramaId": "tainai3",
                            "episodeId": "tainai3_ep03",
                            "nodeId": node["id"],
                            "progressMs": node["trigger"]["timeMs"],
                            "clientTsMs": now_ms,
                            "properties": {"nodeTitle": node["title"]},
                        },
                        {
                            "eventId": "dashboard_start_001",
                            "eventName": "insert_play_start",
                            "screenName": "player",
                            "dramaId": "tainai3",
                            "episodeId": "tainai3_ep03",
                            "nodeId": node["id"],
                            "clientTsMs": now_ms + 10,
                        },
                        {
                            "eventId": "dashboard_complete_001",
                            "eventName": "insert_play_complete",
                            "screenName": "player",
                            "dramaId": "tainai3",
                            "episodeId": "tainai3_ep03",
                            "nodeId": node["id"],
                            "clientTsMs": now_ms + 20,
                        },
                        {
                            "eventId": "dashboard_qoe_start_001",
                            "eventName": "video_start_attempt",
                            "screenName": "player",
                            "dramaId": "tainai3",
                            "episodeId": "tainai3_ep03",
                            "clientTsMs": now_ms + 30,
                            "properties": {"reason": "initial", "playUrlType": "hls"},
                        },
                        {
                            "eventId": "dashboard_qoe_first_frame_001",
                            "eventName": "first_frame_rendered",
                            "screenName": "player",
                            "dramaId": "tainai3",
                            "episodeId": "tainai3_ep03",
                            "clientTsMs": now_ms + 900,
                            "properties": {"startupMs": "870", "playUrlType": "hls"},
                        },
                        {
                            "eventId": "dashboard_qoe_rebuffer_end_001",
                            "eventName": "rebuffer_end",
                            "screenName": "player",
                            "dramaId": "tainai3",
                            "episodeId": "tainai3_ep03",
                            "progressMs": 48_000,
                            "clientTsMs": now_ms + 1_800,
                            "properties": {"durationMs": "420", "playUrlType": "hls"},
                        },
                        {
                            "eventId": "dashboard_highlight_imp_001",
                            "eventName": "home_highlight_impression",
                            "screenName": "home",
                            "dramaId": "tainai3",
                            "episodeId": "tainai3_ep03",
                            "clientTsMs": now_ms + 2_000,
                            "properties": {
                                "selectionStrategy": "heat_score_desc_v1",
                                "momentId": "moment_a",
                                "rank": "1",
                                "heatScore": "90",
                            },
                        },
                        {
                            "eventId": "dashboard_highlight_imp_002",
                            "eventName": "home_highlight_impression",
                            "screenName": "home",
                            "dramaId": "tainai3",
                            "episodeId": "tainai3_ep03",
                            "clientTsMs": now_ms + 2_010,
                            "properties": {
                                "selectionStrategy": "heat_score_desc_v1",
                                "momentId": "moment_b",
                                "rank": "2",
                                "heatScore": "80",
                            },
                        },
                        {
                            "eventId": "dashboard_highlight_click_001",
                            "eventName": "home_highlight_click",
                            "screenName": "home",
                            "dramaId": "tainai3",
                            "episodeId": "tainai3_ep03",
                            "clientTsMs": now_ms + 2_020,
                            "properties": {
                                "selectionStrategy": "heat_score_desc_v1",
                                "momentId": "moment_a",
                                "rank": "1",
                                "heatScore": "90",
                            },
                        },
                        {
                            "eventId": "dashboard_highlight_jump_001",
                            "eventName": "home_highlight_jump",
                            "screenName": "home",
                            "dramaId": "tainai3",
                            "episodeId": "tainai3_ep03",
                            "clientTsMs": now_ms + 2_025,
                            "properties": {
                                "selectionStrategy": "heat_score_desc_v1",
                                "momentId": "moment_a",
                                "rank": "1",
                                "heatScore": "90",
                            },
                        },
                        {
                            "eventId": "dashboard_highlight_imp_003",
                            "eventName": "home_highlight_impression",
                            "screenName": "home",
                            "dramaId": "tainai3",
                            "episodeId": "tainai3_ep03",
                            "clientTsMs": now_ms + 2_030,
                            "properties": {
                                "selectionStrategy": "episode_spread_v1",
                                "momentId": "moment_c",
                                "rank": "1",
                                "heatScore": "70",
                            },
                        },
                        {
                            "eventId": "dashboard_agnes_image_start_001",
                            "eventName": "agnes_image_generate_start",
                            "screenName": "player",
                            "dramaId": "tainai3",
                            "episodeId": "tainai3_ep03",
                            "clientTsMs": now_ms + 2_100,
                            "properties": {"source": "player", "momentId": "moment_a"},
                        },
                        {
                            "eventId": "dashboard_agnes_image_success_001",
                            "eventName": "agnes_image_generate_success",
                            "screenName": "player",
                            "dramaId": "tainai3",
                            "episodeId": "tainai3_ep03",
                            "clientTsMs": now_ms + 2_200,
                            "properties": {
                                "provider": "agnes",
                                "status": "ok",
                                "hasImage": "true",
                                "latencyMs": "1200",
                                "momentId": "moment_a",
                            },
                        },
                        {
                            "eventId": "dashboard_agnes_video_start_001",
                            "eventName": "agnes_video_generate_start",
                            "screenName": "player",
                            "dramaId": "tainai3",
                            "episodeId": "tainai3_ep03",
                            "clientTsMs": now_ms + 2_300,
                            "properties": {"source": "player"},
                        },
                        {
                            "eventId": "dashboard_agnes_video_degraded_001",
                            "eventName": "agnes_video_generate_degraded",
                            "screenName": "player",
                            "dramaId": "tainai3",
                            "episodeId": "tainai3_ep03",
                            "clientTsMs": now_ms + 2_400,
                            "properties": {
                                "provider": "template_ffmpeg",
                                "status": "degraded",
                                "hasMedia": "true",
                                "latencyMs": "2600",
                            },
                        },
                    ]
                },
            )
        await ac.post(
            "/interaction/submit",
            json={
                "submitId": "dashboard_submit_001",
                "dramaId": "tainai3",
                "episodeId": "tainai3_ep03",
                "nodeId": node["id"],
                "triggerMs": node["trigger"]["timeMs"],
                "answer": {"optionId": option["id"]},
            },
        )
        moments_resp = await ac.get("/dramas/tainai3/shareable-moments")
        moment = moments_resp.json()["data"]["items"][0]
        await ac.post(
            "/moments/save",
                json={
                    **moment,
                    "clientTsMs": now_ms + 30,
                },
            )

    store.register_ai_attempt(
        capability="content.story_summary",
        scope_key="drama:tainai3",
        prompt_version="v1",
        drama_id="tainai3",
        episode_id="tainai3_ep03",
        node_id=node["id"],
        status="ok",
        source="remote_model",
        result={"summary": "ok"},
        model_name="qwen",
        cached=False,
        latency_ms=920,
        degrade_reason="",
    )
    store.register_ai_attempt(
        capability="content.video_understanding",
        scope_key="episode:tainai3_ep03",
        prompt_version="v1",
        drama_id="tainai3",
        episode_id="tainai3_ep03",
        node_id=node["id"],
        status="degraded",
        source="local_fallback",
        result={"summary": "fallback"},
        model_name="qwen",
        cached=False,
        latency_ms=2_400,
        degrade_reason="timeout",
    )

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        dashboard_resp = await ac.get("/dashboard/operations", params={"episode_id": "tainai3_ep03"})

    assert dashboard_resp.status_code == 200
    data = dashboard_resp.json()["data"]
    overview = data["overview"]
    assert overview["interactionImpressions"] == 1
    assert overview["interactionSubmits"] == 1
    assert overview["interactionCtr"] > 0
    assert overview["insertPlaybackCompletionRate"] == 1.0
    assert overview["aiSuccessRate"] == 0.5
    assert overview["aiDegradedRate"] == 0.5
    assert overview["aiP95LatencyMs"] == 2_400
    assert overview["videoStartAttempts"] == 1
    assert overview["firstFrameRendered"] == 1
    assert overview["startupSuccessRate"] == 1.0
    assert overview["startupP95Ms"] == 870
    assert overview["rebufferCount"] == 1
    assert overview["rebufferTotalMs"] == 420
    assert len(data["trend"]) == 7
    trend_point = next(point for point in data["trend"] if point["interactionImpressions"] == 1)
    assert trend_point["interactionSubmits"] == 1
    assert trend_point["insertPlaybackCompletionRate"] == 1.0
    assert trend_point["videoStartAttempts"] == 1
    assert trend_point["startupP95Ms"] == 870
    assert trend_point["rebufferTotalMs"] == 420
    assert trend_point["aiSuccessRate"] == 0.5
    assert trend_point["aiDegradedRate"] == 0.5
    assert trend_point["aiP95LatencyMs"] == 2_400
    assert data["hotNodes"]
    assert data["hotNodes"][0]["nodeTitle"]
    assert data["ai"]["capabilities"]
    assert data["highlightStrategies"]
    heat_strategy = next(
        item for item in data["highlightStrategies"] if item["selectionStrategy"] == "heat_score_desc_v1"
    )
    assert heat_strategy["label"] == "热度优先"
    assert heat_strategy["impressions"] == 2
    assert heat_strategy["clicks"] == 1
    assert heat_strategy["ctr"] == 0.5
    assert heat_strategy["jumps"] == 1
    assert heat_strategy["jumpRate"] == 1.0
    assert heat_strategy["averageRank"] == 1.33
    assert heat_strategy["averageHeatScore"] == 86.67
    assert heat_strategy["uniqueMomentCount"] == 2
    assert data["trendSummary"]["activeDayCount"] == 1
    assert data["trendSummary"]["bestStrategy"] == "heat_score_desc_v1"
    assert data["trendSummary"]["bestStrategyCtr"] == 0.5
    assert data["trendSummary"]["qualityStatus"] == "warning"
    assert any("AI 降级率偏高" in note for note in data["trendSummary"]["riskNotes"])
    assert data["agnesGeneration"]["totalStarts"] == 2
    assert data["agnesGeneration"]["totalSuccess"] == 1
    assert data["agnesGeneration"]["totalDegraded"] == 1
    assert data["agnesGeneration"]["localTemplateFallbackCount"] == 1
    assert data["agnesGeneration"]["p95LatencyMs"] == 2_600
    assert data["agnesGeneration"]["image"]["successRate"] == 1.0
    assert data["agnesGeneration"]["video"]["degradedRate"] == 1.0
    assert data["profile"]["interestTags"]
    assert data["profile"]["interestTagDistribution"]
    assert data["profile"]["recommendReason"]


@pytest.mark.asyncio
async def test_operations_dashboard_filters_by_drama_id(monkeypatch, tmp_path):
    from backend.app.main import app
    from backend.app.runtime_sqlite_store import reset_runtime_store_for_tests

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    reset_runtime_store_for_tests()
    now_ms = int(time.time() * 1000)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for drama_id, episode_id in (("tainai3", "tainai3_ep01"), ("new_drama_001", "new_drama_001_ep01")):
            await ac.post(
                "/watch/progress",
                json={
                    "dramaId": drama_id,
                    "episodeId": episode_id,
                    "progressMs": 30_000,
                    "durationMs": 120_000,
                    "isCompleted": drama_id == "new_drama_001",
                },
            )
            await ac.post(
                "/analytics/events",
                json={
                    "events": [
                        {
                            "eventId": f"dashboard_filter_{drama_id}",
                            "eventName": "interaction_impression",
                            "screenName": "player",
                            "dramaId": drama_id,
                            "episodeId": episode_id,
                            "nodeId": f"{drama_id}_node",
                            "clientTsMs": now_ms,
                        }
                    ]
                },
            )

        filtered_resp = await ac.get("/dashboard/operations", params={"drama_id": "new_drama_001"})
        global_resp = await ac.get("/dashboard/operations")

    assert filtered_resp.status_code == 200
    filtered = filtered_resp.json()["data"]
    assert filtered["dramaId"] == "new_drama_001"
    assert filtered["overview"]["watchEpisodeCount"] == 1
    assert filtered["overview"]["watchCompletedCount"] == 1
    assert filtered["overview"]["interactionImpressions"] == 1

    global_data = global_resp.json()["data"]
    assert global_data["dramaId"] == ""
    assert global_data["overview"]["watchEpisodeCount"] == 2
    assert global_data["overview"]["interactionImpressions"] == 2
