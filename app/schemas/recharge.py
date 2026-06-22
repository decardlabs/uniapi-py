"""Recharge-related Pydantic schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RechargeCreate(BaseModel):
    amount: int = Field(..., ge=1, description="Quota amount requested")
    remark: Optional[str] = None


class RechargeResponse(BaseModel):
    id: int
    user_id: int
    amount: int
    status: int
    remark: Optional[str] = None
    admin_remark: Optional[str] = None
    reviewer_id: Optional[int] = None
    reviewed_time: Optional[int] = None
    created_time: int
    username: Optional[str] = None  # joined from User table

    model_config = {"from_attributes": True}


class TopUpRequest(BaseModel):
    """Schema for admin direct top-up."""
    user_id: int = Field(..., ge=1)
    quota: int = Field(..., ge=1)
    remark: Optional[str] = None
    pool_id: int = 0
