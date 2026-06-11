import pytest
from httpx import ASGITransport, AsyncClient


def test_generated_asset_store_caches_remote_media_with_public_url(tmp_path):
    from backend.app.generated_asset_store import cache_remote_generated_asset, get_generated_asset_path

    captured = {}

    def fake_fetcher(url: str, timeout_seconds: int) -> bytes:
        captured["url"] = url
        captured["timeout_seconds"] = timeout_seconds
        return b"\x89PNG\r\nfake-image"

    result = cache_remote_generated_asset(
        remote_url="https://cdn.example.test/checkin.png",
        media_type="image/png",
        request_base_url="http://test/",
        asset_hint="checkin_card",
        asset_root=tmp_path,
        fetcher=fake_fetcher,
    )

    assert result["cacheStatus"] == "cached"
    assert result["remoteUrl"] == "https://cdn.example.test/checkin.png"
    assert result["localUrl"].startswith("http://test/media/generated-assets/")
    assert result["mediaUrl"] == result["localUrl"]
    assert result["contentType"] == "image/png"
    assert result["byteSize"] == len(b"\x89PNG\r\nfake-image")
    assert captured["url"] == "https://cdn.example.test/checkin.png"
    assert get_generated_asset_path(result["assetId"], asset_root=tmp_path).read_bytes() == b"\x89PNG\r\nfake-image"


@pytest.mark.asyncio
async def test_generated_asset_media_route_serves_cached_file(monkeypatch, tmp_path):
    import backend.app.generated_asset_store as generated_asset_store
    from backend.app.generated_asset_store import cache_remote_generated_asset
    from backend.app.main import app

    monkeypatch.setattr(generated_asset_store, "DEFAULT_GENERATED_ASSET_ROOT", tmp_path)
    result = cache_remote_generated_asset(
        remote_url="https://cdn.example.test/continuation.mp4",
        media_type="video/mp4",
        request_base_url="http://test/",
        asset_hint="story_continuation",
        asset_root=tmp_path,
        fetcher=lambda url, timeout_seconds: b"fake-video",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(f"/media/generated-assets/{result['assetId']}")

    assert response.status_code == 200
    assert response.content == b"fake-video"
    assert response.headers["content-type"].startswith("video/mp4")
