"""Budget Pool API — allocate shared budget pools to individual user budgets."""
from __future__ import annotations

import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import admin_auth
from app.models.budget import Budget, BudgetPool, PoolAllocation, PoolTransaction, CostRecord
from app.models.log import Log
from app.models.user import User
from app.budget.arbiter import BudgetArbiter
from app.schemas.common import GenericApiResponse, PaginatedResponse

router = APIRouter(tags=["pools"])


# ── Helpers ────────────────────────────────────────────

def _pool_to_dict(pool: BudgetPool) -> dict:
    return {
        "id": pool.id,
        "name": pool.name,
        "total_funded": round(pool.total_funded, 4),
        "total_allocated": round(pool.total_allocated, 4),
        "total_consumed": round(pool.total_consumed, 4),
        "period_type": pool.period_type,
        "period_key": pool.period_key,
        "status": pool.status,
        "created_at": pool.created_at,
        "closed_at": pool.closed_at,
    }


def _allocation_to_dict(a: PoolAllocation, username: str = "") -> dict:
    net_alloc = a.amount - a.recalled
    remaining = max(0.0, net_alloc - a.consumed)
    return {
        "id": a.id,
        "pool_id": a.pool_id,
        "user_id": a.user_id,
        "username": username,
        "amount": round(a.amount, 4),
        "consumed": round(a.consumed, 4),
        "recalled": round(a.recalled, 4),
        "net_allocated": round(net_alloc, 4),
        "remaining": round(remaining, 4),
        "status": a.status,
        "created_at": a.created_at,
        "updated_at": a.updated_at,
    }


def _tx_to_dict(tx: PoolTransaction) -> dict:
    return {
        "id": tx.id,
        "pool_id": tx.pool_id,
        "type": tx.type,
        "amount": round(tx.amount, 4),
        "user_id": tx.user_id,
        "allocation_id": tx.allocation_id,
        "remark": tx.remark,
        "created_at": tx.created_at,
    }


def _period_ms_range(period_key: str, period_type: str = "monthly") -> tuple[int, int]:
    """Return (start_ms, end_ms) for a period key.

    Supports:
      - "YYYY-MM" (monthly)
      - "YYYY"    (yearly)
      - "YYYY-QN" (quarterly, e.g. "2026-Q1")
      - ""        (oneoff → returns (0, 0): no time filter)
    """
    if not period_key:
        return 0, 0

    # Yearly: single year → Jan 1 of that year to Jan 1 of next year
    if period_type == "yearly" or (period_key.isdigit() and len(period_key) == 4):
        y = int(period_key)
        start = int(datetime(y, 1, 1).timestamp() * 1000)
        end = int(datetime(y + 1, 1, 1).timestamp() * 1000)
        return start, end

    # Quarterly: "YYYY-QN"
    if period_type == "quarterly" or (len(period_key) == 7 and period_key[4] == '-' and period_key[5] == 'Q'):
        parts = period_key.split("-Q")
        y = int(parts[0])
        q = int(parts[1])
        start_month = (q - 1) * 3 + 1
        end_month = start_month + 3
        if end_month > 12:
            end_month -= 12
            start = int(datetime(y, start_month, 1).timestamp() * 1000)
            end = int(datetime(y + 1, 1, 1).timestamp() * 1000)
        else:
            start = int(datetime(y, start_month, 1).timestamp() * 1000)
            end = int(datetime(y, end_month, 1).timestamp() * 1000)
        return start, end

    # Monthly: "YYYY-MM" (default / fallback)
    parts = period_key.split("-")
    year, month = int(parts[0]), int(parts[1])
    start = int(datetime(year, month, 1).timestamp() * 1000)
    if month == 12:
        end = int(datetime(year + 1, 1, 1).timestamp() * 1000)
    else:
        end = int(datetime(year, month + 1, 1).timestamp() * 1000)
    return start, end


# ── Pool CRUD ──────────────────────────────────────────

