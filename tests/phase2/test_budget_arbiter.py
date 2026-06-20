"""Tests for BudgetArbiter core logic."""
import time
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, engine
from app.models.base import Base
from app.models.budget import Budget, CostRecord
from app.budget.arbiter import BudgetArbiter, ActualUsage, BudgetDecision
from tests.conftest import FakeRedisClient


@pytest.fixture(autouse=True)
async def setup_db():
    """Create tables for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def arbiter():
    """Create BudgetArbiter with FakeRedisClient."""
    redis = FakeRedisClient()
    await redis.initialize()
    arb = BudgetArbiter(redis, async_session_factory)
    yield arb
    await redis.close()


@pytest.fixture
async def db():
    """Get a fresh DB session."""
    async with async_session_factory() as session:
        yield session


class TestPreCheck:
    """pre_check should approve/reject based on budget."""

    async def _create_budget(self, user_id: int, monthly: float = 800.0,
                              consumed: float = 0.0, frozen: float = 0.0):
        async with async_session_factory() as session:
            now = int(time.time() * 1000)
            b = Budget(
                user_id=user_id,
                monthly_budget=monthly,
                consumed=consumed,
                frozen=frozen,
                created_at=now,
                updated_at=now,
            )
            session.add(b)
            await session.commit()
        return b

    async def test_approved_with_sufficient_budget(self, arbiter):
        """Request within budget should be approved."""
        await self._create_budget(100, monthly=800.0)

        decision = await arbiter.pre_check(
            user_id=100,
            model="deepseek-v4-pro",
            estimated_input_tokens=1000,
            estimated_output_tokens=500,
        )
        assert decision.status == "approved"
        assert decision.estimated_cost > 0
        assert decision.available > 0
        assert decision.error_code is None

    async def test_rejected_when_exhausted(self, arbiter):
        """Request beyond budget should be rejected with 402."""
        await self._create_budget(101, monthly=800.0)
        # Exhaust budget via Redis freeze
        period = arbiter._compute_period()
        await arbiter.redis.freeze(101, period, 800.0)

        decision = await arbiter.pre_check(
            user_id=101,
            model="deepseek-v4-pro",
            estimated_input_tokens=100000,
            estimated_output_tokens=100000,
        )
        assert decision.status == "rejected"
        assert decision.error_code == 402
        assert "预算" in decision.error_message or "budget" in decision.error_message.lower()

    async def test_auto_creates_budget_if_missing(self, arbiter, db):
        """User without budget record should get one auto-created."""
        decision = await arbiter.pre_check(
            user_id=999,
            model="deepseek-v4-pro",
            estimated_input_tokens=100,
            estimated_output_tokens=50,
        )
        assert decision.status == "approved"

        # Verify budget was created
        result = await db.execute(select(Budget).where(Budget.user_id == 999))
        budget = result.scalar_one_or_none()
        assert budget is not None
        assert budget.monthly_budget == 800.0

    async def test_free_model_always_approved(self, arbiter):
        """Free models (glm-4-flash) should not consume budget."""
        await self._create_budget(103, monthly=800.0)
        # Exhaust budget via Redis
        period = arbiter._compute_period()
        await arbiter.redis.freeze(103, period, 800.0)

        decision = await arbiter.pre_check(
            user_id=103,
            model="glm-4.7-flash",
            estimated_input_tokens=10000,
            estimated_output_tokens=5000,
        )
        assert decision.status == "approved"
        assert decision.estimated_cost == 0.0


class TestPostSettle:
    """post_settle should deduct correct amounts."""

    async def test_deducts_actual_cost(self, arbiter):
        """Settle should increase consumed by actual cost."""
        decision = await arbiter.pre_check(
            user_id=200, model="deepseek-v4-pro",
            estimated_input_tokens=1000, estimated_output_tokens=500,
        )
        period = arbiter._compute_period()

        result = await arbiter.post_settle(
            user_id=200,
            period=period,
            frozen_amount=decision.estimated_cost,
            monthly_budget=800.0,
            actual_usage=ActualUsage(
                model="deepseek-v4-pro",
                input_tokens=1000,
                output_tokens=500,
            ),
            request_id="settle_test_001",
        )
        assert result.cost > 0
        assert result.consumed_now > 0
        assert result.remaining < 800.0

    async def test_overage_does_not_crash(self, arbiter):
        """When actual cost exceeds frozen, handler should not crash."""
        decision = await arbiter.pre_check(
            user_id=201, model="deepseek-v4-pro",
            estimated_input_tokens=100, estimated_output_tokens=50,
        )
        period = arbiter._compute_period()

        # Deliberately use way more tokens than estimated
        result = await arbiter.post_settle(
            user_id=201,
            period=period,
            frozen_amount=decision.estimated_cost,
            monthly_budget=800.0,
            actual_usage=ActualUsage(
                model="deepseek-v4-pro",
                input_tokens=100000,
                output_tokens=50000,
            ),
            request_id="settle_test_002",
        )
        # Should still return a result, not crash
        assert result.cost > decision.estimated_cost
        assert result.consumed_now > 0

    async def test_writes_cost_record(self, arbiter, db):
        """Settle should write a CostRecord to DB."""
        decision = await arbiter.pre_check(
            user_id=202, model="deepseek-v4-pro",
            estimated_input_tokens=1000, estimated_output_tokens=500,
        )
        period = arbiter._compute_period()

        await arbiter.post_settle(
            user_id=202,
            period=period,
            frozen_amount=decision.estimated_cost,
            monthly_budget=800.0,
            actual_usage=ActualUsage(
                model="deepseek-v4-pro",
                input_tokens=1000,
                output_tokens=500,
            ),
            request_id="settle_test_003",
        )

        result = await db.execute(
            select(CostRecord).where(CostRecord.request_id == "settle_test_003")
        )
        record = result.scalar_one_or_none()
        assert record is not None
        assert record.status == "success"
        assert record.cost > 0


class TestBudgetStatus:
    """get_budget_status should return correct info."""

    async def test_returns_budget_info(self, arbiter):
        """Status should include budget breakdown."""
        import asyncio
        # First make a request to create budget + consume
        decision = await arbiter.pre_check(
            user_id=300, model="deepseek-v4-pro",
            estimated_input_tokens=1000, estimated_output_tokens=500,
        )
        period = arbiter._compute_period()

        status = await arbiter.get_budget_status(300, period)
        assert "monthly" in status
        assert "consumed" in status
        assert "remaining" in status
        assert "consumed_pct" in status
        assert status["monthly"] > 0


class TestPeriodReset:
    """Budget should reset automatically on period change."""

    async def test_auto_resets_on_period_change(self, arbiter):
        """When current period differs from budget.budget_period, consumed resets."""
        from sqlalchemy import select
        async with async_session_factory() as db:
            budget = Budget(
                user_id=400, monthly_budget=800.0,
                consumed=100.0, frozen=0.0,
                budget_period="2026-05",
                created_at=int(time.time() * 1000),
                updated_at=int(time.time() * 1000),
            )
            db.add(budget)
            await db.commit()

        decision = await arbiter.pre_check(
            user_id=400, model="deepseek-v4-pro",
            estimated_input_tokens=100, estimated_output_tokens=50,
        )
        assert decision.status == "approved"

        async with async_session_factory() as db:
            result = await db.execute(select(Budget).where(Budget.user_id == 400))
            budget = result.scalar_one()
            assert budget.consumed == 0.0
            assert budget.budget_period == arbiter._compute_period()

    async def test_no_reset_within_same_period(self, arbiter):
        """When period matches, consumed should not reset."""
        period = arbiter._compute_period()
        from sqlalchemy import select
        async with async_session_factory() as db:
            budget = Budget(
                user_id=401, monthly_budget=800.0,
                consumed=50.0, frozen=0.0,
                budget_period=period,
                created_at=int(time.time() * 1000),
                updated_at=int(time.time() * 1000),
            )
            db.add(budget)
            await db.commit()

        await arbiter.pre_check(
            user_id=401, model="deepseek-v4-pro",
            estimated_input_tokens=100, estimated_output_tokens=50,
        )

        async with async_session_factory() as db:
            result = await db.execute(select(Budget).where(Budget.user_id == 401))
            budget = result.scalar_one()
            assert budget.consumed == 50.0  # not reset
