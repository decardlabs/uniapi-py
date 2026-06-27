"""Tests for pool models (BudgetPool, PoolAllocation, PoolTransaction)."""


class TestPoolModels:
    """Pool SQLAlchemy models should exist and be importable."""

    def test_budget_pool_model_exists(self):
        """BudgetPool model should be importable and have required columns."""
        from app.models.budget import BudgetPool
        assert hasattr(BudgetPool, "name")
        assert hasattr(BudgetPool, "total_funded")
        assert hasattr(BudgetPool, "total_allocated")
        assert hasattr(BudgetPool, "total_consumed")
        assert hasattr(BudgetPool, "period_type")
        assert hasattr(BudgetPool, "period_key")
        assert hasattr(BudgetPool, "status")

    def test_pool_allocation_model_exists(self):
        """PoolAllocation model should be importable."""
        from app.models.budget import PoolAllocation
        assert hasattr(PoolAllocation, "pool_id")
        assert hasattr(PoolAllocation, "user_id")
        assert hasattr(PoolAllocation, "amount")
        assert hasattr(PoolAllocation, "consumed")
        assert hasattr(PoolAllocation, "recalled")

    def test_pool_transaction_model_exists(self):
        """PoolTransaction model should be importable."""
        from app.models.budget import PoolTransaction
        assert hasattr(PoolTransaction, "pool_id")
        assert hasattr(PoolTransaction, "type")
        assert hasattr(PoolTransaction, "amount")
        assert hasattr(PoolTransaction, "remark")

    def test_tables_registered(self):
        """Pool tables should be part of Base metadata."""
        from app.models.base import Base
        table_names = Base.metadata.tables
        assert "budget_pools" in table_names
        assert "pool_allocations" in table_names
        assert "pool_transactions" in table_names

    def test_create_budget_pool(self):
        """BudgetPool should be creatable with required fields."""
        from app.models.budget import BudgetPool
        pool = BudgetPool(
            name="Test Pool",
            total_funded=5000.0,
            period_type="monthly",
            period_key="2026-06",
            status="active",
            created_at=1000000,
        )
        assert pool.name == "Test Pool"
        assert pool.total_funded == 5000.0
        assert pool.period_key == "2026-06"
        assert pool.status == "active"

    def test_create_pool_allocation(self):
        """PoolAllocation should be creatable."""
        from app.models.budget import PoolAllocation
        alloc = PoolAllocation(
            pool_id=1,
            user_id=42,
            amount=500.0,
            consumed=0.0,
            recalled=0.0,
            status="active",
            created_at=1000000,
            updated_at=1000000,
        )
        assert alloc.pool_id == 1
        assert alloc.user_id == 42
        assert alloc.amount == 500.0
        assert alloc.consumed == 0.0
        assert alloc.recalled == 0.0

    def test_create_pool_transaction(self):
        """PoolTransaction should be creatable."""
        from app.models.budget import PoolTransaction
        tx = PoolTransaction(
            pool_id=1,
            type="fund",
            amount=5000.0,
            remark="Initial funding",
            created_at=1000000,
        )
        assert tx.pool_id == 1
        assert tx.type == "fund"
        assert tx.amount == 5000.0
