"""Pydantic schemas for management API endpoints (channels, tokens, users, pools, etc.)."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

# ── Top-up / Recharge ──

class TopupActionRequest(BaseModel):
    """PUT /api/topup/ — admin approves or rejects a recharge."""
    id: int
    action: str = Field(pattern=r"^(approve|reject)$")
    admin_remark: str = ""


class ApproveRechargeRequest(BaseModel):
    """POST /api/recharge/{id}/approve"""
    pool_id: int = 0


class RejectRechargeRequest(BaseModel):
    """POST /api/recharge/{id}/reject"""
    admin_remark: str = "Rejected by admin"


# ── Channel ──

class ChannelCreateRequest(BaseModel):
    """POST /api/channel/"""
    name: str = Field(min_length=1, max_length=128)
    type: int
    key: str = ""
    base_url: str = ""
    models: str = ""
    group: str = "default"
    model_mapping: str = ""
    priority: int = 0
    weight: int = 1


class ChannelUpdateRequest(BaseModel):
    """PUT /api/channel/"""
    id: int
    name: Optional[str] = None
    type: Optional[int] = None
    key: Optional[str] = None
    base_url: Optional[str] = None
    models: Optional[str] = None
    group: Optional[str] = None
    status: Optional[int] = None
    model_mapping: Optional[str] = None
    priority: Optional[int] = None
    weight: Optional[int] = None
    ratelimit: Optional[int] = None
    groups: Optional[str] = None
    action: Optional[str] = None
    config: Optional[str] = None
    other: Optional[str] = None
    model_configs: Optional[str] = None
    system_prompt: Optional[str] = None


# ── Token ──

class TokenCreateRequest(BaseModel):
    """POST /api/token/"""
    name: str = ""
    expired_time: str = ""
    models: str = ""
    subnet: str = ""


class TokenUpdateRequest(BaseModel):
    """PUT /api/token/"""
    id: int
    name: Optional[str] = None
    expired_time: Optional[str] = None
    models: Optional[str] = None
    status: Optional[int] = None
    subnet: Optional[str] = None


# ── Admin User ──

class AdminUserCreateRequest(BaseModel):
    """POST /api/user/ — admin creates a user."""
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1)
    display_name: Optional[str] = None
    email: Optional[str] = None
    group: Optional[str] = None
    quota: Optional[int] = None


class AdminUserUpdateRequest(BaseModel):
    """PUT /api/user/ — admin updates a user."""
    id: int
    username: Optional[str] = None
    password: Optional[str] = None
    display_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[int] = None
    status: Optional[int] = None
    group: Optional[str] = None


# ── Budget Pool ──

class PoolCreateRequest(BaseModel):
    """POST /api/pool/"""
    name: str = Field(min_length=1, max_length=128)
    total_funded: float = 0.0
    period_type: str = "monthly"
    period_key: str = ""


class PoolFundRequest(BaseModel):
    """POST /api/pool/{id}/fund"""
    amount: float = Field(gt=0)
    remark: str = ""


class PoolAllocateRequest(BaseModel):
    """POST /api/pool/{id}/allocate"""
    user_id: int = 0
    amount: float = 0
    period_key: str = ""
    remark: str = ""


class PoolRecallRequest(BaseModel):
    """POST /api/pool/{id}/recall"""
    user_id: int = 0
    amount: float = 0
    period_key: str = ""
    remark: str = ""


class PoolUpdateRequest(BaseModel):
    """PUT /api/pool/{id}"""
    name: Optional[str] = None
    total_funded: Optional[float] = None
    status: Optional[str] = None


class PoolConfigRequest(BaseModel):
    """PUT /api/pool/{id}/config"""
    config: dict = {}


class PoolRecallAllRequest(BaseModel):
    """POST /api/pool/{id}/recall_all"""
    user_id: int = 0
    amount: Optional[float] = None  # None = recall all remaining
    period_key: str = ""
    remark: str = ""


class PoolRolloverRequest(BaseModel):
    """POST /api/pool/{id}/rollover"""
    period_key: str = ""
    new_period_key: str = ""
    new_name: str = ""


# ── System Options ──

class OptionUpdateRequest(BaseModel):
    """PUT /api/option/"""
    key: str = Field(min_length=1, max_length=128)
    value: str = ""


# ── Verification / Password Reset ──

class PasswordResetConfirmRequest(BaseModel):
    """POST /api/user/reset"""
    email: str = ""
    token: str = ""
    password: str = ""


# ── Admin Budget ──

class AdminBudgetUpdateRequest(BaseModel):
    """PUT /api/v1/admin/budgets/{user_id}"""
    monthly_budget: Optional[float] = None


# ── User Self Update ──

class UserSelfUpdateRequest(BaseModel):
    """PUT /api/user/self"""
    password: Optional[str] = None
    old_password: Optional[str] = None
    display_name: Optional[str] = None
    email: Optional[str] = None
