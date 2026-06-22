"""Top-up and recharge API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import admin_auth, user_auth
from app.schemas.common import GenericApiResponse, PaginatedResponse
from app.schemas.recharge import RechargeCreate, TopUpRequest
from app.services import recharge as recharge_service

router = APIRouter(tags=["topup"])


# ── Admin direct top-up ──

@router.post("/api/topup/")
async def admin_topup(
    body: TopUpRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Admin directly tops up a user's quota without going through the request/approve flow."""
    admin_id = request.state.user.id
    try:
        result = await recharge_service.admin_topup(
            db,
            admin_id=admin_id,
            user_id=body.user_id,
            quota=body.quota,
            remark=body.remark,
            pool_id=body.pool_id,
        )
        return GenericApiResponse(data=result)
    except ValueError as e:
        return GenericApiResponse(success=False, message=str(e))


@router.get("/api/topup/")
async def list_topups(
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Admin lists all recharge requests (alias for /api/recharge/)."""
    data, total = await recharge_service.list_recharges(db, page=p, size=size)
    return PaginatedResponse(data=data, total=total)


@router.put("/api/topup/")
async def update_topup(
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Admin action on a recharge request via unified PUT (backward compat).

    Body: { id, action: "approve"|"reject", admin_remark?: str }
    """
    recharge_id = body.get("id")
    action = body.get("action")
    admin_remark = body.get("admin_remark", "")
    admin_id = request.state.user.id

    if not recharge_id or action not in ("approve", "reject"):
        return GenericApiResponse(success=False, message="id and action (approve|reject) required")

    try:
        if action == "approve":
            await recharge_service.approve_recharge(db, recharge_id, admin_id)
        else:
            await recharge_service.reject_recharge(db, recharge_id, admin_id, admin_remark or "Rejected by admin")
        return GenericApiResponse(data={"updated": True})
    except ValueError as e:
        return GenericApiResponse(success=False, message=str(e))


# ── Recharge (user-facing) ──

@router.get("/api/recharge/self")
async def list_self_recharges(
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=50),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    _=Depends(user_auth),
):
    """User lists their own recharge requests."""
    user_id = request.state.user.id
    data, total = await recharge_service.list_self_recharges(db, user_id, page=p, size=size)
    return PaginatedResponse(data=data, total=total)


@router.post("/api/recharge/")
async def create_recharge(
    body: RechargeCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(user_auth),
):
    """User creates a recharge request (pending admin approval)."""
    user_id = request.state.user.id
    req = await recharge_service.create_recharge(
        db, user_id=user_id, amount=body.amount, remark=body.remark,
    )
    return GenericApiResponse(data={"id": req.id})


# ── Recharge (admin) ──

@router.get("/api/recharge/")
async def list_recharges(
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Admin lists all recharge requests."""
    data, total = await recharge_service.list_recharges(db, page=p, size=size)
    return PaginatedResponse(data=data, total=total)


@router.post("/api/recharge/{recharge_id}/approve")
async def approve_recharge(
    recharge_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Admin approves a pending recharge request and credits the user's quota."""
    admin_id = request.state.user.id
    try:
        await recharge_service.approve_recharge(db, recharge_id, admin_id)
        return GenericApiResponse(data={"approved": True})
    except ValueError as e:
        return GenericApiResponse(success=False, message=str(e))


@router.post("/api/recharge/{recharge_id}/reject")
async def reject_recharge(
    recharge_id: int,
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Admin rejects a pending recharge request."""
    admin_id = request.state.user.id
    admin_remark = body.get("admin_remark", "Rejected by admin")
    try:
        await recharge_service.reject_recharge(db, recharge_id, admin_id, admin_remark)
        return GenericApiResponse(data={"rejected": True})
    except ValueError as e:
        return GenericApiResponse(success=False, message=str(e))
