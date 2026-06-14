import asyncio
import json

import fakeredis.aioredis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.models import Base, PollerConfig, ProcessorConfig, ProcessorPollerLink


async def _read_control_message(redis):
    pubsub = redis.pubsub()
    await pubsub.subscribe("engine:control")
    return pubsub


async def _next_published_message(pubsub):
    for _ in range(20):
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
        if message is not None:
            return message
        await asyncio.sleep(0.01)
    return None


async def _make_db_factory(*, poller=True, processor=True, link=False):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        poller_row = None
        processor_row = None
        if poller:
            poller_row = PollerConfig(
                module="engine.pollers.corp_ann",
                api_name="corp_ann",
                output_schema="{}",
                enabled=True,
            )
            db.add(poller_row)
        if processor:
            processor_row = ProcessorConfig(
                module="engine.processors.corp_ann",
                api_name="corp_ann",
                input_schema="{}",
                enabled=True,
            )
            db.add(processor_row)
        await db.commit()
        if link and poller_row is not None and processor_row is not None:
            db.add(
                ProcessorPollerLink(
                    processor_id=processor_row.id,
                    poller_id=poller_row.id,
                )
            )
            await db.commit()
    return factory


async def test_get_all_processors_health():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set("processor:corp_ann:status", "running")
    await redis.rpush("queue:corp_ann", json.dumps({"seq_id": "1"}))
    await redis.rpush("queue:corp_ann", json.dumps({"seq_id": "2"}))
    db_factory = await _make_db_factory(processor=True, poller=False)

    from api.app import create_app

    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/processors")

    assert response.status_code == 200
    assert response.json() == [
        {
            "api": "corp_ann",
            "status": "running",
            "queue_size": 2,
            "module": "engine.processors.corp_ann",
            "enabled": True,
            "config": {},
            "pollers": [],
        }
    ]


async def test_get_single_processor_health():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set("processor:corp_ann:status", "paused")
    await redis.rpush("queue:corp_ann", json.dumps({"seq_id": "7"}))
    db_factory = await _make_db_factory(processor=True, poller=False)

    from api.app import create_app

    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/processors/corp_ann")

    assert response.status_code == 200
    assert response.json() == {
        "api": "corp_ann",
        "status": "paused",
        "queue_size": 1,
        "module": "engine.processors.corp_ann",
        "enabled": True,
        "config": {},
        "pollers": [],
    }


async def test_processor_payload_includes_module():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set("processor:corp_ann:status", "running")
    db_factory = await _make_db_factory(processor=True, poller=False)

    from api.app import create_app

    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/processors/corp_ann")
    assert response.status_code == 200
    assert response.json()["module"] == "engine.processors.corp_ann"


async def test_get_unknown_processor_returns_404():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    db_factory = await _make_db_factory(processor=True, poller=False)

    from api.app import create_app

    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/processors/unknown")

    assert response.status_code == 404


async def test_pause_processor_publishes_component_control_message():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    pubsub = await _read_control_message(redis)
    db_factory = await _make_db_factory(processor=True, poller=False)

    from api.app import create_app

    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/admin/processors/corp_ann/pause")

    message = await _next_published_message(pubsub)
    await pubsub.aclose()

    assert response.status_code == 200
    assert response.json() == {"api": "corp_ann", "action": "paused"}
    assert json.loads(message["data"]) == {
        "component": "processor:corp_ann",
        "action": "pause",
    }


async def test_restart_poller_publishes_namespaced_component_control_message():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    pubsub = await _read_control_message(redis)
    db_factory = await _make_db_factory(processor=False, poller=True)

    from api.app import create_app

    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/admin/pollers/corp_ann/restart")

    message = await _next_published_message(pubsub)
    await pubsub.aclose()

    assert response.status_code == 200
    assert response.json() == {"api": "corp_ann", "action": "restarted"}
    assert json.loads(message["data"]) == {
        "component": "poller:corp_ann",
        "action": "restart",
    }


async def test_processor_listing_includes_enabled_config_and_linked_pollers():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set("processor:corp_ann:status", "running")

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        poller_row = PollerConfig(
            module="engine.pollers.corp_ann",
            api_name="corp_ann",
            output_schema="{}",
            enabled=True,
        )
        processor_row = ProcessorConfig(
            module="engine.processors.corp_ann",
            api_name="corp_ann",
            input_schema="{}",
            config=json.dumps({"pool_size": 4}),
            enabled=True,
        )
        db.add_all([poller_row, processor_row])
        await db.commit()
        db.add(
            ProcessorPollerLink(processor_id=processor_row.id, poller_id=poller_row.id)
        )
        await db.commit()

    from api.app import create_app

    app = create_app(redis_override=redis, db_factory_override=factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/processors/corp_ann")

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["config"] == {"pool_size": 4}
    assert body["pollers"] == ["corp_ann"]


async def test_resize_processor_persists_pool_size_and_preserves_config():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        db.add(
            ProcessorConfig(
                module="engine.processors.corp_ann",
                api_name="corp_ann",
                input_schema="{}",
                config=json.dumps({"pool_size": 8, "keep": "me"}),
                enabled=True,
            )
        )
        await db.commit()

    from api.app import create_app

    app = create_app(redis_override=redis, db_factory_override=factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch("/admin/processors/corp_ann", json={"pool_size": 4})
    assert response.status_code == 200
    assert response.json()["config"] == {"pool_size": 4, "keep": "me"}


async def test_resize_processor_rejects_out_of_bounds():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    db_factory = await _make_db_factory(processor=True, poller=False)

    from api.app import create_app

    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        too_low = await client.patch("/admin/processors/corp_ann", json={"pool_size": 0})
        too_high = await client.patch("/admin/processors/corp_ann", json={"pool_size": 65})
    assert too_low.status_code == 422
    assert too_high.status_code == 422


async def test_resize_unknown_processor_returns_404():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    db_factory = await _make_db_factory(processor=True, poller=False)

    from api.app import create_app

    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.patch("/admin/processors/ghost", json={"pool_size": 2})
    assert response.status_code == 404


async def test_links_endpoint_returns_mapping():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    db_factory = await _make_db_factory(poller=True, processor=True, link=True)

    from api.app import create_app

    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/processor-poller-links")

    assert response.status_code == 200
    assert response.json() == [{"processor": "corp_ann", "pollers": ["corp_ann"]}]
