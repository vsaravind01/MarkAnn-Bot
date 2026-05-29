from fastapi import APIRouter, Query, Request
from redis.asyncio import Redis

from engine.events import read_events

router = APIRouter(prefix="/admin/events", tags=["admin-events"])


@router.get("")
async def list_events(request: Request, limit: int = Query(default=100, le=200)):
    redis: Redis = request.app.state.redis
    return await read_events(redis, limit=limit)
