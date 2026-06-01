import hashlib
import json
from datetime import date
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

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
            poller = CorporateAnnouncementsPoller(session=session, redis=fake_redis)
            result = await poller.fetch()
    assert result == [{"seq_id": "1", "symbol": "INFY"}]


@pytest.mark.asyncio
async def test_fetch_sends_today_dates(fake_redis):
    today = date.today().strftime("%d-%m-%Y")
    captured = {}

    def capture(request, route):  # noqa: ARG001
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=[])

    with respx.mock:
        respx.get(url__regex=r".*corporate-announcements.*").mock(side_effect=capture)
        respx.get(NSE_HOME).mock(return_value=httpx.Response(200, text="OK"))
        async with NseSession() as session:
            poller = CorporateAnnouncementsPoller(session=session, redis=fake_redis)
            await poller.fetch()
    assert captured["params"]["from_date"] == today
    assert captured["params"]["to_date"] == today


@pytest.mark.asyncio
async def test_fetch_empty_response_returns_empty_list(fake_redis):
    with respx.mock:
        respx.get(url__regex=r".*corporate-announcements.*").mock(
            return_value=httpx.Response(200, json=[])
        )
        respx.get(NSE_HOME).mock(return_value=httpx.Response(200, text="OK"))
        async with NseSession() as session:
            poller = CorporateAnnouncementsPoller(session=session, redis=fake_redis)
            result = await poller.fetch()
    assert result == []


def test_item_id_returns_seq_id_when_present(fake_redis):
    poller = CorporateAnnouncementsPoller(session=AsyncMock(spec=NseSession), redis=fake_redis)
    assert poller.item_id({"seq_id": "106644730", "symbol": "INFY"}) == "106644730"


def test_item_id_falls_back_to_hash_when_seq_id_absent(fake_redis):
    poller = CorporateAnnouncementsPoller(session=AsyncMock(spec=NseSession), redis=fake_redis)
    item = {"symbol": "INFY", "category": "results"}
    expected_hash = hashlib.sha1(json.dumps(item, sort_keys=True).encode()).hexdigest()[:16]
    assert poller.item_id(item) == expected_hash


def test_item_id_falls_back_to_hash_when_seq_id_is_empty_string(fake_redis):
    poller = CorporateAnnouncementsPoller(session=AsyncMock(spec=NseSession), redis=fake_redis)
    item = {"seq_id": "", "symbol": "INFY"}
    expected_hash = hashlib.sha1(json.dumps(item, sort_keys=True).encode()).hexdigest()[:16]
    assert poller.item_id(item) == expected_hash
