import asyncio
import pytest
import respx
import httpx
from datetime import date
from engine.pollers.corp_ann import CorporateAnnouncementsPoller
from engine.session import NseSession

NSE_CORP_ANN_URL = "https://www.nseindia.com/api/corporate-announcements"
NSE_HOME = "https://www.nseindia.com"


@pytest.mark.asyncio
async def test_fetch_returns_list(fake_redis):
    with respx.mock:
        respx.get(url__regex=r".*corporate-announcements.*").mock(
            return_value=httpx.Response(200, json=[{"seq_id": "1", "symbol": "INFY"}])
        )
        respx.get(NSE_HOME).mock(return_value=httpx.Response(200, text="OK"))
        async with NseSession() as session:
            queue = asyncio.Queue()
            poller = CorporateAnnouncementsPoller(
                queue=queue, session=session, redis=fake_redis, index="equities"
            )
            result = await poller.fetch()
        assert result == [{"seq_id": "1", "symbol": "INFY"}]


@pytest.mark.asyncio
async def test_fetch_sends_today_dates(fake_redis):
    today = date.today().strftime("%d-%m-%Y")
    captured = {}

    def capture(request, _):
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=[])

    with respx.mock:
        respx.get(url__regex=r".*corporate-announcements.*").mock(side_effect=capture)
        respx.get(NSE_HOME).mock(return_value=httpx.Response(200, text="OK"))
        async with NseSession() as session:
            queue = asyncio.Queue()
            poller = CorporateAnnouncementsPoller(
                queue=queue, session=session, redis=fake_redis
            )
            await poller.fetch()
        assert captured["params"]["from_date"] == today
        assert captured["params"]["to_date"] == today


@pytest.mark.asyncio
async def test_fetch_empty_response_returns_empty_list(fake_redis):
    with respx.mock:
        respx.get(url__regex=r".*corporate-announcements.*").mock(return_value=httpx.Response(200, json=[]))
        respx.get(NSE_HOME).mock(return_value=httpx.Response(200, text="OK"))
        async with NseSession() as session:
            queue = asyncio.Queue()
            poller = CorporateAnnouncementsPoller(
                queue=queue, session=session, redis=fake_redis
            )
            result = await poller.fetch()
        assert result == []
