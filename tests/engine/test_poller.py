import asyncio
import hashlib
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from engine.circuit_breaker import CircuitState
from engine.poller import Poller
from engine.session import NseSession


class _StopTest(BaseException):
    """Sentinel exception used to terminate the poller loop in tests."""


class ConcretePoller(Poller):
    def __init__(self, *args, responses=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._responses = iter(responses or [[{"seq_id": "1"}]])

    def item_id(self, item: dict) -> str:
        return item["seq_id"]

    async def fetch(self):
        try:
            value = next(self._responses)
        except StopIteration as exc:
            raise _StopTest from exc
        if value is _StopTest:
            raise _StopTest
        return value


async def test_successful_tick_enqueues_items_to_redis(fake_redis):
    session = AsyncMock(spec=NseSession)
    poller = ConcretePoller(
        api_name="test",
        session=session,
        redis=fake_redis,
        base_interval=0.01,
        responses=[[{"seq_id": "1"}, {"seq_id": "2"}], _StopTest],
    )
    with pytest.raises(_StopTest):
        await poller.run()

    queue_size = await fake_redis.llen("queue:test")
    assert queue_size == 2


async def test_inflight_dedup_skips_already_queued_item(fake_redis):
    await fake_redis.set("inflight:test:1", "1", ex=3600)

    session = AsyncMock(spec=NseSession)
    poller = ConcretePoller(
        api_name="test",
        session=session,
        redis=fake_redis,
        base_interval=0.01,
        responses=[[{"seq_id": "1"}, {"seq_id": "2"}], _StopTest],
    )
    with pytest.raises(_StopTest):
        await poller.run()

    queue_size = await fake_redis.llen("queue:test")
    assert queue_size == 1

    raw_item = await fake_redis.lindex("queue:test", 0)
    item = json.loads(raw_item)
    assert item["seq_id"] == "2"


async def test_inflight_key_is_set_with_one_hour_ttl(fake_redis):
    session = AsyncMock(spec=NseSession)
    poller = ConcretePoller(
        api_name="test",
        session=session,
        redis=fake_redis,
        base_interval=0.01,
        responses=[[{"seq_id": "abc"}], _StopTest],
    )
    with pytest.raises(_StopTest):
        await poller.run()

    ttl = await fake_redis.ttl("inflight:test:abc")
    assert 3500 < ttl <= 3600


async def test_item_id_default_is_stable_hash():
    session = AsyncMock(spec=NseSession)
    poller = ConcretePoller(api_name="test", session=session, redis=AsyncMock())

    item = {"b": 2, "a": 1}
    id_one = Poller.item_id(poller, item)
    id_two = Poller.item_id(poller, {"a": 1, "b": 2})

    assert id_one == id_two
    assert len(id_one) == 16
    expected = hashlib.sha1(json.dumps(item, sort_keys=True).encode()).hexdigest()[:16]
    assert id_one == expected


async def test_failure_doubles_interval(fake_redis):
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
        session=session,
        redis=fake_redis,
        base_interval=1.0,
        max_interval=60.0,
    )
    with pytest.raises(_StopTest):
        await poller.run()
    assert poller._current_interval == 2.0


async def test_session_expired_triggers_refresh(fake_redis):
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
        session=session,
        redis=fake_redis,
        base_interval=0.01,
    )
    with pytest.raises(_StopTest):
        await poller.run()
    session.refresh.assert_called_once()


async def test_circuit_opens_after_threshold(fake_redis):
    session = AsyncMock(spec=NseSession)

    class AlwaysFailPoller(Poller):
        async def fetch(self):
            raise httpx.NetworkError("timeout")

    poller = AlwaysFailPoller(
        api_name="test",
        session=session,
        redis=fake_redis,
        base_interval=0.01,
        failure_threshold=3,
        circuit_hold_off=300.0,
    )
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(poller.run(), timeout=0.5)
    assert poller._circuit.state == CircuitState.OPEN
