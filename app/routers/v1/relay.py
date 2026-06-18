from __future__ import annotations

import logging
import random
import time
import uuid
from typing import Any

import httpx

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import token_auth
from app.models.channel import Channel
from app.models.log import Log
from app.relay.adaptor import BaseAdaptor
from app.relay.meta import RelayMeta
from app.relay.mode import RelayMode, relay_mode_from_path
from app.relay.registry import registry
from app.relay.openai_compatible import relay_chat_completion
from app.budget.arbiter import BudgetArbiter, ActualUsage
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["relay"])


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


async def _select_channel(
    db: AsyncSession,
    model_name: str,
    channel_type: int,
) -> Channel | None:
    """Weighted random channel selection for the given model and provider type.

    Queries all enabled channels matching the provider type, filters to those
    supporting the requested model, then selects one via weighted random
    distribution using the channel's ``weight`` field.

    Returns None if no enabled channel is found.
    """
    result = await db.execute(
        select(Channel)
        .where(Channel.status == 1, Channel.type == channel_type)
        .order_by(Channel.priority.desc())
    )
    channels = list(result.scalars().all())
    if not channels:
        return None

    # Prefer channels that list the requested model in their models field
    matching = []
    for ch in channels:
        if ch.models:
            channel_models = [m.strip() for m in ch.models.split(",")]
            if model_name in channel_models:
                matching.append(ch)
    if not matching:
        matching = channels  # fall back to any channel of this type

    # Weighted random selection (default weight=1 ensures basic distribution)
    weights = [max(ch.weight, 1) for ch in matching]
    return random.choices(matching, weights=weights, k=1)[0]


# ── Channel failover & auto-disable ──

# Track consecutive failures per channel (in-memory, resets on restart)
_channel_failures: dict[int, int] = {}
_CHANNEL_DISABLE_THRESHOLD = 3  # consecutive 5xx before disabling


async def _find_fallback_channel(
    db: AsyncSession,
    channel_type: int,
    exclude_model: str,
) -> Channel | None:
    """Find next available channel with same type, using different model."""
    result = await db.execute(
        select(Channel)
        .where(Channel.status == 1, Channel.type == channel_type)
        .order_by(Channel.priority.desc())
    )
    channels = result.scalars().all()
    for ch in channels:
        if ch.models:
            models = [m.strip() for m in ch.models.split(",")]
            for m in models:
                if m != exclude_model and registry.resolve_channel_type(m) == channel_type:
                    return ch
    return None


async def _record_channel_failure(channel_id: int, db: AsyncSession) -> bool:
    """Record a channel failure. Returns True if channel was auto-disabled."""
    count = _channel_failures.get(channel_id, 0) + 1
    _channel_failures[channel_id] = count
    if count >= _CHANNEL_DISABLE_THRESHOLD:
        logger.warning("Auto-disabling channel %d after %d consecutive failures", channel_id, count)
        await db.execute(
            select(Channel).where(Channel.id == channel_id).limit(1)
        )
        result = await db.execute(select(Channel).where(Channel.id == channel_id))
        ch = result.scalar_one_or_none()
        if ch:
            ch.status = 0
            await db.commit()
        _channel_failures.pop(channel_id, None)
        return True
    return False


def _reset_channel_failures(channel_id: int):
    """Reset failure count after a successful call."""
    _channel_failures.pop(channel_id, None)