@router.get("/api/pool/")
async def list_pools(
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    status: str = "",
    period_type: str = "",
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """List budget pools (paginated)."""
    q = select(BudgetPool)
    if status:
        q = q.where(BudgetPool.status == status)
    if period_type:
        q = q.where(BudgetPool.period_type == period_type)
    q = q.order_by(BudgetPool.created_at.desc())

    total_q = select(func.count()).select_from(q.subquery())
    total = await db.scalar(total_q) or 0

    result = await db.execute(q.offset(p * size).limit(size))
    pools = result.scalars().all()

    return PaginatedResponse(
        data=[_pool_to_dict(p) for p in pools],
        total=total,
    )


@router.post("/api/pool/")
async def create_pool(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Create a new budget pool."""
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Pool name is required")
    total_funded = float(body.get("total_funded", 0))
    if total_funded < 0:
        raise HTTPException(status_code=400, detail="total_funded must be >= 0")
    period_type = body.get("period_type", "monthly")
    period_key = body.get("period_key", "").strip()
    if not period_key:
        raise HTTPException(status_code=400, detail="period_key is required (e.g. 2026-06)")

    now = int(time.time() * 1000)
    pool = BudgetPool(
        name=name,
        total_funded=total_funded,
        period_type=period_type,
        period_key=period_key,
        status="active",
        created_at=now,
    )
    db.add(pool)
    await db.flush()

    # Record initial funding transaction
    if total_funded > 0:
        tx = PoolTransaction(
            pool_id=pool.id,
            type="fund",
            amount=total_funded,
            remark="Initial funding",
            created_at=now,
        )
        db.add(tx)

    await db.commit()
    return GenericApiResponse(data=_pool_to_dict(pool))


@router.get("/api/pool/{pool_id}")
async def get_pool(
    pool_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Get pool details."""
    result = await db.execute(select(BudgetPool).where(BudgetPool.id == pool_id))
    pool = result.scalar_one_or_none()
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    return GenericApiResponse(data=_pool_to_dict(pool))


# ── Fund ───────────────────────────────────────────────

@router.post("/api/pool/{pool_id}/fund")
async def fund_pool(
    pool_id: int,
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Add funds to a pool."""
    result = await db.execute(select(BudgetPool).where(BudgetPool.id == pool_id))
    pool = result.scalar_one_or_none()
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    if pool.status != "active":
        raise HTTPException(status_code=400, detail="Pool is not active")

    amount = float(body.get("amount", 0))
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be > 0")

    remark = body.get("remark", "")

    now = int(time.time() * 1000)
    pool.total_funded += amount
    tx = PoolTransaction(
        pool_id=pool.id,
        type="fund",
        amount=amount,
        remark=remark,
        created_at=now,
    )
    db.add(tx)

    # Log: pool funded
    admin_user = request.state.user
    db.add(Log(
        created_at=now,
        type=3,  # MANAGE
        content=f"Pool \"{pool.name}\" funded +¥{amount:.2f} by {admin_user.username}",
        cost=0,
        request_id=uuid.uuid4().hex,
    ))
    await db.commit()
    return GenericApiResponse(data=_pool_to_dict(pool))


# ── Allocate ───────────────────────────────────────────

@router.post("/api/pool/{pool_id}/allocate")
async def allocate_to_user(
    pool_id: int,
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Allocate budget from pool to a user (legacy — not used in recharge flow).

    Creates a PoolAllocation record and increases the user's
    Budget.monthly_budget. The recharge/approve flow does NOT use
    PoolAllocation — it deducts directly from the pool's total_consumed.
    """
    result = await db.execute(select(BudgetPool).where(BudgetPool.id == pool_id))
    pool = result.scalar_one_or_none()
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    if pool.status != "active":
        raise HTTPException(status_code=400, detail="Pool is not active")

    user_id = int(body.get("user_id", 0))
    amount = float(body.get("amount", 0))
    if user_id <= 0 or amount <= 0:
        raise HTTPException(status_code=400, detail="Valid user_id and amount > 0 required")

    # Check pool has enough available
    available = pool.total_funded - pool.total_allocated
    if amount > available:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient pool balance. Available: {available:.4f}, requested: {amount:.4f}",
        )

    remark = body.get("remark", "")
    now = int(time.time() * 1000)

    # 1. Create allocation
    allocation = PoolAllocation(
        pool_id=pool.id,
        user_id=user_id,
        amount=amount,
        status="active",
        created_at=now,
        updated_at=now,
    )
    db.add(allocation)

    # 2. Update pool totals
    pool.total_allocated += amount

    # 3. Record transaction
    tx = PoolTransaction(
        pool_id=pool.id,
        type="allocate",
        amount=amount,
        user_id=user_id,
        remark=remark,
        created_at=now,
    )
    db.add(tx)

    # 4. Increase user's Budget.monthly_budget and balance
    budget_result = await db.execute(select(Budget).where(Budget.user_id == user_id))
    budget = budget_result.scalar_one_or_none()
    if budget:
        budget.monthly_budget += amount
        budget.updated_at = now
    else:
        budget = Budget(
            user_id=user_id,
            monthly_budget=amount,
            consumed=0.0,
            frozen=0.0,
            created_at=now,
            updated_at=now,
        )
        db.add(budget)

    # 5. Credit user's micro-yuan balance
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user:
        user.balance = (user.balance or 0) + int(amount * 1_000_000)

    # Log: pool allocated
    admin_user = request.state.user
    db.add(Log(
        created_at=now,
        type=3,  # MANAGE
        content=f"Pool \"{pool.name}\" allocated ¥{amount:.2f} to {user.username} (#{user_id}) by {admin_user.username}",
        cost=0,
        request_id=uuid.uuid4().hex,
    ))
    await db.commit()
    return GenericApiResponse(data=_allocation_to_dict(allocation))


# ── Recall ─────────────────────────────────────────────

@router.post("/api/pool/{pool_id}/recall")
async def recall_from_user(
    pool_id: int,
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Recall allocated budget from a user."""
    result = await db.execute(select(BudgetPool).where(BudgetPool.id == pool_id))
    pool = result.scalar_one_or_none()
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    if pool.status != "active":
        raise HTTPException(status_code=400, detail="Pool is not active")

    user_id = int(body.get("user_id", 0))
    amount = float(body.get("amount", 0))
    if user_id <= 0 or amount <= 0:
        raise HTTPException(status_code=400, detail="Valid user_id and amount > 0 required")

    remark = body.get("remark", "")

    # Find the user's active allocation in this pool
    alloc_result = await db.execute(
        select(PoolAllocation)
        .where(PoolAllocation.pool_id == pool_id)
        .where(PoolAllocation.user_id == user_id)
        .where(PoolAllocation.status == "active")
    )
    allocation = alloc_result.scalar_one_or_none()
    if not allocation:
        raise HTTPException(status_code=400, detail="No active allocation found for this user in this pool")

    available_to_recall = allocation.amount - allocation.recalled - allocation.consumed
    if amount > available_to_recall:
        raise HTTPException(
            status_code=400,
            detail=f"Can only recall up to {available_to_recall:.4f} (allocated {allocation.amount:.4f}, consumed {allocation.consumed:.4f}, already recalled {allocation.recalled:.4f})",
        )

    now = int(time.time() * 1000)
    allocation.recalled += amount
    allocation.updated_at = now
    pool.total_allocated -= amount

    tx = PoolTransaction(
        pool_id=pool.id,
        type="recall",
        amount=amount,
        user_id=user_id,
        allocation_id=allocation.id,
        remark=remark,
        created_at=now,
    )
    db.add(tx)

    # Decrease user's Budget.monthly_budget and balance
    budget_result = await db.execute(select(Budget).where(Budget.user_id == user_id))
    budget = budget_result.scalar_one_or_none()
    if budget:
        budget.monthly_budget = max(0.0, budget.monthly_budget - amount)
        budget.updated_at = now

    # Deduct from user's micro-yuan balance
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user:
        user.balance = max(0, (user.balance or 0) - int(amount * 1_000_000))

    # Log: pool recalled
    admin_user = request.state.user
    db.add(Log(
        created_at=now,
        type=3,  # MANAGE
        content=f"Pool \"{pool.name}\" recalled ¥{amount:.2f} from {user.username if user else '#' + str(user_id)} by {admin_user.username}",
        cost=0,
        request_id=uuid.uuid4().hex,
    ))
    await db.commit()
    return GenericApiResponse(data=_allocation_to_dict(allocation))


@router.post("/api/pool/{pool_id}/recall_all")
async def recall_all_from_user(
    pool_id: int,
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Recall all remaining balance from a user in this pool."""
    user_id = int(body.get("user_id", 0))
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="Valid user_id required")

    alloc_result = await db.execute(
        select(PoolAllocation)
        .where(PoolAllocation.pool_id == pool_id)
        .where(PoolAllocation.user_id == user_id)
        .where(PoolAllocation.status == "active")
    )
    allocation = alloc_result.scalar_one_or_none()
    if not allocation:
        raise HTTPException(status_code=400, detail="No active allocation for this user")

    remaining = allocation.amount - allocation.recalled - allocation.consumed
    if remaining <= 0:
        raise HTTPException(status_code=400, detail="No remaining balance to recall")

    # Reuse recall endpoint with the remaining amount
    body["amount"] = remaining
    return await recall_from_user(pool_id, body, request, db, _=None)


# ── Close ──────────────────────────────────────────────

@router.post("/api/pool/{pool_id}/close")
async def close_pool(
    pool_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Close a pool. Runs final reconciliation first."""
    result = await db.execute(select(BudgetPool).where(BudgetPool.id == pool_id))
    pool = result.scalar_one_or_none()
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    if pool.status != "active":
        raise HTTPException(status_code=400, detail="Pool is already closed")

    # Run reconciliation
    await _reconcile_pool(pool, db)

    # Close the pool
    now = int(time.time() * 1000)
    pool.status = "closed"
    pool.closed_at = now

    # Log: pool closed
    admin_user = request.state.user
    db.add(Log(
        created_at=now,
        type=3,  # MANAGE
        content=f"Pool \"{pool.name}\" closed by {admin_user.username}",
        cost=0,
        request_id=uuid.uuid4().hex,
    ))
    await db.commit()
    return GenericApiResponse(data=_pool_to_dict(pool))


# ── Rollover ───────────────────────────────────────────

@router.post("/api/pool/{pool_id}/rollover")
async def rollover_pool(
    pool_id: int,
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Rollover unallocated balance to a new period.

    Creates a new closed-period snapshot and a fresh pool entry
    carrying forward the unallocated balance.
    """
    result = await db.execute(select(BudgetPool).where(BudgetPool.id == pool_id))
    pool = result.scalar_one_or_none()
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    if pool.status != "active":
        raise HTTPException(status_code=400, detail="Pool is not active")

    new_period_key = body.get("new_period_key", "").strip()
    new_name = body.get("new_name", "").strip()
    if not new_period_key:
        raise HTTPException(status_code=400, detail="new_period_key is required")

    # Settle current period
    await _reconcile_pool(pool, db)

    # Carry-forward: unallocated balance = total_funded - total_consumed
    carry = round(max(0.0, pool.total_funded - pool.total_consumed), 4)

    # Close old pool
    now = int(time.time() * 1000)
    pool.status = "closed"
    pool.closed_at = now

    # Create new pool
    new_pool = BudgetPool(
        name=new_name or f"{pool.name} (rolled)",
        total_funded=carry,
        period_type=pool.period_type,
        period_key=new_period_key,
        status="active",
        created_at=now,
    )
    db.add(new_pool)
    await db.flush()

    # Record rollover transaction
    tx = PoolTransaction(
        pool_id=pool.id,
        type="rollover",
        amount=carry,
        remark=f"Rolled over to pool {new_pool.id} ({new_period_key})",
        created_at=now,
    )
    db.add(tx)

    if carry > 0:
        tx2 = PoolTransaction(
            pool_id=new_pool.id,
            type="fund",
            amount=carry,
            remark=f"Rolled over from pool {pool.id} ({pool.period_key})",
            created_at=now,
        )
        db.add(tx2)

    # Log: pool rolled over
    admin_user = request.state.user
    db.add(Log(
        created_at=now,
        type=3,  # MANAGE
        content=f"Pool \"{pool.name}\" rolled over to \"{new_name or new_pool.name}\" ({new_period_key}), carry ¥{carry:.2f} by {admin_user.username}",
        cost=0,
        request_id=uuid.uuid4().hex,
    ))
    await db.commit()
    return GenericApiResponse(data={
        "old_pool": _pool_to_dict(pool),
        "new_pool": _pool_to_dict(new_pool),
        "carried_forward": carry,
    })


# ── Reconciliation ─────────────────────────────────────

@router.get("/api/pool/{pool_id}/reconciliation")
async def get_reconciliation(
    pool_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Get full reconciliation for a pool: allocations, actual usage, available."""
    result = await db.execute(select(BudgetPool).where(BudgetPool.id == pool_id))
    pool = result.scalar_one_or_none()
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")

    # Run reconciliation (re-sync consumption from CostRecords)
    await _reconcile_pool(pool, db)

    # Fetch allocations with usernames
    from app.models.user import User
    alloc_result = await db.execute(
        select(PoolAllocation, User.username)
        .join(User, PoolAllocation.user_id == User.id, isouter=True)
        .where(PoolAllocation.pool_id == pool_id)
        .order_by(PoolAllocation.created_at.desc())
    )
    allocations = [_allocation_to_dict(a, u or "") for a, u in alloc_result.all()]

    pool_info = _pool_to_dict(pool)
    pool_info["available"] = round(max(0.0, pool.total_funded - pool.total_consumed), 4)
    pool_info["used_quota"] = round(pool.total_allocated, 4)  # for frontend compatibility

    return GenericApiResponse(data={
        "pool": pool_info,
        "allocations": allocations,
    })


@router.get("/api/pool/{pool_id}/transactions")
async def list_transactions(
    pool_id: int,
    p: int = Query(0, ge=0),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """List transactions for a pool."""
    q = (
        select(PoolTransaction)
        .where(PoolTransaction.pool_id == pool_id)
        .order_by(PoolTransaction.created_at.desc())
    )
    total_q = select(func.count()).select_from(q.subquery())
    total = await db.scalar(total_q) or 0

    result = await db.execute(q.offset(p * size).limit(size))
    txs = result.scalars().all()

    return PaginatedResponse(
        data=[_tx_to_dict(t) for t in txs],
        total=total,
    )


# ── Internal ───────────────────────────────────────────

async def _reconcile_pool(pool: BudgetPool, db: AsyncSession):
    """Reconcile pool consumption against actual CostRecords.

    For each active allocation, queries actual cost from CostRecord table
    and updates allocation.consumed + pool.total_consumed.
    """
    if not pool.period_key:
        return

    period_start, period_end = _period_ms_range(pool.period_key, pool.period_type or "monthly")

    # Get all allocations for this pool
    result = await db.execute(
        select(PoolAllocation).where(PoolAllocation.pool_id == pool.id)
    )
    allocations = result.scalars().all()

    total_consumed = 0.0
    now = int(time.time() * 1000)

    for alloc in allocations:
        # Query actual cost from CostRecord for this user in this period
        cost_result = await db.execute(
            select(func.coalesce(func.sum(CostRecord.cost), 0))
            .where(CostRecord.user_id == alloc.user_id)
            .where(CostRecord.created_at >= period_start)
            .where(CostRecord.created_at < period_end)
        )
        actual_cost = float(cost_result.scalar() or 0.0)

        old_consumed = alloc.consumed
        alloc.consumed = round(actual_cost, 4)
        alloc.updated_at = now
        total_consumed += alloc.consumed

        # If this is a new settlement and there's unused balance, log a return
        if old_consumed == 0 and alloc.status == "active":
            unused = max(0.0, alloc.amount - alloc.recalled - alloc.consumed)
            if unused > 0.001:  # avoid micro-returns
                tx = PoolTransaction(
                    pool_id=pool.id,
                    type="return",
                    amount=round(unused, 4),
                    user_id=alloc.user_id,
                    allocation_id=alloc.id,
                    remark="Unused balance returned at settlement",
                    created_at=now,
                )
                db.add(tx)

    pool.total_consumed = round(total_consumed, 4)
