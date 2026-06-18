"""Redemption codes API stubs."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import admin_auth
from app.schemas.common import GenericApiResponse, PaginatedResponse

router = APIRouter(tags=["redemption"])


@router.get("/api/redemption/")
async def list_redemptions(db: AsyncSession = Depends(get_db), _=Depends(admin_auth)):
    return PaginatedResponse(data=[], total=0)


@router.get("/api/redemption/search")
async def search_redemptions(db: AsyncSession = Depends(get_db), _=Depends(admin_auth)):
    return PaginatedResponse(data=[], total=0)


@router.get("/api/redemption/{redemption_id}")
async def get_redemption(db: AsyncSession = Depends(get_db), _=Depends(admin_auth)):
    return GenericApiResponse(data={"id": 0})


@router.post("/api/redemption/")
async def create_redemption(db: AsyncSession = Depends(get_db), _=Depends(admin_auth)):
    return GenericApiResponse(data={"id": 0})


@router.put("/api/redemption/")
async def update_redemption(db: AsyncSession = Depends(get_db), _=Depends(admin_auth)):
    return GenericApiResponse(data={"id": 0})


@router.delete("/api/redemption/{redemption_id}")
async def delete_redemption(db: AsyncSession = Depends(get_db), _=Depends(admin_auth)):
    return GenericApiResponse(data={"deleted": True})
