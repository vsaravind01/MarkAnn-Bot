from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import RefreshToken, User
from gateway.admin.schemas import UserOut


def _to_user_out(user: User) -> dict:
    return UserOut.model_validate(user).model_dump(mode="json")


async def list_users(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    role: str | None = None,
) -> dict:
    offset = (page - 1) * page_size
    base_query = select(User)
    count_query = select(func.count()).select_from(User)
    if role:
        base_query = base_query.where(User.role == role)
        count_query = count_query.where(User.role == role)

    total = (await db.execute(count_query)).scalar_one()
    users = (await db.execute(base_query.offset(offset).limit(page_size))).scalars().all()
    return {
        "items": [_to_user_out(user) for user in users],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    return (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()


async def patch_user(
    db: AsyncSession,
    user_id: int,
    is_active: bool | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> User:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise LookupError("User not found")
    if user.role == "superuser" and is_active is False:
        raise ValueError("Cannot disable the superuser")
    # Role changes are intentionally not exposed here — PatchUserBody has no `role`
    # field, so demotion/promotion is structurally impossible via this path.

    if is_active is not None:
        user.is_active = is_active
        if not is_active:
            await db.execute(
                update(RefreshToken).where(RefreshToken.user_id == user_id).values(revoked=True)
            )
    if first_name is not None:
        user.first_name = first_name
    if last_name is not None:
        user.last_name = last_name

    await db.commit()
    await db.refresh(user)
    return user
