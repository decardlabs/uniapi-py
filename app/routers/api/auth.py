from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import user_auth
from app.config import settings
from app.models.channel import Channel
from app.models.option import Option
from app.schemas.common import GenericApiResponse
from app.schemas.management import UserSelfUpdateRequest
from app.schemas.user import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    SelfResponse,
)
from app.services.auth import create_session, get_session_user
from app.services.user import login_user, register_user, verify_turnstile

router = APIRouter(tags=["auth"])


@router.post("/api/user/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    # Turnstile check (if enabled globally)
    turnstile_enabled_result = await db.execute(
        select(Option).where(Option.key == "TurnstileCheckEnabled")
    )
    turnstile_enabled = turnstile_enabled_result.scalar_one_or_none()
    if turnstile_enabled and turnstile_enabled.value.lower() == "true":
        if not await verify_turnstile(body.turnstile_token or ""):
            return JSONResponse(
                status_code=403,
                content=GenericApiResponse(
                    success=False,
                    message="Turnstile verification failed, please refresh and try again",
                ).model_dump(),
            )

    from fastapi import HTTPException
    try:
        user = await login_user(db, body.username, body.password)
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content=GenericApiResponse(
                success=False,
                message=e.detail,
            ).model_dump(),
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
        secure=settings.session_cookie_secure,
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
            balance=user.balance,
            group=user.group,
            created_at=user.created_at // 1000 if user.created_at else 0,
            updated_at=user.updated_at // 1000 if user.updated_at else 0,
        ).model_dump()
    )


@router.put("/api/user/self")
async def update_self(
    body: UserSelfUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update current user's display_name, email, or password."""
    user = await get_session_user(request, db)
    if not user:
        return GenericApiResponse(success=False, message="Not logged in")

    new_password = body.password
    if new_password:
        from app.services.auth import hash_password, verify_password
        from app.services.user import validate_password_strength
        if not verify_password(body.old_password or "", user.password):
            return GenericApiResponse(success=False, message="Old password is incorrect")
        strength_error = validate_password_strength(new_password)
        if strength_error:
            return GenericApiResponse(success=False, message=strength_error)
        user.password = hash_password(new_password)

    if body.display_name is not None:
        user.display_name = body.display_name
    if body.email is not None:
        user.email = body.email
    user.updated_at = int(time.time() * 1000)
    await db.commit()

    # Rotate session token on password change to invalidate old sessions
    if new_password:
        new_session = create_session(user)
        resp = JSONResponse(
            content=GenericApiResponse(data={"updated": True}).model_dump(),
        )
        resp.set_cookie(
            key="session",
            value=new_session,
            max_age=3600 * 168,
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite="lax",
        )
        return resp

    return GenericApiResponse(data={"updated": True})


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
            balance=user.balance,
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
    Falls back to all registered adaptor models when no channels are configured.
    """
    from app.relay.registry import registry

    result = await db.execute(select(Channel).where(Channel.status == 1))
    channels = result.scalars().all()

    models = set()
    if channels:
        for ch in channels:
            if ch.models:
                for m in ch.models.split(","):
                    name = m.strip()
                    if name:
                        models.add(name)
            else:
                # Channel without specific model list: add its adaptor's models
                adaptor = registry.get(ch.type)
                if adaptor:
                    for m in adaptor.get_supported_models():
                        models.add(m)
    else:
        # No channels configured yet — show all adaptor models as preview
        for adaptor in registry.all_adaptors():
            for m in adaptor.get_supported_models():
                models.add(m)

    return GenericApiResponse(data=sorted(models))


@router.get("/api/models/display")
async def models_display(db: AsyncSession = Depends(get_db)):
    """List models from configured channels with pricing.

    Returns channel_name → {models: {model_name: pricing}} mapping.
    Only shows models from channels that are actually configured (status=1).
    Falls back to all registered adaptors when no channels are configured.
    """
    from app.relay.registry import registry
    from app.budget.pricing import get_model_pricing, MODEL_PRICING_YUAN

    result = await db.execute(select(Channel).where(Channel.status == 1))
    channels = result.scalars().all()

    display = {}

    if channels:
        for ch in channels:
            adaptor = registry.get(ch.type)
            if not adaptor:
                continue
            all_models = adaptor.get_supported_models()

            # Determine which models to show for this channel
            if ch.models:
                model_names = [m.strip() for m in ch.models.split(",")]
            else:
                model_names = list(all_models.keys())

            models_data = {}
            for model_name in model_names:
                if model_name not in all_models:
                    continue
                try:
                    pricing = get_model_pricing(model_name)
                except KeyError:
                    # Fallback: use MODEL_PRICING_YUAN with lowercased name
                    try:
                        pricing = get_model_pricing(model_name.lower())
                    except KeyError:
                        continue
                models_data[model_name] = {
                    "input_price": pricing["input"],
                    "output_price": pricing["output"],
                    "cached_input_price": pricing["cache_hit"],
                }

            if models_data:
                display[ch.name or adaptor.provider_name] = {"models": models_data}
    else:
        # No channels configured yet — show all adaptor models as preview
        for adaptor in registry.all_adaptors():
            all_models = adaptor.get_supported_models()
            models_data = {}
            for model_name, _config in all_models.items():
                try:
                    pricing = get_model_pricing(model_name)
                except KeyError:
                    try:
                        pricing = get_model_pricing(model_name.lower())
                    except KeyError:
                        continue
                models_data[model_name] = {
                    "input_price": pricing["input"],
                    "output_price": pricing["output"],
                    "cached_input_price": pricing["cache_hit"],
                }
            if models_data:
                display[adaptor.provider_name] = {"models": models_data}

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
    for ct in registry.all_types():
        adaptor = registry.get(ct)
        if adaptor:
            catalog[str(ct)] = list(adaptor.get_supported_models().keys())

    return GenericApiResponse(data=catalog)
