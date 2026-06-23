from __future__ import annotations

from typing import Optional

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MCPServer(Base):
    __tablename__ = "mcp_servers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=1)  # 1=enabled, 0=disabled
    priority: Mapped[int] = mapped_column(Integer, default=0)
    base_url: Mapped[str] = mapped_column(Text, default="")
    protocol: Mapped[str] = mapped_column(String(64), default="streamable_http")
    auth_type: Mapped[str] = mapped_column(String(32), default="none")
    api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    headers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_whitelist: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_blacklist: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_pricing: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auto_sync_enabled: Mapped[int] = mapped_column(Integer, default=1)
    auto_sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_sync_at: Mapped[int] = mapped_column(BigInteger, default=0)
    last_sync_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    last_test_at: Mapped[int] = mapped_column(BigInteger, default=0)
    last_test_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    tool_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_at: Mapped[int] = mapped_column(BigInteger, default=0)
