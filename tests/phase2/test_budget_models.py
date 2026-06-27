"""Tests for budget models (Budget, CostRecord, BudgetResetLog)."""


class TestBudgetModels:
    """Budget SQLAlchemy models should exist and be importable."""

    def test_budget_model_exists(self):
        """Budget model should be importable and have required columns."""
        from app.models.budget import Budget
        assert hasattr(Budget, "user_id")
        assert hasattr(Budget, "monthly_budget")
        assert hasattr(Budget, "consumed")
        assert hasattr(Budget, "frozen")

    def test_cost_record_model_exists(self):
        """CostRecord model should be importable."""
        from app.models.budget import CostRecord
        assert hasattr(CostRecord, "request_id")
        assert hasattr(CostRecord, "cost")
        assert hasattr(CostRecord, "status")

    def test_budget_reset_log_exists(self):
        """BudgetResetLog model should be importable."""
        from app.models.budget import BudgetResetLog
        assert hasattr(BudgetResetLog, "period")
        assert hasattr(BudgetResetLog, "total_consumed")

    def test_tables_created_with_metadata(self):
        """Budget tables should be part of Base metadata."""
        from app.models.base import Base

        table_names = Base.metadata.tables
        assert "budgets" in table_names
        assert "cost_records" in table_names
        assert "budget_reset_logs" in table_names

    def test_create_budget_record(self):
        """Budget should be creatable with required fields."""
        import time

        from app.models.budget import Budget

        budget = Budget(
            user_id=1,
            monthly_budget=800.00,
            consumed=0.00,
            frozen=0.00,
            created_at=int(time.time() * 1000),
            updated_at=int(time.time() * 1000),
        )
        assert budget.user_id == 1
        assert budget.monthly_budget == 800.00
        assert budget.consumed == 0.00

    def test_create_cost_record(self):
        """CostRecord should be creatable with required fields."""
        from app.models.budget import CostRecord

        record = CostRecord(
            request_id="req_001",
            user_id=1,
            model="deepseek-v4-pro",
            input_tokens=1000,
            output_tokens=500,
            cost=0.006,
            status="success",
        )
        assert record.request_id == "req_001"
        assert record.cost == 0.006
        assert record.status == "success"
