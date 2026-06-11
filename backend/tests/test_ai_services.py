import pytest
from httpx import ASGITransport, AsyncClient


class FakeAIService:
    def __init__(self):
        self.calls: list[tuple[str, dict[str, object], str | None]] = []

    def content_recap(self, payload: dict[str, object], request_base_url: str):
        self.calls.append(("content_recap", payload, request_base_url))
        return {
            "capability": "content.recap",
            "status": "ok",
            "cached": False,
            "model": {"provider": "fake", "model_name": "fake"},
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "latency_ms": 1,
            "result": {"summary": "fake recap"},
        }

    def interaction_feedback(self, payload: dict[str, object], request_base_url: str):
        self.calls.append(("interaction_feedback", payload, request_base_url))
        return {
            "capability": "interaction.feedback",
            "status": "ok",
            "cached": False,
            "model": {"provider": "fake", "model_name": "fake"},
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "latency_ms": 1,
            "result": {"feedback_text": "fake feedback"},
        }

    def tag_extract(self, payload: dict[str, object], request_base_url: str):
        self.calls.append(("tag_extract", payload, request_base_url))
        return {
            "capability": "tag.extract",
            "status": "ok",
            "cached": False,
            "model": {"provider": "fake", "model_name": "fake"},
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "latency_ms": 1,
            "result": {"content_tags": [], "interaction_tags": [], "user_profile_tag_updates": []},
        }

    def moderation_check(self, payload: dict[str, object]):
        self.calls.append(("moderation_check", payload, None))
        return {
            "status": "blocked",
            "result": {
                "decision": "block",
                "risk_flags": ["self_harm"],
                "matched_keywords": ["自杀"],
                "review_text": str(payload.get("text", "")),
            },
            "model": {"provider": "rule", "model_name": "local-moderation-rule"},
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "latency_ms": 0,
            "cache_hit": False,
            "block_reason": "内容包含风险关键词",
        }

    def discussion_seed(self, payload: dict[str, object], request_base_url: str):
        self.calls.append(("discussion_seed", payload, request_base_url))
        return {
            "capability": "discussion.seed",
            "status": "ok",
            "cached": False,
            "model": {"provider": "fake", "model_name": "fake"},
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "latency_ms": 1,
            "result": {"discussion_questions": ["fake question"]},
        }

    def story_continuation(self, payload: dict[str, object], request_base_url: str):
        self.calls.append(("story_continuation", payload, request_base_url))
        return {
            "capability": "story.continuation",
            "status": "ok",
            "cached": False,
            "model": {"provider": "fake", "model_name": "fake"},
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "latency_ms": 1,
            "result": {
                "continuation_title": "fake continuation",
                "generated_asset": {
                    "provider": {"name": "agnes-video", "mode": "remote"},
                    "mediaUrl": "http://test/media/generated-assets/continuation.mp4",
                    "mediaType": "video/mp4",
                    "assetCache": {
                        "cacheStatus": "cached",
                        "remoteUrl": "https://cdn.example.test/continuation.mp4",
                        "localUrl": "http://test/media/generated-assets/continuation.mp4",
                        "mediaUrl": "http://test/media/generated-assets/continuation.mp4",
                    },
                },
            },
        }

    def history_recap(self, payload: dict[str, object], request_base_url: str):
        self.calls.append(("history_recap", payload, request_base_url))
        return {
            "capability": "history.recap",
            "status": "ok",
            "cached": False,
            "model": {"provider": "fake", "model_name": "fake"},
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "latency_ms": 1,
            "result": {"summary": "fake history"},
        }

    def recommend_home(self, payload: dict[str, object], request_base_url: str):
        self.calls.append(("recommend_home", payload, request_base_url))
        return {
            "capability": "recommend.home",
            "status": "ok",
            "cached": False,
            "model": {"provider": "fake", "model_name": "fake"},
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "latency_ms": 1,
            "result": {"strategy": "fake recommend"},
        }

    def agnes_status(self):
        self.calls.append(("agnes_status", {}, None))
        return {
            "configured": True,
            "source": "env",
            "baseUrl": "https://apihub.example.test",
            "imageModel": "agnes-image-1.2",
            "videoModel": "agnes-video-v1.2",
        }

    def checkin_card(self, payload: dict[str, object], request_base_url: str):
        self.calls.append(("checkin_card", payload, request_base_url))
        return {
            "capability": "agnes.checkin_card",
            "status": "ok",
            "cached": False,
            "model": {"provider": "agnes", "model_name": "agnes-image-1.2"},
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "latency_ms": 12,
            "result": {
                "title": "fake checkin",
                "prompt": "fake prompt",
                "imageUrl": "http://test/media/generated-assets/checkin.png",
                "provider": "agnes",
                "status": "ok",
                "latencyMs": 12,
                "degradeReason": "",
                "assetCache": {
                    "cacheStatus": "cached",
                    "remoteUrl": "https://cdn.example.test/checkin.png",
                    "localUrl": "http://test/media/generated-assets/checkin.png",
                    "mediaUrl": "http://test/media/generated-assets/checkin.png",
                },
            },
        }


