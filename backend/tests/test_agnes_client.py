from pathlib import Path


def test_agnes_credentials_prefers_environment_and_redacts_key(monkeypatch, tmp_path):
    from backend.app.agnes_client import load_agnes_credentials

    config_path = tmp_path / "agnes.txt"
    config_path.write_text("file-secret-key", encoding="utf-8")
    monkeypatch.setenv("AGNES_API_KEY", "env-secret-key")
    monkeypatch.setenv("AGNES_BASE_URL", "https://example.test")
    monkeypatch.setenv("AGNES_IMAGE_MODEL", "custom-image")
    monkeypatch.setenv("AGNES_VIDEO_MODEL", "custom-video")

    credentials = load_agnes_credentials(config_path=config_path)

    assert credentials.api_key == "env-secret-key"
    assert credentials.source == "env"
    assert credentials.base_url == "https://example.test"
    assert credentials.image_model == "custom-image"
    assert credentials.video_model == "custom-video"
    assert "env-secret-key" not in str(credentials.public_status())
    assert credentials.public_status()["configured"] is True


def test_agnes_credentials_reads_local_file_without_leaking_key(monkeypatch, tmp_path):
    from backend.app.agnes_client import load_agnes_credentials

    config_path = tmp_path / "agnes.txt"
    config_path.write_text("file-secret-key\n", encoding="utf-8")
    monkeypatch.delenv("AGNES_API_KEY", raising=False)

    credentials = load_agnes_credentials(config_path=config_path)

    assert credentials.api_key == "file-secret-key"
    assert credentials.source == "agnes.txt"
    assert credentials.public_status()["source"] == "agnes.txt"
    assert "file-secret-key" not in str(credentials.public_status())


def test_agnes_credentials_uses_current_default_models(monkeypatch, tmp_path):
    from backend.app.agnes_client import load_agnes_credentials

    config_path = tmp_path / "agnes.txt"
    config_path.write_text("file-secret-key\n", encoding="utf-8")
    monkeypatch.delenv("AGNES_API_KEY", raising=False)
    monkeypatch.delenv("AGNES_IMAGE_MODEL", raising=False)
    monkeypatch.delenv("AGNES_VIDEO_MODEL", raising=False)

    credentials = load_agnes_credentials(config_path=config_path)

    assert credentials.image_model == "agnes-image-2.0-flash"
    assert credentials.video_model == "agnes-video-v2.0"


def test_gitignore_contains_agnes_key_file():
    assert "agnes.txt" in Path(".gitignore").read_text(encoding="utf-8")


def test_agnes_client_generates_image_with_unified_result():
    from backend.app.agnes_client import AgnesClient, AgnesCredentials

    calls = []

    def fake_request(method, path, body=None, timeout_seconds=45):
        calls.append((method, path, body, timeout_seconds))
        return {"data": [{"url": "https://cdn.example.test/checkin.png"}]}

    client = AgnesClient(
        AgnesCredentials(
            api_key="secret-key",
            base_url="https://apihub.example.test",
            image_model="agnes-image-2.0-flash",
            video_model="agnes-video-v2.0",
            source="env",
        ),
        request_json=fake_request,
    )

    result = client.generate_image("生成短剧打卡图", size="1024x1024", n=1)

    assert result["status"] == "ok"
    assert result["provider"] == "agnes"
    assert result["model_name"] == "agnes-image-2.0-flash"
    assert result["media_url"] == "https://cdn.example.test/checkin.png"
    assert calls[0][0] == "POST"
    assert calls[0][1] == "/v1/images/generations"
    assert calls[0][2]["model"] == "agnes-image-2.0-flash"
    assert "secret-key" not in str(result)


def test_agnes_client_converts_request_errors_to_degraded_result():
    from backend.app.agnes_client import AgnesClient, AgnesCredentials

    def fake_request(method, path, body=None, timeout_seconds=45):
        raise RuntimeError("HTTP 500 upstream failed")

    client = AgnesClient(
        AgnesCredentials(
            api_key="secret-key",
            base_url="https://apihub.example.test",
            image_model="agnes-image-2.0-flash",
            video_model="agnes-video-v2.0",
            source="env",
        ),
        request_json=fake_request,
    )

    result = client.generate_image("生成短剧打卡图")

    assert result["status"] == "degraded"
    assert result["media_url"] == ""
    assert result["degrade_reason"] == "HTTP 500 upstream failed"
    assert "secret-key" not in str(result)


def test_agnes_client_creates_and_polls_video_task():
    from backend.app.agnes_client import AgnesClient, AgnesCredentials

    responses = [
        {"id": "task-1", "status": "queued"},
        {"id": "task-1", "status": "processing"},
        {"id": "task-1", "status": "completed", "data": [{"url": "https://cdn.example.test/video.mp4"}]},
    ]

    def fake_request(method, path, body=None, timeout_seconds=45):
        if method == "POST":
            assert path == "/v1/videos"
            assert body["model"] == "agnes-video-v2.0"
            assert body["prompt"] == "生成三秒续写视频"
        return responses.pop(0)

    client = AgnesClient(
        AgnesCredentials(
            api_key="secret-key",
            base_url="https://apihub.example.test",
            image_model="agnes-image-2.0-flash",
            video_model="agnes-video-v2.0",
            source="env",
        ),
        request_json=fake_request,
        sleep=lambda seconds: None,
    )

    created = client.create_video_task("生成三秒续写视频")
    polled = client.poll_video_task(created["task_id"], timeout_seconds=3, interval_seconds=1)

    assert created["status"] == "ok"
    assert created["task_id"] == "task-1"
    assert polled["status"] == "ok"
    assert polled["media_url"] == "https://cdn.example.test/video.mp4"


def test_agnes_client_extracts_v2_video_url_from_completed_task():
    from backend.app.agnes_client import AgnesClient, AgnesCredentials

    def fake_request(method, path, body=None, timeout_seconds=45):
        return {
            "id": "task-v2",
            "status": "completed",
            "model": "agnes-video-v2.0",
            "remixed_from_video_id": "https://cdn.example.test/v2-video.mp4",
        }

    client = AgnesClient(
        AgnesCredentials(
            api_key="secret-key",
            base_url="https://apihub.example.test",
            image_model="agnes-image-2.0-flash",
            video_model="agnes-video-v2.0",
            source="env",
        ),
        request_json=fake_request,
        sleep=lambda seconds: None,
    )

    polled = client.poll_video_task("task-v2", timeout_seconds=1, interval_seconds=1)

    assert polled["status"] == "ok"
    assert polled["media_url"] == "https://cdn.example.test/v2-video.mp4"
