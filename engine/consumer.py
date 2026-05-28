import asyncio
import logging
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

STOP_SENTINEL = object()


class ConsumerPool:
    def __init__(
        self,
        queue: asyncio.Queue,
        processor_fn: Callable[[dict], Awaitable[None]],
        size: int,
    ) -> None:
        self._queue = queue
        self._processor_fn = processor_fn
        self._tasks: set[asyncio.Task] = set()
        self._size = size

    async def start(self) -> None:
        for _ in range(self._size):
            self._spawn()

    def _spawn(self) -> None:
        task = asyncio.create_task(self._consume())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _consume(self) -> None:
        while True:
            item = await self._queue.get()
            if item is STOP_SENTINEL:
                self._queue.task_done()
                return
            try:
                await self._processor_fn(item)
            except Exception:
                logger.exception("Consumer: unhandled error processing item")
            finally:
                self._queue.task_done()

    async def resize(self, new_size: int) -> None:
        current = len(self._tasks)
        if new_size > current:
            for _ in range(new_size - current):
                self._spawn()
        elif new_size < current:
            for _ in range(current - new_size):
                await self._queue.put(STOP_SENTINEL)
        self._size = new_size

    @property
    def size(self) -> int:
        return len(self._tasks)

    async def stop(self) -> None:
        for _ in range(len(self._tasks)):
            await self._queue.put(STOP_SENTINEL)
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
