from __future__ import annotations

import ipaddress
import time
from typing import Optional

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.exceptions import ForbiddenException, UnauthorizedException
from app.models.token import Token
from app.models.user import User
from app.services.auth import get_session_user


async def optional_user_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Try session auth but don't reject if unauthenticated."""
    user = await get_session_user(request, db)
    if user:
        request.state.user = user
    return user


async def user_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require a logged-in user (role >= 1)."""
    user = await get_session_user(request, db)
    if not user:
        raise UnauthorizedException(message="Not logged in")
    if user.role < 1:
        raise ForbiddenException(message="Access denied")
    request.state.user = user
    return user


async def admin_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require admin role (role >= 10)."""
    user = await user_auth(request, db)
    if user.role < 10:
        raise ForbiddenException(message="Admin access required")
    return user


async def root_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require root role (role >= 100)."""
    user = await user_auth(request, db)
    if user.role < 100:
        raise ForbiddenException(message="Root access required")
    return user


def _is_ip_allowed(client_ip: str, subnet_cfg: str) -> bool:
    """Check if client_ip matches any entry in subnet_cfg.

    Supports: single IP, CIDR ranges, comma-separated combinations.
    Invalid entries are silently skipped.
    """
    for entry in subnet_cfg.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            net = ipaddress.ip_network(entry, strict=False)
            if ipaddress.ip_address(client_ip) in net:
                return True
        except ValueError:
            continue
    return False


async def token_auth(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate via Bearer token or x-api-key for relay endpoints.

    Supports both OpenAI-style ``Authorization: Bearer <key>`` and
    Anthropic-style ``x-api-key: <key>`` headers so that Claude Code
    (which uses the Anthropic SDK) can connect without reconfiguration.
    """
    raw_key: str | None = None

    # 1. Authorization: Bearer <key> (OpenAI convention)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        raw_key = auth_header[7:]

    # 2. x-api-key: <key> (Anthropic convention — used by Claude Code)
    if not raw_key:
        raw_key = request.headers.get("x-api-key", "").strip()

    if not raw_key:
        raise UnauthorizedException(message="No token provided")

    # Support admin channel pinning: token_key:channel_id
    channel_id = None
    token_key = raw_key
    if ":" in raw_key:
        parts = raw_key.split(":", 1)
        token_key = parts[0]
        try:
            channel_id = int(parts[1])
        except ValueError:
            pass

    result = await db.execute(select(Token).where(Token.key == token_key))
    token = result.scalar_one_or_none()
    if not token:
        raise UnauthorizedException(message="Invalid token")

    if token.status != 1:
        raise UnauthorizedException(message="Token is disabled or expired")

    if token.expired_time > 0 and token.expired_time < time.time():
        raise UnauthorizedException(message="Token has expired")

    # Enforce IP/subnet restriction if configured on the token
    if token.subnet:
        client_ip = request.client.host if request.client else ""
        if not client_ip or not _is_ip_allowed(client_ip, token.subnet):
            raise UnauthorizedException(message="IP not allowed")

    result = await db.execute(select(User).where(User.id == token.user_id))
    user = result.scalar_one_or_none()
    if not user or user.status != 1:
        raise UnauthorizedException(message="User is disabled")

    request.state.user = user
    request.state.token = token
    request.state.channel_id = channel_id
    request.state.token_key = token_key
    return user
