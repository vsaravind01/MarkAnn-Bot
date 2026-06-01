import asyncio
import json

import fakeredis.aioredis
from httpx import ASGITransport, AsyncClient


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


async def test_get_all_processors_health():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set("processor:corp_ann:status", "running")
    await redis.rpush("queue:corp_ann", json.dumps({"seq_id": "1"}))
    await redis.rpush("queue:corp_ann", json.dumps({"seq_id": "2"}))

    from api.app import create_app

    app = create_app(redis_override=redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/processors")

    assert response.status_code == 200
    assert response.json() == [{"api": "corp_ann", "status": "running", "queue_size": 2}]


async def test_get_single_processor_health():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set("processor:corp_ann:status", "paused")
    await redis.rpush("queue:corp_ann", json.dumps({"seq_id": "7"}))

    from api.app import create_app

    app = create_app(redis_override=redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/processors/corp_ann")

    assert response.status_code == 200
    assert response.json() == {"api": "corp_ann", "status": "paused", "queue_size": 1}


async def test_get_unknown_processor_returns_404():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    from api.app import create_app

    app = create_app(redis_override=redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/processors/unknown")

    assert response.status_code == 404


async def test_pause_processor_publishes_component_control_message():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    pubsub = await _read_control_message(redis)

    from api.app import create_app

    app = create_app(redis_override=redis)
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

    from api.app import create_app

    app = create_app(redis_override=redis)
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
