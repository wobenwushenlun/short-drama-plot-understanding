import json

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.quality_evaluation import (
    STORY_SUMMARY_DRAMA_MAX_CHARS,
    STORY_SUMMARY_DRAMA_MIN_CHARS,
    STORY_SUMMARY_EPISODE_MAX_CHARS,
    STORY_SUMMARY_EPISODE_MIN_CHARS,
)


FORBIDDEN_USER_TEXT_MARKERS = (
    "speaker" + "1",
    "speaker" + " 1",
    "Speaker" + "1",
    "AI" + "识别",
    "A" + "SR",
    "O" + "CR",
    "关" + "键帧",
    "对话" + "识别",
    "视频" + "理解",
    "模" + "型",
)


def _assert_clean_user_text(text: str) -> None:
    assert text.strip()
    for marker in FORBIDDEN_USER_TEXT_MARKERS:
        assert marker not in text


def _assert_story_summary_quality(data: dict) -> None:
    _assert_clean_user_text(data["drama_description"])
    assert "第1集" not in data["drama_description"]
    assert "第2集" not in data["drama_description"]
    assert "speaker" not in data["drama_description"].lower()
    assert "ASR" not in data["drama_description"]
    assert "OCR" not in data["drama_description"]
    assert "容遇" in data["drama_description"] and "纪家" in data["drama_description"]
    assert any(token in data["drama_description"] for token in ("质疑", "误会", "危机", "内斗", "反转", "打脸"))
    assert STORY_SUMMARY_DRAMA_MIN_CHARS <= len(data["drama_description"]) <= STORY_SUMMARY_DRAMA_MAX_CHARS
    assert len(data["episodes"]) == 5
    for episode in data["episodes"]:
        summary = episode["summary"]
        _assert_clean_user_text(summary)
        assert "speaker" not in summary.lower()
        assert "ASR" not in summary
        assert "OCR" not in summary
        assert STORY_SUMMARY_EPISODE_MIN_CHARS <= len(summary) <= STORY_SUMMARY_EPISODE_MAX_CHARS
        assert any(token in summary for token in ("质疑", "嘲讽", "误解", "冲突", "反转", "危机", "打脸", "身份"))


def _seed_story_summary_cache(root, drama_description, episode_summaries):
    story_dir = root / "tainai3"
    story_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "prompt_version": "content.story_summary/p2-grounded-platform-copy",
        "status": "ok",
        "generated_at_ms": 1_900_000_000_000,
        "latency_ms": 1234,
        "model": {"model_name": "doubao-seed-test"},
        "result": {
            "drama_description": drama_description,
            "episodes": [
                {
                    "episode_id": f"tainai3_ep{episode_no:02d}",
                    "summary": summary,
                }
                for episode_no, summary in episode_summaries.items()
            ],
        },
    }
    (story_dir / "story_summaries.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_story_summary_quality_rules(monkeypatch, tmp_path):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog

    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        drama_resp = await ac.get("/dramas/tainai3")
        episodes_resp = await ac.get("/dramas/tainai3/episodes")

    drama = drama_resp.json()["data"]
    episodes = episodes_resp.json()["data"]["episodes"]
    description = drama["description"]

    assert drama_resp.status_code == 200
    assert episodes_resp.status_code == 200
    _assert_clean_user_text(description)
    assert "第1集" not in description and "第2集" not in description and "｜" not in description
    assert "容遇" in description and "纪家" in description
    assert any(token in description for token in ("质疑", "误会", "危机", "内斗", "反转", "打脸"))
    assert STORY_SUMMARY_DRAMA_MIN_CHARS <= len(description) <= STORY_SUMMARY_DRAMA_MAX_CHARS

    assert len(episodes) == 5
    for episode in episodes:
        summary = episode["summary"]
        _assert_clean_user_text(summary)
        assert STORY_SUMMARY_EPISODE_MIN_CHARS <= len(summary) <= STORY_SUMMARY_EPISODE_MAX_CHARS
        assert any(token in summary for token in ("质疑", "嘲讽", "误解", "冲突", "反转", "危机", "打脸", "身份"))


@pytest.mark.asyncio
async def test_interaction_artifact_quality_rules(monkeypatch, tmp_path):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog

    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)
    monkeypatch.setattr(content_catalog, "DEFAULT_DANMAKU_EVIDENCE_PATH", tmp_path / "missing.json")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/episodes/tainai3_ep01/timed-events")

    data = response.json()["data"]
    assert response.status_code == 200
    assert data["eventCount"] == len(data["events"]) == len(data["nodes"])
    assert data["events"]
    for event in data["events"]:
        assert event["eventId"]
        assert event["episodeId"] == "tainai3_ep01"
        assert event["componentType"]
        assert "evidenceRefs" in event
        assert event["generationSource"] in {"manual", "rule", "model", "reviewed_model"}
        assert 0 <= float(event["confidence"]) <= 1
        assert event["reviewStatus"] in {"accepted", "rejected", "edited"}
        assert len(event["payloadHash"]) == 16
    for node in data["nodes"]:
        user_text = " ".join(
            [
                node.get("title", ""),
                node.get("subtitle", ""),
                node.get("display", {}).get("promptText", ""),
                node.get("display", {}).get("badgeText", ""),
                node.get("aiInsert", {}).get("title", ""),
                node.get("aiInsert", {}).get("description", ""),
                " ".join(option.get("text", "") for option in node.get("options", [])),
            ]
        )
        _assert_clean_user_text(user_text)
        assert node["trigger"]["timeMs"] == next(event["startMs"] for event in data["events"] if event["eventId"] == f"timeline_{node['id']}")
        if node["generation"]["generationSource"] != "manual":
            assert any(ref for ref in node["generation"]["evidenceRefs"] or [])