async def _handle_relay(request: Request, db: AsyncSession):
    """Universal relay handler: smart routes based on adaptor NATIVE_FORMATS."""
    user, token = await _resolve_token_and_channel(request, db)
    body = await request.json()
    path = request.url.path
    relay_mode = relay_mode_from_path(path)

    model_name = body.get("model", "")
    stream = body.get("stream", False)

    # Fusion: run multi-model ensemble pipeline
    if model_name == "fusion":
        fusion_engine = getattr(request.app.state, "fusion_engine", None)
        if not fusion_engine:
            raise HTTPException(status_code=400, detail="Fusion engine not available (no API keys configured)")

        from app.fusion.schemas import ChatRequest

        chat_request = ChatRequest.from_dict(body)
        response = await fusion_engine.execute(chat_request)
        result = response.to_dict()

        # Post-consume quota for fusion (estimated from panel usage)
        estimated = sum(
            u.get("prompt_tokens", 0) + u.get("completion_tokens", 0)
            for b in (result.get("usage", {}).get("fusion_breakdown", {}).get("panel", {}) or {}).values()
            for u in [b]
        ) or 5000
        if not token.unlimited_quota and token.remain_quota < estimated:
            raise HTTPException(status_code=400, detail="Insufficient token quota")
        if not token.unlimited_quota:
            token.remain_quota -= estimated
        await db.commit()

        return result

    # Auto model selection: pick highest-priority enabled channel
    channel: Channel | None = None
    channel_type: int | None = None
    if model_name == "auto":
        from sqlalchemy import select as _select

        result = await db.execute(
            _select(Channel)
            .where(Channel.status == 1)
            .order_by(Channel.priority.desc())
            .limit(1)
        )
        channel = result.scalar_one_or_none()
        if not channel:
            raise HTTPException(status_code=400, detail="No enabled channels available for auto selection")
        channel_type = channel.type

        # Resolve model name: channel's configured model, or adaptor default
        if channel.models:
            model_name = channel.models.split(",")[0].strip()
        else:
            adaptor = _get_adaptor(channel_type)
            if not adaptor:
                raise HTTPException(status_code=500, detail="No adaptor configured for auto-selected channel")
            supported = adaptor.get_supported_models()
            if not supported:
                raise HTTPException(status_code=500, detail="Auto-selected adaptor has no supported models")
            model_name = next(iter(supported.keys()))

        body["model"] = model_name

    # Resolve channel type from model name
    if channel_type is None:
        channel_type = registry.resolve_channel_type(model_name)
        if channel_type is None:
            raise HTTPException(status_code=400, detail=f"Model '{model_name}' not supported by any configured provider")

        # Select target channel via weighted random distribution
        channel = await _select_channel(db, model_name, channel_type)
        if channel is None:
            raise HTTPException(status_code=400, detail=f"No enabled channels available for model '{model_name}'")

    _channel_id = channel.id if channel else 1
    _channel_api_key = channel.key or _get_channel_api_key(channel_type)
    _channel_base_url = channel.base_url or ""

    adaptor = _get_adaptor(channel_type)
    if adaptor is None:
        raise HTTPException(status_code=500, detail=f"No adaptor configured for channel type {channel_type}")
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
        channel_id=_channel_id,
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
        channel_id=_channel_id,
        token_id=token.id,
        token_name=token.name,
        user_id=user.id,
        group=user.group or "default",
        api_key=_channel_api_key,
        base_url=_channel_base_url or adaptor.DEFAULT_BASE_URL,
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
        if relay_mode == RelayMode.CLAUDE_MESSAGES:  # CLAUDE_MESSAGES → Chat
            upstream_body = adaptor.convert_claude_request(body)
        elif relay_mode == RelayMode.RESPONSE_API:  # Responses API → Chat
            from app.relay.converter import responses_to_chat
            upstream_body = responses_to_chat(body)
        else:
            upstream_body = await adaptor.convert_request(body, meta)
        upstream_url = adaptor.get_request_url(meta, RelayMode.CHAT_COMPLETIONS)  # ChatCompletions mode

    upstream_headers = adaptor.setup_request_headers(meta.api_key)

    # Determine if SSE format conversion is needed
    needs_sse_conversion = stream and relay_mode == RelayMode.CLAUDE_MESSAGES and not adaptor.supports_native_format(relay_mode)
    output_format = "anthropic" if needs_sse_conversion else "chat"

    # Relay upstream with fallback support
    fallback_channel = None
    fallback_model = None
    upstream_response = None

    for attempt in range(2):  # primary + 1 fallback
        try:
            upstream_response = await relay_chat_completion(
                body=upstream_body,
                upstream_url=upstream_url,
                api_key=meta.api_key,
                stream=stream,
                output_format=output_format,
            )
            _reset_channel_failures(_channel_id)  # reset failure count on success
            break  # success, exit retry loop

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            is_recoverable = status in (429, 500, 502, 503)

            if attempt == 0 and is_recoverable and not stream:
                # Try fallback channel
                fallback_channel = await _find_fallback_channel(db, channel_type, model_name)
                if fallback_channel and fallback_channel.models:
                    fallback_model = fallback_channel.models.split(",")[0].strip()
                    adaptor = _get_adaptor(channel_type)
                    if adaptor:
                        model_name = fallback_model
                        model_config = adaptor.get_supported_models().get(model_name)
                        if model_config:
                            body["model"] = model_name
                            upstream_body = body
                            upstream_url = adaptor.get_request_url(meta, relay_mode)
                            upstream_headers = adaptor.setup_request_headers(
                                _get_channel_api_key(channel_type)
                            )
                            logger.info(
                                "FALLBACK | %d -> model=%s | channel_type=%d",
                                status, model_name, channel_type,
                            )
                            await _record_channel_failure(_channel_id, db)
                            continue  # retry with fallback

            # Fallback failed or not available — refund and raise
            if is_recoverable:
                await _record_channel_failure(_channel_id, db)

            if not token.unlimited_quota:
                token.remain_quota += estimated
            user.quota += estimated
            user.used_quota -= estimated
            await db.commit()
            try:
                err_body = exc.response.json()
            except Exception:
                err_body = {"error": {"message": str(exc)}}
            raise HTTPException(status_code=status, detail=err_body)

        except Exception:
            # Non-HTTP error (timeout, connection error, etc.)
            if attempt == 0 and not stream:
                fallback_channel = await _find_fallback_channel(db, channel_type, model_name)
                if fallback_channel and fallback_channel.models:
                    fallback_model = fallback_channel.models.split(",")[0].strip()
                    adaptor = _get_adaptor(channel_type)
                    if adaptor:
                        model_name = fallback_model
                        model_config = adaptor.get_supported_models().get(model_name)
                        if model_config:
                            body["model"] = model_name
                            upstream_body = body
                            upstream_url = adaptor.get_request_url(meta, relay_mode)
                            upstream_headers = adaptor.setup_request_headers(
                                _get_channel_api_key(channel_type)
                            )
                            logger.info("FALLBACK | error -> model=%s", model_name)
                            await _record_channel_failure(_channel_id, db)
                            continue

            # Refund on failure
            if not token.unlimited_quota:
                token.remain_quota += estimated
            user.quota += estimated
            user.used_quota -= estimated
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
    names = {
        RelayMode.CHAT_COMPLETIONS: "ChatCompletion",
        RelayMode.RESPONSE_API: "ResponseAPI",
        RelayMode.CLAUDE_MESSAGES: "ClaudeMessages",
    }
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
    models = []
    # Collect models from ALL registered adaptors
    for ct in [39, 41, 50, 25, 27]:
        adaptor = _get_adaptor(ct)
        if adaptor:
            for m in adaptor.get_supported_models():
                models.append({"id": m, "object": "model", "created": now, "owned_by": adaptor.provider_name})
    now = int(time.time())
    return {"object": "list", "data": models}


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
