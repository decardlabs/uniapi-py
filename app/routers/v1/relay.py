from __future__ import annotations

import time
import uuid
from typing import Any

import httpx

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import token_auth
from app.models.log import Log
from app.relay.adaptor import BaseAdaptor
from app.relay.meta import RelayMeta
from app.relay.mode import relay_mode_from_path
from app.relay.registry import registry
from app.relay.openai_compatible import relay_chat_completion
from app.budget.arbiter import BudgetArbiter, ActualUsage
from app.config import settings

router = APIRouter(tags=["relay"])

_MODE_MAP = {
    "chat_completions": 1,
    "claude_messages": 12,
    "response_api": 11,
}


async def _resolve_token_and_channel(request: Request, db: AsyncSession):
    """Authenticate request and resolve user/token."""
    user = await token_auth(request, db)
    token = request.state.token
    return user, token


def _get_adaptor(channel_type: int = 39) -> BaseAdaptor | None:
    """Get adaptor for the given channel type."""
    return registry.get(channel_type)


def _estimate_input_tokens(body: dict, model_config=None) -> int:
    """Estimate input token count from request body."""
    messages = body.get("messages", body.get("input", []))
    if isinstance(messages, str):
        total_chars = len(messages)
    else:
        total_chars = sum(len(str(m.get("content", ""))) for m in (messages if isinstance(messages, list) else [messages]))
    return max(10, total_chars // 4)


def _estimate_cost(body: dict, model_config: Any) -> int:
    prompt_tokens = _estimate_input_tokens(body)
    max_tokens = body.get("max_tokens", body.get("max_output_tokens", 256))
    if isinstance(max_tokens, str):
        max_tokens = 256
    completion_tokens = min(max_tokens, 1024)
    return int(
        prompt_tokens * model_config.input_ratio
        + completion_tokens * model_config.output_ratio
    )


def _get_channel_api_key(channel_type: int = 39) -> str:
    """Get API key for the given channel type."""
    from app.config import settings
    from app.relay import channeltype

    key_map = {
        channeltype.DeepSeek: settings.deepseek_api_key,
        channeltype.GLM: settings.glm_api_key,
        channeltype.Moonshot: settings.kimi_api_key,
        channeltype.Minimax: settings.minimax_api_key,
        channeltype.AliBailian: settings.qwen_api_key,
    }
    return key_map.get(channel_type, "")


async def _handle_relay(request: Request, db: AsyncSession):
    """Universal relay handler: smart routes based on adaptor NATIVE_FORMATS."""
    user, token = await _resolve_token_and_channel(request, db)
    body = await request.json()
    path = request.url.path
    relay_mode = relay_mode_from_path(path)

    model_name = body.get("model", "")
    stream = body.get("stream", False)

    # Resolve channel type from model name (supports multi-provider routing)
    channel_type = registry.resolve_channel_type(model_name)
    if channel_type is None:
        raise HTTPException(status_code=400, detail=f"Model '{model_name}' not supported by any configured provider")

    adaptor = _get_adaptor(channel_type)
    if adaptor is None:
        raise HTTPException(status_code=500, detail="No adaptor configured for channel type {channel_type}")
    supported = adaptor.get_supported_models()
    model_config = supported[model_name]

    # Token model permissions
    if hasattr(token, "models") and token.models:
        allowed = [m.strip() for m in token.models.split(",")]
        if model_name not in allowed:
            raise HTTPException(status_code=403, detail=f"Token not allowed to use model '{model_name}'")

    # Budget arbitration pre-check
    budget_arbiter: BudgetArbiter | None = getattr(request.app.state, "budget_arbiter", None)
    if budget_arbiter and settings.budget_enabled:
        estimated_input = _estimate_input_tokens(body, model_config)
        estimated_output = body.get("max_tokens", body.get("max_output_tokens", 256))
        if isinstance(estimated_output, str):
            estimated_output = 256
        decision = await budget_arbiter.pre_check(
            user_id=user.id,
            model=model_name,
            estimated_input_tokens=estimated_input,
            estimated_output_tokens=min(int(estimated_output), 4096),
        )
        if decision.status == "rejected":
            raise HTTPException(status_code=402, detail=decision.error_message)
        request.state.budget_info = {
            "period": budget_arbiter._compute_period(),
            "frozen_amount": decision.estimated_cost,
        }

    # Pre-consume quota
    estimated = _estimate_cost(body, model_config)
    if not token.unlimited_quota and token.remain_quota < estimated:
        raise HTTPException(status_code=400, detail="Insufficient token quota")
    if user.quota < estimated:
        raise HTTPException(status_code=400, detail="Insufficient user quota")

    now_ms = int(time.time() * 1000)
    provisional_log = Log(
        user_id=user.id,
        created_at=now_ms,
        type=6,
        content=f"Pre-consume for {model_name}",
        username=user.username,
        token_name=token.name,
        model_name=model_name,
        quota=estimated,
        channel_id=1,
        request_id=uuid.uuid4().hex,
        is_stream=stream,
    )
    db.add(provisional_log)

    if not token.unlimited_quota:
        token.remain_quota -= estimated
    user.quota -= estimated
    user.used_quota += estimated
    await db.flush()

    # SMART ROUTING: use NATIVE_FORMATS to decide proxy vs convert
    meta = RelayMeta(
        mode=relay_mode,
        channel_type=channel_type,
        channel_id=1,
        token_id=token.id,
        token_name=token.name,
        user_id=user.id,
        group=user.group or "default",
        api_key=_get_channel_api_key(channel_type),
        base_url=adaptor.DEFAULT_BASE_URL,
        is_stream=stream,
        origin_model_name=model_name,
        actual_model_name=model_name,
    )

    if adaptor.supports_native_format(relay_mode):
        # ✅ NATIVE: proxy directly, no conversion
        upstream_body = body
        upstream_url = adaptor.get_request_url(meta, relay_mode)
    else:
        # 🔄 CONVERT: transform to Chat format
        if relay_mode == 12:  # CLAUDE_MESSAGES → Chat
            upstream_body = adaptor.convert_claude_request(body)
        else:
            upstream_body = await adaptor.convert_request(body, meta)
        upstream_url = adaptor.get_request_url(meta, 1)  # ChatCompletions mode

    upstream_headers = adaptor.setup_request_headers(meta.api_key)

    # Determine if SSE format conversion is needed
    needs_sse_conversion = stream and relay_mode == 12 and not adaptor.supports_native_format(relay_mode)
    output_format = "anthropic" if needs_sse_conversion else "chat"

    # Relay upstream
    try:
        upstream_response = await relay_chat_completion(
            body=upstream_body,
            upstream_url=upstream_url,
            api_key=meta.api_key,
            stream=stream,
            output_format=output_format,
        )
    except httpx.HTTPStatusError as exc:
        # Pass through upstream 4xx/5xx errors
        if not token.unlimited_quota:
            token.remain_quota += estimated
        user.quota += estimated
        user.used_quota -= estimated
        await db.commit()
        try:
            err_body = exc.response.json()
        except Exception:
            err_body = {"error": {"message": str(exc)}}
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=err_body,
        )
    except Exception:
        # Refund on failure
        if not token.unlimited_quota:
            token.remain_quota += estimated
        user.quota += estimated
        user.used_quota -= estimated
        # Budget: unfreeze on failure
        if budget_arbiter and settings.budget_enabled and hasattr(request.state, "budget_info") and request.state.budget_info:
            bi = request.state.budget_info
            await budget_arbiter.post_settle(
                user_id=user.id, period=bi["period"], frozen_amount=bi["frozen_amount"],
                monthly_budget=0, request_id=provisional_log.request_id,
                actual_usage=ActualUsage(model=model_name, input_tokens=0, output_tokens=0),
                db_session=db,
            )
        await db.commit()
        raise HTTPException(status_code=502, detail="Upstream request failed")

    if stream:
        return upstream_response

    # Post-consume: reconcile quota
    usage = upstream_response.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    actual = int(
        prompt_tokens * model_config.input_ratio
        + completion_tokens * model_config.output_ratio
    )
    diff = estimated - actual
    if diff > 0:
        if not token.unlimited_quota:
            token.remain_quota += diff
        user.quota += diff
        user.used_quota -= diff

    provisional_log.type = 2
    provisional_log.quota = actual
    provisional_log.prompt_tokens = prompt_tokens
    provisional_log.completion_tokens = completion_tokens
    provisional_log.content = f"{relay_mode_name(relay_mode)} with {model_name}"

    # Budget: post-settle with actual usage
    if budget_arbiter and settings.budget_enabled and hasattr(request.state, "budget_info") and request.state.budget_info:
        bi = request.state.budget_info
        await budget_arbiter.post_settle(
            user_id=user.id, period=bi["period"], frozen_amount=bi["frozen_amount"],
            monthly_budget=0, request_id=provisional_log.request_id,
            actual_usage=ActualUsage(
                model=model_name,
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                cache_hit_tokens=usage.get("cached_tokens", 0),
            ),
            db_session=db,
        )

    await db.commit()
    return upstream_response


