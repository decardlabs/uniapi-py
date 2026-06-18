from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.common import GenericApiResponse
from app.services.user import get_system_status

router = APIRouter(tags=["status"])


@router.get("/api/status")
async def status(db: AsyncSession = Depends(get_db)):
    data = await get_system_status(db)
    return GenericApiResponse(data=data)


@router.get("/api/status/channel")
async def channel_status(p: int = 0, size: int = 10):
    """Return channel health status (simplified MVP)."""
    return GenericApiResponse(data=[], total=0)
