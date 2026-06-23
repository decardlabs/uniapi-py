from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import user_auth
from app.models.channel import Channel
from app.models.option import Option
from app.schemas.common import GenericApiResponse
from app.schemas.user import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    SelfResponse,
)
from app.services.auth import create_session, get_session_user
from app.services.totp import verify_totp_code
from app.services.user import login_user, register_user, verify_turnstile

router = APIRouter(tags=["auth"])


@router.post("/api/user/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await login_user(db, body.username, body.password)

    # TOTP check
    totp_required = bool(user.totp_secret)
    if totp_required:
        totp_code = body.totp_code or ""
        if not totp_code:
            return GenericApiResponse(
                success=False,
                data={"totp_required": True},
            )
        if not verify_totp_code(user.totp_secret, totp_code):
            return GenericApiResponse(
                success=False, message="Invalid TOTP code"
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
            balance=user.balance,
                group=user.group,
                access_token=user.access_token,
                totp_required=totp_required,
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
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Turnstile validation
    turnstile_token = request.query_params.get("turnstile", "")
    turnstile_enabled_result = await db.execute(
        select(Option).where(Option.key == "TurnstileCheckEnabled")
    )
    turnstile_enabled = turnstile_enabled_result.scalar_one_or_none()
    if turnstile_enabled and turnstile_enabled.value.lower() == "true":
        if not await verify_turnstile(turnstile_token):
            return JSONResponse(
                status_code=400,
                content=GenericApiResponse(
                    success=False, message="Turnstile verification failed"
                ).model_dump(),
            )

    user = await register_user(
        db,
        username=body.username,
        password=body.password,
        display_name=body.display_name,
        email=body.email,
        verification_code=body.verification_code,
        aff_code=body.aff_code,
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
            balance=user.balance,
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
            balance=user.balance,
            used_quota=user.used_quota,
            group=user.group,
            created_at=user.created_at // 1000 if user.created_at else 0,
            updated_at=user.updated_at // 1000 if user.updated_at else 0,
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
            balance=user.balance,
            used_quota=user.used_quota,
            group=user.group,
        ).model_dump()
    )


@router.get("/api/available_models")
async def available_models():
    return GenericApiResponse(data=[])


@router.get("/api/user/available_models")
async def user_available_models(
    db: AsyncSession = Depends(get_db),
    _=Depends(user_auth),
):
    """Return models available from enabled channels.

    Used by the frontend playground to populate the model selector.
    Returns model names from all enabled channels.
    """
    result = await db.execute(select(Channel).where(Channel.status == 1))
    channels = result.scalars().all()

    models = set()
    for ch in channels:
        if ch.models:
            for m in ch.models.split(","):
                name = m.strip()
                if name:
                    models.add(name)
        else:
            # Channel without specific model list: add its adaptor's models
            from app.relay.registry import registry
            adaptor = registry.get(ch.type)
            if adaptor:
                for m in adaptor.get_supported_models():
                    models.add(m)

    return GenericApiResponse(data=sorted(models))


@router.get("/api/models/display")
async def models_display(db: AsyncSession = Depends(get_db)):
    """List models from configured channels with pricing.

    Returns channel_name → {models: {model_name: pricing}} mapping.
    Only shows models from channels that are actually configured (status=1).
    """
    from app.relay.registry import registry

    result = await db.execute(select(Channel).where(Channel.status == 1))
    channels = result.scalars().all()

    display = {}
    for ch in channels:
        adaptor = registry.get(ch.type)
        if not adaptor:
            continue
        all_pricing = adaptor.get_supported_models()

        # Determine which models to show for this channel
        if ch.models:
            model_names = [m.strip() for m in ch.models.split(",")]
        else:
            model_names = list(all_pricing.keys())

        models_data = {}
        for model_name in model_names:
            config = all_pricing.get(model_name)
            if config:
                models_data[model_name] = {
                    "input_price": config.input_ratio,
                    "output_price": config.output_ratio,
                    "cached_input_price": config.cached_input_ratio,
                }

        if models_data:
            display[ch.name or adaptor.provider_name] = {"models": models_data}

    return GenericApiResponse(data=display)


@router.get("/api/home_page_content")
async def home_page_content(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Option).where(Option.key == "HomePageContent"))
    opt = result.scalar_one_or_none()
    return GenericApiResponse(data=opt.value if opt else "")


@router.get("/api/about")
async def about_page(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Option).where(Option.key == "About"))
    opt = result.scalar_one_or_none()
    about = opt.value if opt else ""
    return GenericApiResponse(data=about)


@router.get("/api/tools/display")
async def tools_display():
    return GenericApiResponse(data=[])


@router.get("/api/models")
async def models_list():
    """Model catalog by provider type — used by channel form for model selection.

    Returns: {type_id: [model_name, ...]} for all registered providers.
    """
    from app.relay.registry import registry

    catalog = {}
    for ct in [39, 41, 50, 25, 27]:
        adaptor = registry.get(ct)
        if adaptor:
            catalog[str(ct)] = list(adaptor.get_supported_models().keys())

    return GenericApiResponse(data=catalog)
