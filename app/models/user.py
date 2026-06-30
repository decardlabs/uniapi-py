from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(20), index=True, nullable=True)
    role: Mapped[int] = mapped_column(Integer, default=1)  # 0=Guest, 1=Common, 10=Admin, 100=Root
    status: Mapped[int] = mapped_column(Integer, default=1)  # 1=Enabled, 2=Disabled, 3=Deleted
    email: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    session_version: Mapped[int] = mapped_column(Integer, default=1)
    github_id: Mapped[Optional[str]] = mapped_column("github_id", String(64), index=True, nullable=True)
    access_token: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    balance: Mapped[int] = mapped_column(BigInteger, default=0)  # micro-yuan (10^-6 yuan), ¥1 = 1_000_000
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    group: Mapped[str] = mapped_column(String(32), default="default")
    mcp_tool_blacklist: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=0)
