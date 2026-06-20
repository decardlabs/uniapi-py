from __future__ import annotations

import time
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token import Token
from app.services.auth import generate_token_key


async def list_tokens(
    db: AsyncSession,
    user_id: int,
    page: int = 0,
    size: int = 10,
) -> tuple[list[Token], int]:
    base = select(Token).where(Token.user_id == user_id).order_by(Token.id.desc())
    total_query = select(func.count()).select_from(base.subquery())
    total = await db.scalar(total_query)
    result = await db.execute(base.offset(page * size).limit(size))
    return list(result.scalars().all()), total or 0


async def search_tokens(
    db: AsyncSession,
    user_id: int,
    keyword: str,
    page: int = 0,
    size: int = 10,
) -> tuple[list[Token], int]:
    condition = or_(
        Token.name.ilike(f"%{keyword}%"),
        Token.key.ilike(f"%{keyword}%"),
    )
    base = select(Token).where(Token.user_id == user_id).where(condition)
    total_query = select(func.count()).select_from(base.subquery())
    total = await db.scalar(total_query)
    result = await db.execute(
        base.order_by(Token.id.desc()).offset(page * size).limit(size)
    )
    return list(result.scalars().all()), total or 0


async def get_token_by_id(db: AsyncSession, user_id: int, token_id: int) -> Optional[Token]:
    result = await db.execute(
        select(Token).where(Token.id == token_id, Token.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_token(
    db: AsyncSession,
    user_id: int,
    name: str,
    remain_quota: int = 0,
    unlimited_quota: bool = False,
    expired_time: int = -1,
    models: Optional[str | list[str]] = None,
    subnet: Optional[str] = None,
) -> Token:
    now = int(time.time())
    if isinstance(models, list):
        models = ",".join(str(m) for m in models)
    token = Token(
        user_id=user_id,
        key=generate_token_key(),
        name=name,
        status=1,
        remain_quota=remain_quota,
        unlimited_quota=unlimited_quota,
        used_quota=0,
        created_time=now,
        accessed_time=now,
        expired_time=expired_time,
        models=models,
        subnet=subnet or "",
        created_at=now * 1000,
        updated_at=now * 1000,
    )
    db.add(token)
    await db.flush()
    await db.commit()
    return token


async def update_token(
    db: AsyncSession,
    user_id: int,
    token_id: int,
    name: Optional[str] = None,
    remain_quota: Optional[int] = None,
    unlimited_quota: Optional[bool] = None,
    expired_time: Optional[int] = None,
    models: Optional[str | list[str]] = None,
    subnet: Optional[str] = None,
    status: Optional[int] = None,
) -> Token:
    token = await get_token_by_id(db, user_id, token_id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    now = int(time.time() * 1000)
    if name is not None:
        token.name = name
    if remain_quota is not None:
        token.remain_quota = remain_quota
    if unlimited_quota is not None:
        token.unlimited_quota = unlimited_quota
    if expired_time is not None:
        token.expired_time = expired_time
    if models is not None:
        if isinstance(models, list):
            models = ",".join(str(m) for m in models)
        token.models = models
    if subnet is not None:
        token.subnet = subnet
    if status is not None:
        token.status = status
    token.updated_at = now
    await db.commit()
    return token


async def delete_token(db: AsyncSession, user_id: int, token_id: int) -> None:
    token = await get_token_by_id(db, user_id, token_id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")
    await db.delete(token)
    await db.commit()
