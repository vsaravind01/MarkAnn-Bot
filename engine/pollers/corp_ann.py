from datetime import date

from redis.asyncio import Redis

from engine.poller import Poller
from engine.session import NseSession

_NSE_CORP_ANN_URL = "https://www.nseindia.com/api/corporate-announcements"


class CorporateAnnouncementsPoller(Poller):
    def __init__(
        self,
        session: NseSession,
        redis: Redis,
        index: str = "equities",
        **kwargs,
    ) -> None:
        super().__init__(api_name="corp_ann", session=session, redis=redis, **kwargs)
        self._index = index

    def item_id(self, item: dict) -> str:
        return item.get("seq_id") or super().item_id(item)

    async def fetch(self) -> list[dict]:
        today = date.today().strftime("%d-%m-%Y")
        response = await self.session.get(
            _NSE_CORP_ANN_URL,
            params={"index": self._index, "from_date": today, "to_date": today},
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            raise ValueError(
                f"NSE returned non-JSON response (content-type={content_type!r}, "
                f"status={response.status_code}) - session cookie may be missing or blocked"
            )
        return response.json()