@pytest.mark.asyncio
async def test_model_apikey_file_parser_supports_cn_colon(monkeypatch, tmp_path):
    from backend.app.ai_service import load_ark_credentials

    config_file = tmp_path / "model_apikey.txt"
    config_file.write_text("EP：ep-test-123\nAPIKEY：key-test-456\n", encoding="utf-8")
    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("ARK_ENDPOINT_ID", raising=False)
    monkeypatch.delenv("ARK_MODEL", raising=False)
    monkeypatch.delenv("ARK_MODEL_ID", raising=False)
    monkeypatch.setenv("AIGC_MODEL_CONFIG_PATH", str(config_file))

    creds = load_ark_credentials()

    assert creds.endpoint_id == "ep-test-123"
    assert creds.api_key == "key-test-456"
    assert creds.source_path == str(config_file)


def test_model_result_parser_repairs_common_json_variants():
    from backend.app.ai_service import _load_jsonish

    parsed = _load_jsonish(
        """
        下面是结果：
        ```json
        {'summary':'测试摘要','highlights':['要点1',],}
        ```
        """
    )

    assert parsed == {"summary": "测试摘要", "highlights": ["要点1"]}


def test_model_result_parser_extracts_fenced_json_from_explained_response():
    from backend.app.ai_service import _load_jsonish

    parsed = _load_jsonish(
        """
        以下是结果，请查收：
        ```json
        {
          "story_summary": "家庭矛盾升级，人物关系出现新的裂痕。",
          "segments": [{"start_ms": 0, "end_ms": 30000, "summary": "开场冲突"},],
        }
        ```
        以上内容仅供参考。
        """
    )

    assert parsed is not None
    assert parsed["story_summary"].startswith("家庭矛盾升级")
    assert parsed["segments"][0]["summary"] == "开场冲突"


def test_chat_completion_retries_when_json_mode_unsupported(monkeypatch, tmp_path):
    from backend.app.ai_service import AIService, ArkCredentials

    service = AIService(
        ArkCredentials(endpoint_id="ep-test", api_key="key-test"),
        audit_path=tmp_path / "audit.jsonl",
    )
    calls: list[bool] = []

    def fake_call(*args, **kwargs):
        json_mode = bool(kwargs.get("json_mode", True))
        calls.append(json_mode)
        if json_mode:
            raise RuntimeError("response_format unsupported")
        return {"choices": [{"message": {"content": '{"summary":"ok"}'}}]}

    monkeypatch.setattr(service, "_call_chat_completion", fake_call)

    response = service._call_chat_completion_best_effort(
        capability="content.recap",
        messages=[{"role": "user", "content": "只输出 JSON"}],
        max_tokens=32,
        temperature=0.1,
    )

    assert calls == [True, False]
    assert service._parse_model_result(response) == {"summary": "ok"}


def test_chat_completion_falls_back_to_python_http_when_curl_fails(monkeypatch, tmp_path):
    import backend.app.ai_service as ai_service_module
    from backend.app.ai_service import AIService, ArkCredentials

    service = AIService(
        ArkCredentials(endpoint_id="ep-test", api_key="key-test"),
        audit_path=tmp_path / "audit.jsonl",
    )

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self):
            return b'{"choices":[{"message":{"content":"{\\"summary\\":\\"urllib ok\\"}"}}]}'

    monkeypatch.setattr(ai_service_module.shutil, "which", lambda _: "curl.exe")
    monkeypatch.setattr(
        service,
        "_call_chat_completion_with_curl",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("curl failed")),
    )
    monkeypatch.setattr(ai_service_module.urlrequest, "urlopen", lambda *args, **kwargs: FakeResponse())

    response = service._call_chat_completion(
        "content.recap",
        [{"role": "user", "content": "test"}],
        max_tokens=32,
        temperature=0.1,
    )

    assert service._parse_model_result(response) == {"summary": "urllib ok"}


