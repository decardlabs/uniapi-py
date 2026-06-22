"""Redemption code business logic service."""
from __future__ import annotations

import secrets
import string
import time
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.redemption import RedemptionCode


def _generate_code(length: int = 12) -> str:
    """Generate a random alphanumeric redemption code."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


async def create_redemption_codes(
    db: AsyncSession,
    admin_id: int,
    name: str,
    quota: int,
    count: int = 1,
) -> list[RedemptionCode]:
    now = int(time.time() * 1000)
    codes = []
    for _ in range(count):
        code_str = _generate_code()
        # Ensure uniqueness
        while True:
            existing = await db.execute(select(RedemptionCode).where(RedemptionCode.code == code_str))
            if existing.scalar_one_or_none() is None:
                break
            code_str = _generate_code()

        rc = RedemptionCode(
            name=name,
            code=code_str,
            quota=quota,
            status=1,
            created_by=admin_id,
            created_time=now,
        )
        db.add(rc)
        codes.append(rc)

    await db.flush()
    for c in codes:
        await db.refresh(c)
    await db.commit()
    return codes


async def list_codes(
    db: AsyncSession,
    page: int = 0,
    size: int = 10,
) -> tuple[list[dict], int]:
    count_q = select(func.count(RedemptionCode.id))
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    q = (
        select(RedemptionCode)
        .order_by(RedemptionCode.id.desc())
        .offset(page * size)
        .limit(size)
    )
    result = await db.execute(q)
    rows = result.scalars().all()

    data = []
    for rc in rows:
        data.append({
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
    return data, total


async def search_codes(
    db: AsyncSession,
    keyword: str,
) -> list[dict]:
    q = (
        select(RedemptionCode)
        .where(RedemptionCode.name.ilike(f"%{keyword}%"))
        .order_by(RedemptionCode.id.desc())
    )
    result = await db.execute(q)
    rows = result.scalars().all()

    return [
        {
            "id": rc.id,
            "name": rc.name,
            "code": rc.code,
            "quota": rc.quota,
            "status": rc.status,
            "used_by": rc.used_by,
            "used_time": rc.used_time,
            "created_by": rc.created_by,
            "created_time": rc.created_time,
        }
        for rc in rows
    ]


async def get_code(db: AsyncSession, code_id: int) -> RedemptionCode | None:
    result = await db.execute(select(RedemptionCode).where(RedemptionCode.id == code_id))
    return result.scalar_one_or_none()


async def update_code(
    db: AsyncSession,
    code_id: int,
    name: Optional[str] = None,
    quota: Optional[int] = None,
    status_only: bool = False,
    status: Optional[int] = None,
) -> RedemptionCode:
    rc = await get_code(db, code_id)
    if rc is None:
        raise ValueError(f"Redemption code {code_id} not found")

    if status_only and status is not None:
        rc.status = status
    else:
        if name is not None:
            rc.name = name
        if quota is not None:
            rc.quota = quota

    await db.flush()
    await db.refresh(rc)
    await db.commit()
    return rc


async def delete_code(db: AsyncSession, code_id: int) -> None:
    rc = await get_code(db, code_id)
    if rc is None:
        raise ValueError(f"Redemption code {code_id} not found")
    await db.delete(rc)
    await db.flush()
    await db.commit()
