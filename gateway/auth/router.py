from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.exc import IntegrityError

from gateway.auth.deps import get_current_user
from gateway.auth.service import login, logout, refresh_tokens, register_trader
from gateway.auth.tokens import clear_auth_cookies, set_auth_cookies

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterBody(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, password: str) -> str:
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(password) > 72:
            raise ValueError("Password must be at most 72 characters")
        return password


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    role: str
    is_active: bool


@router.post("/register")
async def register(body: RegisterBody, request: Request, response: Response):
    settings = request.app.state.settings
    async with request.app.state.db_factory() as db:
        try:
            access, refresh = await register_trader(
                db, body.email, body.password, body.first_name, body.last_name, settings
            )
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(status_code=409, detail="Email already registered") from exc

    set_auth_cookies(response, access, refresh, settings)
    return {"email": body.email, "role": "trader"}


@router.post("/login")
async def login_endpoint(body: LoginBody, request: Request, response: Response):
    settings = request.app.state.settings
    async with request.app.state.db_factory() as db:
        try:
            access, refresh = await login(db, body.email, body.password, settings)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid credentials") from exc

    set_auth_cookies(response, access, refresh, settings)
    return {"detail": "ok"}


@router.post("/refresh")
async def refresh_endpoint(request: Request, response: Response):
    raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh:
        raise HTTPException(status_code=401, detail="No refresh token")

    settings = request.app.state.settings
    async with request.app.state.db_factory() as db:
        try:
            access, new_refresh = await refresh_tokens(db, raw_refresh, settings)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    set_auth_cookies(response, access, new_refresh, settings)
    return {"detail": "ok"}


@router.post("/logout")
async def logout_endpoint(request: Request, response: Response):
    raw_refresh = request.cookies.get("refresh_token")
    settings = request.app.state.settings
    if raw_refresh:
        async with request.app.state.db_factory() as db:
            await logout(db, raw_refresh)
    clear_auth_cookies(response, settings)
    return {"detail": "ok"}


@router.get("/me", response_model=UserOut)
async def me(request: Request):
    user = await get_current_user(request)
    return UserOut(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        is_active=user.is_active,
    )
