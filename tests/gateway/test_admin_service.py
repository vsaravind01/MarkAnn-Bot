import pytest
from sqlalchemy import select

from database.models import User
from gateway.admin.service import get_user_by_id, list_users, patch_user
from gateway.auth.service import register_admin, register_trader


async def _seed(db_session, settings):
    await register_admin(db_session, "super@e.com", "pass1234", "S", "U", None, settings)
    superuser = (
        await db_session.execute(select(User).where(User.email == "super@e.com"))
    ).scalar_one()
    await register_trader(db_session, "trader1@e.com", "pass1234", "T", "1", settings)
    await register_trader(db_session, "trader2@e.com", "pass1234", "T", "2", settings)
    return superuser


async def test_list_users_returns_all(db_session, settings):
    await _seed(db_session, settings)
    page = await list_users(db_session, page=1, page_size=20)
    assert page["total"] == 3
    assert len(page["items"]) == 3


async def test_list_users_pagination(db_session, settings):
    await _seed(db_session, settings)
    page = await list_users(db_session, page=1, page_size=2)
    assert len(page["items"]) == 2
    assert page["total"] == 3
    assert page["page"] == 1
    page2 = await list_users(db_session, page=2, page_size=2)
    assert len(page2["items"]) == 1


async def test_list_traders_only(db_session, settings):
    await _seed(db_session, settings)
    page = await list_users(db_session, page=1, page_size=20, role="trader")
    assert page["total"] == 2
    assert all(user["role"] == "trader" for user in page["items"])


async def test_get_user_by_id(db_session, settings):
    superuser = await _seed(db_session, settings)
    user = await get_user_by_id(db_session, superuser.id)
    assert user is not None
    assert user.email == "super@e.com"


async def test_get_user_not_found(db_session, settings):
    user = await get_user_by_id(db_session, 9999)
    assert user is None


async def test_patch_user_disables(db_session, settings):
    await _seed(db_session, settings)
    trader = (
        await db_session.execute(select(User).where(User.email == "trader1@e.com"))
    ).scalar_one()
    updated = await patch_user(db_session, trader.id, is_active=False)
    assert updated.is_active is False


async def test_patch_superuser_active_raises(db_session, settings):
    superuser = await _seed(db_session, settings)
    with pytest.raises(ValueError, match="superuser"):
        await patch_user(db_session, superuser.id, is_active=False)
