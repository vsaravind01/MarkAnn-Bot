import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

from llm.provider import LLMRateLimitError

logger = logging.getLogger(__name__)


class ConsumerPool:
    def __init__(
        self,
        redis,
        queue_key: str,
        processor_fn: Callable[[dict], Awaitable[None]],
        size: int,
    ) -> None:
        self._redis = redis
        self._queue_key = queue_key
        self._processor_fn = processor_fn
        self._size = size
        self._tasks: set[asyncio.Task] = set()

    def _spawn(self) -> None:
        task = asyncio.create_task(self._consume())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def run(self) -> None:
        workers = [asyncio.create_task(self._consume()) for _ in range(self._size)]
        self._tasks.update(workers)
        for worker in workers:
            worker.add_done_callback(self._tasks.discard)
        try:
            await asyncio.gather(*workers)
        except asyncio.CancelledError:
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            raise

    async def start(self) -> None:
        for _ in range(self._size):
            self._spawn()

    async def _consume(self) -> None:
        while True:
            result = await self._redis.blpop(self._queue_key, timeout=2)
            if result is None:
                continue

            _, raw_item = result
            # Intentionally outside try/except: bad JSON is unrecoverable; propagating
            # to gather() lets the supervisor restart the pool rather than silently skipping.
            item = json.loads(raw_item)
            try:
                await self._processor_fn(item)
            except LLMRateLimitError as exc:
                await self._redis.rpush(self._queue_key, raw_item)
                wait = exc.retry_after or 60.0
                logger.warning(
                    "Consumer: LLM rate limited (retry-after %.0fs) - item re-queued", wait
                )
                await asyncio.sleep(wait)
            except Exception:
                logger.exception("Consumer: unhandled error processing item")

    async def resize(self, new_size: int) -> None:
        current = len(self._tasks)
        if new_size > current:
            for _ in range(new_size - current):
                self._spawn()
        elif new_size < current:
            to_cancel = list(self._tasks)[: current - new_size]
            for task in to_cancel:
                task.cancel()
            if to_cancel:
                await asyncio.gather(*to_cancel, return_exceptions=True)
        self._size = new_size

    @property
    def size(self) -> int:
        return len(self._tasks)

    async def stop(self) -> None:
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
