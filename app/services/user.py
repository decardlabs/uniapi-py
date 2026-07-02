from __future__ import annotations

import re
import time
import uuid
from typing import Optional

import httpx
from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.option import Option
from app.models.user import User
from app.services.auth import create_default_token, hash_password, verify_password
from app.services.email import verify_code


def _uuid4() -> str:
    return uuid.uuid4().hex


async def verify_turnstile(token: str) -> bool:
    """Validate a Cloudflare Turnstile token.

    Returns True if validation passes or if Turnstile is not configured.
    Returns False if token is missing/invalid when Turnstile is configured.
    """
    secret_key = settings.turnstile_secret_key
    if not secret_key or not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={"secret": secret_key, "response": token},
            )
            result = resp.json()
            return result.get("success", False)
    except httpx.RequestError:
        return False


def validate_password_strength(password: str) -> Optional[str]:
    """Validate password meets policy. Returns error message or None if valid."""
    if len(password) < settings.password_min_length:
        return f"Password must be at least {settings.password_min_length} characters"
    if settings.password_require_uppercase and not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter"
    if settings.password_require_digit and not re.search(r"\d", password):
        return "Password must contain at least one digit"
    if settings.password_require_special and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return "Password must contain at least one special character"
    return None


async def register_user(
    db: AsyncSession,
    username: str,
    password: str,
    display_name: Optional[str] = None,
    email: Optional[str] = None,
    verification_code: Optional[str] = None,
) -> User:
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    strength_error = validate_password_strength(password)
    if strength_error:
        raise HTTPException(status_code=400, detail=strength_error)

    # Verify email code if email is provided
    if email and verification_code:
        if not verify_code(email, verification_code):
            raise HTTPException(status_code=400, detail="验证码错误或已过期")
    elif email and not verification_code:
        raise HTTPException(status_code=400, detail="请先获取邮箱验证码")

    now = int(time.time() * 1000)
    user = User(
        username=username,
        password=hash_password(password),
        display_name=display_name or username,
        role=1,
        status=1,
        email=email,
        balance=2000000,
        group="default",
        access_token=_uuid4(),
        created_at=now,
        updated_at=now,
    )

    db.add(user)
    await db.flush()
    await create_default_token(db, user.id)
    await db.commit()
    return user


class LoginError(HTTPException):
    """HTTPException with optional data payload for lockout/attempts info."""

    def __init__(self, status_code: int, message: str, data: dict | None = None):
        super().__init__(status_code=status_code, detail=message)
        self.data = data


async def login_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> User:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user:
        await db.flush()
        raise LoginError(status_code=401, message="用户名或密码错误")

    now = int(time.time() * 1000)

    # Check lockout BEFORE password check (prevents revealing locked vs wrong-password)
    if user.locked_until is not None and user.locked_until > now:
        raise LoginError(
            status_code=423,
            message="用户名或密码错误",
            data={"locked": True},
        )

    if user.status != 1:
        raise LoginError(status_code=401, message="用户名或密码错误")

    if not verify_password(password, user.password):
        user.failed_login_attempts += 1
        remaining = settings.login_max_attempts - user.failed_login_attempts

        if user.failed_login_attempts >= settings.login_max_attempts:
            # Lock account for configurable duration
            user.locked_until = now + (settings.login_lockout_minutes * 60 * 1000)
            user.updated_at = now
            await db.commit()
            raise LoginError(
                status_code=423,
                message="用户名或密码错误",
                data={"locked": True},
            )

        user.updated_at = now
        await db.commit()
        raise LoginError(
            status_code=401,
            message="用户名或密码错误",
            data={"attempts_remaining": remaining},
        )

    # Successful login: reset failed attempts
    if user.failed_login_attempts > 0 or user.locked_until is not None:
        user.failed_login_attempts = 0
        user.locked_until = None
        user.updated_at = now
        await db.commit()

    return user


# --- Admin user management ---


async def list_users(
    db: AsyncSession,
    page: int = 0,
    size: int = 10,
) -> tuple[list[User], int]:
    query = select(User).where(User.status != 3).order_by(User.id.desc())
    total_query = select(func.count()).select_from(
        select(User).where(User.status != 3).subquery()
    )
    total = await db.scalar(total_query)
    result = await db.execute(query.offset(page * size).limit(size))
    return list(result.scalars().all()), total or 0


