from fastapi import APIRouter

from backend.app.api.routes.content import router as content_router
from backend.app.api.routes.ai import router as ai_router
from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.stability import router as stability_router
from backend.app.api.routes.video_ai import router as video_ai_router


api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(content_router, tags=["content"])
api_router.include_router(ai_router, tags=["ai"])
api_router.include_router(video_ai_router, tags=["ai"])
api_router.include_router(stability_router, tags=["stability"])
