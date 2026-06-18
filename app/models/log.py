from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, index=True, default=0)
    type: Mapped[int] = mapped_column(Integer, index=True, default=2)  # 2=Consume
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    token_name: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    quota: Mapped[int] = mapped_column(Integer, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    channel_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    request_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    elapsed_time: Mapped[int] = mapped_column(BigInteger, default=0)
    is_stream: Mapped[bool] = mapped_column(Boolean, default=False)
    system_prompt_reset: Mapped[bool] = mapped_column(Boolean, default=False)
    cached_prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    _metadata: Mapped[Optional[str]] = mapped_column("metadata", Text, nullable=True)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=0)
