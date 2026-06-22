"""Recharge request database model."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RechargeRequest(Base):
    __tablename__ = "recharge_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    amount: Mapped[int] = mapped_column(BigInteger, default=0)  # quota amount requested
    status: Mapped[int] = mapped_column(Integer, default=1)  # 1=pending, 2=approved, 3=rejected
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    admin_remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reviewed_time: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_time: Mapped[int] = mapped_column(BigInteger, default=0)
