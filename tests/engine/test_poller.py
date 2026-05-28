import asyncio
import pytest
import httpx
from unittest.mock import AsyncMock
from engine.poller import Poller
from engine.session import NseSession
from engine.circuit_breaker import CircuitState


class _StopTest(BaseException):
    """Sentinel exception used to terminate the poller loop in tests."""


class ConcretePoller(Poller):
    def __init__(self, *args, responses=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._responses = iter(responses or [[{"seq_id": "1"}]])

    async def fetch(self):
        try:
            value = next(self._responses)
        except StopIteration:
            raise _StopTest
        if value is _StopTest:
            raise _StopTest
        return value


async def test_successful_tick_puts_items_on_queue(fake_redis):
    queue = asyncio.Queue()
    session = AsyncMock(spec=NseSession)
    poller = ConcretePoller(
        api_name="test",
        queue=queue,
        session=session,
        redis=fake_redis,
        base_interval=0.01,
        responses=[[{"seq_id": "1"}, {"seq_id": "2"}], _StopTest],
    )
    with pytest.raises(_StopTest):
        await poller.run()
    assert queue.qsize() == 2


async def test_failure_doubles_interval(fake_redis):
    queue = asyncio.Queue()
    session = AsyncMock(spec=NseSession)

    call_count = 0

    class FailingPoller(Poller):
        async def fetch(self):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.NetworkError("timeout")
            raise _StopTest

    poller = FailingPoller(
        api_name="test",
        queue=queue,
        session=session,
        redis=fake_redis,
        base_interval=1.0,
        max_interval=60.0,
    )
    with pytest.raises(_StopTest):
        await poller.run()
    assert poller._current_interval == 2.0


async def test_session_expired_triggers_refresh(fake_redis):
    queue = asyncio.Queue()
    session = AsyncMock(spec=NseSession)
    session.refresh = AsyncMock()

    call_count = 0

    class SessionExpiredPoller(Poller):
        async def fetch(self):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError(
                    "401", request=AsyncMock(), response=httpx.Response(401)
                )
            raise _StopTest

    poller = SessionExpiredPoller(
        api_name="test",
        queue=queue,
        session=session,
        redis=fake_redis,
        base_interval=0.01,
    )
    with pytest.raises(_StopTest):
        await poller.run()
    session.refresh.assert_called_once()


async def test_circuit_opens_after_threshold(fake_redis):
    queue = asyncio.Queue()
    session = AsyncMock(spec=NseSession)

    class AlwaysFailPoller(Poller):
        async def fetch(self):
            raise httpx.NetworkError("timeout")

    poller = AlwaysFailPoller(
        api_name="test",
        queue=queue,
        session=session,
        redis=fake_redis,
        base_interval=0.01,
        failure_threshold=3,
        circuit_hold_off=300.0,
    )
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(poller.run(), timeout=0.5)
    assert poller._circuit.state == CircuitState.OPEN
