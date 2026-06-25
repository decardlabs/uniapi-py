"""Passkey (WebAuthn) endpoints for passwordless authentication."""

from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import user_auth
from app.models.passkey import PasskeyCredential
from app.models.token import Token as TokenModel
from app.models.user import User
from app.schemas.common import GenericApiResponse
from app.schemas.user import LoginResponse
from app.services.auth import create_default_token, create_session, hash_password
from app.services.webauthn import (
    generate_registration_opts,
    verify_registration,
    generate_authentication_opts,
    verify_authentication,
)

import secrets
import uuid

router = APIRouter(tags=["passkey"])


def _get_rp_id(request: Request) -> str:
    """Get the Relying Party ID from config, not from user-supplied Host header."""
    from app.config import settings
    return settings.webauthn_rp_id


def _get_origin(request: Request) -> str:
    """Get the origin from the request."""
    forwarded = request.headers.get("x-forwarded-proto", "http")
    host = request.headers.get("host", "localhost")
    return f"{forwarded}://{host}"


def _uuid4() -> str:
    return uuid.uuid4().hex


# --- User-facing endpoints (require auth) ---


@router.get("/api/user/passkey")
async def list_passkeys(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    """List the user's registered passkeys."""
    result = await db.execute(
        select(PasskeyCredential)
        .where(PasskeyCredential.user_id == user.id)
        .order_by(PasskeyCredential.id.desc())
    )
    credentials = result.scalars().all()

    return GenericApiResponse(
        data=[
            {
                "id": c.id,
                "credential_name": c.credential_name,
                "sign_count": c.sign_count,
                "created_at": c.created_at,
            }
            for c in credentials
        ]
    )


@router.post("/api/user/passkey/register/begin")
async def register_passkey_begin(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    """Start WebAuthn registration. Returns publicKey options for the browser."""
    rp_id = _get_rp_id(request)
    origin = _get_origin(request)

    # Get existing credential IDs to exclude
    result = await db.execute(
        select(PasskeyCredential).where(PasskeyCredential.user_id == user.id)
    )
    existing = result.scalars().all()
    existing_ids = [c.credential_id for c in existing]

    public_key = generate_registration_opts(
        rp_id=rp_id,
        rp_name="UniAPI",
        user_name=user.username,
        user_id_str=str(user.id),
        user_display_name=user.display_name or user.username,
        existing_credential_ids=existing_ids,
    )

    return GenericApiResponse(data={"publicKey": public_key})


@router.post("/api/user/passkey/register/finish")
async def register_passkey_finish(
    request: Request,
    name: str = Query("Passkey", max_length=128),
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    """Complete WebAuthn registration by verifying the browser response."""
    rp_id = _get_rp_id(request)
    origin = _get_origin(request)

    body = await request.json()
    result = verify_registration(
        credential=body,
        expected_rp_id=rp_id,
        expected_origin=origin,
    )

    if result is None:
        return GenericApiResponse(success=False, message="注册验证失败")

    # Check for duplicate credential ID
    existing = await db.execute(
        select(PasskeyCredential).where(
            PasskeyCredential.credential_id == result["credential_id"]
        )
    )
    if existing.scalar_one_or_none():
        return GenericApiResponse(success=False, message="此通行密钥已注册")

    now = int(time.time() * 1000)
    credential = PasskeyCredential(
        user_id=user.id,
        credential_id=result["credential_id"],
        public_key=result["public_key"].hex(),
        sign_count=result["sign_count"],
        credential_name=name,
        transports=json.dumps(body.get("response", {}).get("transports", [])),
        created_at=now,
    )
    db.add(credential)
    await db.commit()

    return GenericApiResponse(data={})


@router.delete("/api/user/passkey/{passkey_id}")
async def delete_passkey(
    passkey_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(user_auth),
):
    """Delete a registered passkey."""
    result = await db.execute(
        select(PasskeyCredential).where(
            PasskeyCredential.id == passkey_id,
            PasskeyCredential.user_id == user.id,
        )
    )
    credential = result.scalar_one_or_none()
    if not credential:
        return GenericApiResponse(success=False, message="通行密钥不存在")

    await db.delete(credential)
    await db.commit()

    return GenericApiResponse(data={})


# --- Unauthenticated endpoints (login flow) ---


@router.post("/api/user/passkey/login/begin")
async def login_passkey_begin(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Start WebAuthn authentication (login). Returns publicKey options."""
    rp_id = _get_rp_id(request)

    # Get all registered credentials to offer for login
    result = await db.execute(
        select(PasskeyCredential).order_by(PasskeyCredential.id.desc())
    )
    all_credentials = result.scalars().all()

    credential_descriptors = [
        {"id": c.credential_id} for c in all_credentials
    ]
    public_key = generate_authentication_opts(
        rp_id=rp_id,
        credential_descriptors=credential_descriptors,
    )

    return GenericApiResponse(data={"publicKey": public_key})


@router.post("/api/user/passkey/login/finish")
async def login_passkey_finish(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Complete WebAuthn authentication and log the user in."""
    rp_id = _get_rp_id(request)
    origin = _get_origin(request)

    body = await request.json()
    credential_id = body.get("id", "")
    if not credential_id:
        return GenericApiResponse(success=False, message="缺少凭据 ID")

    # Find the credential record
    result = await db.execute(
        select(PasskeyCredential).where(
            PasskeyCredential.credential_id == credential_id
        )
    )
    credential_record = result.scalar_one_or_none()
    if not credential_record:
        return GenericApiResponse(success=False, message="通行密钥不存在")

    public_key_bytes = bytes.fromhex(credential_record.public_key)

    result = verify_authentication(
        credential=body,
        expected_rp_id=rp_id,
        expected_origin=origin,
        credential_public_key=public_key_bytes,
        credential_current_sign_count=credential_record.sign_count,
    )

    if result is None:
        return GenericApiResponse(success=False, message="登录验证失败")

    # Update sign count
    credential_record.sign_count = result["sign_count"]
    await db.commit()

    # Look up user
    user_result = await db.execute(
        select(User).where(User.id == credential_record.user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user or user.status != 1:
        return GenericApiResponse(success=False, message="用户不存在或已禁用")

    # Create session
    session_token = create_session(user)
    from fastapi.responses import JSONResponse

    response = JSONResponse(
        content=GenericApiResponse(
            data=LoginResponse(
                id=user.id,
                username=user.username,
                display_name=user.display_name or user.username,
                role=user.role,
                status=user.status,
                quota=0,
                group=user.group,
                access_token=user.access_token,
            ).model_dump()
        ).model_dump()
    )
    response.set_cookie(
        key="session",
        value=session_token,
        max_age=3600 * 168,
        httponly=True,
        secure=False,
        samesite="lax",
    )
    return response
