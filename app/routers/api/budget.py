"""Budget status and history API endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import user_auth
from app.budget.arbiter import BudgetArbiter
from app.models.budget import CostRecord

router = APIRouter(tags=["budget"])


@router.get("/api/v1/budget/status")
async def budget_status(request: Request, db: AsyncSession = Depends(get_db)):
    """Get current user's budget status."""
    user = await user_auth(request, db)
    arbiter: BudgetArbiter | None = getattr(request.app.state, "budget_arbiter", None)
    if not arbiter:
        raise HTTPException(status_code=503, detail="Budget service not available")

    period = arbiter._compute_period()
    status = await arbiter.get_budget_status(user.id, period)
    return {"success": True, "data": status}


@router.get("/api/v1/budget/history")
async def budget_history(
    request: Request,
    month: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Get user's cost records for a given month."""
    user = await user_auth(request, db)
    period = month or datetime.now().strftime("%Y-%m")

    result = await db.execute(
        select(CostRecord)
        .where(CostRecord.user_id == user.id)
        .order_by(CostRecord.created_at.desc())
        .limit(100)
    )
    records = result.scalars().all()

    # Aggregate totals
    total_cost = sum(r.cost for r in records)

    return {
        "success": True,
        "data": {
            "period": period,
            "records": [
                {
                    "request_id": r.request_id,
                    "model": r.model,
                    "cost": r.cost,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "status": r.status,
                    "created_at": r.created_at,
                }
                for r in records
            ],
            "total_cost": round(total_cost, 4),
            "total_requests": len(records),
        },
    }
