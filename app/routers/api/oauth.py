"""OAuth endpoints for third-party login (GitHub, etc.)."""

from __future__ import annotations

import secrets
import time
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.option import Option
from app.models.user import User
from app.schemas.common import GenericApiResponse
from app.schemas.user import LoginResponse
from app.services.auth import create_default_token, create_session, hash_password

router = APIRouter(tags=["oauth"])

# In-memory OAuth state store: {state: {"email": str, "expires": int}}
_oauth_states: dict[str, dict] = {}


def _uuid4() -> str:
    return uuid.uuid4().hex


@router.get("/api/oauth/state")
async def oauth_state():
    """Generate an OAuth state token for CSRF protection.

    Returns: {"success": true, "data": "<state_string>"}
    """
    state = secrets.token_hex(16)
    _oauth_states[state] = {
        "expires": int(time.time()) + 600,  # 10-minute TTL
    }
    return GenericApiResponse(data=state)


def _verify_oauth_state(state: str) -> bool:
    """Verify that an OAuth state token is valid and not expired."""
    record = _oauth_states.pop(state, None)
    if not record:
        return False
    if int(time.time()) > record["expires"]:
        return False
    return True


@router.get("/api/oauth/github")
async def github_oauth_callback(
    code: str = "",
    state: str = "",
    db: AsyncSession = Depends(get_db),
):
    """GitHub OAuth callback endpoint.

    Exchanges authorization code for access token,
    fetches user info from GitHub, and creates/logs in the user.
    """
    if not code or not state:
        return GenericApiResponse(success=False, message="Missing code or state parameter")

    # Verify OAuth state (CSRF protection)
    if not _verify_oauth_state(state):
        return GenericApiResponse(success=False, message="Invalid or expired state token")

    # Get GitHub OAuth config
    options_result = await db.execute(
        select(Option).where(
            Option.key.in_(["GitHubOAuthEnabled", "GitHubClientId"])
        )
    )
    opts = {row.key: row.value for row in options_result.scalars().all()}

    if opts.get("GitHubOAuthEnabled", "false").lower() != "true":
        return GenericApiResponse(success=False, message="GitHub OAuth is not enabled")

    client_id = opts.get("GitHubClientId", "")
    client_secret = settings.github_client_secret

    if not client_id or not client_secret:
        return GenericApiResponse(success=False, message="GitHub OAuth not configured")

    # Exchange code for access token
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            if not access_token:
                return GenericApiResponse(
                    success=False,
                    message="Failed to exchange GitHub code for token",
                )

            # Fetch user info
            user_resp = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            github_user = user_resp.json()
            github_id = str(github_user.get("id", ""))
            github_login = github_user.get("login", "")
            github_name = github_user.get("name") or github_login

            # Fetch primary email
            email_resp = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            emails = email_resp.json()
            primary_email = ""
            for e in emails:
                if e.get("primary") and e.get("verified"):
                    primary_email = e.get("email", "")
                    break
            if not primary_email and emails:
                primary_email = emails[0].get("email", "")

    except httpx.RequestError as e:
        return GenericApiResponse(
            success=False, message=f"GitHub API request failed: {str(e)}"
        )

    # Look up existing user by github_id
    user_result = await db.execute(
        select(User).where(User.github_id == github_id)
    )
    user = user_result.scalar_one_or_none()

    if user:
        # Existing user — log them in
        session_token = create_session(user)
        response = JSONResponse(
            content=GenericApiResponse(
                data=LoginResponse(
                    id=user.id,
                    username=user.username,
                    display_name=user.display_name or user.username,
                    role=user.role,
                    status=user.status,
                    quota=user.quota,
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

    # New user — create account via GitHub
    now = int(time.time() * 1000)
    username = github_login
    # Handle username collision
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        username = f"{github_login}_{secrets.token_hex(4)}"

    random_password = secrets.token_hex(16)
    aff_code_val = secrets.token_hex(8)

    user = User(
        username=username,
        password=hash_password(random_password),
        display_name=github_name,
        role=1,
        status=1,
        email=primary_email,
        github_id=github_id,
        quota=1000000,
        used_quota=0,
        group="default",
        access_token=_uuid4(),
        aff_code=aff_code_val,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    await db.flush()
    await create_default_token(db, user.id)
    await db.commit()

    # Create session and return
    session_token = create_session(user)
    response = JSONResponse(
        content=GenericApiResponse(
            data=LoginResponse(
                id=user.id,
                username=user.username,
                display_name=user.display_name or user.username,
                role=user.role,
                status=user.status,
                quota=user.quota,
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
