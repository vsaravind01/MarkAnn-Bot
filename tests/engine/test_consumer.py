import asyncio

from engine.consumer import STOP_SENTINEL, ConsumerPool


async def test_consumers_process_all_items():
    queue = asyncio.Queue()
    processed = []

    async def processor(item):
        processed.append(item)

    pool = ConsumerPool(queue=queue, processor_fn=processor, size=2)
    await pool.start()

    for i in range(5):
        await queue.put({"id": i})

    await queue.join()
    assert len(processed) == 5
    assert pool.size == 2
    await pool.stop()


async def test_scale_up_adds_consumers():
    queue = asyncio.Queue()

    async def processor(_):
        await asyncio.sleep(0)

    pool = ConsumerPool(queue=queue, processor_fn=processor, size=2)
    await pool.start()
    assert pool.size == 2

    await pool.resize(5)
    await asyncio.sleep(0)  # allow new tasks to start
    assert pool.size == 5
    await pool.stop()


async def test_scale_down_removes_consumers():
    queue = asyncio.Queue()

    async def processor(_):
        await asyncio.sleep(0)

    pool = ConsumerPool(queue=queue, processor_fn=processor, size=4)
    await pool.start()
    await pool.resize(2)
    await asyncio.sleep(0.05)
    assert pool.size == 2
    await pool.stop()


async def test_stop_sentinel_exits_consumer():
    queue = asyncio.Queue()
    processed = []

    async def processor(item):
        processed.append(item)

    pool = ConsumerPool(queue=queue, processor_fn=processor, size=1)
    await pool.start()
    await queue.put({"id": 1})
    await queue.put(STOP_SENTINEL)
    await asyncio.sleep(0.05)
    assert processed == [{"id": 1}]
