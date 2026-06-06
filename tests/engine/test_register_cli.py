import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from database.models import Base, PollerConfig, ProcessorConfig, ProcessorPollerLink
from engine.register import run_command


@pytest.fixture
async def db_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def test_register_poller_inserts_disabled_row(db_factory):
    code = await run_command(["poller", "engine.pollers.corp_ann"], db_factory)
    assert code == 0
    async with db_factory() as db:
        row = (await db.execute(select(PollerConfig))).scalar_one()
        assert row.api_name == "corp_ann"
        assert row.enabled is False
        assert "seq_id" in row.output_schema


async def test_register_processor_creates_link_after_validation(db_factory):
    await run_command(["poller", "engine.pollers.corp_ann"], db_factory)
    code = await run_command(
        ["processor", "engine.processors.corp_ann", "--poller", "corp_ann"],
        db_factory,
    )
    assert code == 0
    async with db_factory() as db:
        proc = (await db.execute(select(ProcessorConfig))).scalar_one()
        link = (await db.execute(select(ProcessorPollerLink))).scalar_one()
        assert proc.api_name == "corp_ann"
        assert link.processor_id == proc.id


async def test_register_processor_against_unregistered_poller_fails(db_factory):
    code = await run_command(
        ["processor", "engine.processors.corp_ann", "--poller", "corp_ann"],
        db_factory,
    )
    assert code != 0
    async with db_factory() as db:
        assert (await db.execute(select(ProcessorConfig))).first() is None


async def test_register_processor_incompatible_schema_writes_nothing(db_factory):
    async with db_factory() as db:
        db.add(
            PollerConfig(
                module="engine.pollers.corp_ann",
                api_name="corp_ann",
                output_schema='{"properties": {"unrelated": {"type": "string"}}}',
                enabled=False,
            )
        )
        await db.commit()

    code = await run_command(
        ["processor", "engine.processors.corp_ann", "--poller", "corp_ann"],
        db_factory,
    )
    assert code != 0
    async with db_factory() as db:
        assert (await db.execute(select(ProcessorConfig))).first() is None
        assert (await db.execute(select(ProcessorPollerLink))).first() is None


async def test_enable_and_disable_flip_flag(db_factory):
    await run_command(["poller", "engine.pollers.corp_ann"], db_factory)
    await run_command(["enable", "poller", "corp_ann"], db_factory)
    async with db_factory() as db:
        assert (await db.execute(select(PollerConfig))).scalar_one().enabled is True
    await run_command(["disable", "poller", "corp_ann"], db_factory)
    async with db_factory() as db:
        assert (await db.execute(select(PollerConfig))).scalar_one().enabled is False


async def test_reregister_updates_schema_preserves_enabled(db_factory):
    await run_command(["poller", "engine.pollers.corp_ann"], db_factory)
    await run_command(["enable", "poller", "corp_ann"], db_factory)
    await run_command(["poller", "engine.pollers.corp_ann"], db_factory)
    async with db_factory() as db:
        assert (await db.execute(select(PollerConfig))).scalar_one().enabled is True


async def test_register_poller_seeds_default_config(db_factory):
    await run_command(["poller", "engine.pollers.corp_ann"], db_factory)
    async with db_factory() as db:
        row = (await db.execute(select(PollerConfig))).scalar_one()
        assert json.loads(row.config) == {"base_interval": 5.0}


async def test_register_processor_seeds_default_config(db_factory):
    await run_command(["poller", "engine.pollers.corp_ann"], db_factory)
    await run_command(
        ["processor", "engine.processors.corp_ann", "--poller", "corp_ann"],
        db_factory,
    )
    async with db_factory() as db:
        row = (await db.execute(select(ProcessorConfig))).scalar_one()
        assert json.loads(row.config) == {"pool_size": 8}


async def test_reregister_preserves_operator_config_override(db_factory):
    await run_command(["poller", "engine.pollers.corp_ann"], db_factory)
    # Operator customises the stored config.
    async with db_factory() as db:
        row = (await db.execute(select(PollerConfig))).scalar_one()
        row.config = json.dumps({"base_interval": 99.0})
        await db.commit()

    # Re-registering must not clobber the operator's override.
    await run_command(["poller", "engine.pollers.corp_ann"], db_factory)
    async with db_factory() as db:
        row = (await db.execute(select(PollerConfig))).scalar_one()
        assert json.loads(row.config) == {"base_interval": 99.0}
