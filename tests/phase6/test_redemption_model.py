"""Tests for RedemptionCode model and schemas."""
import pytest
from pydantic import ValidationError

from app.models.redemption import RedemptionCode
from app.schemas.redemption import RedemptionCreate, RedemptionResponse, RedemptionUpdate


class TestRedemptionCodeModel:
    def test_model_attributes(self):
        assert hasattr(RedemptionCode, "id")
        assert hasattr(RedemptionCode, "name")
        assert hasattr(RedemptionCode, "code")
        assert hasattr(RedemptionCode, "quota")
        assert hasattr(RedemptionCode, "status")
        assert hasattr(RedemptionCode, "used_by")
        assert hasattr(RedemptionCode, "used_time")
        assert hasattr(RedemptionCode, "created_by")
        assert hasattr(RedemptionCode, "created_time")

    def test_code_is_unique_indexed(self):
        assert RedemptionCode.__table__.columns["code"].unique
        assert RedemptionCode.__table__.columns["code"].index


class TestRedemptionSchema:
    def test_redemption_create_valid(self):
        data = RedemptionCreate(name="test", quota=1000000, count=5)
        assert data.name == "test"
        assert data.count == 5

    def test_redemption_create_default_count(self):
        data = RedemptionCreate(name="test", quota=1000000)
        assert data.count == 1

    def test_redemption_create_count_too_high(self):
        with pytest.raises(ValidationError):
            RedemptionCreate(name="test", quota=1000000, count=101)

    def test_redemption_update_valid(self):
        data = RedemptionUpdate(id=1, name="new name", quota=500000)
        assert data.id == 1
        assert data.status_only is False

    def test_redemption_response_from_orm(self):
        data = RedemptionResponse(
            id=1, name="test", code="ABC123", quota=1000000,
            status=1, created_by=1, created_time=1000,
        )
        assert data.code == "ABC123"
        assert data.status == 1
