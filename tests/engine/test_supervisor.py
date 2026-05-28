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
