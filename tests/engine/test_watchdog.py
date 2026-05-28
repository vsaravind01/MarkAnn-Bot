import asyncio
import time
from unittest.mock import AsyncMock
from engine.supervisor import Watchdog


async def test_watchdog_restarts_on_missing_heartbeat(fake_redis):
    supervisor = AsyncMock()
    watchdog = Watchdog(
        redis=fake_redis,
        supervisor=supervisor,
        silence_threshold=600.0,
        check_interval=0.05,
    )
    watchdog.register("corp_ann")

    task = asyncio.create_task(watchdog.run())
    await asyncio.sleep(0.15)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    supervisor.restart.assert_called_with("corp_ann")


async def test_watchdog_does_not_restart_with_valid_heartbeat(fake_redis):
    supervisor = AsyncMock()
    watchdog = Watchdog(
        redis=fake_redis,
        supervisor=supervisor,
        silence_threshold=600.0,
        check_interval=0.05,
    )
    watchdog.register("corp_ann")
    await fake_redis.set("poller:corp_ann:heartbeat", int(time.time()), ex=60)

    task = asyncio.create_task(watchdog.run())
    await asyncio.sleep(0.15)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    supervisor.restart.assert_not_called()


async def test_watchdog_logs_silence_alert_without_restart(fake_redis, caplog):
    import logging
    supervisor = AsyncMock()
    watchdog = Watchdog(
        redis=fake_redis,
        supervisor=supervisor,
        silence_threshold=1.0,
        check_interval=0.05,
    )
    watchdog.register("corp_ann")
    await fake_redis.set("poller:corp_ann:heartbeat", int(time.time()), ex=60)
    await fake_redis.set("poller:corp_ann:last_success", int(time.time()) - 10)

    with caplog.at_level(logging.ERROR):
        task = asyncio.create_task(watchdog.run())
        await asyncio.sleep(0.15)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    supervisor.restart.assert_not_called()
    assert any("manual review" in r.message for r in caplog.records)
