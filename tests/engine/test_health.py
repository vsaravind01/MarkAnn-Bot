from engine.health import (
    read_health,
    write_error_count,
    write_heartbeat,
    write_interval,
    write_last_success,
    write_status,
)


async def test_write_heartbeat_sets_key_with_ttl(fake_redis):
    await write_heartbeat(fake_redis, "corp_ann", interval=5.0)
    val = await fake_redis.get("poller:corp_ann:heartbeat")
    assert val is not None
    ttl = await fake_redis.ttl("poller:corp_ann:heartbeat")
    assert 0 < ttl <= 15  # 3 * 5.0


async def test_write_last_success_has_no_ttl(fake_redis):
    await write_last_success(fake_redis, "corp_ann")
    val = await fake_redis.get("poller:corp_ann:last_success")
    assert val is not None
    ttl = await fake_redis.ttl("poller:corp_ann:last_success")
    assert ttl == -1  # no TTL


async def test_write_status(fake_redis):
    await write_status(fake_redis, "corp_ann", "running")
    val = await fake_redis.get("poller:corp_ann:status")
    assert val == "running"


async def test_write_error_count(fake_redis):
    await write_error_count(fake_redis, "corp_ann", 3)
    val = await fake_redis.get("poller:corp_ann:error_count")
    assert val == "3"


async def test_read_health_returns_all_fields(fake_redis):
    await write_status(fake_redis, "corp_ann", "running")
    await write_error_count(fake_redis, "corp_ann", 0)
    await write_interval(fake_redis, "corp_ann", 5.0)
    health = await read_health(fake_redis, "corp_ann")
    assert health["api"] == "corp_ann"
    assert health["status"] == "running"
    assert health["error_count"] == 0
    assert health["interval"] == 5.0


async def test_read_health_missing_keys_returns_defaults(fake_redis):
    health = await read_health(fake_redis, "nonexistent")
    assert health["status"] == "unknown"
    assert health["error_count"] == 0
