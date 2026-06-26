from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import root_auth
from app.models.option import Option
from app.schemas.common import GenericApiResponse
from app.schemas.management import OptionUpdateRequest

router = APIRouter(tags=["options"])


@router.get("/api/option/")
async def list_options(
    db: AsyncSession = Depends(get_db),
    _=Depends(root_auth),
):
    result = await db.execute(select(Option))
    opts = result.scalars().all()
    return GenericApiResponse(
        data=[{"key": o.key, "value": o.value} for o in opts]
    )


@router.put("/api/option/")
async def update_option(
    body: OptionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(root_auth),
):
    key = body.key
    value = body.value
    if not key:
        return GenericApiResponse(success=False, message="Key required")

    import time
    result = await db.execute(select(Option).where(Option.key == key))
    opt = result.scalar_one_or_none()
    now = int(time.time() * 1000)
    if opt:
        opt.value = str(value)
        opt.updated_at = now
    else:
        db.add(Option(key=key, value=str(value), created_at=now, updated_at=now))
    await db.commit()
    return GenericApiResponse(message="Option updated")
