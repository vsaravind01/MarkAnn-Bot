import json

from fastapi import APIRouter, HTTPException, Request
from redis.asyncio import Redis

from engine.health import read_health

router = APIRouter(prefix="/admin/pollers", tags=["admin-pollers"])

_REGISTERED_APIS = ["corp_ann"]


@router.get("")
async def list_pollers(request: Request):
    redis: Redis = request.app.state.redis
    return [await read_health(redis, api) for api in _REGISTERED_APIS]


@router.get("/{api}")
async def get_poller(api: str, request: Request):
    if api not in _REGISTERED_APIS:
        raise HTTPException(status_code=404, detail=f"Poller {api!r} not registered")
    redis: Redis = request.app.state.redis
    return await read_health(redis, api)


async def _publish_control(redis: Redis, api: str, action: str) -> None:
    await redis.publish("engine:control", json.dumps({"api": api, "action": action}))


@router.post("/{api}/pause")
async def pause_poller(api: str, request: Request):
    if api not in _REGISTERED_APIS:
        raise HTTPException(status_code=404, detail=f"Poller {api!r} not registered")
    await _publish_control(request.app.state.redis, api, "pause")
    return {"api": api, "action": "paused"}


@router.post("/{api}/resume")
async def resume_poller(api: str, request: Request):
    if api not in _REGISTERED_APIS:
        raise HTTPException(status_code=404, detail=f"Poller {api!r} not registered")
    await _publish_control(request.app.state.redis, api, "resume")
    return {"api": api, "action": "resumed"}


@router.post("/{api}/restart")
async def restart_poller(api: str, request: Request):
    if api not in _REGISTERED_APIS:
        raise HTTPException(status_code=404, detail=f"Poller {api!r} not registered")
    await _publish_control(request.app.state.redis, api, "restart")
    return {"api": api, "action": "restarted"}