def relay_mode_name(mode: int) -> str:
    names = {1: "ChatCompletion", 11: "ResponseAPI", 12: "ClaudeMessages"}
    return names.get(mode, "Relay")


# ---- Route definitions ----


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, db: AsyncSession = Depends(get_db)):
    return await _handle_relay(request, db)


@router.post("/v1/messages")
async def claude_messages(request: Request, db: AsyncSession = Depends(get_db)):
    return await _handle_relay(request, db)


@router.post("/v1/responses")
async def response_api(request: Request, db: AsyncSession = Depends(get_db)):
    return await _handle_relay(request, db)


@router.get("/v1/models")
async def list_models(request: Request, db: AsyncSession = Depends(get_db)):
    await token_auth(request, db)
    adaptor = _get_adaptor(39)
    if adaptor is None:
        raise HTTPException(status_code=500, detail="No adaptor configured")
    now = int(time.time())
    return {
        "object": "list",
        "data": [
            {"id": m, "object": "model", "created": now, "owned_by": "deepseek"}
            for m in adaptor.get_supported_models()
        ],
    }


@router.get("/v1/models/{model_id}")
async def retrieve_model(model_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    await token_auth(request, db)
    adaptor = _get_adaptor(39)
    if adaptor is None:
        raise HTTPException(status_code=500, detail="No adaptor configured")
    if model_id not in adaptor.get_supported_models():
        raise HTTPException(status_code=404, detail="Model not found")
    return {
        "id": model_id,
        "object": "model",
        "created": int(time.time()),
        "owned_by": "deepseek",
    }
