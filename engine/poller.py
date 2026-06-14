import asyncio
import hashlib
import json
import logging
from abc import ABC, abstractmethod

import httpx
from redis.asyncio import Redis

from database.redis import inflight_key, queue_key
from engine.circuit_breaker import CircuitBreaker
from engine.events import push_event
from engine.health import (
    write_error_count,
    write_heartbeat,
    write_interval,
    write_last_success,
    write_status,
)
from engine.session import NseSession

logger = logging.getLogger(__name__)


class Poller(ABC):
    def __init__(
        self,
        api_name: str,
        session: NseSession,
        redis: Redis,
        base_interval: float = 5.0,
        max_interval: float = 60.0,
        failure_threshold: int = 5,
        circuit_hold_off: float = 300.0,
    ) -> None:
        self.api_name = api_name
        self.session = session
        self.redis = redis
        self.base_interval = base_interval
        self.max_interval = max_interval
        self._current_interval = base_interval
        self._circuit = CircuitBreaker(failure_threshold, circuit_hold_off)
        self._consecutive_failures = 0
        self._running = False

    def item_id(self, item: dict) -> str:
        return hashlib.sha1(json.dumps(item, sort_keys=True).encode()).hexdigest()[:16]

    @abstractmethod
    async def fetch(self) -> list[dict]:
        ...

    async def run(self) -> None:
        self._running = True
        await write_status(self.redis, self.api_name, "running")
        while self._running:
            await write_heartbeat(self.redis, self.api_name, self._current_interval)

            if not self._circuit.can_attempt():
                await write_status(self.redis, self.api_name, "circuit_open")
                await asyncio.sleep(self._current_interval)
                continue

            try:
                data = await self.fetch()
                self._circuit.record_success()
                self._consecutive_failures = 0
                self._current_interval = self.base_interval
                await write_interval(self.redis, self.api_name, self._current_interval)
                await write_error_count(self.redis, self.api_name, 0)

                if data:
                    await write_last_success(self.redis, self.api_name)
                    for item in data:
                        item_id = self.item_id(item)
                        acquired = await self.redis.set(
                            inflight_key(self.api_name, item_id),
                            "1",
                            ex=3600,
                            nx=True,
                        )
                        if not acquired:
                            continue
                        await self.redis.rpush(queue_key(self.api_name), json.dumps(item))

                await write_status(self.redis, self.api_name, "running")
                await asyncio.sleep(self._current_interval)

            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (401, 403):
                    logger.warning("NSE session expired — refreshing cookies")
                    await self.session.refresh()
                    continue
                await self._handle_failure(exc)

            except Exception as exc:
                await self._handle_failure(exc)

    async def _handle_failure(self, exc: Exception) -> None:
        self._circuit.record_failure()
        self._consecutive_failures += 1
        await write_error_count(self.redis, self.api_name, self._consecutive_failures)
        self._current_interval = min(self._current_interval * 2, self.max_interval)
        await write_interval(self.redis, self.api_name, self._current_interval)
        status = "circuit_open" if self._circuit.is_open else "backing_off"
        await write_status(self.redis, self.api_name, status)
        logger.error(
            f"Poller {self.api_name!r} error: {exc!r}. Interval -> {self._current_interval}s"
        )
        exc_summary = f"{type(exc).__name__}: {str(exc)[:120]}"
        if self._circuit.is_open:
            await push_event(
                self.redis,
                "crit",
                f"circuit opened after {self._consecutive_failures} consecutive failures - {exc_summary}",
                api=self.api_name,
            )
        else:
            await push_event(
                self.redis,
                "warn",
                f"fetch error #{self._consecutive_failures} - {exc_summary}",
                api=self.api_name,
            )
        await asyncio.sleep(self._current_interval)

    def stop(self) -> None:
        self._running = False
