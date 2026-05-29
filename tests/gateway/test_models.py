from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from database.models import RefreshToken, User


async def test_user_has_auth_fields(db_session):
    user = User(
        email="trader@example.com",
        password_hash="hashed",
        role="trader",
        first_name="Arjun",
        last_name="Sharma",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.email == "trader@example.com"
    assert user.role == "trader"
    assert user.is_active is True
    assert user.first_name == "Arjun"
    assert user.last_name == "Sharma"
    assert user.created_by is None


async def test_refresh_token_model(db_session):
    user = User(email="u@e.com", password_hash="h", role="trader", first_name="A", last_name="B")
    db_session.add(user)
    await db_session.commit()

    token = RefreshToken(
        user_id=user.id,
        token_hash="abc123",
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    db_session.add(token)
    await db_session.commit()

    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == "abc123")
    )
    row = result.scalar_one()
    assert row.id is not None
    assert row.revoked is False
    assert row.user_id == user.id
