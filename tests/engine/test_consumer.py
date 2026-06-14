import asyncio
import json
from contextlib import suppress

import pytest

from engine.consumer import ConsumerPool
from llm.provider import LLMRateLimitError


async def test_run_processes_items_from_redis_queue(fake_redis):
    processed = []

    async def processor(item):
        processed.append(item)

    await fake_redis.rpush("queue:test", json.dumps({"id": 1}))
    await fake_redis.rpush("queue:test", json.dumps({"id": 2}))

    pool = ConsumerPool(redis=fake_redis, queue_key="queue:test", processor_fn=processor, size=2)
    task = asyncio.create_task(pool.run())
    await asyncio.sleep(0.15)
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    assert sorted(item["id"] for item in processed) == [1, 2]


async def test_run_cancellation_stops_all_workers(fake_redis):
    async def slow_processor(_):
        await asyncio.sleep(10)

    pool = ConsumerPool(
        redis=fake_redis,
        queue_key="queue:test",
        processor_fn=slow_processor,
        size=3,
    )
    task = asyncio.create_task(pool.run())
    await asyncio.sleep(0.05)
    assert pool.size == 3

    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    assert pool.size == 0


async def test_run_propagates_unhandled_worker_failure(fake_redis):
    await fake_redis.rpush("queue:test", "{not-json")

    async def processor(_):
        await asyncio.sleep(0)

    pool = ConsumerPool(redis=fake_redis, queue_key="queue:test", processor_fn=processor, size=1)
    task = asyncio.create_task(pool.run())

    with pytest.raises(json.JSONDecodeError):
        await asyncio.wait_for(task, timeout=0.2)


async def test_unprocessed_items_remain_in_queue_after_cancel(fake_redis):
    started = asyncio.Event()

    async def slow_processor(_):
        started.set()
        await asyncio.sleep(10)

    for index in range(5):
        await fake_redis.rpush("queue:test", json.dumps({"id": index}))

    pool = ConsumerPool(
        redis=fake_redis,
        queue_key="queue:test",
        processor_fn=slow_processor,
        size=1,
    )
    task = asyncio.create_task(pool.run())
    await started.wait()
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    remaining = await fake_redis.llen("queue:test")
    assert remaining >= 1


async def test_rate_limited_item_is_requeued(fake_redis):
    attempts = 0

    async def rate_limited(_):
        nonlocal attempts
        attempts += 1
        raise LLMRateLimitError("too many requests", retry_after=5)

    raw_item = json.dumps({"id": 1})
    await fake_redis.rpush("queue:test", raw_item)

    pool = ConsumerPool(redis=fake_redis, queue_key="queue:test", processor_fn=rate_limited, size=1)

    task = asyncio.create_task(pool._consume())
    await asyncio.sleep(0.05)
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    assert attempts >= 1
    assert await fake_redis.llen("queue:test") >= 1


async def test_start_spawns_workers_and_stop_cancels_them(fake_redis):
    async def processor(_):
        await asyncio.sleep(0)

    pool = ConsumerPool(redis=fake_redis, queue_key="queue:test", processor_fn=processor, size=2)
    await pool.start()
    assert pool.size == 2
    await pool.stop()
    await asyncio.sleep(0.05)
    assert pool.size == 0


async def test_resize_up_adds_workers(fake_redis):
    async def processor(_):
        await asyncio.sleep(0)

    pool = ConsumerPool(redis=fake_redis, queue_key="queue:test", processor_fn=processor, size=2)
    await pool.start()
    await pool.resize(5)
    await asyncio.sleep(0.05)
    assert pool.size == 5
    await pool.stop()


async def test_resize_down_removes_workers(fake_redis):
    async def processor(_):
        await asyncio.sleep(0)

    pool = ConsumerPool(redis=fake_redis, queue_key="queue:test", processor_fn=processor, size=4)
    await pool.start()
    await pool.resize(2)
    await asyncio.sleep(0.1)
    assert pool.size == 2
    await pool.stop()


async def test_processor_exception_does_not_kill_worker(fake_redis):
    call_count = 0

    async def flaky_processor(_):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("oops")

    await fake_redis.rpush("queue:test", json.dumps({"id": 1}))
    await fake_redis.rpush("queue:test", json.dumps({"id": 2}))

    pool = ConsumerPool(
        redis=fake_redis,
        queue_key="queue:test",
        processor_fn=flaky_processor,
        size=1,
    )
    task = asyncio.create_task(pool.run())
    await asyncio.sleep(0.2)
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task

    assert call_count == 2
