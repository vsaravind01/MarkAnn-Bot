from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError

from database.models import UserWatchlist
from database.redis import watch_key

router = APIRouter(prefix="/api/v1/watchlist", tags=["watchlist"])


class WatchlistAdd(BaseModel):
    user_id: int
    symbol: str


@router.post("")
async def subscribe(body: WatchlistAdd, request: Request):
    redis = request.app.state.redis

    async with request.app.state.db_factory() as session:
        entry = UserWatchlist(user_id=body.user_id, symbol=body.symbol.upper())
        session.add(entry)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()

    await redis.sadd(watch_key(body.symbol.upper()), str(body.user_id))
    return {"user_id": body.user_id, "symbol": body.symbol.upper(), "action": "subscribed"}


@router.delete("")
async def unsubscribe(user_id: int, symbol: str, request: Request):
    redis = request.app.state.redis

    async with request.app.state.db_factory() as session:
        await session.execute(
            delete(UserWatchlist).where(
                UserWatchlist.user_id == user_id,
                UserWatchlist.symbol == symbol.upper(),
            )
        )
        await session.commit()

    await redis.srem(watch_key(symbol.upper()), str(user_id))
    return {"user_id": user_id, "symbol": symbol.upper(), "action": "unsubscribed"}
