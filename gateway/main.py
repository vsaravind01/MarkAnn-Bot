from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database.session import AsyncSessionLocal
from gateway.admin.router import router as admin_router
from gateway.auth.router import router as auth_router
from gateway.config import Settings, get_settings
from gateway.proxy.client import close_client
from gateway.proxy.router import router as proxy_router
from gateway.rate_limit.middleware import RateLimitMiddleware


def create_app(
    settings: Settings | None = None,
    db_factory=None,
    redis=None,
) -> FastAPI:
    cfg = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await close_client()
        if hasattr(app.state.redis, "aclose"):
            await app.state.redis.aclose()

    app = FastAPI(title="MarkAnn Gateway", lifespan=lifespan)
    app.state.settings = cfg
    app.state.db_factory = db_factory or AsyncSessionLocal
    app.state.redis = redis or aioredis.from_url(cfg.redis_url)

    # Starlette prepends each middleware, so the last add_middleware call runs
    # outermost. CORS must be outermost so 429 responses carry CORS headers.
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(admin_router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    app.include_router(proxy_router)

    return app


app = create_app()
