from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Token(Base):
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    key: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    status: Mapped[int] = mapped_column(Integer, default=1)  # 1=Enabled, 2=Disabled, 3=Expired, 4=Exhausted
    name: Mapped[str] = mapped_column(String(64), index=True, default="")
    created_time: Mapped[int] = mapped_column(BigInteger, default=0)
    accessed_time: Mapped[int] = mapped_column(BigInteger, default=0)
    expired_time: Mapped[int] = mapped_column(BigInteger, default=-1)
    remain_quota: Mapped[int] = mapped_column(BigInteger, default=0)
    unlimited_quota: Mapped[bool] = mapped_column(Boolean, default=False)
    used_quota: Mapped[int] = mapped_column(BigInteger, default=0)
    models: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subnet: Mapped[Optional[str]] = mapped_column(String(255), default="")
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=0)
