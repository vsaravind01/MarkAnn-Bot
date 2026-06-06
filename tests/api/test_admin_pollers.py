import json

import fakeredis.aioredis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.models import Base, PollerConfig


async def _make_db_factory(*, api_name="corp_ann", config="{}", enabled=True):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        db.add(
            PollerConfig(
                module=f"engine.pollers.{api_name}",
                api_name=api_name,
                output_schema="{}",
                config=config,
                enabled=enabled,
            )
        )
        await db.commit()
    return factory


async def test_poller_listing_includes_enabled_and_config():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set("poller:corp_ann:status", "running")
    db_factory = await _make_db_factory(
        config=json.dumps({"base_interval": 5.0}), enabled=False
    )

    from api.app import create_app

    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/pollers/corp_ann")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["config"] == {"base_interval": 5.0}


async def test_get_all_pollers_health():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set("poller:corp_ann:status", "running")
    await redis.set("poller:corp_ann:error_count", "0")
    await redis.set("poller:corp_ann:interval", "5.0")
    db_factory = await _make_db_factory()

    from api.app import create_app

    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/pollers")
    assert response.status_code == 200
    data = response.json()
    assert any(p["api"] == "corp_ann" for p in data)


async def test_get_single_poller_health():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set("poller:corp_ann:status", "backing_off")
    db_factory = await _make_db_factory()

    from api.app import create_app

    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/pollers/corp_ann")
    assert response.status_code == 200
    assert response.json()["status"] == "backing_off"


async def test_get_unknown_poller_returns_404():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    db_factory = await _make_db_factory()

    from api.app import create_app

    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/pollers/ghost")
    assert response.status_code == 404


async def test_list_pollers_reads_registered_api_from_db():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set("poller:custom_feed:status", "running")
    db_factory = await _make_db_factory(api_name="custom_feed")

    from api.app import create_app

    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/pollers")
    assert response.status_code == 200
    assert response.json()[0]["api"] == "custom_feed"
