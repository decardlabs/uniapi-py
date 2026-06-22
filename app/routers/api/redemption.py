"""Redemption codes API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import admin_auth
from app.schemas.common import GenericApiResponse, PaginatedResponse
from app.schemas.redemption import RedemptionCreate, RedemptionUpdate
from app.services import redemption as redemption_service

router = APIRouter(tags=["redemption"])


@router.get("/api/redemption/")
async def list_redemptions(
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    data, total = await redemption_service.list_codes(db, page=p, size=size)
    return PaginatedResponse(data=data, total=total)


@router.get("/api/redemption/search")
async def search_redemptions(
    keyword: str = Query(""),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    data = await redemption_service.search_codes(db, keyword)
    return PaginatedResponse(data=data, total=len(data))


@router.get("/api/redemption/{redemption_id}")
async def get_redemption(
    redemption_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    rc = await redemption_service.get_code(db, redemption_id)
    if rc is None:
        return GenericApiResponse(success=False, message="Redemption code not found")
    return GenericApiResponse(data={
        "id": rc.id,
        "name": rc.name,
        "code": rc.code,
        "quota": rc.quota,
        "status": rc.status,
        "used_by": rc.used_by,
        "used_time": rc.used_time,
        "created_by": rc.created_by,
        "created_time": rc.created_time,
    })


@router.post("/api/redemption/")
async def create_redemption(
    body: RedemptionCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    codes = await redemption_service.create_redemption_codes(
        db,
        admin_id=request.state.user.id,
        name=body.name,
        quota=body.quota,
        count=body.count,
    )
    first = codes[0]
    return GenericApiResponse(data={
        "id": first.id,
        "name": first.name,
        "code": first.code,
        "quota": first.quota,
        "status": first.status,
        "created_by": first.created_by,
        "created_time": first.created_time,
    })


@router.put("/api/redemption/")
async def update_redemption(
    body: RedemptionUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    try:
        rc = await redemption_service.update_code(
            db,
            code_id=body.id,
            name=body.name,
            quota=body.quota,
            status_only=body.status_only,
            status=body.status,
        )
        return GenericApiResponse(data={
            "id": rc.id,
            "name": rc.name,
            "code": rc.code,
            "quota": rc.quota,
            "status": rc.status,
        })
    except ValueError as e:
        return GenericApiResponse(success=False, message=str(e))


@router.delete("/api/redemption/{redemption_id}")
async def delete_redemption(
    redemption_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    try:
        await redemption_service.delete_code(db, redemption_id)
        return GenericApiResponse(data={"deleted": True})
    except ValueError as e:
        return GenericApiResponse(success=False, message=str(e))
