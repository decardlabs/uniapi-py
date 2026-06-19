from __future__ import annotations

import time
import uuid
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.option import Option
from app.models.token import Token
from app.models.user import User
from app.services.auth import create_default_token, hash_password, verify_password


def _uuid4() -> str:
    return uuid.uuid4().hex


async def register_user(
    db: AsyncSession,
    username: str,
    password: str,
    display_name: Optional[str] = None,
    email: Optional[str] = None,
) -> User:
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already taken")

    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    now = int(time.time() * 1000)
    user = User(
        username=username,
        password=hash_password(password),
        display_name=display_name or username,
        role=1,
        status=1,
        email=email,
        quota=1000000,
        used_quota=0,
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


async def login_user(
    db: AsyncSession,
    username: str,
    password: str,
) -> User:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if user.status != 1:
        raise HTTPException(status_code=401, detail="Account is disabled")

    if not verify_password(password, user.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")

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
        quota=quota or 1000000,
        used_quota=0,
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
        user.quota = quota
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


async def admin_disable_totp(db: AsyncSession, user_id: int) -> None:
    user = await get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.totp_secret = None
    user.updated_at = int(time.time() * 1000)
    await db.commit()


async def list_groups(db: AsyncSession) -> list[str]:
    result = await db.execute(select(User.group).distinct())
    return [row[0] for row in result.all()]


async def get_system_status(db: AsyncSession) -> dict:
    options_result = await db.execute(select(Option))
    options = {row.key: row.value for row in options_result.scalars().all()}

    import importlib.metadata
    version = importlib.metadata.version("uniapi-py")

    return {
        "version": version,
        "system_name": options.get("SystemName", "UniAPI"),
        "logo": options.get("Logo", ""),
        "footer_html": options.get("Footer", ""),
        "home_page_content": options.get("HomePageContent", ""),
        "theme": "modern",
        "server_address": options.get("ServerAddress", ""),
        "quota_per_unit": 500000,
        "display_in_currency": False,
        "display_unit": "token",
        "turnstile_check": False,
        "password_login_enabled": True,
        "password_register_enabled": True,
        "email_verification_enabled": False,
        "github_oauth": False,
        "top_up_link": options.get("TopUpLink", ""),
        "chat_link": options.get("ChatLink", ""),
        "register_enabled": True,
        "group": "",
    }
