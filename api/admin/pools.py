from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from database.models import EngineConfig

router = APIRouter(prefix="/admin/pools", tags=["admin-pools"])

_REGISTERED_POOLS = ["corp_ann"]
_DEFAULT_SIZES = {"corp_ann": 8}


class PoolSizeUpdate(BaseModel):
    size: int


@router.get("/{api}")
async def get_pool_size(api: str, request: Request):
    if api not in _REGISTERED_POOLS:
        raise HTTPException(status_code=404, detail=f"Pool {api!r} not found")
    async with request.app.state.db_factory() as session:
        result = await session.execute(
            select(EngineConfig).where(EngineConfig.key == f"pool_size:{api}")
        )
        config = result.scalar_one_or_none()
    size = int(config.value) if config else _DEFAULT_SIZES.get(api, 4)
    return {"api": api, "size": size}


@router.patch("/{api}")
async def update_pool_size(api: str, body: PoolSizeUpdate, request: Request):
    if api not in _REGISTERED_POOLS:
        raise HTTPException(status_code=404, detail=f"Pool {api!r} not found")
    if body.size < 1:
        raise HTTPException(status_code=422, detail="size must be >= 1")

    async with request.app.state.db_factory() as session:
        config = await session.get(EngineConfig, f"pool_size:{api}")
        if config:
            config.value = str(body.size)
        else:
            session.add(EngineConfig(key=f"pool_size:{api}", value=str(body.size)))
        await session.commit()

    pools = request.app.state.pools
    if pools and api in pools:
        await pools[api].resize(body.size)

    return {"api": api, "size": body.size}
