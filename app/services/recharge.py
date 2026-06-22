"""Recharge business logic service."""
from __future__ import annotations

import time
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.log import Log
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


async def approve_recharge(
    db: AsyncSession,
    recharge_id: int,
    admin_id: int,
) -> RechargeRequest:
    req = await get_recharge_by_id(db, recharge_id)
    if req is None:
        raise ValueError(f"Recharge request {recharge_id} not found")
    if req.status != 1:
        raise ValueError(f"Recharge request {recharge_id} is not pending")

    now = int(time.time() * 1000)
    req.status = 2
    req.reviewer_id = admin_id
    req.reviewed_time = now

    # Add quota to user
    result = await db.execute(select(User).where(User.id == req.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError(f"User {req.user_id} not found")
    user.quota = (user.quota or 0) + req.amount

    # Create log entry
    log = Log(
        user_id=req.user_id,
        created_at=now,
        type=1,  # TOPUP
        content=f"Recharge approved: +{req.amount} quota (request #{recharge_id})",
        quota=req.amount,
    )
    db.add(log)
    await db.flush()
    await db.refresh(req)
    await db.commit()
    return req


async def reject_recharge(
    db: AsyncSession,
    recharge_id: int,
    admin_id: int,
    admin_remark: str,
) -> RechargeRequest:
    req = await get_recharge_by_id(db, recharge_id)
    if req is None:
        raise ValueError(f"Recharge request {recharge_id} not found")
    if req.status != 1:
        raise ValueError(f"Recharge request {recharge_id} is not pending")

    now = int(time.time() * 1000)
    req.status = 3
    req.reviewer_id = admin_id
    req.reviewed_time = now
    req.admin_remark = admin_remark

    await db.flush()
    await db.refresh(req)
    await db.commit()
    return req


async def admin_topup(
    db: AsyncSession,
    admin_id: int,
    user_id: int,
    quota: int,
    pool_id: int,
    remark: Optional[str] = None,
) -> dict:
    """Admin directly tops up a user's quota. Returns user info dict."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise ValueError(f"User {user_id} not found")

    now = int(time.time() * 1000)
    user.quota = (user.quota or 0) + quota

    log = Log(
        user_id=user_id,
        created_at=now,
        type=1,  # TOPUP
        content=f"Admin top-up: +{quota} quota (by admin #{admin_id})" + (f" [{remark}]" if remark else ""),
        quota=quota,
    )
    db.add(log)
    await db.flush()
    await db.commit()

    return {
        "id": user.id,
        "username": user.username,
        "quota": user.quota,
    }