@pytest.mark.asyncio
async def test_story_summary_cache_quality_and_fallback_contract(monkeypatch, tmp_path):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog

    monkeypatch.setenv("AIGC_AI_REMOTE_MODEL", "0")
    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)
    _seed_story_summary_cache(
        tmp_path,
        "1955年，容遇意外穿到七十年后的同名少女身上。她先稳住纪家晚辈的质疑，再在纪家误会和内斗中一步步夺回主动权，"
        "同时守住亲情线索、压住家族舆论，并在一连串试探里把局势重新拉回自己手中。",
        {
            1: "第1集｜容遇醒来后先压住混乱场面，避免身份暴露。",
            2: "第2集｜纪家继续试探她，她借势反击并让局面开始反转。",
            3: "第3集｜身份线索开始浮现，家族态度出现动摇。",
            4: "第4集｜冲突升级为正面对线，容遇逐渐掌控局势。",
            5: "第5集｜人物关系和身份线索汇合，更大危机被吊起。",
        },
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        first_resp = await ac.get("/story-summary/cache", params={"drama_id": "tainai3"})
        second_resp = await ac.get("/story-summary/cache", params={"drama_id": "tainai3"})
        refresh_resp = await ac.post("/story-summary/cache/refresh", json={"dramaId": "tainai3"})

    assert first_resp.status_code == 200
    assert second_resp.status_code == 200
    assert refresh_resp.status_code == 200

    first_data = first_resp.json()["data"]
    second_data = second_resp.json()["data"]
    refresh_data = refresh_resp.json()["data"]

    assert first_data == second_data
    assert first_data["prompt_version"] == "content.story_summary/p2-grounded-platform-copy"
    assert first_data["source"] == "latest_success"
    assert first_data["status"] == "ok"
    assert first_data["generated_at"] == 1_900_000_000_000
    assert first_data["model_name"] == "doubao-seed-test"
    assert first_data["latency_ms"] == 1234
    assert first_data["degrade_reason"] == ""
    assert first_data["cache_policy"]["success_result_versioned"] is True
    assert first_data["cache_policy"]["degraded_attempt_does_not_override_success"] is True
    _assert_story_summary_quality(first_data)

    assert refresh_data["source"] == "latest_success"
    assert refresh_data["latest_attempt"]["source"] == "latest_attempt"
    assert refresh_data["latest_attempt"]["status"] == "degraded"
    assert refresh_data["latest_attempt"]["degrade_reason"]
    _assert_story_summary_quality(refresh_data)


@pytest.mark.asyncio
async def test_story_summary_cache_rejects_technical_payloads(monkeypatch, tmp_path):
    from backend.app.main import app
    import backend.app.content_catalog as content_catalog

    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)
    _seed_story_summary_cache(
        tmp_path,
        "speaker1: ASR/OCR/关键帧 融合理解结果",
        {
            1: "第1集｜speaker1 通过 ASR 识别台词，画面 OCR 也给出提示。",
            2: "第2集｜继续展示视频理解过程和模型输出。",
        },
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/story-summary/cache", params={"drama_id": "tainai3"})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["source"] == "local_fallback"
    assert data["status"] == "local_fallback"
    _assert_story_summary_quality(data)
    assert "speaker" not in data["drama_description"].lower()
    assert "ASR" not in data["drama_description"]
    assert "OCR" not in data["drama_description"]


@pytest.mark.asyncio
async def test_quality_evaluation_report_exposes_regression_gates(monkeypatch, tmp_path):
    from backend.app.main import app
    from backend.app.runtime_sqlite_store import reset_runtime_store_for_tests
    import backend.app.content_catalog as content_catalog

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    reset_runtime_store_for_tests()
    monkeypatch.setattr(content_catalog, "DEFAULT_VIDEO_UNDERSTANDING_ROOT", tmp_path)
    monkeypatch.setattr(content_catalog, "DEFAULT_DANMAKU_EVIDENCE_PATH", tmp_path / "missing.json")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/quality/evaluation")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["suiteVersion"] == "quality.shortplay/p2-regression-v1"
    assert data["source"] == "stable_cache_and_timed_events"
    assert data["summary"]["total"] == len(data["checks"])
    assert data["summary"]["failed"] == 0
    check_ids = {item["checkId"] for item in data["checks"]}
    assert "story.drama_clean" in check_ids
    assert "story.drama_not_episode_concat" in check_ids
    assert "interaction.timed_event_schema" in check_ids
    assert "interaction.traceable_evidence" in check_ids
    assert "interaction.high_energy_alignment" in check_ids
    assert "evidence.graph_complete" in check_ids
    assert "aigc.output_story_fit" in check_ids


def test_quality_evaluation_flags_bad_interaction_and_aigc_samples():
    from backend.app.quality_evaluation import build_quality_evaluation_report

    report = build_quality_evaluation_report(
        summary_status={
            "drama_description": "容遇回到纪家后面对质疑和危机，凭借判断力完成反转打脸。",
            "episodes": [
                {"summary": "容遇遭到质疑后稳住局势，身份线索开始浮出水面。"}
                for _ in range(5)
            ],
        },
        timed_payload={
            "events": [
                {
                    "eventId": "bad_event",
                    "episodeId": "tainai3_ep01",
                    "startMs": 1000,
                    "endMs": 2000,
                    "componentType": "",
                    "generationSource": "model",
                    "reviewStatus": "accepted",
                    "payloadHash": "",
                    "payload": {"id": "bad_node"},
                }
            ],
            "nodes": [
                {
                    "id": "bad_node",
                    "title": "ASR speaker1 prompt 泄露",
                    "generation": {
                        "generationSource": "model",
                        "evidenceRefs": [],
                        "confidence": 0.3,
                        "reviewStatus": "accepted",
                    },
                    "display": {"promptText": "OCR 识别结果"},
                    "options": [{"text": "继续"}],
                }
            ],
            "evidenceGraph": {"nodes": [], "evidence": [], "relations": []},
        },
        highlight_payload={"items": [{"sourceNodeId": "another_node"}]},
        generation_tasks=[
            {
                "taskId": "bad_aigc",
                "taskType": "story_continuation_video",
                "status": "succeeded",
                "mediaUrl": "https://cdn.example.test/bad.mp4",
                "result": {"title": "speaker1 prompt", "summary": "ASR OCR 技术过程"},
            }
        ],
        generated_at_ms=1,
    )

    failed = {check["checkId"]: check for check in report["checks"] if not check["passed"]}
    assert "interaction.timed_event_schema" in failed
    assert "interaction.traceable_evidence" in failed
    assert "interaction.user_text_clean" in failed
    assert "interaction.high_energy_alignment" in failed
    assert "evidence.graph_complete" in failed
    assert "aigc.output_story_fit" in failed
    assert failed["interaction.user_text_clean"]["targets"] == ["bad_node"]
    assert failed["aigc.output_story_fit"]["targets"] == ["bad_aigc"]
