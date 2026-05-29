import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Response

from gateway.config import Settings


def create_access_token(user_id: int, role: str, email: str, settings: Settings) -> str:
    exp = datetime.now(UTC) + timedelta(minutes=settings.jwt_ttl_minutes)
    payload = {"user_id": user_id, "role": role, "email": email, "exp": exp}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    settings: Settings,
) -> None:
    secure = settings.https
    response.set_cookie(
        "access_token",
        access_token,
        httponly=True,
        samesite="strict",
        secure=secure,
        path="/",
    )
    response.set_cookie(
        "refresh_token",
        refresh_token,
        httponly=True,
        samesite="strict",
        secure=secure,
        path="/auth/refresh",
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    secure = settings.https
    response.set_cookie(
        "access_token",
        "",
        httponly=True,
        samesite="strict",
        secure=secure,
        path="/",
        max_age=0,
    )
    response.set_cookie(
        "refresh_token",
        "",
        httponly=True,
        samesite="strict",
        secure=secure,
        path="/auth/refresh",
        max_age=0,
    )
