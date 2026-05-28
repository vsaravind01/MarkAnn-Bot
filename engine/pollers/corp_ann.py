import asyncio
from datetime import date

from redis.asyncio import Redis

from engine.poller import Poller
from engine.session import NseSession

_NSE_CORP_ANN_URL = "https://www.nseindia.com/api/corporate-announcements"


class CorporateAnnouncementsPoller(Poller):
    def __init__(
        self,
        queue: asyncio.Queue,
        session: NseSession,
        redis: Redis,
        index: str = "equities",
        **kwargs,
    ) -> None:
        super().__init__(api_name="corp_ann", queue=queue, session=session, redis=redis, **kwargs)
        self._index = index

    async def fetch(self) -> list[dict]:
        today = date.today().strftime("%d-%m-%Y")
        response = await self.session.get(
            _NSE_CORP_ANN_URL,
            params={"index": self._index, "from_date": today, "to_date": today},
        )
        response.raise_for_status()
        return response.json()
