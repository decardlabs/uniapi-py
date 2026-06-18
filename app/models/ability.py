from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Ability(Base):
    __tablename__ = "abilities"

    group: Mapped[str] = mapped_column(String(32), primary_key=True)
    model: Mapped[str] = mapped_column(String(128), primary_key=True)
    channel_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(BigInteger, default=0, index=True)
    suspend_until: Mapped[Optional[datetime]] = mapped_column(Time, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=0)
