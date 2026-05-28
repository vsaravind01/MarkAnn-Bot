import fakeredis.aioredis
from httpx import ASGITransport, AsyncClient


async def test_get_all_pollers_health():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set("poller:corp_ann:status", "running")
    await redis.set("poller:corp_ann:error_count", "0")
    await redis.set("poller:corp_ann:interval", "5.0")

    from api.app import create_app
    app = create_app(redis_override=redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/pollers")
    assert response.status_code == 200
    data = response.json()
    assert any(p["api"] == "corp_ann" for p in data)


async def test_get_single_poller_health():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await redis.set("poller:corp_ann:status", "backing_off")

    from api.app import create_app
    app = create_app(redis_override=redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/admin/pollers/corp_ann")
    assert response.status_code == 200
    assert response.json()["status"] == "backing_off"
