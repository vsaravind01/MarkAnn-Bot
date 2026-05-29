from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import RefreshToken, User
from gateway.auth.passwords import hash_password, verify_password
from gateway.auth.tokens import create_access_token, generate_refresh_token, hash_token
from gateway.config import Settings


async def register_trader(
    db: AsyncSession,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    settings: Settings,
) -> tuple[str, str]:
    user = User(
        email=email,
        password_hash=hash_password(password),
        role="trader",
        first_name=first_name,
        last_name=last_name,
    )
    db.add(user)
    await db.flush()
    access_token, refresh_token = await _issue_tokens(db, user, settings)
    await db.commit()
    return access_token, refresh_token


async def register_admin(
    db: AsyncSession,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    created_by_id: int | None,
    settings: Settings,
) -> tuple[str, str, User]:
    count = (
        await db.execute(
            select(func.count()).select_from(User).where(User.role.in_(["admin", "superuser"]))
        )
    ).scalar_one()
    if count > 0 and created_by_id is None:
        raise PermissionError("Only superuser can create admins")
    role = "superuser" if count == 0 else "admin"

    user = User(
        email=email,
        password_hash=hash_password(password),
        role=role,
        first_name=first_name,
        last_name=last_name,
        created_by=created_by_id,
    )
    db.add(user)
    await db.flush()
    access_token, refresh_token = await _issue_tokens(db, user, settings)
    await db.commit()
    return access_token, refresh_token, user


async def login(db: AsyncSession, email: str, password: str, settings: Settings) -> tuple[str, str]:
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise ValueError("Invalid credentials")
    if not user.is_active:
        raise ValueError("Account disabled")
    access_token, refresh_token = await _issue_tokens(db, user, settings)
    await db.commit()
    return access_token, refresh_token


async def refresh_tokens(
    db: AsyncSession,
    raw_token: str,
    settings: Settings,
) -> tuple[str, str]:
    token_hash = hash_token(raw_token)
    refresh_token = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one_or_none()
    if refresh_token is None:
        raise ValueError("Invalid token")
    if refresh_token.revoked:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == refresh_token.user_id)
            .values(revoked=True)
        )
        await db.commit()
        raise ValueError("Token reuse detected")
    if refresh_token.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
        raise ValueError("Token expired")

    refresh_token.revoked = True
    user = (await db.execute(select(User).where(User.id == refresh_token.user_id))).scalar_one()
    if not user.is_active:
        await db.commit()
        raise ValueError("Account disabled")

    access_token, new_refresh_token = await _issue_tokens(db, user, settings)
    await db.commit()
    return access_token, new_refresh_token


async def logout(db: AsyncSession, raw_token: str) -> None:
    token_hash = hash_token(raw_token)
    refresh_token = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one_or_none()
    if refresh_token:
        refresh_token.revoked = True
        await db.commit()


async def revoke_all_tokens(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user_id).values(revoked=True)
    )
    await db.commit()


async def _issue_tokens(db: AsyncSession, user: User, settings: Settings) -> tuple[str, str]:
    raw_refresh = generate_refresh_token()
    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=(datetime.now(UTC) + timedelta(days=settings.refresh_ttl_days)).replace(tzinfo=None),
    )
    db.add(refresh_token)
    access_token = create_access_token(user.id, user.role, user.email, settings)
    return access_token, raw_refresh
