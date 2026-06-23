from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import admin_auth, user_auth
from app.models.log import Log
from app.schemas.common import GenericApiResponse, PaginatedResponse

router = APIRouter(tags=["logs"])


def _log_to_dict(log: Log) -> dict:
    return {
        "id": log.id,
        "user_id": log.user_id,
        "created_at": log.created_at // 1000 if log.created_at else 0,
        "type": log.type,
        "content": log.content,
        "username": log.username,
        "token_name": log.token_name,
        "model_name": log.model_name,
        "quota": log.cost,
        "prompt_tokens": log.prompt_tokens,
        "completion_tokens": log.completion_tokens,
        "cached_prompt_tokens": log.cached_prompt_tokens,
        "cached_completion_tokens": log.cached_completion_tokens,
        "channel": log.channel_id,
        "channel_id": log.channel_id,
        "request_id": log.request_id,
        "trace_id": log.trace_id,
        "elapsed_time": log.elapsed_time,
        "is_stream": log.is_stream,
    }


@router.get("/api/log/self")
async def list_self_logs(
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    base = select(Log).where(Log.user_id == user.id).order_by(Log.id.desc())
    total_q = select(func.count()).select_from(base.subquery())
    total = await db.scalar(total_q) or 0
    result = await db.execute(base.offset(p * size).limit(size))
    logs = result.scalars().all()
    return PaginatedResponse(data=[_log_to_dict(l) for l in logs], total=total)


@router.get("/api/log/self/stat")
async def self_log_stats(
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    base = select(func.coalesce(func.sum(Log.cost), 0), func.count()).where(Log.user_id == user.id)
    result = await db.execute(base)
    row = result.one()
    return GenericApiResponse(data={
        "quota": row[0] or 0,
        "request_count": row[1] or 0,
    })


@router.get("/api/log/self/search")
async def search_self_logs(
    keyword: str = "",
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    base = select(Log).where(
        Log.user_id == user.id,
        Log.content.ilike(f"%{keyword}%"),
    ).order_by(Log.id.desc())
    total_q = select(func.count()).select_from(base.subquery())
    total = await db.scalar(total_q) or 0
    result = await db.execute(base.offset(p * size).limit(size))
    logs = result.scalars().all()
    return PaginatedResponse(data=[_log_to_dict(l) for l in logs], total=total)


@router.get("/api/log/")
async def list_all_logs(
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    base = select(Log).order_by(Log.id.desc())
    total_q = select(func.count()).select_from(base.subquery())
    total = await db.scalar(total_q) or 0
    result = await db.execute(base.offset(p * size).limit(size))
    logs = result.scalars().all()
    return PaginatedResponse(data=[_log_to_dict(l) for l in logs], total=total)


@router.get("/api/log/stat")
async def all_log_stats(
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    base = select(func.coalesce(func.sum(Log.cost), 0), func.count())
    result = await db.execute(base)
    row = result.one()
    return GenericApiResponse(data={
        "quota": row[0] or 0,
        "request_count": row[1] or 0,
    })


@router.get("/api/log/search")
async def search_all_logs(
    keyword: str = "",
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    base = select(Log).where(
        Log.content.ilike(f"%{keyword}%")
    ).order_by(Log.id.desc())
    total_q = select(func.count()).select_from(base.subquery())
    total = await db.scalar(total_q) or 0
    result = await db.execute(base.offset(p * size).limit(size))
    logs = result.scalars().all()
    return PaginatedResponse(data=[_log_to_dict(l) for l in logs], total=total)


@router.delete("/api/log/")
async def delete_logs(
    target_timestamp: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    stmt = sa_delete(Log).where(Log.created_at < target_timestamp)
    result = await db.execute(stmt)
    await db.commit()
    return GenericApiResponse(message=f"Deleted {result.rowcount} log entries")
