import asyncio

from engine.supervisor import Supervisor


async def test_start_all_runs_registered_factories():
    ran = []

    async def factory_a():
        ran.append("a")

    async def factory_b():
        ran.append("b")

    supervisor = Supervisor(restart_delay=0.01)
    supervisor.register("a", factory_a)
    supervisor.register("b", factory_b)
    await supervisor.start_all()
    await asyncio.sleep(0.05)
    assert "a" in ran
    assert "b" in ran
    await supervisor.shutdown()


async def test_crashed_task_is_restarted():
    restart_count = []

    async def crasher():
        restart_count.append(1)
        if len(restart_count) < 3:
            raise RuntimeError("boom")

    supervisor = Supervisor(restart_delay=0.01)
    supervisor.register("crasher", crasher)
    await supervisor.start_all()
    await asyncio.sleep(0.15)
    assert len(restart_count) >= 3
    await supervisor.shutdown()


async def test_shutdown_stops_restarts():
    restarts = []

    async def forever():
        restarts.append(1)
        await asyncio.sleep(10)

    supervisor = Supervisor(restart_delay=0.01)
    supervisor.register("forever", forever)
    await supervisor.start_all()
    await asyncio.sleep(0.05)
    await supervisor.shutdown()
    count_at_shutdown = len(restarts)
    await asyncio.sleep(0.1)
    assert len(restarts) == count_at_shutdown


async def test_restart_cancels_and_restarts_task():
    states = []

    async def worker():
        states.append("start")
        await asyncio.sleep(10)

    supervisor = Supervisor(restart_delay=0.01)
    supervisor.register("worker", worker)
    await supervisor.start_all()
    await asyncio.sleep(0.05)
    await supervisor.restart("worker")
    await asyncio.sleep(0.05)
    assert states.count("start") >= 2
    await supervisor.shutdown()


async def test_restart_isolated_by_namespace():
    states = {"poller": 0, "processor": 0}

    async def poller_worker():
        states["poller"] += 1
        await asyncio.sleep(10)

    async def processor_worker():
        states["processor"] += 1
        await asyncio.sleep(10)

    supervisor = Supervisor(restart_delay=0.01)
    supervisor.register("poller:corp_ann", poller_worker)
    supervisor.register("processor:corp_ann", processor_worker)

    await supervisor.start_all()
    await asyncio.sleep(0.05)
    await supervisor.restart("poller:corp_ann")
    await asyncio.sleep(0.05)

    assert states["poller"] >= 2
    assert states["processor"] == 1

    await supervisor.shutdown()


async def test_pause_poller_does_not_affect_processor():
    poller_started = asyncio.Event()
    processor_started = asyncio.Event()

    async def poller_worker():
        poller_started.set()
        await asyncio.sleep(10)

    async def processor_worker():
        processor_started.set()
        await asyncio.sleep(10)

    supervisor = Supervisor(restart_delay=0.01)
    supervisor.register("poller:corp_ann", poller_worker)
    supervisor.register("processor:corp_ann", processor_worker)

    await supervisor.start_all()
    await asyncio.sleep(0.05)
    assert poller_started.is_set()
    assert processor_started.is_set()

    await supervisor.pause("poller:corp_ann")

    assert supervisor._tasks["poller:corp_ann"].done()
    assert not supervisor._tasks["processor:corp_ann"].done()

    await supervisor.shutdown()


async def test_pause_processor_does_not_affect_poller():
    poller_started = asyncio.Event()
    processor_started = asyncio.Event()

    async def poller_worker():
        poller_started.set()
        await asyncio.sleep(10)

    async def processor_worker():
        processor_started.set()
        await asyncio.sleep(10)

    supervisor = Supervisor(restart_delay=0.01)
    supervisor.register("poller:corp_ann", poller_worker)
    supervisor.register("processor:corp_ann", processor_worker)

    await supervisor.start_all()
    await asyncio.sleep(0.05)
    assert poller_started.is_set()
    assert processor_started.is_set()

    await supervisor.pause("processor:corp_ann")

    assert supervisor._tasks["processor:corp_ann"].done()
    assert not supervisor._tasks["poller:corp_ann"].done()

    await supervisor.shutdown()


async def test_start_is_noop_when_task_already_running():
    starts = []

    async def worker():
        starts.append(1)
        await asyncio.sleep(10)

    supervisor = Supervisor(restart_delay=0.01)
    supervisor.register("processor:corp_ann", worker)

    await supervisor.start("processor:corp_ann")
    await asyncio.sleep(0.05)
    await supervisor.start("processor:corp_ann")
    await asyncio.sleep(0.05)

    assert len(starts) == 1

    await supervisor.shutdown()
