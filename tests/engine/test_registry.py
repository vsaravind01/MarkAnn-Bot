import pytest

from database.models import PollerConfig, ProcessorConfig, ProcessorPollerLink
from engine.registry import (
    ContractError,
    api_name_from_module,
    load_enabled,
    load_poller_module,
    load_processor_module,
    schema_incompatibilities,
)


def _schema(props, required=None):
    out = {"properties": props}
    if required is not None:
        out["required"] = required
    return out


def test_compatible_when_all_input_fields_present_with_matching_types():
    inp = _schema({"seq_id": {"type": "string"}, "symbol": {"type": "string"}})
    out = _schema(
        {
            "seq_id": {"type": "string"},
            "symbol": {"type": "string"},
            "extra": {"type": "string"},
        }
    )
    assert schema_incompatibilities(inp, out) == []


def test_rejects_missing_field():
    inp = _schema({"attachment_url": {"type": "string"}})
    out = _schema({"seq_id": {"type": "string"}})
    errors = schema_incompatibilities(inp, out)
    assert len(errors) == 1
    assert "attachment_url" in errors[0]
    assert "not present" in errors[0]


def test_rejects_type_mismatch():
    inp = _schema({"seq_id": {"type": "string"}})
    out = _schema({"seq_id": {"type": "integer"}})
    errors = schema_incompatibilities(inp, out)
    assert len(errors) == 1
    assert "seq_id" in errors[0]
    assert "string" in errors[0] and "integer" in errors[0]


def test_extra_output_fields_are_allowed():
    inp = _schema({"seq_id": {"type": "string"}})
    out = _schema(
        {
            "seq_id": {"type": "string"},
            "a": {"type": "string"},
            "b": {"type": "integer"},
        }
    )
    assert schema_incompatibilities(inp, out) == []


def test_api_name_is_last_module_segment():
    assert api_name_from_module("engine.pollers.corp_ann") == "corp_ann"


def test_load_poller_module_returns_schema_and_class():
    info = load_poller_module("tests.engine.fixtures.good_poller")
    assert info.api_name == "good_poller"
    assert info.poller_cls.__name__ == "Poller"
    assert info.output_schema["properties"]["seq_id"]["type"] == "string"
    assert info.default_config == {"base_interval": 7.0}


def test_load_poller_module_missing_contract_raises():
    with pytest.raises(ContractError, match="OutputSchema"):
        load_poller_module("tests.engine.fixtures.bad_poller")


def test_load_processor_module_returns_schema_and_class():
    info = load_processor_module("tests.engine.fixtures.good_processor")
    assert info.api_name == "good_processor"
    assert info.processor_cls.__name__ == "Processor"
    assert info.input_schema["properties"]["seq_id"]["type"] == "string"
    assert info.default_config == {"pool_size": 4}


_POLLER_OUT = '{"properties": {"seq_id": {"type": "string"}}}'
_PROC_IN = '{"properties": {"seq_id": {"type": "string"}}}'


async def _seed(db, *, poller_enabled=True, processor_enabled=True, link=True):
    poller = PollerConfig(
        module="tests.engine.fixtures.good_poller",
        api_name="good_poller",
        output_schema=_POLLER_OUT,
        config='{"base_interval": 9.0}',
        enabled=poller_enabled,
    )
    processor = ProcessorConfig(
        module="tests.engine.fixtures.good_processor",
        api_name="good_processor",
        input_schema=_PROC_IN,
        config="{}",
        enabled=processor_enabled,
    )
    db.add_all([poller, processor])
    await db.commit()
    if link:
        db.add(ProcessorPollerLink(processor_id=processor.id, poller_id=poller.id))
        await db.commit()
    return poller, processor


async def test_load_enabled_returns_loaded_components(async_db_session):
    await _seed(async_db_session)
    pollers, processors = await load_enabled(async_db_session)

    assert len(pollers) == 1
    assert pollers[0].api_name == "good_poller"
    assert pollers[0].config["base_interval"] == 9.0

    assert len(processors) == 1
    assert processors[0].api_name == "good_processor"
    assert processors[0].poller_api_names == ["good_poller"]
    assert processors[0].config["pool_size"] == 4


async def test_load_enabled_skips_disabled_poller(async_db_session):
    await _seed(async_db_session, poller_enabled=False)
    pollers, processors = await load_enabled(async_db_session)

    assert pollers == []
    assert processors == []


async def test_load_enabled_skips_processor_with_incompatible_schema(async_db_session):
    poller = PollerConfig(
        module="tests.engine.fixtures.good_poller",
        api_name="good_poller",
        output_schema='{"properties": {"other": {"type": "string"}}}',
        enabled=True,
    )
    processor = ProcessorConfig(
        module="tests.engine.fixtures.good_processor",
        api_name="good_processor",
        input_schema=_PROC_IN,
        enabled=True,
    )
    async_db_session.add_all([poller, processor])
    await async_db_session.commit()
    async_db_session.add(
        ProcessorPollerLink(processor_id=processor.id, poller_id=poller.id)
    )
    await async_db_session.commit()

    pollers, processors = await load_enabled(async_db_session)
    assert len(pollers) == 1
    assert processors == []


async def test_load_enabled_skips_unimportable_module(async_db_session):
    async_db_session.add(
        PollerConfig(
            module="tests.engine.fixtures.does_not_exist",
            api_name="ghost",
            output_schema="{}",
            enabled=True,
        )
    )
    await async_db_session.commit()

    pollers, processors = await load_enabled(async_db_session)
    assert pollers == []
