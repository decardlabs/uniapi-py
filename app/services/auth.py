from __future__ import annotations

import secrets
import time
from typing import Optional

import bcrypt
from fastapi import Request
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.token import Token
from app.models.user import User

_serializer: Optional[URLSafeTimedSerializer] = None


def _get_serializer() -> URLSafeTimedSerializer:
    global _serializer
    if _serializer is None:
        _serializer = URLSafeTimedSerializer(
            settings.session_secret_key, salt="session"
        )
    return _serializer


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_session(user: User) -> str:
    data = {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "status": user.status,
    }
    return _get_serializer().dumps(data)


def decode_session(token: str) -> Optional[dict]:
    try:
        return _get_serializer().loads(token, max_age=settings.cookie_max_age_hours * 3600)
    except Exception:
        return None


async def get_session_user(request: Request, db: AsyncSession) -> Optional[User]:
    token = request.cookies.get("session")
    if not token:
        # Fallback: check Authorization header for access_token
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            access_key = auth[7:]
            result = await db.execute(
                select(User).where(User.access_token == access_key, User.status == 1)
            )
            return result.scalar_one_or_none()
        return None

    data = decode_session(token)
    if not data:
        return None

    result = await db.execute(select(User).where(User.id == data["id"]))
    return result.scalar_one_or_none()


def generate_token_key() -> str:
    return settings.token_key_prefix + secrets.token_hex(24)


async def create_default_token(db: AsyncSession, user_id: int) -> Token:
    now = int(time.time())
    token = Token(
        user_id=user_id,
        key=generate_token_key(),
        name="default",
        created_time=now * 1000,
        accessed_time=now * 1000,
        created_at=int(time.time() * 1000),
        updated_at=int(time.time() * 1000),
    )
    db.add(token)
    await db.flush()
    return token
