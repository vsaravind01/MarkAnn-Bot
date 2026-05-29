import jwt
from fastapi import HTTPException, Request
from sqlalchemy import select

from database.models import User
from gateway.auth.tokens import decode_access_token


async def get_current_user(request: Request) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    settings = request.app.state.settings
    try:
        payload = decode_access_token(token, settings)
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    async with request.app.state.db_factory() as db:
        user = (
            await db.execute(select(User).where(User.id == payload["user_id"]))
        ).scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_roles(*roles: str):
    async def dependency(request: Request) -> User:
        user = await get_current_user(request)
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency
