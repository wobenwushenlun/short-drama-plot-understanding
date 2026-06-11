import json
from pathlib import Path


def test_template_aigc_insert_provider_builds_asset_from_understanding(tmp_path, monkeypatch):
    from backend.app.aigc_insert_service import TemplateAigcInsertProvider

    understanding_dir = tmp_path / "understanding" / "tainai3_ep01"
    understanding_dir.mkdir(parents=True)
    (understanding_dir / "understanding.json").write_text(
        """
        {
          "envelope": {
            "result": {
              "summary": "主角完成反击",
              "audio_text": {
                "corrected_transcript": "容遇终于开口了，这次反击很爽。"
              },
              "screen_text_cues": [
                {"text": "科学院首席院士 容遇"}
              ]
            }
          }
        }
        """,
        encoding="utf-8",
    )

    def fake_render(self, output_path: Path, script: dict):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake mp4")

    monkeypatch.setattr(TemplateAigcInsertProvider, "_render_mp4", fake_render)
    provider = TemplateAigcInsertProvider(
        asset_root=tmp_path / "assets",
        understanding_root=tmp_path / "understanding",
    )
    result = provider.build_insert(
        episode_id="tainai3_ep01",
        node={"id": "n_001", "subtitle": "剧情提速", "trigger": {"timeMs": 118_000}},
        episode_summary="主角开始反击。",
        request_base_url="http://test/",
    )

    assert result["provider"]["name"] == "template_ffmpeg"
    assert result["mediaUrl"].endswith("/media/aigc-inserts/tainai3_ep01/n_001.mp4")
    assert result["mediaType"] == "video/mp4"
    assert result["title"] == "反击加速包"
    assert "容遇终于开口" in result["highEnergyLine"]
    assert result["playback"]["mode"] == "REPLACE_MAIN"
    assert result["playback"]["segmentId"] == "n_001"
    assert result["playback"]["startMs"] == 0
    assert result["playback"]["endMs"] == 3000
    assert result["playback"]["returnSeekMs"] == 118_000
    assert (tmp_path / "assets" / "tainai3_ep01" / "n_001.mp4").exists()


def test_template_aigc_insert_provider_uses_continuation_script_override(tmp_path, monkeypatch):
    from backend.app.aigc_insert_service import TemplateAigcInsertProvider

    captured_script: dict = {}

    def fake_render(self, output_path: Path, script: dict):
        captured_script.update(script)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake continuation mp4")

    monkeypatch.setattr(TemplateAigcInsertProvider, "_render_mp4", fake_render)
    provider = TemplateAigcInsertProvider(
        asset_root=tmp_path / "assets",
        understanding_root=tmp_path / "understanding",
    )
    result = provider.build_insert(
        episode_id="tainai3_ep01",
        node={
            "id": "continuation_001",
            "generatedTitle": "下一幕预演",
            "generatedHighEnergyLine": "容遇：现在，该说清真相了。",
            "generatedSubtitle": "门厅的灯忽然熄灭",
            "badgeText": "AI 生成 · 下一幕预演",
            "progressText": "续写展开",
            "playbackMode": "POST_EPISODE_CONTINUATION",
            "trigger": {"timeMs": 245_840},
        },
        episode_summary="容遇准备公开证据。",
        request_base_url="http://test/",
    )

    assert captured_script["title"] == "下一幕预演"
    assert captured_script["high_energy_line"] == "容遇：现在，该说清真相了。"
    assert captured_script["badge_text"] == "AI 生成 · 下一幕预演"
    assert captured_script["source_evidence"][0] == "Doubao 续写台词"
    assert result["playback"]["mode"] == "POST_EPISODE_CONTINUATION"


