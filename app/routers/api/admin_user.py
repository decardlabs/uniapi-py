from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import admin_auth
from app.schemas.common import GenericApiResponse, PaginatedResponse
from app.schemas.user import UserResponse
from app.services import user as user_service
from app.models.budget import CostRecord

router = APIRouter(tags=["admin-users"])


def _user_to_response(u, total_spent: float = 0.0) -> dict:
    return UserResponse(
        id=u.id,
        username=u.username,
        display_name=u.display_name or u.username,
        email=u.email,
        role=u.role,
        status=u.status,
        balance=u.balance,
        total_spent=total_spent,
        group=u.group,
        created_at=u.created_at // 1000 if u.created_at else 0,
        updated_at=u.updated_at // 1000 if u.updated_at else 0,
    ).model_dump()


async def _batch_total_spent(db: AsyncSession, user_ids: list[int]) -> dict[int, float]:
    """Return {user_id: total_spent_yuan} for the given user IDs."""
    if not user_ids:
        return {}
    result = await db.execute(
        select(CostRecord.user_id, func.sum(CostRecord.cost))
        .where(CostRecord.user_id.in_(user_ids))
        .group_by(CostRecord.user_id)
    )
    return {row[0]: round(float(row[1] or 0), 6) for row in result.all()}


@router.get("/api/user/")
async def list_users(
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    users, total = await user_service.list_users(db, page=p, size=size)
    user_ids = [u.id for u in users]
    spent_map = await _batch_total_spent(db, user_ids)
    return PaginatedResponse(
        data=[_user_to_response(u, spent_map.get(u.id, 0.0)) for u in users],
        total=total,
    )


@router.get("/api/user/search")
async def search_users(
    keyword: str = "",
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    users, total = await user_service.search_users(db, keyword=keyword, page=p, size=size)
    user_ids = [u.id for u in users]
    spent_map = await _batch_total_spent(db, user_ids)
    return PaginatedResponse(
        data=[_user_to_response(u, spent_map.get(u.id, 0.0)) for u in users],
        total=total,
    )


async def _user_to_response_with_spent(db: AsyncSession, u) -> dict:
    """Fetch a single user's response with total_spent populated."""
    spent_map = await _batch_total_spent(db, [u.id])
    return _user_to_response(u, spent_map.get(u.id, 0.0))


@router.get("/api/user/{user_id}")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    user = await user_service.get_user_by_id(db, user_id)
    if not user:
        return GenericApiResponse(success=False, message="User not found")
    return GenericApiResponse(data=await _user_to_response_with_spent(db, user))


@router.post("/api/user/")
async def create_user(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    user = await user_service.admin_create_user(
        db,
        username=body.get("username", ""),
        password=body.get("password", ""),
        display_name=body.get("display_name"),
        email=body.get("email"),
        quota=body.get("quota"),
        group=body.get("group"),
    )
    return GenericApiResponse(message="User created", data=await _user_to_response_with_spent(db, user))


@router.put("/api/user/")
async def update_user(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    user_id = body.get("id")
    if not user_id:
        return GenericApiResponse(success=False, message="User ID required")

    user = await user_service.admin_update_user(
        db,
        user_id=user_id,
        username=body.get("username"),
        display_name=body.get("display_name"),
        password=body.get("password"),
        email=body.get("email"),
        quota=body.get("quota"),
        group=body.get("group"),
        status=body.get("status"),
    )
    return GenericApiResponse(message="User updated", data=await _user_to_response_with_spent(db, user))


@router.delete("/api/user/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    await user_service.admin_delete_user(db, user_id)
    return GenericApiResponse(message="User deleted")


@router.post("/api/user/totp/disable/{user_id}")
async def disable_user_totp(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    await user_service.admin_disable_totp(db, user_id)
    return GenericApiResponse(message="TOTP disabled")


@router.post("/api/admin/users/{user_id}/unlock")
async def admin_unlock_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Unlock a permanently locked user account (sets locked_until=None)."""
    from app.models.user import User
    from fastapi import HTTPException

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.locked_until = None
    user.failed_login_attempts = 0
    await db.commit()
    return GenericApiResponse(
        data={"unlocked": True, "user_id": user_id, "username": user.username}
    )


@router.get("/api/group/")
async def list_groups(
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    groups = await user_service.list_groups(db)
    return GenericApiResponse(data=groups)
