import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.models import Base
from gateway.config import Settings

_TEST_DB = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        backend_url="http://test-backend",
        jwt_secret="test-secret-exactly-32-bytes-here!",
        jwt_ttl_minutes=15,
        refresh_ttl_days=30,
        database_url=_TEST_DB,
        redis_url="redis://localhost",
        allowed_origins="http://localhost:5173",
        https=False,
    )


@pytest.fixture
async def db_engine():
    engine = create_async_engine(_TEST_DB, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
def fake_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
async def client(settings, db_engine, fake_redis):
    from gateway.main import create_app

    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    app = create_app(settings=settings, db_factory=factory, redis=fake_redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
