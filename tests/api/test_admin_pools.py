import fakeredis.aioredis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.models import Base


async def _make_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def test_get_pool_size():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    db_factory = await _make_db()
    from api.app import create_app
    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/pools/corp_ann")
    assert response.status_code == 200
    assert "size" in response.json()


async def test_update_pool_size():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    db_factory = await _make_db()
    from api.app import create_app
    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch("/admin/pools/corp_ann", json={"size": 12})
    assert response.status_code == 200
    assert response.json()["size"] == 12
