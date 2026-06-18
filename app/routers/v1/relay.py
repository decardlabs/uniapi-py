from __future__ import annotations

import time
import uuid
from typing import Any

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


def _get_adaptor() -> BaseAdaptor:
    """Get the DeepSeek adaptor (will be registry-based when multi-provider)."""
    adp = registry.get(39)  # DEEPSEEK_CHANNEL_TYPE
    if not adp:
        raise HTTPException(status_code=500, detail="No adaptor configured")
    return adp


def _estimate_cost(body: dict, model_config: Any) -> int:
    messages = body.get("messages", body.get("input", []))
    if isinstance(messages, str):
        total_chars = len(messages)
    else:
        total_chars = sum(len(str(m.get("content", ""))) for m in (messages if isinstance(messages, list) else [messages]))
    prompt_tokens = max(10, total_chars // 4)
    max_tokens = body.get("max_tokens", body.get("max_output_tokens", 256))
    if isinstance(max_tokens, str):
        max_tokens = 256
    completion_tokens = min(max_tokens, 1024)
    return int(
        prompt_tokens * model_config.input_ratio
        + completion_tokens * model_config.output_ratio * model_config.input_ratio
    )


def _get_channel_api_key() -> str:
    from app.config import settings
    return settings.deepseek_api_key


async def _handle_relay(request: Request, db: AsyncSession):
    """Universal relay handler: smart routes based on adaptor NATIVE_FORMATS."""
    user, token = await _resolve_token_and_channel(request, db)
    body = await request.json()
    path = request.url.path
    relay_mode = relay_mode_from_path(path)

    model_name = body.get("model", "")
    stream = body.get("stream", False)
    adaptor = _get_adaptor()
    supported = adaptor.get_supported_models()

    if model_name not in supported:
        raise HTTPException(status_code=400, detail=f"Model '{model_name}' not supported")

    # Token model permissions
    if hasattr(token, "models") and token.models:
        allowed = [m.strip() for m in token.models.split(",")]
        if model_name not in allowed:
            raise HTTPException(status_code=403, detail=f"Token not allowed to use model '{model_name}'")

    # Pre-consume quota
    model_config = supported[model_name]
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
        channel_type=39,
        channel_id=1,
        token_id=token.id,
        token_name=token.name,
        user_id=user.id,
        group=user.group or "default",
        api_key=_get_channel_api_key(),
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
        # 🔄 CONVERT: transform to chat format
        upstream_body = await adaptor.convert_request(body, meta)
        upstream_url = adaptor.get_request_url(meta, 1)  # ChatCompletions mode

    upstream_headers = adaptor.setup_request_headers(meta.api_key)

    # Relay upstream
    try:
        upstream_response = await relay_chat_completion(
            body=upstream_body,
            upstream_url=upstream_url,
            api_key=meta.api_key,
            stream=stream,
        )
    except Exception:
        # Refund on failure
        if not token.unlimited_quota:
            token.remain_quota += estimated
        user.quota += estimated
        user.used_quota -= estimated
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
        + completion_tokens * model_config.output_ratio * model_config.input_ratio
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
    adaptor = _get_adaptor()
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
    adaptor = _get_adaptor()
    if model_id not in adaptor.get_supported_models():
        raise HTTPException(status_code=404, detail="Model not found")
    return {
        "id": model_id,
        "object": "model",
        "created": int(time.time()),
        "owned_by": "deepseek",
    }
