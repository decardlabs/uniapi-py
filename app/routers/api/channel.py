"""Channel CRUD API — management endpoints for AI provider channels.

Route ordering note: specific paths (search, test, disabled) MUST be
defined BEFORE the {channel_id} parameterized route to avoid conflicts.
"""
from __future__ import annotations

import time
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import admin_auth
from app.models.channel import Channel
from app.models.log import Log
from app.schemas.common import GenericApiResponse, PaginatedResponse

router = APIRouter(tags=["channels"])


# ──────────────────────────────────────────────
# Static routes first (before {channel_id})
# ──────────────────────────────────────────────


@router.get("/api/channel/")
async def list_channels(
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    sort: str = "id",
    order: str = "desc",
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """List channels (paginated, sortable)."""
    sort_col = getattr(Channel, sort, Channel.id)
    order_fn = sort_col.desc() if order == "desc" else sort_col.asc()

    total = await db.scalar(select(func.count()).select_from(Channel)) or 0
    result = await db.execute(
        select(Channel).order_by(order_fn).offset(p * size).limit(size)
    )
    return PaginatedResponse(
        data=[_channel_to_dict(c) for c in result.scalars().all()],
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
    clause = or_(Channel.name.ilike(f"%{keyword}%"), Channel.models.ilike(f"%{keyword}%"))
    total = await db.scalar(select(func.count()).select_from(Channel).where(clause)) or 0
    result = await db.execute(
        select(Channel).where(clause).order_by(Channel.id.desc()).limit(size)
    )
    return PaginatedResponse(
        data=[_channel_to_dict(c) for c in result.scalars().all()],
        total=total,
    )


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
    """Update a channel. Supports full update or status-only toggle."""
    channel_id = body.get("id")
    if not channel_id:
        raise HTTPException(status_code=400, detail="id is required")

    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Status-only update (from manage action like enable/disable)
    if request.query_params.get("status_only") == "1" or body.get("action"):
        action = body.get("action", "")
        if action == "enable":
            channel.status = 1
        elif action == "disable":
            channel.status = 2
        elif body.get("status") is not None:
            channel.status = int(body["status"])
        channel.updated_at = int(time.time() * 1000)
        await db.commit()
        return GenericApiResponse(data=_channel_to_dict(channel))

    # Full field update
    for field in ("name", "type", "key", "status", "base_url", "models",
                   "group", "weight", "priority", "model_mapping", "other"):
        if field in body:
            setattr(channel, field, body[field])
    channel.updated_at = int(time.time() * 1000)
    await db.commit()
    await db.refresh(channel)
    return GenericApiResponse(data=_channel_to_dict(channel))


@router.get("/api/channel/test")
async def test_all_channels(
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Test connectivity for all enabled channels by calling their /models endpoint."""
    result = await db.execute(select(Channel).where(Channel.status == 1))
    channels = result.scalars().all()

    results = []
    for channel in channels:
        # Resolve base URL: channel setting → adaptor default
        base_url = channel.base_url
        if not base_url:
            from app.relay.registry import registry
            adaptor = registry.get(channel.type)
            if adaptor:
                base_url = adaptor.DEFAULT_BASE_URL

        if not base_url:
            results.append({"channel_id": channel.id, "name": channel.name, "status": "skipped", "detail": "No base_url"})
            continue

        api_key = channel.key
        if not api_key:
            from app.relay.registry import registry
            from app.config import settings
            from app.relay import channeltype
            key_map = {
                channeltype.DeepSeek: settings.deepseek_api_key,
                channeltype.GLM: settings.glm_api_key,
                channeltype.Moonshot: settings.kimi_api_key,
                channeltype.Minimax: settings.minimax_api_key,
                channeltype.AliBailian: settings.qwen_api_key,
            }
            api_key = key_map.get(channel.type, "")

        try:
            test_url = f"{base_url.rstrip('/')}/models"
            async with httpx.AsyncClient(timeout=10) as client:
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                resp = await client.get(test_url, headers=headers)
                channel.test_time = int(time.time() * 1000)
                status = "ok" if resp.is_success else "error"

            # Log the test request
            now_ms = int(time.time() * 1000)
            db.add(Log(
                user_id=0,
                created_at=now_ms,
                type=1,
                content=f"Channel test: {channel.name} ({base_url})",
                username="admin",
                model_name="",
                quota=0,
                channel_id=channel.id,
                request_id=uuid.uuid4().hex,
            ))

            results.append({
                "channel_id": channel.id,
                "name": channel.name,
                "status": status,
                "http_status": resp.status_code,
            })
        except Exception as exc:
            results.append({"channel_id": channel.id, "name": channel.name, "status": "error", "detail": str(exc)})

    await db.commit()
    return GenericApiResponse(data={"total": len(channels), "results": results})


@router.get("/api/channel/default-pricing")
async def channel_default_pricing(
    type: int = Query(0, alias="type"),
    _=Depends(admin_auth),
):
    """Return default pricing for a given channel type."""
    from app.relay.registry import registry
    adaptor = registry.get(type)
    if not adaptor:
        return GenericApiResponse(data={})
    from app.relay.adaptor import ModelConfig
    models = adaptor.get_supported_models()
    pricing = {}
    for name, cfg in models.items():
        pricing[name] = {
            "input_price": cfg.input_ratio,
            "output_price": cfg.output_ratio,
            "cached_input_price": cfg.cached_input_ratio,
        }
    return GenericApiResponse(data=pricing)


@router.get("/api/channel/metadata")
async def channel_metadata(
    type: int = Query(0, alias="type"),
    _=Depends(admin_auth),
):
    """Return metadata (supported params, capabilities) for a channel type."""
    return GenericApiResponse(data={
        "type": type,
        "capabilities": ["chat_completions", "claude_messages"],
    })


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

    # Resolve base URL: channel setting → adaptor default
    base_url = channel.base_url
    if not base_url:
        from app.relay.registry import registry
        adaptor = registry.get(channel.type)
        if adaptor:
            base_url = adaptor.DEFAULT_BASE_URL

    if not base_url:
        return GenericApiResponse(data={"channel_id": channel_id, "status": "skipped", "detail": "No base_url"})

    # Resolve API key: channel key → env var
    api_key = channel.key
    if not api_key:
        from app.config import settings
        from app.relay import channeltype
        key_map = {
            channeltype.DeepSeek: settings.deepseek_api_key,
            channeltype.GLM: settings.glm_api_key,
            channeltype.Moonshot: settings.kimi_api_key,
            channeltype.Minimax: settings.minimax_api_key,
            channeltype.AliBailian: settings.qwen_api_key,
        }
        api_key = key_map.get(channel.type, "")

    try:
        test_url = f"{base_url.rstrip('/')}/models"
        async with httpx.AsyncClient(timeout=10) as client:
            headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
            resp = await client.get(test_url, headers=headers)
            channel.test_time = int(time.time() * 1000)
            status = "ok" if resp.is_success else "error"

        # Log the test request
        now_ms = int(time.time() * 1000)
        db.add(Log(
            user_id=0,
            created_at=now_ms,
            type=1,
            content=f"Channel test: {channel.name} ({base_url})",
            username="admin",
            model_name="",
            quota=0,
            channel_id=channel_id,
            request_id=uuid.uuid4().hex,
        ))
        await db.commit()

        return GenericApiResponse(data={
            "channel_id": channel_id,
            "status": status,
            "http_status": resp.status_code,
        })
    except Exception as exc:
        return GenericApiResponse(data={"channel_id": channel_id, "status": "error", "detail": str(exc)})


@router.delete("/api/channel/disabled")
async def delete_disabled_channels(
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Delete all disabled channels."""
    result = await db.execute(select(Channel).where(Channel.status == 2))
    channels = result.scalars().all()
    for c in channels:
        await db.delete(c)
    await db.commit()
    return GenericApiResponse(data={"deleted_count": len(channels)})


# ──────────────────────────────────────────────
# Parameterized routes (keep at bottom)
# ──────────────────────────────────────────────


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