def test_agnes_aigc_insert_provider_caches_remote_video_url(monkeypatch):
    import backend.app.aigc_insert_service as aigc_insert_service
    from backend.app.aigc_insert_service import AgnesAigcInsertProvider

    captured_prompt = {}
    captured_request = {}

    def fake_cache_remote_generated_asset(**kwargs):
        assert kwargs["remote_url"] == "https://cdn.example.test/continuation.mp4"
        assert kwargs["media_type"] == "video/mp4"
        return {
            "assetId": "story_continuation_001.mp4",
            "remoteUrl": kwargs["remote_url"],
            "localUrl": "http://test/media/generated-assets/story_continuation_001.mp4",
            "mediaUrl": "http://test/media/generated-assets/story_continuation_001.mp4",
            "contentType": "video/mp4",
            "cacheStatus": "cached",
            "byteSize": 10,
        }

    monkeypatch.setattr(
        aigc_insert_service,
        "cache_remote_generated_asset",
        fake_cache_remote_generated_asset,
        raising=False,
    )

    class FakeAgnesClient:
        credentials = type("Credentials", (), {"video_model": "agnes-video-v2.0"})()

        def create_video_task(self, prompt, image_urls=None, keyframes=None):
            captured_prompt["text"] = prompt
            captured_request["image_urls"] = image_urls or []
            captured_request["keyframes"] = keyframes or []
            return {"status": "ok", "task_id": "task-1", "degrade_reason": ""}

        def poll_video_task(self, task_id):
            assert task_id == "task-1"
            return {
                "status": "ok",
                "task_id": "task-1",
                "media_url": "https://cdn.example.test/continuation.mp4",
                "latency_ms": 1200,
                "degrade_reason": "",
            }

    provider = AgnesAigcInsertProvider(agnes_client=FakeAgnesClient())
    result = provider.build_insert(
        episode_id="tainai3_ep01",
        node={
            "id": "continuation_001",
            "generatedTitle": "下一幕预演",
            "generatedHighEnergyLine": "容遇：现在，该说清真相了。",
            "generatedSubtitle": "门厅灯光骤暗，证据被推到桌面中央",
            "playbackMode": "POST_EPISODE_CONTINUATION",
            "trigger": {"timeMs": 245_840},
        },
        episode_summary="容遇准备公开证据。",
        request_base_url="http://test/",
    )

    assert result["provider"]["name"] == "agnes-video"
    assert "agnes-video-v2.0" in result["provider"]["compatibleProviders"]
    assert result["status"] == "ok"
    assert result["mediaUrl"] == "http://test/media/generated-assets/story_continuation_001.mp4"
    assert result["assetCache"]["remoteUrl"] == "https://cdn.example.test/continuation.mp4"
    assert result["assetCache"]["cacheStatus"] == "cached"
    assert result["mediaType"] == "video/mp4"
    assert result["playback"]["mode"] == "POST_EPISODE_CONTINUATION"
    assert "容遇准备公开证据" in captured_prompt["text"]
    assert "容遇：现在，该说清真相了。" in captured_prompt["text"]


