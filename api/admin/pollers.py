import json

from fastapi import APIRouter, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy import select

from database.models import PollerConfig
from engine.health import read_health

router = APIRouter(prefix="/admin/pollers", tags=["admin-pollers"])


def _parse_config(raw: str) -> dict:
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}


async def _poller_rows(request: Request) -> list[PollerConfig]:
    async with request.app.state.db_factory() as db:
        return list(
            (
                await db.execute(select(PollerConfig).order_by(PollerConfig.api_name))
            ).scalars().all()
        )


async def _poller_payload(redis: Redis, row: PollerConfig) -> dict:
    health = await read_health(redis, row.api_name)
    return {**health, "enabled": row.enabled, "config": _parse_config(row.config)}


@router.get("")
async def list_pollers(request: Request):
    redis: Redis = request.app.state.redis
    return [await _poller_payload(redis, row) for row in await _poller_rows(request)]


@router.get("/{api}")
async def get_poller(api: str, request: Request):
    rows = {row.api_name: row for row in await _poller_rows(request)}
    row = rows.get(api)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Poller {api!r} not registered")
    return await _poller_payload(request.app.state.redis, row)


async def _publish_control(redis: Redis, api: str, action: str) -> None:
    await redis.publish(
        "engine:control",
        json.dumps({"component": f"poller:{api}", "action": action}),
    )


async def _ensure_registered(api: str, request: Request) -> None:
    if api not in {row.api_name for row in await _poller_rows(request)}:
        raise HTTPException(status_code=404, detail=f"Poller {api!r} not registered")


@router.post("/{api}/pause")
async def pause_poller(api: str, request: Request):
    await _ensure_registered(api, request)
    await _publish_control(request.app.state.redis, api, "pause")
    return {"api": api, "action": "paused"}


@router.post("/{api}/resume")
async def resume_poller(api: str, request: Request):
    await _ensure_registered(api, request)
    await _publish_control(request.app.state.redis, api, "resume")
    return {"api": api, "action": "resumed"}


@router.post("/{api}/restart")
async def restart_poller(api: str, request: Request):
    await _ensure_registered(api, request)
    await _publish_control(request.app.state.redis, api, "restart")
    return {"api": api, "action": "restarted"}
