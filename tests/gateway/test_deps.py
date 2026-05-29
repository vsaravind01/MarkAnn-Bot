from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from database.models import User
from gateway.auth.deps import get_current_user
from gateway.auth.tokens import create_access_token


def _make_request(token: str | None, db_user: User | None, settings):
    mock_request = MagicMock()
    mock_request.cookies = {"access_token": token} if token else {}

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = db_user

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_factory = MagicMock(return_value=mock_session)
    mock_request.app.state.settings = settings
    mock_request.app.state.db_factory = mock_factory
    return mock_request


async def test_valid_token_returns_user(settings):
    token = create_access_token(1, "trader", "t@e.com", settings)
    user = User(
        id=1,
        email="t@e.com",
        role="trader",
        first_name="A",
        last_name="B",
        password_hash="h",
        is_active=True,
    )
    request = _make_request(token, user, settings)
    result = await get_current_user(request)
    assert result.id == 1


async def test_missing_cookie_raises_401(settings):
    request = _make_request(None, None, settings)
    with pytest.raises(HTTPException) as exc:
        await get_current_user(request)
    assert exc.value.status_code == 401


async def test_invalid_token_raises_401(settings):
    request = _make_request("not.a.valid.jwt", None, settings)
    with pytest.raises(HTTPException) as exc:
        await get_current_user(request)
    assert exc.value.status_code == 401


async def test_inactive_user_raises_401(settings):
    token = create_access_token(1, "trader", "t@e.com", settings)
    user = User(
        id=1,
        email="t@e.com",
        role="trader",
        first_name="A",
        last_name="B",
        password_hash="h",
        is_active=False,
    )
    request = _make_request(token, user, settings)
    with pytest.raises(HTTPException) as exc:
        await get_current_user(request)
    assert exc.value.status_code == 401