def test_agnes_aigc_insert_provider_passes_story_summary_and_reference_frames(tmp_path):
    from backend.app.aigc_insert_service import AgnesAigcInsertProvider

    episode_id = "tainai3_ep01"
    frame_root = tmp_path / "video_understanding_frames"
    frame_dir = frame_root / episode_id
    frame_dir.mkdir(parents=True)
    frame_path = frame_dir / "frame_001.jpg"
    frame_path.write_bytes(b"fake-image")
    understanding_root = tmp_path / "video_understanding_results"
    episode_root = understanding_root / episode_id
    episode_root.mkdir(parents=True)
    (episode_root / "understanding.json").write_text(
        json.dumps(
            {
                "result": {
                    "summary": "容遇以纪家太奶奶身份登场，压住家族质疑。",
                    "characters": [{"name": "容遇", "traits": ["气场强", "穿越者"]}],
                },
                "assets": {
                    "frames": [
                        {
                            "timeMs": 118000,
                            "path": str(frame_path),
                            "availableForVision": True,
                            "samplingReason": "容遇正面高光截图",
                        }
                    ]
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    captured = {}

    class FakeAgnesClient:
        credentials = type("Credentials", (), {"video_model": "agnes-video-v2.0"})()

        def create_video_task(self, prompt, image_urls=None, keyframes=None):
            captured["prompt"] = prompt
            captured["image_urls"] = image_urls or []
            captured["keyframes"] = keyframes or []
            return {"status": "ok", "task_id": "task-1", "degrade_reason": ""}

        def poll_video_task(self, task_id):
            return {
                "status": "ok",
                "task_id": task_id,
                "media_url": "https://cdn.example.test/continuation.mp4",
                "latency_ms": 1200,
            }

    provider = AgnesAigcInsertProvider(
        agnes_client=FakeAgnesClient(),
        understanding_root=understanding_root,
        frame_root=frame_root,
    )
    provider.build_insert(
        episode_id=episode_id,
        node={
            "id": "continuation_001",
            "generatedTitle": "下一幕预演",
            "generatedHighEnergyLine": "容遇：现在，该说清真相了。",
            "generatedSubtitle": "门厅灯光骤暗，证据被推到桌面中央",
            "trigger": {"timeMs": 120000},
        },
        episode_summary="容遇准备公开证据。",
        request_base_url="https://public.example.test/",
    )

    assert "容遇准备公开证据" in captured["prompt"]
    assert "容遇以纪家太奶奶身份登场" in captured["prompt"]
    assert "人物一致性" in captured["prompt"]
    assert captured["image_urls"] == [
        "https://public.example.test/media/video-understanding-frames/tainai3_ep01/frame_001.jpg"
    ]
    assert captured["keyframes"][0]["image_url"] == captured["image_urls"][0]
    assert captured["keyframes"][0]["time_ms"] == 118000


def test_agnes_aigc_insert_provider_degrades_when_reference_frame_url_is_local(tmp_path):
    from backend.app.aigc_insert_service import AgnesAigcInsertProvider

    episode_id = "tainai3_ep01"
    frame_root = tmp_path / "video_understanding_frames"
    frame_dir = frame_root / episode_id
    frame_dir.mkdir(parents=True)
    frame_path = frame_dir / "frame_001.jpg"
    frame_path.write_bytes(b"fake-image")
    understanding_root = tmp_path / "video_understanding_results"
    episode_root = understanding_root / episode_id
    episode_root.mkdir(parents=True)
    (episode_root / "understanding.json").write_text(
        json.dumps(
            {
                "result": {"summary": "容遇准备公开证据。"},
                "assets": {
                    "frames": [
                        {
                            "timeMs": 118000,
                            "path": str(frame_path),
                            "availableForVision": True,
                            "samplingReason": "容遇正面高光截图",
                        }
                    ]
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class FakeAgnesClient:
        credentials = type("Credentials", (), {"video_model": "agnes-video-v2.0"})()

        def create_video_task(self, prompt, image_urls=None, keyframes=None):
            raise AssertionError("local reference frame URL must not be sent to Agnes")

    class FakeFallbackProvider:
        def build_insert(self, **kwargs):
            return {
                "provider": {"name": "template_ffmpeg", "compatibleProviders": ["template_ffmpeg"]},
                "status": "ok",
                "mediaUrl": "http://127.0.0.1:8000/media/aigc-inserts/tainai3_ep01/fallback.mp4",
                "mediaType": "video/mp4",
                "playback": {"mode": "POST_EPISODE_CONTINUATION"},
            }

    provider = AgnesAigcInsertProvider(
        agnes_client=FakeAgnesClient(),
        fallback_provider=FakeFallbackProvider(),
        understanding_root=understanding_root,
        frame_root=frame_root,
    )
    result = provider.build_insert(
        episode_id=episode_id,
        node={"id": "continuation_001", "trigger": {"timeMs": 120000}},
        episode_summary="容遇准备公开证据。",
        request_base_url="http://127.0.0.1:8000/",
    )

    assert result["provider"]["name"] == "template_ffmpeg"
    assert result["provider"]["attemptedProvider"] == "agnes-video"
    assert result["provider"]["degradeReason"] == "reference_frame_url_not_public"
    assert result["remoteAttempt"]["referenceStatus"] == "blocked_local_url"


def test_agnes_aigc_insert_provider_falls_back_to_template_when_remote_degrades():
    from backend.app.aigc_insert_service import AgnesAigcInsertProvider

    class FakeAgnesClient:
        credentials = type("Credentials", (), {"video_model": "agnes-video-v2.0"})()

        def create_video_task(self, prompt, image_urls=None, keyframes=None):
            return {"status": "degraded", "task_id": "", "degrade_reason": "timeout"}

    class FakeFallbackProvider:
        def build_insert(self, **kwargs):
            return {
                "provider": {"name": "template_ffmpeg", "compatibleProviders": ["template_ffmpeg"]},
                "status": "ok",
                "mediaUrl": "http://test/media/aigc-inserts/tainai3_ep01/fallback.mp4",
                "mediaType": "video/mp4",
                "playback": {"mode": "POST_EPISODE_CONTINUATION"},
            }

    provider = AgnesAigcInsertProvider(
        agnes_client=FakeAgnesClient(),
        fallback_provider=FakeFallbackProvider(),
    )
    result = provider.build_insert(
        episode_id="tainai3_ep01",
        node={"id": "continuation_001", "trigger": {"timeMs": 245_840}},
        episode_summary="容遇准备公开证据。",
        request_base_url="http://test/",
    )

    assert result["provider"]["name"] == "template_ffmpeg"
    assert result["provider"]["attemptedProvider"] == "agnes-video"
    assert result["provider"]["degradeReason"] == "timeout"
    assert result["status"] == "ok"
