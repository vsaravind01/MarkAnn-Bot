import asyncio
import logging
import time
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class Supervisor:
    def __init__(self, restart_delay: float = 2.0) -> None:
        self._restart_delay = restart_delay
        self._tasks: dict[str, asyncio.Task] = {}
        self._factories: dict[str, Callable[[], Coroutine[Any, Any, None]]] = {}
        self._shutdown = False

    def register(self, name: str, factory: Callable[[], Coroutine[Any, Any, None]]) -> None:
        self._factories[name] = factory

    async def start(self, name: str) -> None:
        factory = self._factories[name]
        task = asyncio.create_task(factory(), name=name)
        self._tasks[name] = task
        task.add_done_callback(lambda t: self._on_done(name, t))

    async def start_all(self) -> None:
        for name in self._factories:
            await self.start(name)

    def _on_done(self, name: str, task: asyncio.Task) -> None:
        if self._shutdown:
            return
        if task.cancelled():
            return
        exc = task.exception() if not task.cancelled() else None
        logger.warning(
            f"Supervisor: {name!r} ended (exc={exc!r}), restarting in {self._restart_delay}s"
        )
        loop = asyncio.get_event_loop()
        loop.call_later(self._restart_delay, lambda: asyncio.ensure_future(self.start(name)))

    async def restart(self, name: str) -> None:
        if name in self._tasks and not self._tasks[name].done():
            self._tasks[name].cancel()
            try:
                await self._tasks[name]
            except (asyncio.CancelledError, Exception):
                pass
        await self.start(name)

    async def pause(self, name: str) -> None:
        if name in self._tasks and not self._tasks[name].done():
            self._tasks[name].cancel()
            try:
                await self._tasks[name]
            except (asyncio.CancelledError, Exception):
                pass

    async def shutdown(self) -> None:
        self._shutdown = True
        for task in self._tasks.values():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)


class Watchdog:
    def __init__(
        self,
        redis,
        supervisor: Supervisor,
        silence_threshold: float = 600.0,
        check_interval: float = 30.0,
    ) -> None:
        self._redis = redis
        self._supervisor = supervisor
        self._silence_threshold = silence_threshold
        self._check_interval = check_interval
        self._pollers: list[str] = []

    def register(self, api_name: str) -> None:
        self._pollers.append(api_name)

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self._check_interval)
            for api in self._pollers:
                await self._check(api)

    async def _check(self, api: str) -> None:
        heartbeat_exists = await self._redis.exists(f"poller:{api}:heartbeat")
        if not heartbeat_exists:
            logger.warning(f"Watchdog: {api!r} heartbeat missing — restarting")
            await self._supervisor.restart(api)
            return

        last_success_raw = await self._redis.get(f"poller:{api}:last_success")
        if last_success_raw:
            elapsed = time.time() - float(last_success_raw)
            if elapsed > self._silence_threshold:
                logger.error(
                    f"Watchdog: {api!r} has not produced data in {elapsed:.0f}s "
                    f"(threshold={self._silence_threshold}s) — manual review required"
                )
