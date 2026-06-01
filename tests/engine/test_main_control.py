import asyncio
import json
from contextlib import suppress
from unittest.mock import AsyncMock

import fakeredis.aioredis

from engine.main import _listen_control


async def test_listen_control_handles_component_payload_for_processor_pause():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    supervisor = AsyncMock()

    task = asyncio.create_task(_listen_control(redis, supervisor))
    await asyncio.sleep(0)
    await redis.publish(
        "engine:control",
        json.dumps({"component": "processor:corp_ann", "action": "pause"}),
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    supervisor.pause.assert_awaited_once_with("processor:corp_ann")
    assert await redis.get("processor:corp_ann:status") == "paused"


async def test_listen_control_maps_legacy_api_field_to_poller_component():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    supervisor = AsyncMock()

    task = asyncio.create_task(_listen_control(redis, supervisor))
    await asyncio.sleep(0)
    await redis.publish(
        "engine:control",
        json.dumps({"api": "corp_ann", "action": "restart"}),
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    supervisor.restart.assert_awaited_once_with("poller:corp_ann")


async def test_listen_control_marks_processor_running_on_resume():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    supervisor = AsyncMock()

    task = asyncio.create_task(_listen_control(redis, supervisor))
    await asyncio.sleep(0)
    await redis.publish(
        "engine:control",
        json.dumps({"component": "processor:corp_ann", "action": "resume"}),
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    supervisor.start.assert_awaited_once_with("processor:corp_ann")
    assert await redis.get("processor:corp_ann:status") == "running"


async def test_listen_control_marks_poller_running_on_resume():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    supervisor = AsyncMock()

    task = asyncio.create_task(_listen_control(redis, supervisor))
    await asyncio.sleep(0)
    await redis.publish(
        "engine:control",
        json.dumps({"component": "poller:corp_ann", "action": "resume"}),
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    supervisor.start.assert_awaited_once_with("poller:corp_ann")
    assert await redis.get("poller:corp_ann:status") == "running"
