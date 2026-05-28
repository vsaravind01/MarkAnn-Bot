import json
import re

import httpx
import pytest
import respx

from engine.session import NSE_HOME, NseSession


@respx.mock
async def test_initialize_requests_nse_home():
    respx.get(NSE_HOME).mock(return_value=httpx.Response(200))
    session = NseSession()
    await session.initialize()
    assert respx.calls.call_count == 1
    await session.close()


@respx.mock
async def test_get_returns_response():
    # Use pattern matcher to handle both NSE_HOME and API calls
    respx.get(re.compile(r"https://www\.nseindia\.com")).mock(
        return_value=httpx.Response(200, content=json.dumps({"ok": True}).encode())
    )
    session = NseSession()
    await session.initialize()
    response = await session.get("https://www.nseindia.com/api/test")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    await session.close()


@respx.mock
async def test_refresh_requests_nse_home_again():
    respx.get(NSE_HOME).mock(return_value=httpx.Response(200))
    session = NseSession()
    await session.initialize()
    await session.refresh()
    assert respx.calls.call_count == 2
    await session.close()


async def test_get_before_initialize_raises():
    session = NseSession()
    with pytest.raises(RuntimeError, match="not initialized"):
        await session.get("https://www.nseindia.com/api/test")


@respx.mock
async def test_context_manager():
    respx.get(NSE_HOME).mock(return_value=httpx.Response(200))
    async with NseSession() as session:
        assert session._client is not None
    assert session._client is None
