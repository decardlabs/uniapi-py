"""Redemption code database model."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RedemptionCode(Base):
    __tablename__ = "redemption_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    quota: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)  # 1=active, 2=disabled, 3=used
    used_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    used_time: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, default=0)
    created_time: Mapped[int] = mapped_column(BigInteger, default=0)
