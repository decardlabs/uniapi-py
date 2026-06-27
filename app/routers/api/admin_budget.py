"""Admin budget management API endpoints."""
from __future__ import annotations

import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.budget.arbiter import BudgetArbiter
from app.database import get_db
from app.dependencies import admin_auth
from app.models.budget import Budget, BudgetResetLog
from app.schemas.common import GenericApiResponse, PaginatedResponse
from app.schemas.management import AdminBudgetUpdateRequest

router = APIRouter(tags=["admin-budget"])


@router.get("/api/v1/admin/budgets")
async def admin_list_budgets(
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """List all budgets with user info (paginated)."""
    # Total count
    total_q = select(func.count()).select_from(Budget)
    total = await db.scalar(total_q) or 0

    # Fetch budgets with user info
    from app.models.user import User
    result = await db.execute(
        select(Budget, User.username)
        .join(User, Budget.user_id == User.id)
        .order_by(Budget.monthly_budget.desc())
        .offset(p * size)
        .limit(size)
    )
    rows = result.all()

    data = []
    for budget, username in rows:
        data.append({
            "user_id": budget.user_id,
            "username": username,
            "monthly_budget": budget.monthly_budget,
            "consumed": budget.consumed,
            "frozen": budget.frozen,
            "budget_period": budget.budget_period,
        })

    return PaginatedResponse(data=data, total=total)


@router.get("/api/v1/admin/budgets/stats")
async def admin_budget_stats(
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Aggregate budget statistics."""
    # Total budgets
    total_budgets_q = select(func.count()).select_from(Budget)
    total_budgets = await db.scalar(total_budgets_q) or 0

    # Sum of monthly budgets
    total_monthly_q = select(func.coalesce(func.sum(Budget.monthly_budget), 0))
    total_monthly = (await db.scalar(total_monthly_q)) or 0.0

    # Total consumed across all budgets
    total_consumed_q = select(func.coalesce(func.sum(Budget.consumed), 0))
    total_consumed = (await db.scalar(total_consumed_q)) or 0.0

    # Top spenders by consumed
    from app.models.user import User
    top_q = (
        select(Budget, User.username)
        .join(User, Budget.user_id == User.id)
        .order_by(Budget.consumed.desc())
        .limit(5)
    )
    top_result = await db.execute(top_q)
    top_spenders = [
        {
            "user_id": b.user_id,
            "username": u,
            "consumed": b.consumed,
            "monthly_budget": b.monthly_budget,
        }
        for b, u in top_result.all()
        if b.consumed > 0
    ]

    return GenericApiResponse(data={
        "total_budgets": total_budgets,
        "total_monthly": round(total_monthly, 2),
        "total_consumed": round(total_consumed, 4),
        "top_spenders": top_spenders,
        "avg_budget": round(total_monthly / total_budgets, 2) if total_budgets > 0 else 0,
    })


@router.put("/api/v1/admin/budgets/{user_id}")
async def admin_update_budget(
    user_id: int,
    body: AdminBudgetUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Update a user's monthly budget."""
    result = await db.execute(select(Budget).where(Budget.user_id == user_id))
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found for this user")

    new_budget = body.monthly_budget
    if new_budget is not None and new_budget >= 0:
        budget.monthly_budget = float(new_budget)
        budget.updated_at = int(time.time() * 1000)
        await db.commit()
        return GenericApiResponse(data={
            "user_id": user_id,
            "monthly_budget": budget.monthly_budget,
        })

    raise HTTPException(status_code=400, detail="Invalid monthly_budget value")


@router.post("/api/v1/admin/budgets/reset/{user_id}")
async def admin_reset_budget(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Force reset a user's budget (archive current period, zero consumed/frozen)."""
    result = await db.execute(select(Budget).where(Budget.user_id == user_id))
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    previous_consumed = budget.consumed
    period = budget.budget_period or datetime.now().strftime("%Y-%m")

    # Archive to reset log
    reset_log = BudgetResetLog(
        user_id=user_id,
        period=period,
        total_consumed=previous_consumed,
        total_requests=0,
        reset_at=int(time.time() * 1000),
    )
    db.add(reset_log)

    # Reset budget
    budget.consumed = 0.0
    budget.frozen = 0.0
    budget.budget_period = ""
    budget.updated_at = int(time.time() * 1000)
    await db.commit()

    # Also clear Redis keys
    arbiter: BudgetArbiter | None = getattr(request.app.state, "budget_arbiter", None)
    if arbiter:
        await arbiter.redis.settle(user_id, period, 0, 0)

    return GenericApiResponse(data={
        "user_id": user_id,
        "previous_consumed": previous_consumed,
        "period": period,
    })
