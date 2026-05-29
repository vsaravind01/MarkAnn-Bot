import json
import time

_KEY = "engine:events"
_MAX = 200


async def push_event(
    redis,
    level: str,
    message: str,
    api: str | None = None,
) -> None:
    entry: dict = {"ts": int(time.time()), "lvl": level, "msg": message}
    if api:
        entry["api"] = api
    await redis.lpush(_KEY, json.dumps(entry))
    await redis.ltrim(_KEY, 0, _MAX - 1)


async def read_events(redis, limit: int = 100) -> list[dict]:
    raw = await redis.lrange(_KEY, 0, limit - 1)
    events = []
    for item in raw:
        try:
            events.append(json.loads(item))
        except (json.JSONDecodeError, TypeError):
            pass
    return events
