import json

from fastapi import APIRouter, HTTPException, Request
from redis.asyncio import Redis

from database.redis import processor_status_key, queue_key

router = APIRouter(prefix="/admin/processors", tags=["admin-processors"])

_REGISTERED_APIS = ["corp_ann"]


async def _read_processor_health(redis: Redis, api: str) -> dict:
    status = await redis.get(processor_status_key(api)) or "unknown"
    queue_size = await redis.llen(queue_key(api))
    return {"api": api, "status": status, "queue_size": queue_size}


async def _publish_control(redis: Redis, api: str, action: str) -> None:
    await redis.publish(
        "engine:control",
        json.dumps({"component": f"processor:{api}", "action": action}),
    )


@router.get("")
async def list_processors(request: Request):
    redis: Redis = request.app.state.redis
    return [await _read_processor_health(redis, api) for api in _REGISTERED_APIS]


@router.get("/{api}")
async def get_processor(api: str, request: Request):
    if api not in _REGISTERED_APIS:
        raise HTTPException(status_code=404, detail=f"Processor {api!r} not registered")
    return await _read_processor_health(request.app.state.redis, api)


@router.post("/{api}/pause")
async def pause_processor(api: str, request: Request):
    if api not in _REGISTERED_APIS:
        raise HTTPException(status_code=404, detail=f"Processor {api!r} not registered")
    await _publish_control(request.app.state.redis, api, "pause")
    return {"api": api, "action": "paused"}


@router.post("/{api}/resume")
async def resume_processor(api: str, request: Request):
    if api not in _REGISTERED_APIS:
        raise HTTPException(status_code=404, detail=f"Processor {api!r} not registered")
    await _publish_control(request.app.state.redis, api, "resume")
    return {"api": api, "action": "resumed"}


@router.post("/{api}/restart")
async def restart_processor(api: str, request: Request):
    if api not in _REGISTERED_APIS:
        raise HTTPException(status_code=404, detail=f"Processor {api!r} not registered")
    await _publish_control(request.app.state.redis, api, "restart")
    return {"api": api, "action": "restarted"}
