"""TOTP (two-factor authentication) endpoints for regular users."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import user_auth
from app.schemas.common import GenericApiResponse
from app.services.totp import generate_totp_secret, get_totp_uri, verify_totp_code

router = APIRouter(tags=["totp"])

# In-memory pending TOTP setups: {user_id: secret}
_pending_setups: dict[int, str] = {}


@router.get("/api/user/totp/status")
async def totp_status(
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    """Check if TOTP is enabled for the current user."""
    return GenericApiResponse(
        data={"totp_enabled": bool(user.totp_secret)}
    )


@router.get("/api/user/totp/setup")
async def totp_setup(
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    """Generate a new TOTP secret and provisioning URI.

    The secret is stored in memory until confirmed via /confirm.
    Calling this again overwrites any pending unconfirmed secret.
    """
    secret = generate_totp_secret()
    email = user.email or f"{user.username}@localhost"
    uri = get_totp_uri(secret, email)
    _pending_setups[user.id] = secret

    return GenericApiResponse(data={
        "secret": secret,
        "qr_code": uri,
    })


@router.post("/api/user/totp/confirm")
async def totp_confirm(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    """Verify a TOTP code and enable TOTP for the user."""
    totp_code = body.get("totp_code", "")
    if not totp_code or not isinstance(totp_code, str) or len(totp_code) != 6:
        return GenericApiResponse(success=False, message="验证码格式不正确")

    secret = _pending_setups.get(user.id)
    if not secret:
        return GenericApiResponse(success=False, message="请先获取验证码密钥")

    if not verify_totp_code(secret, totp_code):
        return GenericApiResponse(success=False, message="验证码错误")

    # Save secret to user record
    user.totp_secret = secret
    user.updated_at = int(time.time() * 1000)
    _pending_setups.pop(user.id, None)
    await db.commit()

    return GenericApiResponse(data={})


@router.post("/api/user/totp/disable")
async def totp_disable(
    body: dict,
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    """Disable TOTP by verifying a valid code first."""
    totp_code = body.get("totp_code", "")
    if not totp_code or not isinstance(totp_code, str) or len(totp_code) != 6:
        return GenericApiResponse(success=False, message="验证码格式不正确")

    if not user.totp_secret:
        return GenericApiResponse(success=False, message="TOTP 未开启")

    if not verify_totp_code(user.totp_secret, totp_code):
        return GenericApiResponse(success=False, message="验证码错误")

    user.totp_secret = None
    user.updated_at = int(time.time() * 1000)
    await db.commit()

    return GenericApiResponse(data={})
