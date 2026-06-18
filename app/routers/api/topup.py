"""Top-up and recharge API stubs."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import admin_auth, user_auth
from app.schemas.common import GenericApiResponse, PaginatedResponse

router = APIRouter(tags=["topup"])


# ── Topup ──

@router.get("/api/topup/")
async def list_topups(db: AsyncSession = Depends(get_db), _=Depends(admin_auth)):
    return PaginatedResponse(data=[], total=0)


@router.post("/api/topup/")
async def create_topup(db: AsyncSession = Depends(get_db), _=Depends(user_auth)):
    return GenericApiResponse(data={"id": 0})


@router.put("/api/topup/")
async def update_topup(db: AsyncSession = Depends(get_db), _=Depends(admin_auth)):
    return GenericApiResponse(data={"updated": True})


# ── Recharge (user-facing) ──

@router.get("/api/recharge/self")
async def list_self_recharges(db: AsyncSession = Depends(get_db), _=Depends(user_auth)):
    return PaginatedResponse(data=[], total=0)


@router.post("/api/recharge/")
async def create_recharge(db: AsyncSession = Depends(get_db), _=Depends(user_auth)):
    return GenericApiResponse(data={"id": 0})


# ── Recharge (admin) ──

@router.get("/api/recharge/")
async def list_recharges(db: AsyncSession = Depends(get_db), _=Depends(admin_auth)):
    return PaginatedResponse(data=[], total=0)


@router.post("/api/recharge/{recharge_id}/approve")
async def approve_recharge(db: AsyncSession = Depends(get_db), _=Depends(admin_auth)):
    return GenericApiResponse(data={"approved": True})


@router.post("/api/recharge/{recharge_id}/reject")
async def reject_recharge(db: AsyncSession = Depends(get_db), _=Depends(admin_auth)):
    return GenericApiResponse(data={"rejected": True})
