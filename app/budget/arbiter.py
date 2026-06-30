"""BudgetArbiter — pre-check and post-settle for real-currency budget control.

Two-phase protocol:
  1. pre_check: verify budget → freeze → approve/reject
  2. post_settle: calculate actual cost → settle → record
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.budget.pricing import calculate_cost, compute_period, estimate_cost, get_model_pricing
from app.models.budget import Budget, BudgetResetLog, CostRecord

logger = logging.getLogger(__name__)


@dataclass
class BudgetDecision:
    status: str = "approved"
    estimated_cost: float = 0.0
    available: float = 0.0
    remaining_after: float = 0.0
    monthly_budget: float = 0.0
    error_code: int | None = None
    error_message: str = ""


@dataclass
class ActualUsage:
    model: str
    input_tokens: int
    output_tokens: int
    cache_hit_tokens: int = 0


@dataclass
class SettlementResult:
    cost: float = 0.0
    consumed_now: float = 0.0
    remaining: float = 0.0


class BudgetArbiter:
    """Budget arbitration for real-currency (yuan) cost tracking."""

    def __init__(
        self,
        redis_client: Any,
        db_session_factory: async_sessionmaker,
        default_monthly_budget: float = 800.0,
    ):
        self.redis = redis_client
        self.db_session_factory = db_session_factory
        self.default_monthly_budget = default_monthly_budget

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def pre_check(
        self,
        user_id: int,
        model: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int = 1000,
    ) -> BudgetDecision:
        """Pre-request budget check.

        1. Get or create Budget record for user
        2. Calculate available = monthly_budget - consumed - frozen
        3. Estimate cost (conservative, with safety margin)
        4. If enough: freeze in Redis, return approved
        5. If not enough: return rejected (402)
        """
        period = self._compute_period()

        # Step 1: get/create budget record
        budget = await self._get_or_create_budget(user_id)

        # Step 1b: auto-reset if period changed
        await self._check_period_reset(budget, user_id, period)

        # Step 2: get consumed + frozen from Redis (or DB fallback)
        consumed = await self.redis.get_consumed(user_id, period)
        frozen = await self.redis.get_frozen(user_id, period)
        if consumed == 0.0 and frozen == 0.0 and not self.redis.available:
            # Redis unavailable — read from DB directly
            consumed = budget.consumed
            frozen = budget.frozen

        available = budget.monthly_budget - consumed - frozen
        estimated = estimate_cost(model, estimated_input_tokens, estimated_output_tokens)

        # Free model check (cost = 0 → always allow)
        try:
            pricing = get_model_pricing(model)
            if pricing["input"] == 0 and pricing["output"] == 0:
                return BudgetDecision(
                    status="approved", estimated_cost=0.0,
                    available=available, monthly_budget=budget.monthly_budget,
                )
        except KeyError:
            pass

        # Step 3-4: check and freeze
        if available >= estimated:
            await self.redis.freeze(user_id, period, estimated)
            remaining_after = round(available - estimated, 4)
            return BudgetDecision(
                status="approved",
                estimated_cost=estimated,
                available=available,
                remaining_after=remaining_after,
                monthly_budget=budget.monthly_budget,
            )

        # Step 5: rejected
        return BudgetDecision(
            status="rejected",
            estimated_cost=estimated,
            available=available,
            monthly_budget=budget.monthly_budget,
            error_code=402,
            error_message=(
                f"月度预算不足。当前可用 ¥{available:.2f}，"
                f"预估需 ¥{estimated:.4f}。"
                f"请等待下月重置或联系管理员增加预算。"
            ),
        )

    async def post_settle(
        self,
        user_id: int,
        period: str,
        frozen_amount: float,
        monthly_budget: float,
        actual_usage: ActualUsage,
        request_id: str,
        db_session=None,
    ) -> SettlementResult:
        """Post-request settlement.

        1. Calculate actual cost from real token usage
        2. Redis atomic: unfreeze frozen, deduct actual cost
        3. If overage: log warning
        4. Write CostRecord to DB (async)
        """
        # Step 1: actual cost
        actual = calculate_cost(
            actual_usage.model,
            actual_usage.input_tokens,
            actual_usage.output_tokens,
            actual_usage.cache_hit_tokens,
        )

        # Step 2: atomic settle in Redis
        consumed_now, _ = await self.redis.settle(
            user_id, period, frozen_amount, actual
        )

        # Step 2b: update Budget.consumed in DB (for DB fallback when Redis is unavailable)
        async with self.db_session_factory() as session:
            budget_row = await session.execute(
                select(Budget).where(Budget.user_id == user_id, Budget.budget_period == period).with_for_update()
            )
            budget_row = budget_row.scalar_one_or_none()
            if budget_row:
                budget_row.consumed = (budget_row.consumed or 0.0) + actual
                await session.commit()

        # Step 3: overage warning
        if actual > frozen_amount:
            logger.warning(
                "Budget overage: user=%s request=%s frozen=%.6f actual=%.6f overage=%.6f",
                user_id, request_id, frozen_amount, actual, actual - frozen_amount,
            )

        # Step 4: write cost record to DB
        await self._write_cost_record(
            request_id=request_id,
            user_id=user_id,
            model=actual_usage.model,
            input_tokens=actual_usage.input_tokens,
            output_tokens=actual_usage.output_tokens,
            cache_hit_tokens=actual_usage.cache_hit_tokens,
            cost=actual,
            estimated_cost=frozen_amount,
            status="success",
            db_session=db_session,
        )

        remaining = round(monthly_budget - consumed_now, 4)
        return SettlementResult(cost=actual, consumed_now=consumed_now, remaining=remaining)

    async def get_budget_status(self, user_id: int, period: str) -> dict:
        """Get current budget status for API response."""
        budget = await self._get_or_create_budget(user_id)
        consumed = await self.redis.get_consumed(user_id, period)
        frozen = await self.redis.get_frozen(user_id, period)

        if consumed == 0.0 and frozen == 0.0 and not self.redis.available:
            consumed = budget.consumed
            frozen = budget.frozen

        remaining = round(budget.monthly_budget - consumed - frozen, 4)
        consumed_pct = round(
            ((consumed + frozen) / budget.monthly_budget * 100) if budget.monthly_budget > 0 else 0,
            1,
        )
        return {
            "monthly": budget.monthly_budget,
            "consumed": round(consumed, 4),
            "frozen": round(frozen, 4),
            "remaining": remaining,
            "consumed_pct": consumed_pct,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_period(self) -> str:
        """Return current budget period as 'YYYY-MM'."""
        return compute_period()

    async def _get_or_create_budget(self, user_id: int) -> Budget:
        """Get user's Budget record, creating with defaults if missing."""
        async with self.db_session_factory() as session:
            result = await session.execute(
                select(Budget).where(Budget.user_id == user_id).with_for_update()
            )
            budget = result.scalar_one_or_none()
            if budget:
                return budget

            now = int(time.time() * 1000)
            budget = Budget(
                user_id=user_id,
                monthly_budget=self.default_monthly_budget,
                consumed=0.0,
                frozen=0.0,
                created_at=now,
                updated_at=now,
            )
            session.add(budget)
            await session.commit()
            return budget

    async def _check_period_reset(self, budget: Budget, user_id: int, current_period: str):
        """If the budget period has changed, archive old period and reset balances."""
        if budget.budget_period == current_period:
            return
        if not budget.budget_period:
            # First use ever — just set the period
            budget.budget_period = current_period
            budget.updated_at = int(time.time() * 1000)
            async with self.db_session_factory() as session:
                await session.merge(budget)
                await session.commit()
            return

        # Period changed: archive old period
        old_period = budget.budget_period
        async with self.db_session_factory() as session:
            # Create reset log
            reset_log = BudgetResetLog(
                user_id=user_id,
                period=old_period,
                total_consumed=budget.consumed,
                total_requests=0,
                reset_at=int(time.time() * 1000),
            )
            session.add(reset_log)

            # Reset budget
            budget.consumed = 0.0
            budget.frozen = 0.0
            budget.budget_period = current_period
            budget.updated_at = int(time.time() * 1000)
            await session.merge(budget)
            await session.commit()

        # Clear Redis keys for old period
        await self.redis.settle(user_id, old_period, 0, 0)

    async def _write_cost_record(
        self,
        request_id: str,
        user_id: int,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_hit_tokens: int,
        cost: float,
        estimated_cost: float,
        status: str = "success",
        db_session=None,
    ):
        """Write a cost record to DB. Use db_session if provided (same transaction),
        otherwise create a new session."""
        session = db_session or self.db_session_factory()
        record = CostRecord(
            request_id=request_id,
            user_id=user_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_hit_tokens=cache_hit_tokens,
            cost=cost,
            estimated_cost=estimated_cost,
            status=status,
            created_at=int(time.time() * 1000),
        )
        session.add(record)
        if not db_session:
            await session.commit()
            await session.close()
