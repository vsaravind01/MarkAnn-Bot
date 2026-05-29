import pytest
from sqlalchemy import select

from database.models import RefreshToken, User
from gateway.auth.service import login, logout, refresh_tokens, register_admin, register_trader
from gateway.auth.tokens import hash_token


async def test_register_trader_creates_user(db_session, settings):
    access, refresh = await register_trader(
        db_session, "trader@example.com", "password123", "Arjun", "Sharma", settings
    )
    assert access
    assert refresh

    user = (
        await db_session.execute(select(User).where(User.email == "trader@example.com"))
    ).scalar_one()
    assert user.role == "trader"
    assert user.first_name == "Arjun"
    assert user.is_active is True


async def test_register_first_admin_becomes_superuser(db_session, settings):
    await register_admin(
        db_session,
        "super@example.com",
        "password123",
        "Super",
        "User",
        created_by_id=None,
        settings=settings,
    )
    user = (
        await db_session.execute(select(User).where(User.email == "super@example.com"))
    ).scalar_one()
    assert user.role == "superuser"


async def test_register_second_admin_is_admin(db_session, settings):
    await register_admin(db_session, "super@example.com", "password123", "S", "U", None, settings)
    superuser = (
        await db_session.execute(select(User).where(User.email == "super@example.com"))
    ).scalar_one()

    await register_admin(
        db_session,
        "admin@example.com",
        "password123",
        "A",
        "D",
        created_by_id=superuser.id,
        settings=settings,
    )
    admin = (
        await db_session.execute(select(User).where(User.email == "admin@example.com"))
    ).scalar_one()
    assert admin.role == "admin"


async def test_login_returns_tokens(db_session, settings):
    await register_trader(db_session, "t@e.com", "pass1234", "T", "E", settings)
    access, refresh = await login(db_session, "t@e.com", "pass1234", settings)
    assert access
    assert refresh


async def test_login_wrong_password_raises(db_session, settings):
    await register_trader(db_session, "t@e.com", "pass1234", "T", "E", settings)
    with pytest.raises(ValueError, match="Invalid credentials"):
        await login(db_session, "t@e.com", "wrongpass", settings)


async def test_login_unknown_email_raises(db_session, settings):
    with pytest.raises(ValueError, match="Invalid credentials"):
        await login(db_session, "nobody@e.com", "pass", settings)


async def test_refresh_rotates_token(db_session, settings):
    await register_trader(db_session, "t@e.com", "pass1234", "T", "E", settings)
    _, old_refresh = await login(db_session, "t@e.com", "pass1234", settings)

    new_access, new_refresh = await refresh_tokens(db_session, old_refresh, settings)
    assert new_access
    assert new_refresh != old_refresh

    refresh = (
        await db_session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(old_refresh))
        )
    ).scalar_one()
    assert refresh.revoked is True


async def test_refresh_reuse_revokes_all(db_session, settings):
    await register_trader(db_session, "t@e.com", "pass1234", "T", "E", settings)
    _, raw = await login(db_session, "t@e.com", "pass1234", settings)
    await refresh_tokens(db_session, raw, settings)

    with pytest.raises(ValueError, match="reuse"):
        await refresh_tokens(db_session, raw, settings)


async def test_logout_revokes_token(db_session, settings):
    await register_trader(db_session, "t@e.com", "pass1234", "T", "E", settings)
    _, raw = await login(db_session, "t@e.com", "pass1234", settings)
    await logout(db_session, raw)

    refresh = (
        await db_session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw))
        )
    ).scalar_one()
    assert refresh.revoked is True
