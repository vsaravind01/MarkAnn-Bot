from database.redis import (
    alert_channel,
    dedup_key,
    inflight_key,
    queue_key,
    result_key,
    seconds_until_midnight,
    user_channels_key,
    watch_key,
)


def test_dedup_key():
    assert dedup_key("corp_ann", "12345") == "dedup:corp_ann:12345"


def test_result_key_contains_today():
    from datetime import datetime
    today = datetime.now().strftime("%Y%m%d")
    assert result_key("INFY", "12345") == f"result:{today}:INFY:12345"


def test_watch_key():
    assert watch_key("INFY") == "watch:INFY"


def test_user_channels_key():
    assert user_channels_key(42) == "user:42:channels"


def test_alert_channel():
    assert alert_channel("INFY") == "alerts:INFY"


def test_queue_key():
    assert queue_key("corp_ann") == "queue:corp_ann"


def test_inflight_key():
    assert inflight_key("corp_ann", "abc123") == "inflight:corp_ann:abc123"


def test_seconds_until_midnight_positive():
    ttl = seconds_until_midnight()
    assert 0 < ttl <= 86400


async def test_redis_set_get(fake_redis):
    await fake_redis.set("foo", "bar")
    val = await fake_redis.get("foo")
    assert val == "bar"


async def test_redis_dedup_flow(fake_redis):
    key = dedup_key("corp_ann", "99999")
    assert await fake_redis.exists(key) == 0
    await fake_redis.set(key, "1", ex=172800)
    assert await fake_redis.exists(key) == 1