async def search_users(
    db: AsyncSession,
    keyword: str,
    page: int = 0,
    size: int = 10,
) -> tuple[list[User], int]:
    pattern = f"%{keyword}%"
    condition = or_(
        User.username.ilike(pattern),
        User.display_name.ilike(pattern),
        User.email.ilike(pattern),
    )
    base = select(User).where(User.status != 3).where(condition)
    total_query = select(func.count()).select_from(base.subquery())
    total = await db.scalar(total_query)
    result = await db.execute(base.order_by(User.id.desc()).offset(page * size).limit(size))
    return list(result.scalars().all()), total or 0


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def admin_create_user(
    db: AsyncSession,
    username: str,
    password: str,
    display_name: Optional[str] = None,
    email: Optional[str] = None,
    quota: Optional[int] = None,
    group: Optional[str] = None,
) -> User:
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    now = int(time.time() * 1000)
    user = User(
        username=username,
        password=hash_password(password),
        display_name=display_name or username,
        role=1,
        status=1,
        email=email,
        balance=(quota or 1000000) * 2,
        group=group or "default",
        access_token=_uuid4(),
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    await db.flush()
    await create_default_token(db, user.id)
    await db.commit()
    return user


async def admin_update_user(
    db: AsyncSession,
    user_id: int,
    username: Optional[str] = None,
    display_name: Optional[str] = None,
    password: Optional[str] = None,
    email: Optional[str] = None,
    quota: Optional[int] = None,
    group: Optional[str] = None,
    status: Optional[int] = None,
) -> User:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = int(time.time() * 1000)
    if username is not None:
        user.username = username
    if display_name is not None:
        user.display_name = display_name
    if password is not None:
        user.password = hash_password(password)
    if email is not None:
        user.email = email
    if quota is not None:
        user.balance = quota * 2  # old token units → micro-yuan (approximate)
    if group is not None:
        user.group = group
    if status is not None:
        user.status = status
    user.updated_at = now
    await db.commit()
    return user


async def admin_delete_user(db: AsyncSession, user_id: int) -> None:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = int(time.time() * 1000)
    user.status = 3  # Deleted
    user.username = f"deleted_{_uuid4()[:8]}"
    user.updated_at = now
    await db.commit()


async def list_groups(db: AsyncSession) -> list[str]:
    result = await db.execute(select(User.group).distinct())
    return [row[0] for row in result.all()]


async def get_system_status(db: AsyncSession, version: str = "") -> dict:
    options_result = await db.execute(select(Option))
    options = {row.key: row.value for row in options_result.scalars().all()}

    return {
        "version": version,
        "system_name": options.get("SystemName", "UniAPI"),
        "logo": options.get("Logo", ""),
        "footer_html": options.get("Footer", ""),
        "home_page_content": options.get("HomePageContent", ""),
        "theme": options.get("Theme", "modern"),
        "server_address": options.get("ServerAddress", ""),
        "quota_per_unit": int(options.get("QuotaPerUnit", "500000")),
        "display_in_currency": options.get("DisplayInCurrencyEnabled", "false").lower() == "true",
        "display_unit": "token",
        "register_enabled": options.get("RegisterEnabled", "true").lower() == "true",
        "password_login_enabled": options.get("PasswordLoginEnabled", "true").lower() == "true",
        "password_register_enabled": options.get("PasswordRegisterEnabled", "true").lower() == "true",
        "email_verification_enabled": options.get("EmailVerificationEnabled", "false").lower() == "true",
        "turnstile_check": options.get("TurnstileCheckEnabled", "false").lower() == "true",
        "turnstile_site_key": options.get("TurnstileSiteKey", ""),
        "github_oauth": options.get("GitHubOAuthEnabled", "false").lower() == "true",
        "github_client_id": options.get("GitHubClientId", ""),
        "top_up_link": options.get("TopUpLink", ""),
        "chat_link": options.get("ChatLink", ""),
        "group": options.get("Group", ""),
    }
