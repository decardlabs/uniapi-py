"""Channel CRUD API — management endpoints for AI provider channels."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import admin_auth
from app.models.channel import Channel
from app.schemas.common import GenericApiResponse, PaginatedResponse

router = APIRouter(tags=["channels"])


@router.get("/api/channel/")
async def list_channels(
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    sort: str = "id",
    order: str = "desc",
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """List channels (paginated)."""
    sort_col = getattr(Channel, sort, Channel.id)
    order_fn = sort_col.desc() if order == "desc" else sort_col.asc()

    total_q = select(func.count()).select_from(Channel)
    total = await db.scalar(total_q) or 0

    result = await db.execute(
        select(Channel).order_by(order_fn).offset(p * size).limit(size)
    )
    channels = result.scalars().all()

    return PaginatedResponse(
        data=[_channel_to_dict(c) for c in channels],
        total=total,
    )


@router.get("/api/channel/search")
async def search_channels(
    keyword: str = "",
    size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Search channels by name or model keyword."""
    total_q = select(func.count()).select_from(Channel).where(
        or_(Channel.name.ilike(f"%{keyword}%"), Channel.models.ilike(f"%{keyword}%"))
    )
    total = await db.scalar(total_q) or 0

    result = await db.execute(
        select(Channel)
        .where(or_(Channel.name.ilike(f"%{keyword}%"), Channel.models.ilike(f"%{keyword}%")))
        .order_by(Channel.id.desc())
        .limit(size)
    )
    channels = result.scalars().all()

    return PaginatedResponse(
        data=[_channel_to_dict(c) for c in channels],
        total=total,
    )


@router.get("/api/channel/{channel_id}")
async def get_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Get a single channel by ID."""
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return GenericApiResponse(data=_channel_to_dict(channel))


@router.post("/api/channel/")
async def create_channel(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Create a new channel."""
    now = int(time.time() * 1000)
    channel = Channel(
        name=body.get("name", ""),
        type=body.get("type", 0),
        key=body.get("key", ""),
        status=body.get("status", 1),
        base_url=body.get("base_url", ""),
        models=body.get("models", ""),
        group=body.get("group", "default"),
        weight=body.get("weight", 0),
        priority=body.get("priority", 0),
        model_mapping=body.get("model_mapping", ""),
        created_time=now,
        created_at=now,
        updated_at=now,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return GenericApiResponse(data=_channel_to_dict(channel))


@router.put("/api/channel/")
async def update_channel(
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Update a channel. Supports both field updates and status-only toggle."""
    channel_id = body.get("id")
    if not channel_id:
        raise HTTPException(status_code=400, detail="id is required")

    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Status-only update (from manage action)
    is_status_only = request.query_params.get("status_only") == "1"
    if is_status_only:
        new_status = body.get("status")
        if new_status is not None:
            channel.status = int(new_status)
        # Also handle action field (enable/disable/check)
        action = body.get("action")
        if action == "enable":
            channel.status = 1
        elif action == "disable":
            channel.status = 2
        channel.updated_at = int(time.time() * 1000)
        await db.commit()
        return GenericApiResponse(data=_channel_to_dict(channel))

    # Full field update
    updatable = [
        "name", "type", "key", "status", "base_url", "models", "group",
        "weight", "priority", "model_mapping", "other",
    ]
    for field in updatable:
        if field in body:
            setattr(channel, field, body[field])
    channel.updated_at = int(time.time() * 1000)
    await db.commit()
    await db.refresh(channel)
    return GenericApiResponse(data=_channel_to_dict(channel))


@router.delete("/api/channel/{channel_id}")
async def delete_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Delete a single channel."""
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    await db.delete(channel)
    await db.commit()
    return GenericApiResponse(data={"deleted": channel_id})


@router.delete("/api/channel/disabled")
async def delete_disabled_channels(
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Delete all disabled channels."""
    result = await db.execute(select(Channel).where(Channel.status == 2))
    channels = result.scalars().all()
    count = len(channels)
    for c in channels:
        await db.delete(c)
    await db.commit()
    return GenericApiResponse(data={"deleted_count": count})


@router.get("/api/channel/test/{channel_id}")
async def test_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Test connectivity for a specific channel."""
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Simple connectivity test: try to GET the models endpoint
    import httpx
    base_url = channel.base_url or ""
    if not base_url:
        return GenericApiResponse(data={"channel_id": channel_id, "status": "skipped", "detail": "No base_url configured"})

    try:
        test_url = f"{base_url.rstrip('/')}/models"
        async with httpx.AsyncClient(timeout=10) as client:
            headers = {"Authorization": f"Bearer {channel.key}"} if channel.key else {}
            resp = await client.get(test_url, headers=headers)
            channel.test_time = int(time.time() * 1000)
            channel.response_time = int(time.time() * 1000 - channel.test_time) if channel.test_time else 0
            await db.commit()
            return GenericApiResponse(data={
                "channel_id": channel_id,
                "status": "ok" if resp.is_success else "error",
                "http_status": resp.status_code,
            })
    except Exception as exc:
        return GenericApiResponse(data={
            "channel_id": channel_id,
            "status": "error",
            "detail": str(exc),
        })


@router.get("/api/channel/test")
async def test_all_channels(
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Test connectivity for all enabled channels."""
    result = await db.execute(select(Channel).where(Channel.status == 1))
    channels = result.scalars().all()
    return GenericApiResponse(data={
        "total": len(channels),
        "tested": [c.name for c in channels],
    })


def _channel_to_dict(c: Channel) -> dict:
    """Convert Channel ORM to dict matching frontend Channel interface."""
    return {
        "id": c.id,
        "type": c.type,
        "key": c.key or "",
        "status": c.status,
        "name": c.name,
        "base_url": c.base_url or "",
        "models": c.models or "",
        "group": c.group,
        "model_mapping": c.model_mapping or "",
        "priority": c.priority,
        "weight": c.weight,
        "other_info": c.other or "",
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }
