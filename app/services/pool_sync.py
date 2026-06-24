"""Real-time pool consumption sync from API relay usage.

Deducts API call cost from the single global BudgetPool after each
relay request, keeping pool.total_consumed in sync with actual spending.

The pool is a single global ledger (root-owned), not per-user allocations.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.budget import BudgetPool, PoolTransaction

logger = logging.getLogger(__name__)


async def sync_consumption_to_pool(
    db: AsyncSession,
    user_id: int,
    cost_yuan: float,
    model_name: str = "",
    request_id: str = "",
) -> None:
    """Deduct API consumption from the active budget pool directly.

    This runs after CostRecord is written. It finds the active pool
    (no per-user allocation), deducts total_consumed, and records a
    PoolTransaction. This is a non-critical operation — failures are
    silently logged, never propagated.

    Args:
        db: Database session (must be in an active transaction).
        user_id: The user who made the API call.
        cost_yuan: Actual cost in yuan (float, from CostRecord).
        model_name: Model used (for transaction remark).
        request_id: Relay request ID (for transaction traceability).
    """
    if cost_yuan <= 0:
        return

    # Find the active pool — no per-user allocation, pool is the global ledger
    result = await db.execute(
        select(BudgetPool).where(BudgetPool.status == "active").order_by(BudgetPool.id).limit(1)
    )
    pool = result.scalar_one_or_none()
    if not pool:
        return  # No active pool — nothing to sync (not an error, pool may not be set up yet)

    now = int(time.time() * 1000)

    # Cap at remaining available balance to avoid negative available
    available = pool.total_funded - pool.total_consumed
    actual = min(cost_yuan, available)
    if actual <= 0.001:  # Skip micro-amounts (less than 0.1 fen)
        return

    pool.total_consumed = round(pool.total_consumed + actual, 4)

    remark = f"API: {model_name}" if model_name else "API usage"
    if request_id:
        remark += f" [{request_id[:12]}]"

    db.add(PoolTransaction(
        pool_id=pool.id,
        type="consume",
        amount=round(actual, 4),
        user_id=user_id,
        remark=remark,
        created_at=now,
    ))

    logger.debug(
        "Pool sync | user=%d cost=%.6f pool_consumed=%.4f",
        user_id, actual, pool.total_consumed,
    )
