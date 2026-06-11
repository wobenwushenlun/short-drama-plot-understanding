from contextlib import asynccontextmanager
import asyncio
import os

from fastapi import FastAPI

from backend.app.api.router import api_router
from backend.app.content_catalog import warm_video_understanding_cache


def _warmup_base_url() -> str:
    return (os.environ.get("AIGC_PUBLIC_BASE_URL") or "http://127.0.0.1:8000").strip() or "http://127.0.0.1:8000"


async def _warm_video_understanding_cache() -> None:
    try:
        await asyncio.to_thread(warm_video_understanding_cache, _warmup_base_url())
    except Exception:
        return


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(_warm_video_understanding_cache())
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(api_router)
