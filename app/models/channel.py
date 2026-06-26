from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[int] = mapped_column(Integer, default=0)
    key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=1)  # 1=Enabled
    name: Mapped[str] = mapped_column(String(64), index=True, default="")
    weight: Mapped[int] = mapped_column(Integer, default=1)
    created_time: Mapped[int] = mapped_column(BigInteger, default=0)
    test_time: Mapped[int] = mapped_column(BigInteger, default=0)
    response_time: Mapped[int] = mapped_column(Integer, default=0)
    base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    other: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    balance: Mapped[float] = mapped_column(default=0.0)
    balance_updated_time: Mapped[int] = mapped_column(BigInteger, default=0)
    models: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_configs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    group: Mapped[str] = mapped_column(String(64), default="default")
    used_quota: Mapped[int] = mapped_column(BigInteger, default=0)
    model_mapping: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(BigInteger, default=0)
    config: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rate_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    testing_model: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    inference_profile_arn_map: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=0)
