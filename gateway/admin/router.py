from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.exc import IntegrityError

from gateway.admin.schemas import UserOut
from gateway.admin.service import get_user_by_id, list_users, patch_user
from gateway.auth.deps import get_current_user, require_roles
from gateway.auth.service import register_admin
from gateway.auth.tokens import set_auth_cookies

router = APIRouter(prefix="/auth/admin", tags=["admin"])


class AdminRegisterBody(BaseModel):
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


class PatchUserBody(BaseModel):
    is_active: bool | None = None
    first_name: str | None = None
    last_name: str | None = None


@router.post("/register")
async def admin_register(body: AdminRegisterBody, request: Request):
    settings = request.app.state.settings
    is_bootstrap = False
    current_user = None
    token = request.cookies.get("access_token")
    if token:
        current_user = await get_current_user(request)
        if current_user.role != "superuser":
            raise HTTPException(status_code=403, detail="Only superuser can create admins")
        created_by_id = current_user.id
    else:
        created_by_id = None

    async with request.app.state.db_factory() as db:
        try:
            access, refresh, created_user = await register_admin(
                db,
                body.email,
                body.password,
                body.first_name,
                body.last_name,
                created_by_id,
                settings,
            )
            is_bootstrap = created_user.role == "superuser"
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except IntegrityError as exc:
            await db.rollback()
            if created_by_id is None and "ux_users_single_superuser" in str(exc):
                raise HTTPException(
                    status_code=403, detail="Bootstrap already completed; authenticate as superuser"
                ) from exc
            raise HTTPException(status_code=409, detail="Email already registered") from exc

    response = JSONResponse(
        {"email": created_user.email, "role": created_user.role, "id": created_user.id}
    )
    if is_bootstrap or current_user is None:
        set_auth_cookies(response, access, refresh, settings)
    return response


@router.get("/users")
async def list_all_users(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    _ = await require_roles("superuser")(request)
    async with request.app.state.db_factory() as db:
        return await list_users(db, page=page, page_size=page_size)


@router.get("/users/{user_id}")
async def get_user(user_id: int, request: Request):
    _ = await require_roles("superuser")(request)
    async with request.app.state.db_factory() as db:
        user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.model_validate(user).model_dump(mode="json")


@router.patch("/users/{user_id}")
async def patch_user_endpoint(user_id: int, body: PatchUserBody, request: Request):
    _ = await require_roles("superuser")(request)
    async with request.app.state.db_factory() as db:
        try:
            user = await patch_user(
                db,
                user_id,
                is_active=body.is_active,
                first_name=body.first_name,
                last_name=body.last_name,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return UserOut.model_validate(user).model_dump(mode="json")


@router.get("/traders")
async def list_traders(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    _ = await require_roles("admin", "superuser")(request)
    async with request.app.state.db_factory() as db:
        return await list_users(db, page=page, page_size=page_size, role="trader")


@router.patch("/traders/{user_id}")
async def patch_trader_endpoint(user_id: int, body: PatchUserBody, request: Request):
    _ = await require_roles("admin", "superuser")(request)
    async with request.app.state.db_factory() as db:
        existing_user = await get_user_by_id(db, user_id)
        if existing_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        if existing_user.role != "trader":
            raise HTTPException(status_code=422, detail="Target user is not a trader")
        try:
            user = await patch_user(
                db,
                user_id,
                is_active=body.is_active,
                first_name=body.first_name,
                last_name=body.last_name,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return UserOut.model_validate(user).model_dump(mode="json")
