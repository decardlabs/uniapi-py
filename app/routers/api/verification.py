"""Verification & password reset endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.option import Option
from app.models.user import User
from app.schemas.common import GenericApiResponse
from app.schemas.management import PasswordResetConfirmRequest
from app.services.auth import hash_password
from app.services.email import (
    generate_reset_token,
    send_verification_code,
    verify_reset_token,
)
from app.services.user import verify_turnstile

router = APIRouter(tags=["verification"])


class SendVerificationRequest(BaseModel):
    """POST /api/verification"""
    email: str = Field(..., pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    turnstile: str = Field(default="", description="Cloudflare Turnstile token")


@router.post("/api/verification")
async def send_verification(
    body: SendVerificationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a verification code to the given email."""
    # Turnstile check
    turnstile_enabled_result = await db.execute(
        select(Option).where(Option.key == "TurnstileCheckEnabled")
    )
    turnstile_enabled = turnstile_enabled_result.scalar_one_or_none()
    if turnstile_enabled and turnstile_enabled.value.lower() == "true":
        if not await verify_turnstile(body.turnstile):
            return JSONResponse(
                status_code=400,
                content=GenericApiResponse(
                    success=False, message="Turnstile verification failed"
                ).model_dump(),
            )

    # NOTE: Email uniqueness check is intentionally NOT done here
    # to avoid leaking which emails are registered. The check
    # happens at the bind (POST /api/oauth/email/bind) or
    # register (POST /api/user/register) endpoint instead.
    success, message = await send_verification_code(db, body.email)
    if success:
        return GenericApiResponse(success=True, message=message)
    return GenericApiResponse(success=False, message=message)


@router.get("/api/reset_password")
async def reset_password_request(
    email: str = Query(..., description="Email to send reset link"),
    turnstile: str = Query("", description="Cloudflare Turnstile token"),
    db: AsyncSession = Depends(get_db),
):
    """Send a password reset link to the given email."""
    # Turnstile check
    turnstile_enabled_result = await db.execute(
        select(Option).where(Option.key == "TurnstileCheckEnabled")
    )
    turnstile_enabled = turnstile_enabled_result.scalar_one_or_none()
    if turnstile_enabled and turnstile_enabled.value.lower() == "true":
        if not await verify_turnstile(turnstile):
            return JSONResponse(
                status_code=400,
                content=GenericApiResponse(
                    success=False, message="Turnstile verification failed"
                ).model_dump(),
            )

    # Check if user exists
    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    if not user:
        # Don't reveal whether the email exists
        return GenericApiResponse(
            success=True,
            message="如果该邮箱已注册，您将收到密码重置邮件",
        )

    # Generate and send reset token
    token = generate_reset_token(email)
    from app.services.email import load_smtp_config, send_email

    smtp_config = await load_smtp_config(db)
    if smtp_config["host"]:
        reset_link = f"/reset-password?email={email}&token={token}"
        sent = await send_email(
            email,
            subject="密码重置",
            body=f"请点击以下链接重置密码：{reset_link}\n\n链接有效期 30 分钟。",
            smtp_config=smtp_config,
        )
        if not sent:
            return GenericApiResponse(success=False, message="发送密码重置邮件失败")
    else:
        # SMTP not configured - just acknowledge
        pass

    return GenericApiResponse(
        success=True,
        message="如果该邮箱已注册，您将收到密码重置邮件",
    )


@router.post("/api/user/reset")
async def reset_password_confirm(
    body: PasswordResetConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using a reset token."""
    email = body.email
    token = body.token
    new_password = body.password

    if not email or not token or not new_password:
        return GenericApiResponse(success=False, message="缺少必要参数")

    if len(new_password) < 8:
        return GenericApiResponse(success=False, message="密码长度至少 8 位")

    # Verify token
    token_email = verify_reset_token(token)
    if token_email is None:
        return GenericApiResponse(success=False, message="重置链接已过期或无效")

    if token_email != email:
        return GenericApiResponse(success=False, message="邮箱不匹配")

    # Update password
    user_result = await db.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    if not user:
        return GenericApiResponse(success=False, message="用户不存在")

    import time
    user.password = hash_password(new_password)
    user.updated_at = int(time.time() * 1000)
    await db.commit()

    return GenericApiResponse(success=True, message="密码重置成功")


@router.get("/api/internal/verification-code")
async def debug_get_verification_code(
    email: str = Query(..., description="Email to get the code for"),
):
    """Return the stored verification code for the given email.

    ONLY available when DEBUG=true. Used by E2E tests.
    """
    if not settings.debug:
        return GenericApiResponse(success=False, message="Only available in debug mode")

    from app.services.email import get_stored_code

    code = get_stored_code(email)
    if code is None:
        return GenericApiResponse(success=False, message="No verification code found for this email")

    return GenericApiResponse(data={"code": code})
