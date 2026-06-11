import secrets
import time
from uuid import uuid4

from fastapi import APIRouter, Header, Response


router = APIRouter(prefix="/auth")
TOKEN_EXPIRE_MS = 7 * 24 * 60 * 60 * 1000
_guest_sessions: dict[str, dict[str, object]] = {}


def _ok(data: dict[str, object]) -> dict[str, object]:
    return {"code": 0, "message": "ok", "data": data}


def _error(response: Response, status_code: int, message: str) -> dict[str, object]:
    response.status_code = status_code
    return {"code": status_code, "message": message, "data": {}}


def _parse_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    token = authorization[len(prefix):].strip()
    return token or None


@router.post("/guest/login")
def guest_login():
    user_id = f"guest_{uuid4().hex}"
    token = secrets.token_urlsafe(32)
    expires_at_ms = int(time.time() * 1000) + TOKEN_EXPIRE_MS
    _guest_sessions[token] = {
        "user_id": user_id,
        "is_guest": True,
        "expires_at_ms": expires_at_ms,
    }
    return _ok(
        {
            "user_id": user_id,
            "token": token,
            "token_expire_ms": TOKEN_EXPIRE_MS,
            "is_guest": True,
        }
    )


@router.get("/session")
def get_session(response: Response, authorization: str | None = Header(default=None)):
    token = _parse_bearer_token(authorization)
    if token is None:
        return _error(response, 401, "missing bearer token")

    session = _guest_sessions.get(token)
    if session is None:
        return _error(response, 401, "invalid token")

    if int(session["expires_at_ms"]) <= int(time.time() * 1000):
        _guest_sessions.pop(token, None)
        return _error(response, 401, "expired token")

    return _ok(
        {
            "user_id": session["user_id"],
            "is_guest": session["is_guest"],
        }
    )
