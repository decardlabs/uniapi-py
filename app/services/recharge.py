"""Recharge business logic service."""
from __future__ import annotations

import time
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recharge import RechargeRequest
from app.models.user import User


async def create_recharge(
    db: AsyncSession,
    user_id: int,
    amount: int,
    remark: Optional[str] = None,
) -> RechargeRequest:
    # Verify user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError(f"User {user_id} not found")

    now = int(time.time() * 1000)
    req = RechargeRequest(
        user_id=user_id,
        amount=amount,
        status=1,
        remark=remark,
        created_time=now,
    )
    db.add(req)
    await db.flush()
    await db.refresh(req)
    await db.commit()
    return req


async def list_recharges(
    db: AsyncSession,
    page: int = 0,
    size: int = 10,
) -> tuple[list[dict], int]:
    """Admin list all recharge requests with user info joined."""
    count_q = select(func.count(RechargeRequest.id))
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    q = (
        select(RechargeRequest, User.username)
        .outerjoin(User, RechargeRequest.user_id == User.id)
        .order_by(RechargeRequest.id.desc())
        .offset(page * size)
        .limit(size)
    )
    result = await db.execute(q)
    rows = result.all()

    data = []
    for req, username in rows:
        item = {
            "id": req.id,
            "user_id": req.user_id,
            "amount": req.amount,
            "status": req.status,
            "remark": req.remark,
            "admin_remark": req.admin_remark,
            "reviewer_id": req.reviewer_id,
            "reviewed_time": req.reviewed_time,
            "created_time": req.created_time,
            "username": username,
        }
        data.append(item)
    return data, total


async def list_self_recharges(
    db: AsyncSession,
    user_id: int,
    page: int = 0,
    size: int = 10,
) -> tuple[list[dict], int]:
    count_q = select(func.count(RechargeRequest.id)).where(RechargeRequest.user_id == user_id)
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    q = (
        select(RechargeRequest)
        .where(RechargeRequest.user_id == user_id)
        .order_by(RechargeRequest.id.desc())
        .offset(page * size)
        .limit(size)
    )
    result = await db.execute(q)
    rows = result.scalars().all()

    data = []
    for req in rows:
        item = {
            "id": req.id,
            "user_id": req.user_id,
            "amount": req.amount,
            "status": req.status,
            "remark": req.remark,
            "admin_remark": req.admin_remark,
            "reviewer_id": req.reviewer_id,
            "reviewed_time": req.reviewed_time,
            "created_time": req.created_time,
        }
        data.append(item)
    return data, total


async def get_recharge_by_id(db: AsyncSession, recharge_id: int) -> RechargeRequest | None:
    result = await db.execute(select(RechargeRequest).where(RechargeRequest.id == recharge_id))
    return result.scalar_one_or_none()
