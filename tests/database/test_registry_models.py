from database.models import PollerConfig, ProcessorConfig, ProcessorPollerLink


async def test_poller_config_persists(async_db_session):
    row = PollerConfig(
        module="engine.pollers.corp_ann",
        api_name="corp_ann",
        output_schema='{"properties": {"seq_id": {"type": "string"}}}',
        config="{}",
        enabled=False,
    )
    async_db_session.add(row)
    await async_db_session.commit()

    fetched = await async_db_session.get(PollerConfig, row.id)
    assert fetched.module == "engine.pollers.corp_ann"
    assert fetched.api_name == "corp_ann"
    assert fetched.enabled is False


async def test_processor_links_to_poller(async_db_session):
    poller = PollerConfig(
        module="engine.pollers.corp_ann",
        api_name="corp_ann",
        output_schema="{}",
    )
    processor = ProcessorConfig(
        module="engine.processors.corp_ann",
        api_name="corp_ann",
        input_schema="{}",
    )
    async_db_session.add_all([poller, processor])
    await async_db_session.commit()

    link = ProcessorPollerLink(processor_id=processor.id, poller_id=poller.id)
    async_db_session.add(link)
    await async_db_session.commit()

    fetched = await async_db_session.get(ProcessorPollerLink, (processor.id, poller.id))
    assert fetched is not None
