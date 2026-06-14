import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import select

from database.models import PollerConfig, ProcessorConfig, ProcessorPollerLink
from database.redis import processor_status_key, queue_key

router = APIRouter(tags=["admin-processors"])


class PoolSizeUpdate(BaseModel):
    pool_size: int = Field(ge=1, le=64)


def _parse_config(raw: str) -> dict:
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}


async def _read_processor_health(redis: Redis, api: str) -> dict:
    status = await redis.get(processor_status_key(api)) or "unknown"
    queue_size = await redis.llen(queue_key(api))
    return {"api": api, "status": status, "queue_size": queue_size}


async def _publish_control(redis: Redis, api: str, action: str) -> None:
    await redis.publish(
        "engine:control",
        json.dumps({"component": f"processor:{api}", "action": action}),
    )


async def _processor_payloads(request: Request, *, only_api: str | None = None) -> list[dict]:
    redis: Redis = request.app.state.redis
    async with request.app.state.db_factory() as db:
        query = select(ProcessorConfig).order_by(ProcessorConfig.api_name)
        if only_api is not None:
            query = query.where(ProcessorConfig.api_name == only_api)
        processors = (await db.execute(query)).scalars().all()
        pollers = (await db.execute(select(PollerConfig))).scalars().all()
        links = (await db.execute(select(ProcessorPollerLink))).scalars().all()

    poller_api_by_id = {poller.id: poller.api_name for poller in pollers}
    links_by_processor: dict[int, list[str]] = {}
    for link in links:
        poller_api = poller_api_by_id.get(link.poller_id)
        if poller_api is not None:
            links_by_processor.setdefault(link.processor_id, []).append(poller_api)

    payloads = []
    for processor in processors:
        health = await _read_processor_health(redis, processor.api_name)
        payloads.append(
            {
                **health,
                "module": processor.module,
                "enabled": processor.enabled,
                "config": _parse_config(processor.config),
                "pollers": sorted(links_by_processor.get(processor.id, [])),
            }
        )
    return payloads


async def _registered_apis(request: Request) -> list[str]:
    async with request.app.state.db_factory() as db:
        rows = (
            await db.execute(
                select(ProcessorConfig.api_name).order_by(ProcessorConfig.api_name)
            )
        ).scalars().all()
    return list(rows)


@router.get("/admin/processors")
async def list_processors(request: Request):
    return await _processor_payloads(request)


@router.get("/admin/processor-poller-links")
async def list_links(request: Request):
    async with request.app.state.db_factory() as db:
        processors = (
            await db.execute(select(ProcessorConfig).order_by(ProcessorConfig.api_name))
        ).scalars().all()
        pollers = (await db.execute(select(PollerConfig))).scalars().all()
        links = (await db.execute(select(ProcessorPollerLink))).scalars().all()

    poller_api_by_id = {poller.id: poller.api_name for poller in pollers}
    links_by_processor: dict[int, list[str]] = {processor.id: [] for processor in processors}
    for link in links:
        poller_api = poller_api_by_id.get(link.poller_id)
        if poller_api is not None:
            links_by_processor.setdefault(link.processor_id, []).append(poller_api)

    return [
        {"processor": processor.api_name, "pollers": sorted(links_by_processor[processor.id])}
        for processor in processors
        if links_by_processor[processor.id]
    ]


@router.patch("/admin/processors/{api}")
async def resize_processor(api: str, body: PoolSizeUpdate, request: Request):
    async with request.app.state.db_factory() as db:
        row = (
            await db.execute(select(ProcessorConfig).where(ProcessorConfig.api_name == api))
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Processor {api!r} not registered")

        config = _parse_config(row.config)
        config["pool_size"] = body.pool_size
        row.config = json.dumps(config)
        await db.commit()

    payloads = await _processor_payloads(request, only_api=api)
    return payloads[0]


@router.get("/admin/processors/{api}")
async def get_processor(api: str, request: Request):
    payloads = await _processor_payloads(request, only_api=api)
    if not payloads:
        raise HTTPException(status_code=404, detail=f"Processor {api!r} not registered")
    return payloads[0]


@router.post("/admin/processors/{api}/pause")
async def pause_processor(api: str, request: Request):
    if api not in await _registered_apis(request):
        raise HTTPException(status_code=404, detail=f"Processor {api!r} not registered")
    await _publish_control(request.app.state.redis, api, "pause")
    return {"api": api, "action": "paused"}


@router.post("/admin/processors/{api}/resume")
async def resume_processor(api: str, request: Request):
    if api not in await _registered_apis(request):
        raise HTTPException(status_code=404, detail=f"Processor {api!r} not registered")
    await _publish_control(request.app.state.redis, api, "resume")
    return {"api": api, "action": "resumed"}


@router.post("/admin/processors/{api}/restart")
async def restart_processor(api: str, request: Request):
    if api not in await _registered_apis(request):
        raise HTTPException(status_code=404, detail=f"Processor {api!r} not registered")
    await _publish_control(request.app.state.redis, api, "restart")
    return {"api": api, "action": "restarted"}
