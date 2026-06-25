from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from typing import Any

import httpx

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import token_auth
from app.exceptions import RelayException, UpstreamException
from app.models.channel import Channel
from app.models.log import Log
from app.relay.adaptor import BaseAdaptor
from app.relay.meta import RelayMeta
from app.relay.mode import RelayMode, relay_mode_from_path
from app.relay.registry import registry
from app.relay.openai_compatible import relay_chat_completion
from app.budget.arbiter import BudgetArbiter, ActualUsage
from app.budget.pricing import calculate_cost, calculate_cost_micro, estimate_cost_micro, get_model_pricing, MAX_OVERDRAFT_MICRO
from app.models.budget import CostRecord
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




def _make_stream_usage_callback(
    log_id: int,
    estimated_micro: int,
    user_id: int,
) -> Any:
    """Return a callback that patches the provisional log after a stream ends.

    The callback runs in a *new* database session because the original
    request's session is already closed by the time the SSE stream finishes.
    """
    from app.database import async_session_factory
    from app.models.log import Log as LogModel
    from app.models.user import User

    async def _on_usage(usage: dict[str, Any]) -> None:
        prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0

        cache_hit = (
            usage.get("prompt_cache_hit_tokens")
            or (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
            or usage.get("cache_read_input_tokens")
            or usage.get("cached_tokens")
            or 0
        )
        if prompt_tokens == 0 and cache_hit > 0:
            prompt_tokens = cache_hit
        cache_miss = max(0, prompt_tokens - cache_hit)


        async with async_session_factory() as session:
            log_entry = await session.get(LogModel, log_id)
            if log_entry is None:
                return

            # Calculate cost using the model name stored in the log entry
            try:
                actual_micro = calculate_cost_micro(
                    log_entry.model_name or "",
                    prompt_tokens, completion_tokens, cache_hit,
                )
            except KeyError:
                actual_micro = estimated_micro  # fallback: use pre-estimate

            log_entry.cost = actual_micro
            log_entry.prompt_tokens = prompt_tokens
            log_entry.completion_tokens = completion_tokens
            log_entry.cached_prompt_tokens = cache_hit

            log_entry.prompt_tokens = prompt_tokens
            log_entry.completion_tokens = completion_tokens
            log_entry.cached_prompt_tokens = cache_hit

            # Always update type to 2 (consume), even when usage is empty.
            # Without this, error/empty streams leave stale type=6 records.
            log_entry.type = 2
            if not usage or not any(usage.values()):
                log_entry.content = f"Stream ended without usage data for {log_entry.model_name}"
                with open("/tmp/_on_usage_debug.log", "a") as f:
                    f.write(f"_on_usage: empty usage for log {log_id}, still patched\n")

            await session.commit()
            with open("/tmp/_on_usage_debug.log", "a") as f:
                f.write(f"_on_usage: COMMITTED log {log_id}\n")

            # Refund overcharge to user's micro-yuan balance
            diff_micro = estimated_micro - actual_micro
            if diff_micro > 0:
                user = await session.get(User, user_id)
                if user:
                    user.balance += diff_micro
                await session.commit()

            # Write CostRecord
            try:
                cr = CostRecord(
                    request_id=log_entry.request_id,
                    user_id=user_id,
                    model=log_entry.model_name or "",
                    input_tokens=prompt_tokens,
                    output_tokens=completion_tokens,
                    cache_hit_tokens=cache_hit,
                    cost=round(actual_micro / 1_000_000, 6),
                    status="success",
                    created_at=int(time.time() * 1000),
                )
                session.add(cr)
                await session.commit()
            except Exception:
                pass

            # Real-time pool consumption sync (stream path)
            try:
                from app.services.pool_sync import sync_consumption_to_pool
                await sync_consumption_to_pool(
                    session,
                    user_id=user_id,
                    cost_yuan=actual_micro / 1_000_000,
                    model_name=log_entry.model_name or "",
                    request_id=log_entry.request_id or "",
                )
            except Exception:
                pass

    return _on_usage


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

    # ── 429 cooldown filter: skip channels in cooldown ──
    # If ALL matching channels are in cooldown, allow all (avoid total outage).
    available = [ch for ch in matching if not _is_channel_in_cooldown(ch.id)]
    if available:
        matching = available

    # Weighted random selection (default weight=1 ensures basic distribution)
    weights = [max(ch.weight, 1) for ch in matching]
    return random.choices(matching, weights=weights, k=1)[0]


# ── Channel failover & auto-disable ──

# Track consecutive failures per channel (in-memory, resets on restart)
# Only counts 5xx / connection errors — 429 is handled by the cooldown mechanism.
_channel_failures: dict[int, int] = {}
_CHANNEL_DISABLE_THRESHOLD = 3  # consecutive 5xx before disabling

# ── 429 cooldown: slow down, don't disable ──

# Map channel_id → cooldown expiry timestamp (time.monotonic())
# A channel in cooldown is skipped by _select_channel() for a short period.
_channel_cooldowns: dict[int, float] = {}

# Map channel_id → consecutive 429 count (for progressive cooldown backoff)
_channel_429_counts: dict[int, int] = {}

# Base cooldown duration in seconds. Grows exponentially with repeated 429s.
_COOLDOWN_BASE_SECONDS = 10.0
_COOLDOWN_MAX_SECONDS = 120.0  # cap at 2 minutes


def _cooldown_channel(channel_id: int) -> float:
    """Place a channel into 429 cooldown. Returns the cooldown duration.

    Cooldown grows exponentially: base → 2× → 4× → … capped at _COOLDOWN_MAX_SECONDS.
    When the channel successfully serves a request, its 429 count resets.
    """
    count = _channel_429_counts.get(channel_id, 0) + 1
    _channel_429_counts[channel_id] = count
    duration = min(_COOLDOWN_BASE_SECONDS * (2 ** (count - 1)), _COOLDOWN_MAX_SECONDS)
    expiry = time.monotonic() + duration
    _channel_cooldowns[channel_id] = expiry
    logger.warning(
        "429 COOLDOWN | channel=%d duration=%.1fs 429_strike=%d",
        channel_id, duration, count,
    )
    return duration


def _is_channel_in_cooldown(channel_id: int) -> bool:
    """Check if a channel is currently in 429 cooldown. Auto-cleans expired entries."""
    expiry = _channel_cooldowns.get(channel_id)
    if expiry is None:
        return False
    if time.monotonic() > expiry:
        # Cooldown expired — clean up
        _channel_cooldowns.pop(channel_id, None)
        return False
    return True


def _reset_channel_429_count(channel_id: int):
    """Reset 429 strike counter after a successful request."""
    _channel_429_counts.pop(channel_id, None)
    _channel_cooldowns.pop(channel_id, None)


async def _find_fallback_channel(
    db: AsyncSession,
    channel_type: int,
    exclude_model: str,
) -> Channel | None:
    """Find next available channel with same type, using different model.
    
    Skips channels currently in 429 cooldown. Falls back to including cooldown
    channels if no other options exist.
    """
    result = await db.execute(
        select(Channel)
        .where(Channel.status == 1, Channel.type == channel_type)
        .order_by(Channel.priority.desc())
    )
    channels = result.scalars().all()
    # Separate into available and cooldown
    available = [ch for ch in channels if not _is_channel_in_cooldown(ch.id)]
    if not available:
        available = channels  # all in cooldown → allow any
    
    for ch in available:
        if ch.models:
            models = [m.strip() for m in ch.models.split(",")]
            for m in models:
                if m != exclude_model and registry.resolve_channel_type(m) == channel_type:
                    return ch
    return None


def _check_token_model(token, model_name: str) -> bool:
    """Check if the token has permission to use the given model."""
    if hasattr(token, "models") and token.models:
        allowed = [m.strip() for m in token.models.split(",")]
        if model_name not in allowed:
            return False
    return True


async def _record_channel_failure(channel_id: int, db: AsyncSession) -> bool:
    """Record a channel failure. Returns True if channel was auto-disabled."""
    count = _channel_failures.get(channel_id, 0) + 1
    _channel_failures[channel_id] = count
    if count >= _CHANNEL_DISABLE_THRESHOLD:
        logger.warning("Auto-disabling channel %d after %d consecutive failures", channel_id, count)
        result = await db.execute(select(Channel).where(Channel.id == channel_id))
        ch = result.scalar_one_or_none()
        if ch:
            ch.status = 0
            await db.commit()
        _channel_failures.pop(channel_id, None)
        return True
    return False


def _reset_channel_failures(channel_id: int):
    """Reset failure count AND 429 cooldown after a successful call."""
    _channel_failures.pop(channel_id, None)
    _reset_channel_429_count(channel_id)


async def _refund_and_raise_connection_error(
    provider_name: str,
    exc: Exception,
    user: Any,
    estimated_micro: int,
    budget_arbiter: Any | None,
    request: Request,
    db: AsyncSession,
    provisional_log: Any,
) -> None:
    """Refund the user and raise an UpstreamException for a connection error.

    Extracted so both the main ``except Exception`` handler and the inline
    429 fallback handler can share the same refund+raise logic.
    """
    # Refund micro-yuan balance on failure
    user.balance += estimated_micro

    # Patch the provisional log so it doesn't remain as stale type=6
    provisional_log.type = 2
    provisional_log.content = f"Failed: {exc}"
    import time as _time
    provisional_log.elapsed_time = int(_time.time() * 1000)

    if budget_arbiter and settings.budget_enabled and hasattr(request.state, "budget_info") and request.state.budget_info:
        bi = request.state.budget_info
        from app.budget.arbiter import ActualUsage
        await budget_arbiter.post_settle(
            user_id=user.id, period=bi["period"], frozen_amount=bi["frozen_amount"],
            monthly_budget=bi["monthly_budget"], request_id=provisional_log.request_id,
            actual_usage=ActualUsage(model="", input_tokens=0, output_tokens=0),
            db_session=db,
        )
    await db.commit()

    # Map connection error to UniAPI code
    from app.relay.upstream_errors import map_upstream_connection_error

    error_type = "timeout" if "timeout" in str(exc).lower() else "unknown"
    uni_code, upstream, reason = map_upstream_connection_error(provider_name, error_type)
    details = {"reason": reason} if reason else None
    raise UpstreamException(
        message=f"Upstream request failed: {exc}",
        code=uni_code,
        upstream_provider=upstream["provider"],
        upstream_status=upstream["status_code"],
        details=details,
    ) from exc


async def _handle_relay(request: Request, db: AsyncSession):
    """Universal relay handler: smart routes based on adaptor NATIVE_FORMATS."""
    relay_start = time.time()
    user, token = await _resolve_token_and_channel(request, db)
    body = await request.json()
    path = request.url.path
    relay_mode = relay_mode_from_path(path)

    model_name = body.get("model", "")
    stream = body.get("stream", False)

    # Token model permissions check (early validation)
    token_allowed_models = None
    if hasattr(token, "models") and token.models:
        token_allowed_models = [m.strip() for m in token.models.split(",") if m.strip()]
    
    # If model is specified, validate it against token permissions
    if model_name and token_allowed_models and model_name not in token_allowed_models:
        raise RelayException(
            code="UNIAPI_TOKEN_MODEL_NOT_ALLOWED",
            message=f"Token not allowed to use model '{model_name}'. "
                    f"Allowed models: {', '.join(token_allowed_models)}. "
                    f"Call GET /v1/models to list available models.",
            details={"requested_model": model_name, "allowed_models": token_allowed_models},
            suggestion="Call GET /v1/models to list available models.",
        )

    # If no model specified but token has restrictions, require explicit selection
    if not model_name and token_allowed_models and model_name != "auto":
        raise RelayException(
            code="UNIAPI_MODEL_NOT_SPECIFIED",
            message=f"Model not specified. Token is restricted to: {', '.join(token_allowed_models)}. "
                    f"Please specify one of these models, use model='auto' for automatic selection, "
                    f"or call GET /v1/models to list available models.",
            suggestion="Specify a model in the request body, or use model='auto'.",
        )

    # Fusion: multi-model ensemble from token-authorized models
    if model_name == "fusion":
        fusion_registry = getattr(request.app.state, "fusion_registry", None)
        if not fusion_registry:
            raise RelayException(
                code="UNIAPI_SERVICE_DISABLED",
                message="Fusion engine not available (no API keys configured)",
            )

        # Select panel from token-authorized models that are in the fusion registry
        token_models: list[str] = []
        if hasattr(token, "models") and token.models:
            token_models = [m.strip() for m in token.models.split(",")]

        available = fusion_registry.list_models()
        if token_models:
            panel = [m for m in token_models if m in available]
        else:
            panel = available[:]

        if not panel:
            raise RelayException(
                code="UNIAPI_TOKEN_MODEL_NOT_ALLOWED",
                message="No fusion-authorized models available for this token",
            )

        if len(panel) < 2:
            # Fallback to single model passthrough
            model_name = panel[0]
            channel_type = registry.resolve_channel_type(model_name)
            body["model"] = model_name
        else:
            # Use top models: strongest as judge/synthesizer
            from app.fusion.core.engine import FusionConfig, FusionEngine

            # Score models by price (higher = more capable = better for judge/synth)
            from app.budget.pricing import get_model_pricing

            scored = []
            for m_name in panel:
                try:
                    p = get_model_pricing(m_name)
                    scored.append((p["input"] + p["output"], m_name))
                except KeyError:
                    continue
            scored.sort(reverse=True)

            fusion_config = FusionConfig(
                panel=panel,
                judge=scored[0][1] if scored else panel[0],
                synthesizer=scored[0][1] if scored else panel[-1],
                timeout_seconds=30,
                retry_count=1,
                fallback_model=panel[0],
            )
            engine = FusionEngine(fusion_registry, fusion_config)
            from app.fusion.schemas import ChatRequest

            chat_request = ChatRequest.from_dict(body)
            response = await engine.execute(chat_request)
            result = response.to_dict()
            await db.commit()
            return result

    # Auto model selection: pick cheapest model the token can access
    channel: Channel | None = None
    channel_type: int | None = None
    if model_name == "auto":
        from sqlalchemy import select as _select

        # Determine token-allowed models
        allowed_models: list[str] | None = None
        if hasattr(token, "models") and token.models:
            allowed_models = [m.strip() for m in token.models.split(",")]

        # Collect all enabled channels with their models and pricing
        result = await db.execute(
            _select(Channel).where(Channel.status == 1)
        )
        channels = result.scalars().all()
        if not channels:
            raise RelayException(
                code="UNIAPI_CHANNEL_UNAVAILABLE",
                message="No enabled channels available for auto selection",
            )

        # Build (price, model_name, channel) candidates
        candidates: list[tuple[float, str, Channel]] = []
        for ch in channels:
            ch_models = [m.strip() for m in ch.models.split(",")] if ch.models else []
            adaptor = _get_adaptor(ch.type)
            if not adaptor:
                continue
            supported = adaptor.get_supported_models()
            model_list = ch_models or list(supported.keys())
            for m_name in model_list:
                if allowed_models is not None and m_name not in allowed_models:
                    continue
                if m_name not in supported:
                    continue
                # Use combined yuan price as sort key (lower = cheaper)
                try:
                    p = get_model_pricing(m_name)
                    price = p["input"] + p["output"]
                except KeyError:
                    price = 999.0
                candidates.append((price, m_name, ch))

        if not candidates:
            if allowed_models:
                raise RelayException(
                    code="UNIAPI_TOKEN_MODEL_NOT_ALLOWED",
                    message=f"Token has no authorized model for auto selection. Allowed: {', '.join(allowed_models)}",
                )
            raise RelayException(
                code="UNIAPI_MODEL_NOT_SUPPORTED",
                message="No suitable model found for auto selection",
            )

        # Pick the cheapest
        candidates.sort(key=lambda x: x[0])
        price, model_name, channel = candidates[0]
        channel_type = channel.type
        body["model"] = model_name

    # Resolve channel type from model name
    if channel_type is None:
        channel_type = registry.resolve_channel_type(model_name)
        if channel_type is None:
            raise RelayException(
                code="UNIAPI_MODEL_NOT_SUPPORTED",
                message=f"Model '{model_name}' not supported by any configured provider",
                details={"model": model_name},
            )

        # Resolve model name to canonical form (handles case-insensitive aliases)
        adaptor = _get_adaptor(channel_type)
        canonical = adaptor.resolve_model_name(model_name) if adaptor else None
        if canonical is not None:
            model_name = canonical
            body["model"] = canonical

        # Select target channel via weighted random distribution
        channel = await _select_channel(db, model_name, channel_type)
        if channel is None:
            raise RelayException(
                code="UNIAPI_CHANNEL_UNAVAILABLE",
                message=f"No enabled channels available for model '{model_name}'",
                details={"model": model_name},
            )

    _channel_id = channel.id if channel else 1
    _channel_api_key = channel.key or _get_channel_api_key(channel_type)
    _channel_base_url = channel.base_url or ""

    adaptor = _get_adaptor(channel_type)
    if adaptor is None:
        raise RelayException(
            code="UNIAPI_INTERNAL_ERROR",
            message=f"No adaptor configured for channel type {channel_type}",
        )
    supported = adaptor.get_supported_models()
    model_config = supported[model_name]

    # Token model permissions (final check after any model resolution/selection)
    if token_allowed_models and model_name not in token_allowed_models:
        raise RelayException(
            code="UNIAPI_TOKEN_MODEL_NOT_ALLOWED",
            message=f"Token not allowed to use model '{model_name}'. "
                    f"Allowed models: {', '.join(token_allowed_models)}. "
                    f"Call GET /v1/models to list available models.",
            details={"requested_model": model_name, "allowed_models": token_allowed_models},
            suggestion="Call GET /v1/models to list available models.",
        )

    # Channel group access control
    if channel and channel.group and channel.group != "default":
        user_group = user.group or "default"
        if user_group != channel.group:
            raise RelayException(
                code="UNIAPI_GROUP_ACCESS_DENIED",
                message=f"User group '{user_group}' not allowed to access channel group '{channel.group}'",
                details={"user_group": user_group, "channel_group": channel.group},
            )

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
            raise RelayException(
                code="UNIAPI_QUOTA_EXHAUSTED",
                message=decision.error_message or "Budget exceeded",
            )
        request.state.budget_info = {
            "period": budget_arbiter._compute_period(),
            "frozen_amount": decision.estimated_cost,
            "monthly_budget": decision.monthly_budget,
        }

    # Pre-consume: check and deduct micro-yuan balance
    input_tokens_est = _estimate_input_tokens(body, model_config)
    output_tokens_est = min(body.get("max_tokens", body.get("max_output_tokens", 256)), 4096)
    try:
        estimated_micro = estimate_cost_micro(model_name, input_tokens_est, output_tokens_est)
    except KeyError:
        logger.warning("estimate_cost_micro failed for model=%r, using default", model_name)
        estimated_micro = 1000  # fallback: ~1k micro-yuan

    # Allow ¥1 overdraft — conservative estimation is imprecise
    if user.balance < estimated_micro and user.balance - estimated_micro < -MAX_OVERDRAFT_MICRO:
        raise RelayException(
            code="UNIAPI_QUOTA_EXHAUSTED",
            message="Insufficient user balance",
        )

    now_ms = int(time.time() * 1000)
    provisional_log = Log(
        user_id=user.id,
        created_at=now_ms,
        type=6,
        content=f"Pre-consume for {model_name}",
        username=user.username,
        token_name=token.name,
        model_name=model_name,
        cost=estimated_micro,
        channel_id=_channel_id,
        request_id=uuid.uuid4().hex,
        is_stream=stream,
    )
    db.add(provisional_log)

    user.balance -= estimated_micro
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
        upstream_body = adaptor.normalize_request_body(body)
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

    try:
        upstream_headers = adaptor.setup_request_headers(meta.api_key)
    except ValueError as e:
        # e.g. GLM key not in "id.secret" format — channel is misconfigured
        logger.warning("setup_request_headers failed for channel %d: %s", _channel_id, e)
        raise RelayException(
            message=f"渠道 {_channel_id} API key 配置错误: {e}",
            code="UNIAPI_CHANNEL_UNAVAILABLE",
        ) from e

    # Determine if SSE format conversion is needed
    needs_sse_conversion = stream and relay_mode == RelayMode.CLAUDE_MESSAGES and not adaptor.supports_native_format(relay_mode)
    output_format = "anthropic" if needs_sse_conversion else "chat"

    # Native Claude Messages streaming: use raw byte-level passthrough to
    # preserve upstream Anthropic SSE format (event: / data: lines) intact.
    # The chat-oriented SSE handler would mangle event: lines by wrapping
    # them in data: prefixes, which breaks Claude Code clients.
    native_claude_stream = (
        stream
        and relay_mode == RelayMode.CLAUDE_MESSAGES
        and adaptor.supports_native_format(relay_mode)
    )

    # Relay upstream with fallback support
    fallback_channel = None
    fallback_model = None
    upstream_response = None

    # Pre-create stream usage callback (before relay_chat_completion call)
    stream_usage_cb = None
    if stream:
        # Capture provisional_log.id from the already-flushed object
        stream_log_id = provisional_log.id
        stream_usage_cb = _make_stream_usage_callback(
            log_id=stream_log_id,
            estimated_micro=estimated_micro,
            user_id=user.id,
        )

    async def _prepare_fallback_request(next_model_name: str, next_channel: Channel) -> tuple[dict, str, dict[str, str]] | None:
        """Prepare upstream payload/url/headers using fallback channel context."""
        nonlocal meta

        next_api_key = next_channel.key or _get_channel_api_key(channel_type)
        if not next_api_key:
            return None

        next_base_url = next_channel.base_url or adaptor.DEFAULT_BASE_URL
        meta.channel_id = next_channel.id
        meta.api_key = next_api_key
        meta.base_url = next_base_url
        meta.actual_model_name = next_model_name

        body["model"] = next_model_name

        if adaptor.supports_native_format(relay_mode):
            next_body = adaptor.normalize_request_body(body)
            next_url = adaptor.get_request_url(meta, relay_mode)
        else:
            if relay_mode == RelayMode.CLAUDE_MESSAGES:
                next_body = adaptor.convert_claude_request(body)
            elif relay_mode == RelayMode.RESPONSE_API:
                from app.relay.converter import responses_to_chat

                next_body = responses_to_chat(body)
            else:
                next_body = await adaptor.convert_request(body, meta)
            next_url = adaptor.get_request_url(meta, RelayMode.CHAT_COMPLETIONS)

        try:
            next_headers = adaptor.setup_request_headers(meta.api_key)
        except ValueError:
            logger.warning("FALLBACK skip | setup_request_headers failed for channel %d", next_channel.id)
            return None
        return next_body, next_url, next_headers

    MAX_RETRIES = settings.upstream_retry_max
    BACKOFF_BASE = settings.upstream_retry_backoff_base

    for attempt in range(MAX_RETRIES):
        try:
            upstream_response = await relay_chat_completion(
                body=upstream_body,
                upstream_url=upstream_url,
                api_key=meta.api_key,
                stream=stream,
                request_headers=upstream_headers,
                output_format=output_format,
                on_stream_usage=stream_usage_cb,
                raw_passthrough=native_claude_stream,
            )
            _reset_channel_failures(_channel_id)
            break  # success, exit retry loop

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            remaining = MAX_RETRIES - attempt - 1
            _is_quota_exhausted = False
            _msg_429 = ""

            # ── 429 handling ──
            # Two distinct cases:
            #   1. Genuine rate limit → exponential backoff × remaining retries
            #   2. Quota/credits exhausted → retrying is useless, fail fast
            if status == 429:
                try:
                    _body_429 = exc.response.json()
                    _msg_429 = (
                        _body_429.get("error", {}).get("message", "")
                        or str(_body_429)
                    )
                    _quota_keywords = (
                        "quota", "用量", "plan", "credits", "balance",
                        "insufficient", "exhausted", "limit reached",
                    )
                    _is_quota_exhausted = any(kw in _msg_429.lower() for kw in _quota_keywords)
                except Exception:
                    _msg_429 = str(exc)

                if not _is_quota_exhausted and remaining >= 1:
                    # Path A: genuine rate limit → exponential backoff
                    delay = BACKOFF_BASE * (2 ** attempt) * (0.5 + random.random() * 0.5)
                    logger.info(
                        "UPSTREAM 429 (rate limit) | channel=%d attempt=%d/%d retry_in=%.2fs",
                        _channel_id, attempt + 1, MAX_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                    continue  # retry same channel — no failure count, no refund

                # Path B: quota exhausted or no retries left → diagnostic + fall through
                logger.warning(
                    "UPSTREAM 429 (quota exhausted) | channel=%d model=%s err=%s",
                    _channel_id, model_name, _msg_429,
                )

            # ── All retries and fallbacks exhausted → record failure/cooldown, refund, raise ──
            if status == 429 and _is_quota_exhausted:
                pass  # skip fallback, go straight to refund
            elif status == 429:
                fallback_channel = await _find_fallback_channel(db, channel_type, model_name)
                if fallback_channel and fallback_channel.models:
                    fallback_model = fallback_channel.models.split(",")[0].strip()
                    if _check_token_model(token, fallback_model):
                        adaptor = _get_adaptor(channel_type)
                        if adaptor:
                            model_name = fallback_model
                            model_config = adaptor.get_supported_models().get(model_name)
                            if model_config:
                                failed_channel_id = _channel_id
                                prepared = await _prepare_fallback_request(model_name, fallback_channel)
                                if prepared is not None:
                                    upstream_body, upstream_url, upstream_headers = prepared
                                    _channel_id = fallback_channel.id
                                    logger.info(
                                        "FALLBACK | 429 -> model=%s | channel_type=%d",
                                        model_name, channel_type,
                                    )
                                    _cooldown_channel(failed_channel_id)
                                    # Execute fallback inline (last iteration — can't continue)
                                    try:
                                        upstream_response = await relay_chat_completion(
                                            body=upstream_body,
                                            upstream_url=upstream_url,
                                            api_key=meta.api_key,
                                            stream=stream,
                                            request_headers=upstream_headers,
                                            output_format=output_format,
                                            on_stream_usage=stream_usage_cb,
                                            raw_passthrough=native_claude_stream,
                                        )
                                        _reset_channel_failures(_channel_id)
                                        break  # fallback succeeded
                                    except httpx.HTTPStatusError as exc2:
                                        exc = exc2
                                        status = exc2.response.status_code
                                        is_recoverable = status in (500, 502, 503)
                                        # Fall through to refund/raise below
                                    except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as fb_exc:
                                        # Non-HTTP error on fallback — refund before re-raising
                                        await _refund_and_raise_connection_error(
                                            provider_name=adaptor.provider_name if adaptor else "unknown",
                                            exc=fb_exc,
                                            user=user,
                                            estimated_micro=estimated_micro,
                                            budget_arbiter=budget_arbiter,
                                            request=request,
                                            db=db,
                                            provisional_log=provisional_log,
                                        )
                                else:
                                    logger.info("FALLBACK skip | prepare_fallback returned None")
                    else:
                        logger.info("FALLBACK skip | model=%s not allowed by token", fallback_model)
                # Fall through to refund/raise code below

            # ── Path C: 5xx recoverable, first attempt → try fallback ──
            # Works for both stream and non-stream: the eager status check in
            # relay_chat_completion() catches 4xx/5xx before streaming begins.
            is_recoverable = status in (500, 502, 503)
            if attempt == 0 and is_recoverable:
                fallback_channel = await _find_fallback_channel(db, channel_type, model_name)
                if fallback_channel and fallback_channel.models:
                    fallback_model = fallback_channel.models.split(",")[0].strip()
                    if _check_token_model(token, fallback_model):
                        adaptor = _get_adaptor(channel_type)
                        if adaptor:
                            model_name = fallback_model
                            model_config = adaptor.get_supported_models().get(model_name)
                            if model_config:
                                failed_channel_id = _channel_id
                                prepared = await _prepare_fallback_request(model_name, fallback_channel)
                                if prepared is not None:
                                    upstream_body, upstream_url, upstream_headers = prepared
                                    _channel_id = fallback_channel.id
                                    logger.info(
                                        "FALLBACK | %d -> model=%s | channel_type=%d",
                                        status, model_name, channel_type,
                                    )
                                    await _record_channel_failure(failed_channel_id, db)
                                    continue
                    else:
                        logger.info("FALLBACK skip | model=%s not allowed by token", fallback_model)

            # ── All retries and fallbacks exhausted → record failure/cooldown, refund, raise ──
            if status == 429:
                # 429 is NOT a server failure — use cooldown instead of disabling
                _cooldown_channel(_channel_id)
            elif is_recoverable:
                await _record_channel_failure(_channel_id, db)

            # Refund micro-yuan balance
            user.balance += estimated_micro

            # Mark log as failed so it doesn't remain as stale type=6
            provisional_log.type = 2
            provisional_log.content = f"Upstream {status} for {model_name}"
            import time as _time
            provisional_log.elapsed_time = int(_time.time() * 1000)

            await db.commit()

            # Budget settlement
            if budget_arbiter and settings.budget_enabled and hasattr(request.state, "budget_info") and request.state.budget_info:
                bi = request.state.budget_info
                await budget_arbiter.post_settle(
                    user_id=user.id, period=bi["period"], frozen_amount=bi["frozen_amount"],
                    monthly_budget=bi["monthly_budget"], request_id=provisional_log.request_id,
                    actual_usage=ActualUsage(model=model_name, input_tokens=0, output_tokens=0),
                    db_session=db,
                )

            # Capture upstream error body for diagnosis
            try:
                _upstream_err_body = exc.response.json()
            except Exception:
                _upstream_err_body = str(exc)
            logger.warning(
                "RELAY_FAILED request=%s model=%s channel=%d status=%d err=%s",
                provisional_log.request_id, model_name, _channel_id, status,
                _upstream_err_body,
            )

            # Map upstream HTTP error to UniAPI code
            from app.relay.upstream_errors import map_upstream_http_error

            try:
                err_body = exc.response.json()
            except Exception as err:
                err_body = str(err)
            provider_name = adaptor.provider_name if adaptor else "unknown"
            uni_code, upstream, reason = map_upstream_http_error(provider_name, status, err_body)
            details = {"reason": reason} if reason else None
            raise UpstreamException(
                message=f"Upstream returned {status}",
                code=uni_code,
                upstream_provider=upstream["provider"],
                upstream_status=upstream["status_code"],
                upstream_code=upstream.get("code"),
                upstream_message=upstream.get("message"),
                details=details,
            )

        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            # Non-HTTP-status error (timeout, connection error, protocol error)
            # Works for both stream and non-stream: connection errors are raised
            # inside relay_chat_completion() before streaming begins.
            if attempt == 0:
                fallback_channel = await _find_fallback_channel(db, channel_type, model_name)
                if fallback_channel and fallback_channel.models:
                    fallback_model = fallback_channel.models.split(",")[0].strip()
                    if _check_token_model(token, fallback_model):
                        adaptor = _get_adaptor(channel_type)
                        if adaptor:
                            model_name = fallback_model
                            model_config = adaptor.get_supported_models().get(model_name)
                            if model_config:
                                failed_channel_id = _channel_id
                                prepared = await _prepare_fallback_request(model_name, fallback_channel)
                                if prepared is not None:
                                    upstream_body, upstream_url, upstream_headers = prepared
                                    _channel_id = fallback_channel.id
                                    logger.info("FALLBACK | error -> model=%s", model_name)
                                    await _record_channel_failure(failed_channel_id, db)
                                    continue
                    else:
                        logger.info("FALLBACK skip | model=%s not allowed by token", fallback_model)

            # Refund and raise — shared helper
            await _refund_and_raise_connection_error(
                provider_name=adaptor.provider_name if adaptor else "unknown",
                exc=exc,
                user=user,
                estimated_micro=estimated_micro,
                budget_arbiter=budget_arbiter,
                request=request,
                db=db,
                provisional_log=provisional_log,
            )

    if stream:
        provisional_log.type = 2
        provisional_log.elapsed_time = int((time.time() - relay_start) * 1000)
        provisional_log.content = f"Stream: {relay_mode_name(relay_mode)} with {model_name}"
        await db.commit()
        return upstream_response

    # Post-consume: reconcile micro-yuan balance
    usage = upstream_response.get("usage", {})

    # Parse cache tokens — support both DeepSeek and OpenAI formats
    prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
    completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0

    # DeepSeek format: prompt_cache_hit_tokens / prompt_cache_miss_tokens
    cache_hit = usage.get("prompt_cache_hit_tokens") or 0
    cache_miss = usage.get("prompt_cache_miss_tokens") or 0

    # OpenAI format: prompt_tokens_details.cached_tokens
    if not cache_hit and not cache_miss:
        details = usage.get("prompt_tokens_details") or {}
        cache_hit = details.get("cached_tokens") or 0
        # MiniMax quirk: when prompt_tokens=0 but cached_tokens>0,
        # the cached_tokens IS the total prompt tokens (all were cached)
        if prompt_tokens == 0 and cache_hit > 0:
            prompt_tokens = cache_hit
        cache_miss = max(0, prompt_tokens - cache_hit)

    # Fallback: legacy cached_tokens field
    if not cache_hit and not cache_miss:
        cache_hit = usage.get("cached_tokens") or 0
        # Same MiniMax quirk
        if prompt_tokens == 0 and cache_hit > 0:
            prompt_tokens = cache_hit
        cache_miss = max(0, prompt_tokens - cache_hit)

    # Calculate actual cost in micro-yuan
    try:
        actual_micro = calculate_cost_micro(model_name, prompt_tokens, completion_tokens, cache_hit)
    except KeyError:
        logger.warning("calculate_cost_micro failed for model=%r, using estimate", model_name)
        actual_micro = estimated_micro

    # Refund/charge difference to user's balance
    diff_micro = estimated_micro - actual_micro
    if diff_micro != 0:
        user.balance += diff_micro

    provisional_log.type = 2
    provisional_log.cost = actual_micro
    provisional_log.prompt_tokens = prompt_tokens
    provisional_log.completion_tokens = completion_tokens
    provisional_log.elapsed_time = int((time.time() - relay_start) * 1000)
    provisional_log.cached_prompt_tokens = cache_hit
    provisional_log.cached_completion_tokens = 0
    provisional_log.content = f"{relay_mode_name(relay_mode)} with {model_name}"

    # Budget: post-settle with actual usage
    if budget_arbiter and settings.budget_enabled and hasattr(request.state, "budget_info") and request.state.budget_info:
        bi = request.state.budget_info
        await budget_arbiter.post_settle(
            user_id=user.id, period=bi["period"], frozen_amount=bi["frozen_amount"],
            monthly_budget=bi["monthly_budget"], request_id=provisional_log.request_id,
            actual_usage=ActualUsage(
                model=model_name,
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                cache_hit_tokens=cache_hit,
            ),
            db_session=db,
        )

    # Lightweight cost recording (runs when budget is DISABLED;
    # when budget is enabled, post_settle → _write_cost_record handles it).
    if provisional_log.request_id and not settings.budget_enabled:
        try:
            yuan_cost = calculate_cost(model_name, prompt_tokens, completion_tokens, cache_hit)
        except Exception:
            yuan_cost = 0.0
        db.add(CostRecord(
            request_id=provisional_log.request_id,
            user_id=user.id,
            model=model_name,
            input_tokens=prompt_tokens,
            output_tokens=completion_tokens,
            cache_hit_tokens=cache_hit,
            cost=round(yuan_cost, 6),
            status="success",
            created_at=int(time.time() * 1000),
        ))

        # Real-time pool consumption sync
        try:
            from app.services.pool_sync import sync_consumption_to_pool
            await sync_consumption_to_pool(
                db,
                user_id=user.id,
                cost_yuan=yuan_cost,
                model_name=model_name,
                request_id=provisional_log.request_id,
            )
        except Exception:
            logger.warning("Pool sync failed (non-fatal)", exc_info=True)

    await db.commit()

    # Convert Chat response → Anthropic format for non-native Claude Messages adaptors
    if relay_mode == RelayMode.CLAUDE_MESSAGES and not adaptor.supports_native_format(relay_mode):
        from app.relay.converter import chat_response_to_anthropic
        upstream_response = chat_response_to_anthropic(upstream_response, provisional_log.request_id)

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
    token = request.state.token
    now = int(time.time())

    # Build token allowlist (if token restricts models)
    allowed_models: set[str] | None = None
    if hasattr(token, "models") and token.models:
        allowed_models = {m.strip() for m in token.models.split(",")}

    # Find which channel types have at least one enabled channel
    result = await db.execute(
        select(Channel).where(Channel.status == 1)
    )
    enabled_channels = result.scalars().all()
    enabled_types = {ch.type for ch in enabled_channels}

    models = []
    for adp in registry.all_adaptors():
        ch_type = adp.get_channel_type()
        # Skip adaptors with no enabled channels
        if ch_type not in enabled_types:
            continue
        for m in adp.get_supported_models():
            # Respect token model allowlist
            if allowed_models is not None and m not in allowed_models:
                continue
            models.append({"id": m, "object": "model", "created": now, "owned_by": adp.provider_name})
    return {"object": "list", "data": models}


@router.get("/v1/models/{model_id}")
async def retrieve_model(model_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    await token_auth(request, db)
    now = int(time.time())
    for adp in registry.all_adaptors():
        if adp.resolve_model_name(model_id):
            return {
                "id": model_id,
                "object": "model",
                "created": now,
                "owned_by": adp.provider_name,
            }
    raise RelayException(
        code="UNIAPI_RESOURCE_NOT_FOUND",
        message=f"Model '{model_id}' not found",
        details={"model_id": model_id},
    )
