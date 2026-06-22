"""Redemption code Pydantic schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class RedemptionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    quota: int = Field(..., ge=1)
    count: int = Field(default=1, ge=1, le=100)


class RedemptionUpdate(BaseModel):
    id: int
    name: Optional[str] = None
    quota: Optional[int] = None
    status_only: bool = False
    status: Optional[int] = None  # only used if status_only=True


class RedemptionResponse(BaseModel):
    id: int
    name: str
    code: str
    quota: int
    status: int
    used_by: Optional[int] = None
    used_time: Optional[int] = None
    created_by: Optional[int] = None
    created_time: int

    model_config = {"from_attributes": True}
