import time

from redis.asyncio import Redis

from database.redis import (
    poller_error_count_key,
    poller_heartbeat_key,
    poller_interval_key,
    poller_last_success_key,
    poller_status_key,
    processor_status_key,
)


async def write_heartbeat(redis: Redis, api: str, interval: float) -> None:
    ttl = max(1, int(3 * interval))
    await redis.set(poller_heartbeat_key(api), int(time.time()), ex=ttl)


async def write_last_success(redis: Redis, api: str) -> None:
    await redis.set(poller_last_success_key(api), int(time.time()))


async def write_status(redis: Redis, api: str, status: str) -> None:
    await redis.set(poller_status_key(api), status)


async def write_error_count(redis: Redis, api: str, count: int) -> None:
    await redis.set(poller_error_count_key(api), str(count))


async def write_interval(redis: Redis, api: str, interval: float) -> None:
    await redis.set(poller_interval_key(api), str(interval))


async def write_processor_status(redis: Redis, api: str, status: str) -> None:
    await redis.set(processor_status_key(api), status)


async def read_health(redis: Redis, api: str) -> dict:
    keys = [
        poller_heartbeat_key(api),
        poller_last_success_key(api),
        poller_status_key(api),
        poller_error_count_key(api),
        poller_interval_key(api),
    ]
    values = await redis.mget(*keys)
    return {
        "api": api,
        "heartbeat": values[0],
        "last_success": values[1],
        "status": values[2] if values[2] else "unknown",
        "error_count": int(values[3]) if values[3] else 0,
        "interval": float(values[4]) if values[4] else 5.0,
    }
