import fakeredis.aioredis
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.models import Base, User
from database.redis import watch_key


async def _setup():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        user = User()
        s.add(user)
        await s.commit()
        user_id = user.id
    return factory, user_id


async def test_subscribe_adds_to_watchlist_and_redis():
    db_factory, user_id = await _setup()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    from api.app import create_app
    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/watchlist", json={"user_id": user_id, "symbol": "INFY"}
        )
    assert response.status_code == 200
    members = await redis.smembers(watch_key("INFY"))
    assert str(user_id) in members


async def test_unsubscribe_removes_from_watchlist_and_redis():
    db_factory, user_id = await _setup()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    from api.app import create_app
    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/watchlist", json={"user_id": user_id, "symbol": "INFY"})
        response = await client.delete(
            "/api/v1/watchlist", params={"user_id": user_id, "symbol": "INFY"}
        )
    assert response.status_code == 200
    members = await redis.smembers(watch_key("INFY"))
    assert str(user_id) not in members


async def test_subscribe_duplicate_is_idempotent():
    db_factory, user_id = await _setup()
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

    from api.app import create_app
    app = create_app(redis_override=redis, db_factory_override=db_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/watchlist", json={"user_id": user_id, "symbol": "INFY"})
        response = await client.post("/api/v1/watchlist", json={"user_id": user_id, "symbol": "INFY"})
    assert response.status_code == 200
