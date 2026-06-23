"""Channel CRUD API — management endpoints for AI provider channels.

Route ordering note: specific paths (search, test, disabled) MUST be
defined BEFORE the {channel_id} parameterized route to avoid conflicts.
"""
from __future__ import annotations

import json
import logging
import time
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import admin_auth
from app.models.channel import Channel
from app.models.log import Log
from app.models.token import Token
from app.models.user import User
from app.schemas.common import GenericApiResponse, PaginatedResponse

router = APIRouter(tags=["channels"])
logger = logging.getLogger(__name__)


def _json_str(val):
    """Convert a value to a JSON string for DB text columns.

    Handles dicts, lists, and other types that SQLite can't store directly.
    """
    if val is None:
        return None
    if isinstance(val, (dict, list, bool)):
        import json
        try:
            return json.dumps(val)
        except (TypeError, ValueError):
            return str(val)
    return str(val)


# ──────────────────────────────────────────────
# Static routes first (before {channel_id})
# ──────────────────────────────────────────────


@router.get("/api/channel/")
async def list_channels(
    p: int = Query(0, ge=0),
    size: int = Query(10, ge=1, le=100),
    sort: str = "id",
    order: str = "desc",
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """List channels (paginated, sortable)."""
    sort_col = getattr(Channel, sort, Channel.id)
    order_fn = sort_col.desc() if order == "desc" else sort_col.asc()

    total = await db.scalar(select(func.count()).select_from(Channel)) or 0
    result = await db.execute(
        select(Channel).order_by(order_fn).offset(p * size).limit(size)
    )
    return PaginatedResponse(
        data=[_channel_to_dict(c) for c in result.scalars().all()],
        total=total,
    )


@router.get("/api/channel/search")
async def search_channels(
    keyword: str = "",
    size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Search channels by name or model keyword."""
    clause = or_(Channel.name.ilike(f"%{keyword}%"), Channel.models.ilike(f"%{keyword}%"))
    total = await db.scalar(select(func.count()).select_from(Channel).where(clause)) or 0
    result = await db.execute(
        select(Channel).where(clause).order_by(Channel.id.desc()).limit(size)
    )
    return PaginatedResponse(
        data=[_channel_to_dict(c) for c in result.scalars().all()],
        total=total,
    )


@router.post("/api/channel/")
async def create_channel(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Create a new channel.

    Supports multi-key creation: when the ``key`` field contains multiple
    lines (separated by ``\\n``), one channel record is created per line.
    All other fields (name, type, models, weight, etc.) are shared across
    all generated channels.

    This matches the UX of the Go uniapi project where users paste several
    API keys in the Textarea and the backend auto-expands them.
    """
    now_ms = int(time.time() * 1000)
    now_s = int(time.time())

    # Transform arrays to comma-separated strings for DB storage
    models_raw = body.get("models", "")
    if isinstance(models_raw, list):
        models_raw = ",".join(str(m).strip() for m in models_raw)

    # Normalize model names to canonical form (handles case-insensitive aliases)
    if models_raw:
        from app.relay.registry import registry
        normalized = []
        for m_name in (x.strip() for x in models_raw.split(",") if x.strip()):
            ct = registry.resolve_channel_type(m_name)
            if ct is not None:
                adaptor = registry.get(ct)
                if adaptor:
                    canonical = adaptor.resolve_model_name(m_name)
                    if canonical:
                        normalized.append(canonical)
                        continue
            normalized.append(m_name)
        models_raw = ",".join(normalized)

    groups_raw = body.get("groups", body.get("group", "default"))
    if isinstance(groups_raw, list):
        group_val = groups_raw[0] if groups_raw else "default"
    else:
        group_val = groups_raw

    # Split key by newlines to support multi-key batch creation
    # (matching the Go uniapi project's controller/channel.go AddChannel)
    keys = [k.strip() for k in body.get("key", "").split("\n") if k.strip()]
    if not keys:
        keys = [""]

    channels = []
    for key in keys:
        channel = Channel(
            name=body.get("name", ""),
            type=body.get("type", 0),
            key=key,
            status=body.get("status", 1),
            base_url=body.get("base_url", ""),
            models=models_raw,
            group=group_val,
            weight=body.get("weight", 0),
            priority=body.get("priority", 0),
            model_mapping=_json_str(body.get("model_mapping")),
            other=_json_str(body.get("other")),
            model_configs=_json_str(body.get("model_configs")),
            system_prompt=_json_str(body.get("system_prompt")),
            config=_json_str(body.get("config")),
            rate_limit=body.get("ratelimit", 0),
            created_time=now_s,
            created_at=now_ms,
            updated_at=now_ms,
        )
        db.add(channel)
        channels.append(channel)

    await db.commit()
    for ch in channels:
        await db.refresh(ch)

    # Return the first channel's data for frontend compatibility
    return GenericApiResponse(data=_channel_to_dict(channels[0]))


@router.put("/api/channel/")
async def update_channel(
    body: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Update a channel. Supports full update or status-only toggle."""
    channel_id = body.get("id")
    if not channel_id:
        raise HTTPException(status_code=400, detail="id is required")

    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # Status-only update (from manage action like enable/disable)
    if request.query_params.get("status_only") == "1" or body.get("action"):
        action = body.get("action", "")
        if action == "enable":
            channel.status = 1
        elif action == "disable":
            channel.status = 2
        elif body.get("status") is not None:
            channel.status = int(body["status"])
        channel.updated_at = int(time.time() * 1000)
        await db.commit()
        return GenericApiResponse(data=_channel_to_dict(channel))

    # Full field update
    text_fields = {"model_mapping", "other", "model_configs", "system_prompt", "config"}
    for field in ("name", "type", "key", "status", "base_url", "models",
                   "group", "weight", "priority", "model_mapping", "other",
                   "model_configs", "system_prompt", "config"):
        if field in body:
            val = body[field]
            if field in text_fields:
                val = _json_str(val)
            setattr(channel, field, val)
    # Map frontend field name to backend field
    if "ratelimit" in body:
        channel.rate_limit = body["ratelimit"]
    if "groups" in body:
        g = body["groups"]
        channel.group = g[0] if isinstance(g, list) and g else "default"
    channel.updated_at = int(time.time() * 1000)
    await db.commit()
    await db.refresh(channel)
    return GenericApiResponse(data=_channel_to_dict(channel))


@router.get("/api/channel/test")
async def test_all_channels(
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Test each model in every enabled channel with a minimal chat completion request.

    For each channel + model combination:
      - Sends a real POST /chat/completions with "hi" as the user message
      - Records prompt tokens, completion tokens, cost, and latency
      - Uses the root user's \"default\" token for permission checks
      - Logs results with username=\"root\", token_name=\"default\"
    """
    from app.relay import channeltype
    from app.config import settings
    from app.relay.registry import registry

    result = await db.execute(select(Channel).where(Channel.status == 1))
    channels = result.scalars().all()

    # Find root's default token for model permission checks
    root_user = await db.execute(select(User).where(User.username == "root"))
    root = root_user.scalar_one_or_none()
    default_token = None
    if root:
        token_result = await db.execute(
            select(Token).where(Token.user_id == root.id, Token.name == "default")
        )
        default_token = token_result.scalar_one_or_none()

    token_allowed_models: set[str] | None = None
    if default_token and default_token.models:
        token_allowed_models = set(m.strip() for m in default_token.models.split(",") if m.strip())

    key_map = {
        channeltype.DeepSeek: settings.deepseek_api_key,
        channeltype.GLM: settings.glm_api_key,
        channeltype.Moonshot: settings.kimi_api_key,
        channeltype.Minimax: settings.minimax_api_key,
        channeltype.AliBailian: settings.qwen_api_key,
    }

    now_ms = int(time.time() * 1000)
    results = []

    for channel in channels:
        # Per-channel try-except: a crash in one channel must NOT fail the entire batch.
        # Per-channel SAVEPOINT: DB changes (response_time, test_time, logs) are committed
        # per-channel via SAVEPOINT + RELEASE, so a failure in one channel does not
        # roll back results from earlier channels.
        try:
            await db.execute(text("SAVEPOINT sp_channel_test"))
        except Exception:
            pass  # SAVEPOINT is a best-effort isolation; proceed without it if unsupported

        try:
            adaptor = registry.get(channel.type)
            if not adaptor:
                results.append({
                    "channel_id": channel.id, "name": channel.name,
                    "status": "skipped", "detail": f"No adaptor for channel type {channel.type}",
                })
                continue

            # Determine models to test: prefer channel-specific, fall back to adaptor defaults
            if channel.models:
                models_to_test = [m.strip() for m in channel.models.split(",") if m.strip()]
            else:
                models_to_test = list(adaptor.get_supported_models().keys())

            if not models_to_test:
                results.append({
                    "channel_id": channel.id, "name": channel.name,
                    "status": "skipped", "detail": "No models configured on this channel",
                })
                continue

            # Resolve base URL and API key
            base_url = channel.base_url or adaptor.DEFAULT_BASE_URL
            if not base_url:
                results.append({
                    "channel_id": channel.id, "name": channel.name,
                    "status": "skipped", "detail": "No base URL",
                })
                continue

            api_key = channel.key or key_map.get(channel.type, "")
            if not api_key:
                results.append({
                    "channel_id": channel.id, "name": channel.name,
                    "status": "skipped", "detail": "No API key configured",
                })
                continue

            headers = adaptor.setup_request_headers(api_key)
            upstream_url = f"{base_url.rstrip('/')}/chat/completions"
            supported_models = adaptor.get_supported_models()
            channel.test_time = now_ms
            has_success = False

            for model_name in models_to_test:
                # Token permission check
                if token_allowed_models is not None and model_name not in token_allowed_models:
                    results.append({
                        "channel_id": channel.id, "name": channel.name, "model": model_name,
                        "status": "skipped",
                        "detail": f"Token 'default' does not have permission for model '{model_name}'. "
                                  "Please update the default token's model settings.",
                    })
                    continue

                model_config = supported_models.get(model_name)
                test_start = 0  # Defensive init — prevents UnboundLocalError

                try:
                    test_start = int(time.time() * 1000)
                    test_body = {
                        "model": model_name,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": 5,
                    }

                    logger.info("TEST channel=%s model=%s url=%s", channel.name, model_name, upstream_url)

                    async with httpx.AsyncClient(timeout=10) as client:
                        resp = await client.post(upstream_url, json=test_body, headers=headers)
                        elapsed = int(time.time() * 1000) - test_start
                        body = resp.json()

                    logger.info(
                        "TEST RESP status=%d ok=%s body_keys=%s usage=%s",
                        resp.status_code, resp.is_success,
                        list(body.keys()), body.get("usage"),
                    )

                    if resp.is_success:
                        usage = body.get("usage", {})
                        prompt_tokens = usage.get("prompt_tokens", 0) or 0
                        completion_tokens = usage.get("completion_tokens", 0) or 0

                        cost = 0
                        if model_config:
                            cost = int(
                                prompt_tokens * model_config.input_ratio
                                + completion_tokens * model_config.output_ratio
                            )

                        logger.info(
                            "TEST RESULT ok channel=%s model=%s pt=%d ct=%d cost=%d elapsed=%dms usage_keys=%s",
                            channel.name, model_name, prompt_tokens, completion_tokens, cost, elapsed,
                            list(usage.keys()) if usage else "none",
                        )

                        channel.response_time = elapsed
                        has_success = True

                        db.add(Log(
                            user_id=root.id if root else 0,
                            created_at=test_start,
                            type=5,
                            content=f"[ok] {channel.name} / {model_name} — {prompt_tokens}↑{completion_tokens}↓ {cost} | uk={list(usage.keys()) if usage else 'none'}",
                            username="root",
                            token_name="default",
                            model_name=model_name,
                            quota=cost,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            channel_id=channel.id,
                            request_id=uuid.uuid4().hex,
                            elapsed_time=elapsed,
                        ))

                        results.append({
                            "channel_id": channel.id, "name": channel.name, "model": model_name,
                            "status": "ok",
                            "http_status": resp.status_code,
                            "time": round(elapsed / 1000, 3),
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "cost": cost,
                        })
                    else:
                        logger.warning(
                            "TEST RESP error channel=%s model=%s status=%d body_keys=%s body_preview=%s",
                            channel.name, model_name, resp.status_code,
                            list(body.keys()) if isinstance(body, dict) else type(body).__name__,
                            str(body)[:200],
                        )
                        db.add(Log(
                            user_id=root.id if root else 0,
                            created_at=test_start,
                            type=5,
                            content=f"[error] {channel.name} / {model_name} — HTTP {resp.status_code}",
                            username="root",
                            token_name="default",
                            model_name=model_name,
                            quota=0,
                            channel_id=channel.id,
                            request_id=uuid.uuid4().hex,
                            elapsed_time=elapsed,
                        ))
                        results.append({
                            "channel_id": channel.id, "name": channel.name, "model": model_name,
                            "status": "error",
                            "http_status": resp.status_code,
                            "time": round(elapsed / 1000, 3),
                            "detail": resp.text[:300],
                        })

                except Exception as exc:
                    elapsed_ms = int(time.time() * 1000) - (test_start or int(time.time() * 1000))
                    logger.warning(
                        "TEST EXCEPTION channel=%s model=%s err=%s elapsed=%dms",
                        channel.name, model_name, exc, elapsed_ms,
                    )
                    db.add(Log(
                        user_id=root.id if root else 0,
                        created_at=int(time.time() * 1000),
                        type=5,
                        content=f"[error] {channel.name} / {model_name} — {exc}",
                        username="root",
                        token_name="default",
                        model_name=model_name,
                        quota=0,
                        channel_id=channel.id,
                        request_id=uuid.uuid4().hex,
                        elapsed_time=elapsed_ms,
                    ))
                    results.append({
                        "channel_id": channel.id, "name": channel.name, "model": model_name,
                        "status": "error",
                        "time": round(elapsed_ms / 1000, 3),
                        "detail": str(exc),
                    })

            if not has_success:
                channel.response_time = -1
            await db.flush()

        except Exception as channel_exc:
            logger.error(
                "TEST CHANNEL EXCEPTION channel=%s err=%s",
                channel.name, channel_exc,
            )
            results.append({
                "channel_id": channel.id, "name": channel.name,
                "status": "error",
                "detail": f"Channel-level error: {channel_exc}",
            })
        else:
            # No exception in this channel's outer block — release the SAVEPOINT
            # so per-channel changes survive without a final db.commit().
            try:
                await db.execute(text("RELEASE SAVEPOINT sp_channel_test"))
            except Exception:
                pass

    await db.commit()
    return GenericApiResponse(data={"total": len(results), "results": results})


@router.get("/api/channel/default-pricing")
async def channel_default_pricing(
    type: int = Query(0, alias="type"),
    _=Depends(admin_auth),
):
    """Return default pricing for a given channel type, including model_configs as JSON string."""
    from app.relay.registry import registry
    adaptor = registry.get(type)
    if not adaptor:
        return GenericApiResponse(data={})

    models = adaptor.get_supported_models()
    pricing = {}
    model_configs = {}
    for name, cfg in models.items():
        pricing[name] = {
            "input_price": cfg.input_ratio,
            "output_price": cfg.output_ratio,
            "cached_input_price": cfg.cached_input_ratio,
        }
        model_configs[name] = {
            "ratio": cfg.input_ratio,
            "completion_ratio": cfg.output_ratio,
            "max_tokens": cfg.max_tokens,
        }

    import json
    return GenericApiResponse(data={
        "model_configs": json.dumps(model_configs),
        "tooling": json.dumps({"whitelist": [], "pricing": {}}),
        "pricing": pricing,
    })


@router.get("/api/channel/metadata")
async def channel_metadata(
    type: int = Query(0, alias="type"),
    _=Depends(admin_auth),
):
    """Return metadata (supported params, capabilities) for a channel type."""
    adaptor = registry.get(type)
    caps = list(adaptor.NATIVE_FORMATS) if adaptor else []
    return GenericApiResponse(data={
        "type": type,
        "capabilities": caps,
    })


@router.get("/api/channel/test/{channel_id}")
async def test_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Test connectivity for a specific channel."""
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    from app.relay.registry import registry

    adaptor = registry.get(channel.type)
    if not adaptor:
        return GenericApiResponse(
            data={"channel_id": channel_id, "status": "skipped", "detail": f"No adaptor for channel type {channel.type}"}
        )

    # Resolve base URL: channel setting → adaptor default
    base_url = channel.base_url
    if not base_url:
        base_url = adaptor.DEFAULT_BASE_URL

    if not base_url:
        return GenericApiResponse(data={"channel_id": channel_id, "status": "skipped", "detail": "No base_url"})

    # Resolve API key: channel key → env var
    api_key = channel.key
    if not api_key:
        from app.config import settings
        from app.relay import channeltype
        key_map = {
            channeltype.DeepSeek: settings.deepseek_api_key,
            channeltype.GLM: settings.glm_api_key,
            channeltype.Moonshot: settings.kimi_api_key,
            channeltype.Minimax: settings.minimax_api_key,
            channeltype.AliBailian: settings.qwen_api_key,
        }
        api_key = key_map.get(channel.type, "")

    try:
        test_start = int(time.time() * 1000)
        test_url = f"{base_url.rstrip('/')}/models"
        async with httpx.AsyncClient(timeout=10) as client:
            headers = adaptor.setup_request_headers(api_key) if api_key else {}
            resp = await client.get(test_url, headers=headers)
            channel.test_time = test_start
            status = "ok" if resp.is_success else "error"
            elapsed = int(time.time() * 1000) - test_start

        db.add(Log(
            user_id=0,
            created_at=test_start,
            type=5,
            content=f"[{status}] {channel.name} — HTTP {resp.status_code} ({elapsed}ms)",
            username="admin",
            token_name="channel_test",
            model_name=channel.name,
            quota=0,
            channel_id=channel_id,
            request_id=uuid.uuid4().hex,
            elapsed_time=elapsed,
        ))
        await db.commit()

        return {
            "success": True,
            "data": {"channel_id": channel_id, "status": status, "http_status": resp.status_code},
            "time": round(elapsed / 1000, 3),
        }
    except Exception as exc:
        return {
            "success": False,
            "message": str(exc),
            "time": 0,
        }


@router.delete("/api/channel/disabled")
async def delete_disabled_channels(
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Delete all disabled channels."""
    result = await db.execute(select(Channel).where(Channel.status == 2))
    channels = result.scalars().all()
    for c in channels:
        await db.delete(c)
    await db.commit()
    return GenericApiResponse(data={"deleted_count": len(channels)})


# ──────────────────────────────────────────────
# Parameterized routes (keep at bottom)
# ──────────────────────────────────────────────


@router.get("/api/channel/{channel_id}")
async def get_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Get a single channel by ID."""
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return GenericApiResponse(data=_channel_to_dict(channel))


@router.delete("/api/channel/{channel_id}")
async def delete_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(admin_auth),
):
    """Delete a single channel."""
    result = await db.execute(select(Channel).where(Channel.id == channel_id))
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    await db.delete(channel)
    await db.commit()
    return GenericApiResponse(data={"deleted": channel_id})


def _to_seconds(ts: int) -> int:
    """Normalize timestamp to seconds (detect and convert ms values)."""
    if ts > 100000000000:  # 13+ digits = milliseconds
        return ts // 1000
    return ts


def _channel_to_dict(c: Channel) -> dict:
    """Convert Channel ORM to dict matching frontend Channel interface."""
    return {
        "id": c.id,
        "type": c.type,
        "key": c.key or "",
        "status": c.status,
        "name": c.name,
        "base_url": c.base_url or "",
        "models": c.models or "",
        "group": c.group,
        "model_mapping": c.model_mapping or "",
        "priority": c.priority,
        "weight": c.weight,
        "other_info": c.other or "",
        "model_configs": c.model_configs or "",
        "system_prompt": c.system_prompt or "",
        "config": c.config or "",
        "rate_limit": c.rate_limit or 0,
        "created_time": _to_seconds(c.created_time),
        "created_at": _to_seconds(c.created_at),
        "updated_at": _to_seconds(c.updated_at),
        "test_time": _to_seconds(c.test_time),
        "response_time": _to_seconds(c.response_time),
    }
