"""Budget-related SQLAlchemy ORM models."""
from __future__ import annotations

from sqlalchemy import BigInteger, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    monthly_budget: Mapped[float] = mapped_column(Float, default=800.0)
    consumed: Mapped[float] = mapped_column(Float, default=0.0)
    frozen: Mapped[float] = mapped_column(Float, default=0.0)
    budget_period: Mapped[str] = mapped_column(String(7), default="")
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=0)


class CostRecord(Base):
    __tablename__ = "cost_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    model: Mapped[str] = mapped_column(String(64), default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cache_hit_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    protocol: Mapped[str] = mapped_column(String(32), default="")
    agent_type: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), default="success")
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)


class BudgetResetLog(Base):
    __tablename__ = "budget_reset_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    period: Mapped[str] = mapped_column(String(7), default="")
    total_consumed: Mapped[float] = mapped_column(Float, default=0.0)
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    reset_at: Mapped[int] = mapped_column(BigInteger, default=0)


class BudgetPool(Base):
    """A shared budget pool for allocating budgets to users."""

    __tablename__ = "budget_pools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    total_funded: Mapped[float] = mapped_column(Float, default=0.0)
    total_allocated: Mapped[float] = mapped_column(Float, default=0.0)
    total_consumed: Mapped[float] = mapped_column(Float, default=0.0)
    period_type: Mapped[str] = mapped_column(String(16), default="monthly")
    period_key: Mapped[str] = mapped_column(String(16), default="")
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)
    closed_at: Mapped[int] = mapped_column(BigInteger, nullable=True, default=None)


class PoolAllocation(Base):
    """An allocation from a budget pool to a specific user."""

    __tablename__ = "pool_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pool_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    consumed: Mapped[float] = mapped_column(Float, default=0.0)
    recalled: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16), default="active")
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=0)


class PoolTransaction(Base):
    """Transaction log for a budget pool."""

    __tablename__ = "pool_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pool_id: Mapped[int] = mapped_column(Integer, index=True)
    type: Mapped[str] = mapped_column(String(16), default="")
    amount: Mapped[float] = mapped_column(Float, default=0.0)
    user_id: Mapped[int] = mapped_column(Integer, nullable=True, default=None)
    allocation_id: Mapped[int] = mapped_column(Integer, nullable=True, default=None)
    remark: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)
