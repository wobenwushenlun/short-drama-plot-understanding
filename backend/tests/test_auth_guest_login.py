import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_guest_login_ok():
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/auth/guest/login", json={})

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["message"] == "ok"
    assert body["data"]["is_guest"] is True
    assert isinstance(body["data"]["token"], str) and body["data"]["token"]
    assert isinstance(body["data"]["user_id"], str) and body["data"]["user_id"]
    assert isinstance(body["data"]["token_expire_ms"], int) and body["data"]["token_expire_ms"] > 0


@pytest.mark.asyncio
async def test_guest_session_verify_ok():
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        login_resp = await ac.post("/auth/guest/login", json={})
        token = login_resp.json()["data"]["token"]
        resp = await ac.get("/auth/session", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["message"] == "ok"
    assert body["data"]["is_guest"] is True
    assert isinstance(body["data"]["user_id"], str) and body["data"]["user_id"]


@pytest.mark.asyncio
async def test_guest_session_rejects_invalid_token():
    from backend.app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/auth/session", headers={"Authorization": "Bearer invalid-token"})

    assert resp.status_code == 401
    assert resp.json() == {"code": 401, "message": "invalid token", "data": {}}
