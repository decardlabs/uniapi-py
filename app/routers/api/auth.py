from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.common import GenericApiResponse
from app.schemas.user import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    SelfResponse,
)
from app.services.auth import create_session, get_session_user
from app.services.user import login_user, register_user

router = APIRouter(tags=["auth"])


@router.post("/api/user/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await login_user(db, body.username, body.password)
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


@router.post("/api/user/register")
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await register_user(
        db,
        username=body.username,
        password=body.password,
        display_name=body.display_name,
        email=body.email,
    )
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


@router.get("/api/user/logout")
async def logout():
    response = JSONResponse(
        content=GenericApiResponse(message="Logged out").model_dump()
    )
    response.delete_cookie("session")
    return response


@router.get("/api/user/self")
async def self_info(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await get_session_user(request, db)
    if not user:
        return GenericApiResponse(success=False, message="Not logged in")
    return GenericApiResponse(
        data=SelfResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name or user.username,
            email=user.email,
            role=user.role,
            status=user.status,
            quota=user.quota,
            used_quota=user.used_quota,
            group=user.group,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ).model_dump()
    )


@router.put("/api/user/self")
async def update_self(
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update current user's display_name, email, or password."""
    user = await get_session_user(request, db)
    if not user:
        return GenericApiResponse(success=False, message="Not logged in")

    new_password = body.get("password")
    if new_password:
        from app.services.auth import hash_password, verify_password
        if not verify_password(body.get("old_password", ""), user.password):
            return GenericApiResponse(success=False, message="Old password is incorrect")
        user.password = hash_password(new_password)

    if "display_name" in body:
        user.display_name = body["display_name"]
    if "email" in body:
        user.email = body["email"]
    user.updated_at = int(time.time() * 1000)
    await db.commit()
    return GenericApiResponse(data={"updated": True})


@router.get("/api/user/aff")
async def user_aff(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Get current user's affiliate info."""
    user = await get_session_user(request, db)
    if not user:
        return GenericApiResponse(success=False, message="Not logged in")
    return GenericApiResponse(data={
        "aff_code": user.aff_code or "",
        "inviter_id": user.inviter_id,
    })


@router.get("/api/user/token")
async def get_access_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await get_session_user(request, db)
    if not user:
        return GenericApiResponse(success=False, message="Not logged in")
    return GenericApiResponse(data=user.access_token)


@router.get("/api/user/get-by-token")
async def get_by_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    from app.dependencies import token_auth

    user = await token_auth(request, db)
    if not user:
        return GenericApiResponse(success=False, message="Invalid token")
    return GenericApiResponse(
        data=SelfResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name or user.username,
            role=user.role,
            status=user.status,
            quota=user.quota,
            used_quota=user.used_quota,
            group=user.group,
        ).model_dump()
    )


@router.get("/api/available_models")
async def available_models():
    return GenericApiResponse(data=[])


@router.get("/api/user/available_models")
async def user_available_models():
    """Public model listing (expected by frontend at this path)."""
    return GenericApiResponse(data=[])


@router.get("/api/models/display")
async def models_display():
    """Public model listing with pricing."""
    from app.relay.adaptors.deepseek.pricing import MODEL_PRICING

    models_data = {}
    for model_name, config in MODEL_PRICING.items():
        input_price = config.input_ratio * 500000 / 1000000
        output_price = config.output_ratio * config.input_ratio * 500000 / 1000000
        cached_price = config.cached_input_ratio * 500000 / 1000000
        models_data[model_name] = {
            "input_price": input_price,
            "output_price": output_price,
            "cached_input_price": cached_price,
        }

    return GenericApiResponse(
        data={
            "DeepSeek": {
                "models": models_data,
            }
        }
    )


@router.get("/api/home_page_content")
async def home_page_content():
    return GenericApiResponse(data={"content": ""})


@router.get("/api/about")
async def about_page():
    return GenericApiResponse(data={"content": ""})


@router.get("/api/tools/display")
async def tools_display():
    return GenericApiResponse(data=[])


@router.get("/api/models")
async def models_list():
    """Model list (same as /api/models/display for compatibility)."""
    # Import and delegate
    return await models_display()
