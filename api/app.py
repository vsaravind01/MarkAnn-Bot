from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.admin.events import router as events_router
from api.admin.pollers import router as pollers_router
from api.admin.processors import router as processors_router
from api.v1.watchlist import router as watchlist_router
from database.redis import get_redis_client
from database.session import AsyncSessionLocal


def create_app(
    redis_override=None,
    db_factory_override=None,
    supervisor_override=None,
) -> FastAPI:
    redis_client = redis_override or get_redis_client()
    db_factory = db_factory_override or AsyncSessionLocal

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        if hasattr(app.state.redis, "aclose"):
            await app.state.redis.aclose()

    app = FastAPI(title="MarkAnn API", lifespan=lifespan)
    app.state.redis = redis_client
    app.state.db_factory = db_factory
    app.state.supervisor = supervisor_override

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(events_router)
    app.include_router(pollers_router)
    app.include_router(processors_router)
    app.include_router(watchlist_router)
    return app


app = create_app()
