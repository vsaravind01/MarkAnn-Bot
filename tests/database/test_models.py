import pytest
from sqlalchemy import select
from database.models import User, UserWatchlist, UserChannel, EngineConfig, Announcement


async def test_user_create(async_db_session):
    user = User()
    async_db_session.add(user)
    await async_db_session.commit()
    result = await async_db_session.execute(select(User))
    assert result.scalar_one().id == 1


async def test_user_watchlist_composite_pk(async_db_session):
    user = User()
    async_db_session.add(user)
    await async_db_session.flush()
    wl = UserWatchlist(user_id=user.id, symbol="INFY")
    async_db_session.add(wl)
    await async_db_session.commit()
    result = await async_db_session.execute(select(UserWatchlist))
    row = result.scalar_one()
    assert row.user_id == user.id
    assert row.symbol == "INFY"


async def test_engine_config_upsert(async_db_session):
    cfg = EngineConfig(key="pool_size:corp_ann", value="8")
    async_db_session.add(cfg)
    await async_db_session.commit()
    result = await async_db_session.execute(
        select(EngineConfig).where(EngineConfig.key == "pool_size:corp_ann")
    )
    assert result.scalar_one().value == "8"


async def test_announcement_fields(async_db_session):
    from datetime import datetime, timezone
    ann = Announcement(
        seq_id="12345",
        symbol="INFY",
        company="Infosys Limited",
        category="financial_results",
        announcement_text="Quarterly results...",
        summary="Strong Q4 growth.",
        attachment_url="https://nsearchives.nseindia.com/test.pdf",
        announced_at=datetime(2026, 5, 28, 23, 55, 28, tzinfo=timezone.utc),
    )
    async_db_session.add(ann)
    await async_db_session.commit()
    result = await async_db_session.execute(select(Announcement))
    row = result.scalar_one()
    assert row.seq_id == "12345"
    assert row.symbol == "INFY"
