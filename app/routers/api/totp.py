"""TOTP (two-factor authentication) endpoints for regular users."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import user_auth
from app.schemas.common import GenericApiResponse
from app.services.totp import generate_totp_secret, get_totp_uri, verify_totp_code

router = APIRouter(tags=["totp"])


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

    The secret is stored in the database with an expiry time until confirmed
    via /confirm. Calling this again overwrites any pending unconfirmed secret.
    """
    secret = generate_totp_secret()
    email = user.email or f"{user.username}@localhost"
    uri = get_totp_uri(secret, email)

    # Persist to DB instead of memory
    expires_at_ms = int(time.time() * 1000) + settings.totp_pending_ttl_seconds * 1000
    user.pending_totp_secret = secret
    user.pending_totp_expires_at = expires_at_ms
    user.updated_at = int(time.time() * 1000)
    await db.commit()

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

    now_ms = int(time.time() * 1000)
    pending_secret = user.pending_totp_secret
    expires_at = user.pending_totp_expires_at

    # Check expiry
    if not pending_secret or not expires_at or expires_at < now_ms:
        return GenericApiResponse(
            success=False,
            message="TOTP setup expired, please retry",
        )

    if not verify_totp_code(pending_secret, totp_code):
        return GenericApiResponse(success=False, message="验证码错误")

    # Commit permanently
    user.totp_secret = pending_secret
    user.pending_totp_secret = None
    user.pending_totp_expires_at = None
    user.updated_at = now_ms
    await db.commit()

    return GenericApiResponse(data={})


@router.post("/api/user/totp/cancel")
async def totp_cancel(
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    """Cancel a pending TOTP setup."""
    user.pending_totp_secret = None
    user.pending_totp_expires_at = None
    user.updated_at = int(time.time() * 1000)
    await db.commit()
    return GenericApiResponse(data={"cancelled": True})


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
        return GenericApiResponse(success=False, message="TOTP is not enabled")

    if not verify_totp_code(user.totp_secret, totp_code):
        return GenericApiResponse(success=False, message="验证码错误")

    user.totp_secret = None
    user.updated_at = int(time.time() * 1000)
    await db.commit()

    return GenericApiResponse(data={})