def test_video_understanding_evidence_reads_drama_namespaced_cache(monkeypatch, tmp_path):
    import json
    import backend.app.ai_service as ai_service_module

    root = tmp_path / "video_understanding_results"
    namespaced_dir = root / "jiali_jiawai" / "jiali_jiawai_ep01"
    legacy_dir = root / "jiali_jiawai_ep01"
    namespaced_dir.mkdir(parents=True)
    legacy_dir.mkdir(parents=True)
    (namespaced_dir / "understanding.json").write_text(
        json.dumps(
            {
                "envelope": {
                    "result": {
                        "story_summary": "家里家外第一集围绕家庭矛盾展开。",
                        "audio_text": {"speaker_transcript": "家人围坐争执"},
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (legacy_dir / "understanding.json").write_text(
        json.dumps(
            {
                "envelope": {
                    "result": {
                        "story_summary": "旧路径不应优先命中。",
                        "audio_text": {"speaker_transcript": "legacy"},
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AIGC_VIDEO_UNDERSTANDING_ROOT", str(root))

    evidence = ai_service_module._load_video_understanding_evidence(
        "jiali_jiawai_ep01",
        drama_id="jiali_jiawai",
    )

    assert evidence["story_summary"] == "家里家外第一集围绕家庭矛盾展开。"
    assert evidence["speakerTranscript"] == "家人围坐争执"


def test_degraded_ai_response_replays_last_success_artifact(monkeypatch, tmp_path):
    from backend.app.ai_service import AIService, ArkCredentials
    from backend.app.runtime_sqlite_store import get_runtime_store, reset_runtime_store_for_tests

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    reset_runtime_store_for_tests()
    service = AIService(
        ArkCredentials(endpoint_id="ep-test", api_key="key-test"),
        audit_path=tmp_path / "audit.jsonl",
    )
    context = {
        "drama": {"dramaId": "tainai3"},
        "episode": {"episodeId": "tainai3_ep01"},
    }
    success = service._decorate_response(
        capability="content.recap",
        result={"summary": "成功产物"},
        status="ok",
        latency_ms=20,
        usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        cache_hit=False,
        model_info={"provider": "volcengine-ark", "model_name": "ep-test"},
    )
    service._append_audit(
        capability="content.recap",
        payload=context,
        envelope=success,
        prompt_version="content.recap/test",
    )
    degraded = service._decorate_response(
        capability="content.recap",
        result={"summary": "降级兜底"},
        status="degraded",
        latency_ms=10,
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        cache_hit=False,
        model_info={"provider": "volcengine-ark", "model_name": "ep-test"},
        degrade_reason="remote timeout",
    )
    service._append_audit(
        capability="content.recap",
        payload=context,
        envelope=degraded,
        prompt_version="content.recap/test",
    )

    assert success["artifact"]["version"] == 1
    assert degraded["status"] == "degraded"
    assert degraded["result"]["summary"] == "成功产物"
    assert degraded["artifact"]["source"] == "last_success_artifact"
    assert degraded["artifact"]["restored_from_last_success"] is True
    assert degraded["artifact"]["last_success_version"] == 1
    summary = get_runtime_store().build_runtime_summary("tainai3_ep01")
    assert summary["ai"]["successRate"] == 0.5
    assert summary["ai"]["degradedRate"] == 0.5
    assert summary["ai"]["p95LatencyMs"] == 20


@pytest.mark.asyncio
async def test_ai_endpoints_delegate_to_service(monkeypatch):
    from backend.app.main import app
    import backend.app.api.routes.ai as ai_routes

    fake_service = FakeAIService()
    monkeypatch.setattr(ai_routes, "get_ai_service", lambda: fake_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        recap_resp = await ac.post("/ai/content/recap", json={"episodeId": "tainai3_ep01"})
        feedback_resp = await ac.post(
            "/ai/interaction/feedback",
            json={
                "episodeId": "tainai3_ep01",
                "nodeId": "n_045_vote_stance",
                "optionId": "B",
            },
        )
        tag_resp = await ac.post(
            "/ai/tag/extract",
            json={
                "episodeId": "tainai3_ep01",
                "nodeId": "n_045_vote_stance",
                "optionId": "B",
            },
        )
        moderation_resp = await ac.post("/ai/moderation/check", json={"text": "自杀"})
        discussion_resp = await ac.post(
            "/ai/discussion/seed",
            json={
                "episodeId": "tainai3_ep01",
                "nodeId": "n_045_vote_stance",
                "optionId": "B",
            },
        )
        continuation_resp = await ac.post("/ai/story/continuation", json={"episodeId": "tainai3_ep01"})
        history_resp = await ac.post("/ai/history/recap", json={"size": 3})
        recommend_resp = await ac.post("/ai/recommend/home", json={"size": 3})
        agnes_status_resp = await ac.get("/ai/agnes/status")
        checkin_resp = await ac.post("/ai/checkin-card", json={"episodeId": "tainai3_ep01"})

    assert recap_resp.status_code == 200
    assert recap_resp.json()["data"]["result"]["summary"] == "fake recap"
    assert feedback_resp.status_code == 200
    assert feedback_resp.json()["data"]["result"]["feedback_text"] == "fake feedback"
    assert tag_resp.status_code == 200
    assert tag_resp.json()["data"]["result"]["content_tags"] == []
    assert moderation_resp.status_code == 200
    assert moderation_resp.json()["data"]["status"] == "blocked"
    assert discussion_resp.status_code == 200
    assert discussion_resp.json()["data"]["result"]["discussion_questions"] == ["fake question"]
    assert continuation_resp.status_code == 200
    assert continuation_resp.json()["data"]["result"]["continuation_title"] == "fake continuation"
    assert history_resp.status_code == 200
    assert history_resp.json()["data"]["result"]["summary"] == "fake history"
    assert recommend_resp.status_code == 200
    assert recommend_resp.json()["data"]["result"]["strategy"] == "fake recommend"
    assert agnes_status_resp.status_code == 200
    assert agnes_status_resp.json()["data"]["configured"] is True
    assert checkin_resp.status_code == 200
    assert checkin_resp.json()["data"]["result"]["imageUrl"].endswith("/checkin.png")
    assert [item[0] for item in fake_service.calls] == [
        "content_recap",
        "interaction_feedback",
        "tag_extract",
        "moderation_check",
        "discussion_seed",
        "story_continuation",
        "history_recap",
        "recommend_home",
        "agnes_status",
        "checkin_card",
    ]


@pytest.mark.asyncio
async def test_generation_task_endpoints_persist_task_and_last_success(monkeypatch, tmp_path):
    from backend.app.main import app
    from backend.app.runtime_sqlite_store import reset_runtime_store_for_tests
    import backend.app.api.routes.ai as ai_routes

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    reset_runtime_store_for_tests()
    fake_service = FakeAIService()
    monkeypatch.setattr(ai_routes, "get_ai_service", lambda: fake_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        create_resp = await ac.post(
            "/ai/generation/tasks",
            json={"taskType": "story_continuation_video", "episodeId": "tainai3_ep01", "dramaId": "tainai3"},
        )
        created = create_resp.json()["data"]
        query_resp = await ac.get(f"/ai/generation/tasks/{created['taskId']}")

    assert create_resp.status_code == 200
    assert created["taskType"] == "story_continuation_video"
    assert created["status"] == "queued"
    assert created["mediaUrl"] == ""
    assert created["lastSuccess"]["taskId"] == ""
    assert query_resp.status_code == 200
    queried = query_resp.json()["data"]
    assert queried["taskId"] == created["taskId"]
    assert queried["status"] == "succeeded"
    assert queried["mediaUrl"] == "http://test/media/generated-assets/continuation.mp4"
    assert queried["result"]["assetCache"]["cacheStatus"] == "cached"
    assert queried["lastSuccess"]["mediaUrl"] == queried["mediaUrl"]
    assert queried["lastSuccess"]["assetCache"]["localUrl"] == queried["mediaUrl"]
    assert fake_service.calls[-1][0] == "story_continuation"


@pytest.mark.asyncio
async def test_generated_asset_management_lists_success_and_cleans_failed(monkeypatch, tmp_path):
    from backend.app.main import app
    from backend.app.runtime_sqlite_store import get_runtime_store, reset_runtime_store_for_tests

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    reset_runtime_store_for_tests()
    store = get_runtime_store()
    store.save_generation_task(
        {
            "taskId": "gen_success_checkin",
            "taskType": "checkin_card",
            "dramaId": "tainai3",
            "episodeId": "tainai3_ep01",
            "status": "succeeded",
            "provider": "agnes",
            "modelName": "agnes-image-2.0-flash",
            "mediaUrl": "http://test/media/generated-assets/checkin.png",
            "mediaType": "image/png",
            "latencyMs": 1200,
            "result": {
                "title": "反转打卡",
                "assetCache": {
                    "assetId": "checkin.png",
                    "remoteUrl": "https://cdn.example.test/checkin.png",
                    "localUrl": "http://test/media/generated-assets/checkin.png",
                    "mediaUrl": "http://test/media/generated-assets/checkin.png",
                    "contentType": "image/png",
                    "cacheStatus": "cached",
                    "byteSize": 2048,
                },
            },
        }
    )
    store.save_generation_task(
        {
            "taskId": "gen_failed_video",
            "taskType": "story_continuation_video",
            "dramaId": "tainai3",
            "episodeId": "tainai3_ep01",
            "status": "failed",
            "provider": "agnes-video",
            "modelName": "agnes-video-v2.0",
            "mediaUrl": "",
            "mediaType": "",
            "degradeReason": "timeout",
            "result": {"title": "失败续写"},
        }
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        list_resp = await ac.get("/ai/generated-assets?drama_id=tainai3")
        cleanup_resp = await ac.delete("/ai/generated-assets/failed?drama_id=tainai3")
        after_resp = await ac.get("/ai/generated-assets?drama_id=tainai3")

    assert list_resp.status_code == 200
    data = list_resp.json()["data"]
    assert data["summary"]["successCount"] == 1
    assert data["summary"]["failedCount"] == 1
    assert data["recentSuccesses"][0]["taskId"] == "gen_success_checkin"
    assert data["recentSuccesses"][0]["assetCache"]["localUrl"].endswith("/checkin.png")
    assert cleanup_resp.status_code == 200
    assert cleanup_resp.json()["data"]["deletedCount"] == 1
    assert after_resp.json()["data"]["summary"]["failedCount"] == 0


def test_ai_service_checkin_card_uses_aggregated_context_without_secret_leak(monkeypatch, tmp_path):
    import backend.app.ai_service as ai_service_module
    from backend.app.ai_service import AIService, ArkCredentials

    captured_prompt = {}

    def fake_cache_remote_generated_asset(**kwargs):
        assert kwargs["remote_url"] == "https://cdn.example.test/checkin.png"
        return {
            "assetId": "checkin_card_001.png",
            "remoteUrl": kwargs["remote_url"],
            "localUrl": "http://test/media/generated-assets/checkin_card_001.png",
            "mediaUrl": "http://test/media/generated-assets/checkin_card_001.png",
            "contentType": "image/png",
            "cacheStatus": "cached",
            "byteSize": 12,
        }

    class FakeAgnesClient:
        credentials = type("Credentials", (), {"image_model": "agnes-image-1.2"})()

        def generate_image(self, prompt, size="1024x1024", n=1):
            captured_prompt["text"] = prompt
            return {
                "provider": "agnes",
                "model_name": "agnes-image-1.2",
                "status": "ok",
                "media_url": "https://cdn.example.test/checkin.png",
                "latency_ms": 33,
                "degrade_reason": "",
            }

    monkeypatch.setattr(ai_service_module, "AgnesClient", lambda: FakeAgnesClient())
    monkeypatch.setattr(
        ai_service_module,
        "cache_remote_generated_asset",
        fake_cache_remote_generated_asset,
        raising=False,
    )
    service = AIService(
        ArkCredentials(endpoint_id="ep-test", api_key="key-test"),
        audit_path=tmp_path / "audit.jsonl",
    )

    result = service.checkin_card({"episodeId": "tainai3_ep01", "style": "short_drama_poster"}, "http://test/")

    assert result["status"] == "ok"
    assert result["result"]["imageUrl"] == "http://test/media/generated-assets/checkin_card_001.png"
    assert result["result"]["remoteImageUrl"] == "https://cdn.example.test/checkin.png"
    assert result["result"]["assetCache"]["cacheStatus"] == "cached"
    assert result["result"]["provider"] == "agnes"
    assert result["result"]["status"] == "ok"
    assert "弹幕内容" not in captured_prompt["text"]
    assert "secret" not in str(result).lower()
    assert "tainai3_ep01" in captured_prompt["text"]


def test_ai_service_checkin_card_applies_style_template_and_interaction_context(monkeypatch, tmp_path):
    import backend.app.ai_service as ai_service_module
    from backend.app.ai_service import AIService, ArkCredentials

    captured_prompt = {}

    class FakeAgnesClient:
        credentials = type("Credentials", (), {"image_model": "agnes-image-2.1-flash"})()

        def generate_image(self, prompt, size="1024x1024", n=1):
            captured_prompt["text"] = prompt
            return {
                "provider": "agnes",
                "model_name": "agnes-image-2.1-flash",
                "status": "ok",
                "media_url": "https://cdn.example.test/checkin-style.png",
                "latency_ms": 41,
                "degrade_reason": "",
            }

    monkeypatch.setattr(ai_service_module, "AgnesClient", lambda: FakeAgnesClient())
    monkeypatch.setattr(
        ai_service_module,
        "cache_remote_generated_asset",
        lambda **kwargs: {
            "assetId": "checkin_style_001.png",
            "remoteUrl": kwargs["remote_url"],
            "localUrl": "http://test/media/generated-assets/checkin_style_001.png",
            "mediaUrl": "http://test/media/generated-assets/checkin_style_001.png",
            "contentType": "image/png",
            "cacheStatus": "cached",
            "byteSize": 12,
        },
        raising=False,
    )
    service = AIService(
        ArkCredentials(endpoint_id="ep-test", api_key="key-test"),
        audit_path=tmp_path / "audit.jsonl",
    )

    result = service.checkin_card(
        {"episodeId": "tainai3_ep02", "style": "identity_reveal"},
        "http://test/",
    )

    assert result["status"] == "ok"
    assert result["result"]["style"] == "identity_reveal"
    assert result["result"]["styleLabel"] == "身份揭露"
    assert "身份揭露" in captured_prompt["text"]
    assert "风格模板（最高优先级）：身份揭露" in captured_prompt["text"]
    assert "冷蓝暗调配金色线索光" in captured_prompt["text"]
    assert "不要使用豪门大厅群像" in captured_prompt["text"]
    assert "人物关系：" in captured_prompt["text"]
    assert "互动爽点：" in captured_prompt["text"]
    assert "原始弹幕" not in captured_prompt["text"]
    assert "speaker1" not in captured_prompt["text"].lower()


def test_ai_service_checkin_card_refines_user_intent_before_agnes_prompt(monkeypatch, tmp_path):
    import backend.app.ai_service as ai_service_module
    from backend.app.ai_service import AIService, ArkCredentials

    monkeypatch.setenv("AIGC_AI_REMOTE_MODEL", "1")
    captured_prompt = {}

    class FakeAgnesClient:
        credentials = type("Credentials", (), {"image_model": "agnes-image-2.1-flash"})()

        def generate_image(self, prompt, size="1024x1024", n=1):
            captured_prompt["text"] = prompt
            return {
                "provider": "agnes",
                "model_name": "agnes-image-2.1-flash",
                "status": "ok",
                "media_url": "https://cdn.example.test/checkin-intent.png",
                "latency_ms": 42,
                "degrade_reason": "",
            }

    monkeypatch.setattr(ai_service_module, "AgnesClient", lambda: FakeAgnesClient())
    monkeypatch.setattr(
        ai_service_module,
        "cache_remote_generated_asset",
        lambda **kwargs: {
            "assetId": "checkin_intent_001.png",
            "remoteUrl": kwargs["remote_url"],
            "localUrl": "http://test/media/generated-assets/checkin_intent_001.png",
            "mediaUrl": "http://test/media/generated-assets/checkin_intent_001.png",
            "contentType": "image/png",
            "cacheStatus": "cached",
            "byteSize": 12,
        },
        raising=False,
    )
    service = AIService(
        ArkCredentials(endpoint_id="ep-test", api_key="key-test"),
        audit_path=tmp_path / "audit.jsonl",
    )
    monkeypatch.setattr(
        service,
        "_call_chat_completion_best_effort",
        lambda **kwargs: {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"intent_summary":"用户希望女主黑化反击",'
                            '"story_direction":"女主不再退让，公开证据反制家族",'
                            '"image_prompt_addon":"黑化女主站在强光中心，身后家族众人震惊后退",'
                            '"video_prompt_addon":"镜头从低角度推进，女主拿出证据完成反杀",'
                            '"negative_prompt":"不要温情和解，不要平淡合影",'
                            '"safety_notes":["保留虚构剧情"]}'
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        },
    )

    result = service.checkin_card(
        {
            "episodeId": "tainai3_ep02",
            "style": "reversal_scene",
            "userIntent": "我想要女主黑化反击，结局更狠一点",
        },
        "http://test/",
    )

    assert result["status"] == "ok"
    assert result["result"]["promptRefinement"]["intentSummary"] == "用户希望女主黑化反击"
    assert "黑化女主站在强光中心" in captured_prompt["text"]
    assert "不要温情和解" in captured_prompt["text"]
    assert "我想要女主黑化反击" in captured_prompt["text"]


def test_ai_service_story_continuation_passes_refined_user_intent_to_video_provider(monkeypatch, tmp_path):
    from backend.app.ai_service import AIService, ArkCredentials

    monkeypatch.setenv("AIGC_AI_REMOTE_MODEL", "1")
    captured_node = {}

    class FakeProvider:
        def build_insert(self, *, episode_id, node, episode_summary, request_base_url):
            captured_node.update(node)
            return {
                "provider": {"name": "fake-video", "mode": "remote"},
                "status": "ok",
                "mediaUrl": "http://test/media/story.mp4",
                "mediaType": "video/mp4",
                "playback": {"mode": "POST_EPISODE_CONTINUATION"},
            }

    import backend.app.ai_service as ai_service_module

    monkeypatch.setattr(ai_service_module, "get_aigc_insert_provider", lambda: FakeProvider())
    service = AIService(
        ArkCredentials(endpoint_id="ep-test", api_key="key-test"),
        audit_path=tmp_path / "audit.jsonl",
    )

    def fake_chat_completion(**kwargs):
        content = kwargs["messages"][1]["content"]
        if '"task":"creative.prompt.refine"' in content:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"intent_summary":"希望男主回头道歉",'
                                '"story_direction":"男主公开认错，女主保留主动权",'
                                '"image_prompt_addon":"雨夜对峙，女主背光转身",'
                                '"video_prompt_addon":"雨夜门口，男主追上来道歉但女主没有立刻原谅",'
                                '"negative_prompt":"不要立刻大团圆",'
                                '"safety_notes":[]}'
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 5, "total_tokens": 8},
            }
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"continuation_title":"雨夜回头",'
                            '"continuation_summary":"男主追到门口道歉，女主没有立刻原谅。",'
                            '"scene_direction":"雨夜门口，车灯照亮两人",'
                            '"dialogue_lines":["女主：道歉不是结局。"],'
                            '"viewer_hook":"她会不会给第二次机会？"}'
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        }

    monkeypatch.setattr(service, "_call_chat_completion_best_effort", fake_chat_completion)

    result = service.story_continuation(
        {
            "episodeId": "tainai3_ep01",
            "userIntent": "希望男主回头道歉，但女主不要马上原谅",
            "desiredEnding": "女主保留主动权",
        },
        "http://test/",
    )

    assert result["status"] == "ok"
    assert result["result"]["prompt_refinement"]["intent_summary"] == "希望男主回头道歉"
    assert captured_node["userIntent"] == "希望男主回头道歉，但女主不要马上原谅"
    assert "雨夜门口，男主追上来道歉" in captured_node["creativePrompt"]["videoPromptAddon"]


def test_ai_service_checkin_card_degrades_to_local_text_card(monkeypatch, tmp_path):
    import backend.app.ai_service as ai_service_module
    from backend.app.ai_service import AIService, ArkCredentials
    from backend.app.runtime_sqlite_store import reset_runtime_store_for_tests

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    reset_runtime_store_for_tests()
    calls = {"count": 0}

    class FakeAgnesClient:
        credentials = type("Credentials", (), {"image_model": "agnes-image-2.1-flash"})()

        def generate_image(self, prompt, size="1024x1024", n=1):
            calls["count"] += 1
            if calls["count"] == 1:
                return {
                    "provider": "agnes",
                    "model_name": "agnes-image-2.1-flash",
                    "status": "ok",
                    "media_url": "https://cdn.example.test/checkin-success.png",
                    "latency_ms": 11,
                    "degrade_reason": "",
                }
            return {
                "provider": "agnes",
                "model_name": "agnes-image-2.1-flash",
                "status": "degraded",
                "media_url": "",
                "latency_ms": 9,
                "degrade_reason": "remote timeout",
            }

    monkeypatch.setattr(ai_service_module, "AgnesClient", lambda: FakeAgnesClient())
    monkeypatch.setattr(
        ai_service_module,
        "cache_remote_generated_asset",
        lambda **kwargs: {
            "assetId": "checkin_success_001.png",
            "remoteUrl": kwargs["remote_url"],
            "localUrl": "http://test/media/generated-assets/checkin_success_001.png",
            "mediaUrl": "http://test/media/generated-assets/checkin_success_001.png",
            "contentType": "image/png",
            "cacheStatus": "cached",
            "byteSize": 12,
        },
        raising=False,
    )
    service = AIService(
        ArkCredentials(endpoint_id="ep-test", api_key="key-test"),
        audit_path=tmp_path / "audit.jsonl",
    )

    first = service.checkin_card(
        {"episodeId": "tainai3_ep03", "style": "face_slap"},
        "http://test/",
    )
    result = service.checkin_card(
        {"episodeId": "tainai3_ep03", "style": "face_slap"},
        "http://test/",
    )

    assert first["status"] == "ok"
    assert result["status"] == "degraded"
    assert result["result"]["provider"] == "local_fallback"
    assert result["result"]["imageUrl"] == ""
    assert result["result"]["fallbackCard"]["source"] == "local_fallback"
    assert result["result"]["fallbackCard"]["styleLabel"] == "打脸爽点"
    assert result["artifact"]["source"] == "local_fallback"
    assert result["artifact"]["restored_from_last_success"] is False
    assert result["artifact"]["last_success_version"] == 1


@pytest.mark.asyncio
async def test_ai_service_content_recap_uses_model_response(monkeypatch, tmp_path):
    from backend.app.ai_service import AIService, ArkCredentials

    monkeypatch.setenv("AIGC_AI_REMOTE_MODEL", "1")
    service = AIService(
        ArkCredentials(endpoint_id="ep-test", api_key="key-test"),
        audit_path=tmp_path / "audit.jsonl",
    )

    monkeypatch.setattr(
        service,
        "_call_chat_completion_best_effort",
        lambda **kwargs: {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"summary":"测试摘要","highlights":["要点1"],'
                            '"character_focus":["太奶奶"],"discussion_seeds":["问题1"],'
                            '"continue_reason":"继续看"}'
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        },
    )

    result = service.content_recap({"episodeId": "tainai3_ep01"}, "http://test/")

    assert result["status"] == "ok"
    assert result["result"]["summary"] == "测试摘要"
    assert result["result"]["character_focus"] == ["太奶奶"]
    assert result["model"]["model_name"] == "ep-test"


def test_ai_service_content_recap_parses_json_string_summary(monkeypatch, tmp_path):
    from backend.app.ai_service import AIService, ArkCredentials

    monkeypatch.setenv("AIGC_AI_REMOTE_MODEL", "1")
    service = AIService(
        ArkCredentials(endpoint_id="ep-test", api_key="key-test"),
        audit_path=tmp_path / "audit.jsonl",
    )

    monkeypatch.setattr(
        service,
        "_call_chat_completion_best_effort",
        lambda **kwargs: {
            "choices": [
                {
                    "message": {
                        "content": (
                            '"{\\"summary\\":\\"第1集围绕太奶奶回归家族展开，'
                            '她在误解和试探中重新掌握局面。\\",'
                            '\\"highlights\\":[\\"太奶奶回归\\",\\"家族误解升级\\"],'
                            '\\"character_focus\\":[\\"太奶奶\\"],'
                            '\\"discussion_seeds\\":[\\"你觉得她会如何反击？\\"],'
                            '\\"continue_reason\\":\\"身份反转刚开始，适合继续看下一集\\"}"'
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        },
    )

    result = service.content_recap({"episodeId": "tainai3_ep01", "dramaId": "tainai3"}, "http://test/")

    assert result["status"] == "ok"
    assert result["result"]["summary"].startswith("第1集围绕太奶奶")
    assert "{" not in result["result"]["summary"]
    assert result["result"]["highlights"] == ["太奶奶回归", "家族误解升级"]


@pytest.mark.asyncio
async def test_ai_service_moderation_blocks_risky_text(tmp_path):
    from backend.app.ai_service import AIService, ArkCredentials

    service = AIService(
        ArkCredentials(endpoint_id="ep-test", api_key="key-test"),
        audit_path=tmp_path / "unused-audit.jsonl",
    )

    result = service.moderation_check({"text": "我想自杀"})

    assert result["status"] == "blocked"
    assert result["result"]["decision"] == "block"
    assert "self_harm" in result["result"]["risk_flags"]


@pytest.mark.asyncio
async def test_ai_service_discussion_seed_uses_model_response(monkeypatch, tmp_path):
    from backend.app.ai_service import AIService, ArkCredentials

    monkeypatch.setenv("AIGC_AI_REMOTE_MODEL", "1")
    service = AIService(
        ArkCredentials(endpoint_id="ep-test", api_key="key-test"),
        audit_path=tmp_path / "audit.jsonl",
    )

    monkeypatch.setattr(
        service,
        "_call_chat_completion_best_effort",
        lambda **kwargs: {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"discussion_questions":["你怎么看？"],'
                            '"character_perspectives":[{"name":"太奶奶","question":"她为什么这样选？"}],'
                            '"next_episode_predictions":["会反转"],'
                            '"alternate_choice_topics":["另一种选择会怎样"],'
                            '"share_text":"一起讨论"}'
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        },
    )

    result = service.discussion_seed(
        {
            "episodeId": "tainai3_ep01",
            "nodeId": "n_045_vote_stance",
            "optionId": "B",
        },
        "http://test/",
    )

    assert result["status"] == "ok"
    assert result["result"]["discussion_questions"] == ["你怎么看？"]
    assert result["result"]["character_perspectives"][0]["name"] == "太奶奶"


@pytest.mark.asyncio
async def test_ai_service_story_continuation_builds_generated_clip(monkeypatch, tmp_path):
    import backend.app.ai_service as ai_service_module
    from backend.app.ai_service import AIService, ArkCredentials

    monkeypatch.setenv("AIGC_AI_REMOTE_MODEL", "1")
    service = AIService(
        ArkCredentials(endpoint_id="ep-test", api_key="key-test"),
        audit_path=tmp_path / "audit.jsonl",
    )
    captured_node: dict[str, object] = {}

    class FakeInsertProvider:
        def build_insert(self, *, episode_id, node, episode_summary, request_base_url):
            captured_node.update(node)
            return {
                "mediaUrl": f"{request_base_url}media/aigc-inserts/{episode_id}/continuation.mp4",
                "mediaType": "video/mp4",
                "playback": {"mode": node["playbackMode"]},
            }

    monkeypatch.setattr(ai_service_module, "get_aigc_insert_provider", lambda: FakeInsertProvider())
    monkeypatch.setattr(
        service,
        "_call_chat_completion_best_effort",
        lambda **kwargs: {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"continuation_title":"证据公开",'
                            '"continuation_summary":"容遇拿出证据扭转局面。",'
                            '"scene_direction":"众人沉默",'
                            '"dialogue_lines":["容遇：看清楚了。"],'
                            '"viewer_hook":"你会先公开哪份证据？"}'
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
        },
    )

    result = service.story_continuation({"episodeId": "tainai3_ep01"}, "http://test/")

    assert result["status"] == "ok"
    assert result["result"]["continuation_title"] == "证据公开"
    assert result["result"]["generated_asset"]["mediaUrl"].endswith("/continuation.mp4")
    assert captured_node["generatedHighEnergyLine"] == "容遇：看清楚了。"
    assert captured_node["playbackMode"] == "POST_EPISODE_CONTINUATION"


def test_story_continuation_restored_artifact_uses_current_playable_media(monkeypatch, tmp_path):
    import backend.app.ai_service as ai_service_module
    from backend.app.ai_service import AIService, ArkCredentials
    from backend.app.runtime_sqlite_store import get_runtime_store, reset_runtime_store_for_tests

    monkeypatch.setenv("AIGC_RUNTIME_DB_PATH", str(tmp_path / "runtime.sqlite3"))
    reset_runtime_store_for_tests()
    monkeypatch.setenv("AIGC_AI_REMOTE_MODEL", "1")

    service = AIService(
        ArkCredentials(endpoint_id="ep-test", api_key="bad-key"),
        audit_path=tmp_path / "audit.jsonl",
    )
    stale_success = {
        "episode_id": "tainai3_ep01",
        "continuation_title": "旧续写",
        "continuation_summary": "旧成功结果",
        "scene_direction": "继续反转",
        "dialogue_lines": ["容遇：看清楚了。"],
        "viewer_hook": "继续吗？",
        "generated_asset": {
            "mediaUrl": "http://test/media/aigc-inserts/tainai3_ep01/continuation.mp4",
            "mediaType": "video/mp4",
            "assetCache": {
                "localUrl": "http://test/media/generated-assets/continuation.mp4",
                "mediaUrl": "http://test/media/generated-assets/continuation.mp4",
                "remoteUrl": "https://cdn.example.test/continuation.mp4",
            },
            "playback": {"mode": "POST_EPISODE_CONTINUATION"},
        },
    }
    get_runtime_store().register_ai_attempt(
        capability="story.continuation",
        scope_key="story.continuation|drama=tainai3|episode=tainai3_ep01",
        prompt_version="story.continuation/v1",
        drama_id="tainai3",
        episode_id="tainai3_ep01",
        node_id="",
        status="ok",
        source="remote_model",
        result=stale_success,
        model_name="old-model",
        cached=False,
        latency_ms=12,
        degrade_reason="",
    )

    class FakeInsertProvider:
        def build_insert(self, *, episode_id, node, episode_summary, request_base_url):
            return {
                "mediaUrl": f"{request_base_url}media/aigc-inserts/{episode_id}/new-degraded.mp4",
                "mediaType": "video/mp4",
                "playback": {"mode": "POST_EPISODE_CONTINUATION"},
            }

    monkeypatch.setattr(ai_service_module, "get_aigc_insert_provider", lambda: FakeInsertProvider())
    monkeypatch.setattr(
        service,
        "_call_chat_completion_best_effort",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("remote failed")),
    )

    result = service.story_continuation(
        {"dramaId": "tainai3", "episodeId": "tainai3_ep01"},
        "http://127.0.0.1:8000/",
    )

    asset = result["result"]["generated_asset"]
    assert result["artifact"]["restored_from_last_success"] is True
    assert asset["mediaUrl"] == "http://127.0.0.1:8000/media/aigc-inserts/tainai3_ep01/new-degraded.mp4"
    assert asset["mediaType"] == "video/mp4"
    assert "assetCache" not in asset
