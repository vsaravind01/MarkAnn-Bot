import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

_RATE_LIMITED_PATHS = {"/auth/login", "/auth/register", "/auth/admin/register"}
_WINDOW_SECONDS = 60
_LIMIT = 10
_SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
local window_start = now - window

redis.call("ZREMRANGEBYSCORE", key, 0, window_start)
redis.call("ZADD", key, now, member)
local count = redis.call("ZCARD", key)
redis.call("EXPIRE", key, window + 1)

if count > limit then
  local oldest = redis.call("ZRANGE", key, 0, 0, "WITHSCORES")
  local retry_after = window
  if oldest[2] ~= nil then
    retry_after = math.max(1, window - (now - tonumber(oldest[2])))
  end
  return {0, count, retry_after}
end

return {1, count, 0}
"""


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path in _RATE_LIMITED_PATHS:
            redis = request.app.state.redis
            client_ip = request.client.host if request.client else "unknown"
            key = f"rl:{request.url.path}:{client_ip}"
            now = int(time.time())

            try:
                allowed, _, retry_after = await redis.eval(
                    _SLIDING_WINDOW_SCRIPT,
                    1,
                    key,
                    now,
                    _WINDOW_SECONDS,
                    _LIMIT,
                    str(time.time_ns()),
                )
            except Exception:
                # Fallback when Lua scripting is unavailable in local/test Redis.
                try:
                    async with redis.pipeline(transaction=True) as pipeline:
                        window_start = now - _WINDOW_SECONDS
                        pipeline.zremrangebyscore(key, 0, window_start)
                        pipeline.zadd(key, {str(time.time_ns()): now})
                        pipeline.zcard(key)
                        pipeline.zrange(key, 0, 0, withscores=True)
                        pipeline.expire(key, _WINDOW_SECONDS + 1)
                        _, _, count, oldest, _ = await pipeline.execute()
                    if count > _LIMIT:
                        oldest_score = oldest[0][1] if oldest else now
                        retry_after = max(1, _WINDOW_SECONDS - (now - int(oldest_score)))
                        return JSONResponse(
                            {"detail": "Too many requests"},
                            status_code=429,
                            headers={"Retry-After": str(retry_after)},
                        )
                except Exception:
                    return await call_next(request)
            else:
                if int(allowed) == 0:
                    return JSONResponse(
                        {"detail": "Too many requests"},
                        status_code=429,
                        headers={"Retry-After": str(int(retry_after))},
                    )

        return await call_next(request)
