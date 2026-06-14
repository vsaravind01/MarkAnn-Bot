from unittest.mock import AsyncMock

from database.models import PollerConfig, ProcessorConfig, ProcessorPollerLink
from engine.main import build_components
from engine.supervisor import Supervisor

_CORP_ANN_SCHEMA = (
    '{"properties": {'
    '"seq_id": {"type": "string"}, '
    '"symbol": {"type": "string"}, '
    '"sm_name": {"type": "string"}, '
    '"attchmntFile": {"type": "string"}, '
    '"attchmntText": {"type": "string"}, '
    '"an_dt": {"type": "string"}'
    "}}"
)


async def _seed_corp_ann(db, *, enabled=True):
    poller = PollerConfig(
        module="engine.pollers.corp_ann",
        api_name="corp_ann",
        output_schema=_CORP_ANN_SCHEMA,
        config="{}",
        enabled=enabled,
    )
    processor = ProcessorConfig(
        module="engine.processors.corp_ann",
        api_name="corp_ann",
        input_schema=_CORP_ANN_SCHEMA,
        config="{}",
        enabled=enabled,
    )
    db.add_all([poller, processor])
    await db.commit()
    db.add(ProcessorPollerLink(processor_id=processor.id, poller_id=poller.id))
    await db.commit()


async def test_build_components_registers_namespaced_supervisor_keys(
    async_db_session,
    fake_redis,
):
    await _seed_corp_ann(async_db_session)
    supervisor = Supervisor(restart_delay=0.01)
    watchdog_apis: list[str] = []

    await build_components(
        db=async_db_session,
        supervisor=supervisor,
        redis=fake_redis,
        session=AsyncMock(),
        llm=AsyncMock(),
        process_pool=AsyncMock(),
        db_factory=AsyncMock(),
        watchdog_register=watchdog_apis.append,
    )

    assert "poller:corp_ann" in supervisor._factories
    assert "processor:corp_ann" in supervisor._factories
    assert watchdog_apis == ["corp_ann"]


async def test_build_components_skips_when_disabled(async_db_session, fake_redis):
    await _seed_corp_ann(async_db_session, enabled=False)
    supervisor = Supervisor(restart_delay=0.01)

    await build_components(
        db=async_db_session,
        supervisor=supervisor,
        redis=fake_redis,
        session=AsyncMock(),
        llm=AsyncMock(),
        process_pool=AsyncMock(),
        db_factory=AsyncMock(),
        watchdog_register=lambda api: None,
    )

    assert supervisor._factories == {}
