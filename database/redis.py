import os
from datetime import datetime, timedelta

import pytz
from redis.asyncio import Redis
from redis.asyncio import from_url as redis_from_url


def get_redis_client(url: str | None = None) -> Redis:
    return redis_from_url(
        url or os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )


_IST = pytz.timezone("Asia/Kolkata")


def seconds_until_midnight() -> int:
    now = datetime.now(tz=_IST)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((midnight - now).total_seconds())


def dedup_key(api: str, seq_id: str) -> str:
    return f"dedup:{api}:{seq_id}"


def result_key(symbol: str, seq_id: str) -> str:
    date_str = datetime.now(tz=_IST).strftime("%Y%m%d")
    return f"result:{date_str}:{symbol}:{seq_id}"


def watch_key(symbol: str) -> str:
    return f"watch:{symbol}"


def user_channels_key(user_id: int) -> str:
    return f"user:{user_id}:channels"


def alert_channel(symbol: str) -> str:
    return f"alerts:{symbol}"


def queue_key(api: str) -> str:
    return f"queue:{api}"


def inflight_key(api: str, item_id: str) -> str:
    return f"inflight:{api}:{item_id}"


def poller_heartbeat_key(api: str) -> str:
    return f"poller:{api}:heartbeat"


def poller_last_success_key(api: str) -> str:
    return f"poller:{api}:last_success"


def poller_status_key(api: str) -> str:
    return f"poller:{api}:status"


def poller_error_count_key(api: str) -> str:
    return f"poller:{api}:error_count"


def poller_interval_key(api: str) -> str:
    return f"poller:{api}:interval"


def processor_status_key(api: str) -> str:
    return f"processor:{api}:status"
