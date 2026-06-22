"""Tests for RechargeRequest model and schemas."""
import pytest
from pydantic import ValidationError

from app.models.recharge import RechargeRequest
from app.schemas.recharge import RechargeCreate, RechargeResponse, TopUpRequest


class TestRechargeRequestModel:
    def test_model_attributes(self):
        """Verify model has expected columns."""
        assert hasattr(RechargeRequest, "id")
        assert hasattr(RechargeRequest, "user_id")
        assert hasattr(RechargeRequest, "amount")
        assert hasattr(RechargeRequest, "status")
        assert hasattr(RechargeRequest, "remark")
        assert hasattr(RechargeRequest, "admin_remark")
        assert hasattr(RechargeRequest, "reviewer_id")
        assert hasattr(RechargeRequest, "reviewed_time")
        assert hasattr(RechargeRequest, "created_time")

    def test_default_status_is_pending(self):
        """Status should default to 1 (pending)."""
        assert RechargeRequest.__table__.columns["status"].default.arg == 1


class TestRechargeStatus:
    def test_recharge_status_values(self):
        from app.schemas.recharge import RechargeStatus
        assert RechargeStatus.PENDING == 1
        assert RechargeStatus.APPROVED == 2
        assert RechargeStatus.REJECTED == 3


class TestRechargeSchema:
    def test_recharge_create_valid(self):
        data = RechargeCreate(amount=1000000, remark="test top-up")
        assert data.amount == 1000000
        assert data.remark == "test top-up"

    def test_recharge_create_negative_rejected(self):
        with pytest.raises(ValidationError):
            RechargeCreate(amount=-1)

    def test_recharge_create_zero_rejected(self):
        with pytest.raises(ValidationError):
            RechargeCreate(amount=0)

    def test_recharge_create_no_remark(self):
        data = RechargeCreate(amount=500000)
        assert data.remark is None

    def test_topup_request_valid(self):
        data = TopUpRequest(user_id=1, quota=1000000, remark="admin top-up", pool_id=3)
        assert data.user_id == 1
        assert data.quota == 1000000
        assert data.pool_id == 3

    def test_topup_request_default_pool_id(self):
        data = TopUpRequest(user_id=1, quota=1000000)
        assert data.pool_id == 0

    def test_recharge_response_from_orm(self):
        data = RechargeResponse(
            id=1, user_id=2, amount=1000000, status=1,
            created_time=1000, username="testuser",
        )
        assert data.id == 1
        assert data.status == 1
        assert data.username == "testuser"
