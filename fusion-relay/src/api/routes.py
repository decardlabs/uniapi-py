"""
API routes: OpenAI + Anthropic dual-protocol endpoints.

OpenAI protocol:
  POST /v1/chat/completions  -> main entry (fusion or passthrough)
  GET  /v1/models            -> list available models

Anthropic protocol:
  POST /v1/messages          -> Anthropic Messages API (Claude Code / Anthropic SDK)

Admin:
  GET  /admin/fusion/config  -> view fusion config
  PUT  /admin/fusion/config  -> update fusion config (hot reload)
  GET  /admin/stats          -> fusion statistics
  GET  /health               -> health check
"""

import logging
import time
import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from src.models.schemas import ChatRequest, ChatResponse, ModelRequest
from src.core.fusion_engine import FusionEngine, FusionConfig
from src.adapters.registry import AdapterRegistry
from src.api.protocol_adapters import (
    AnthropicMessagesRequest,
    anthropic_to_internal,
    internal_to_anthropic,
    openai_chunk_to_anthropic_events,
    anthropic_stream_start,
    anthropic_stream_stop,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_registry(request: Request) -> AdapterRegistry:
    return request.app.state.registry


def get_fusion_engine(request: Request) -> FusionEngine:
    return request.app.state.fusion_engine


# ──────────────────────────────────────────────
# Core request handler (shared by both protocols)
# ──────────────────────────────────────────────

async def _handle_chat_request(
    chat_request: ChatRequest,
    registry: AdapterRegistry,
    fusion_engine: FusionEngine,
) -> ChatResponse:
    """
    Unified handler for both OpenAI and Anthropic protocols.
    After protocol conversion, both arrive as ChatRequest.
    """
    if chat_request.is_fusion:
        if chat_request.fusion_override:
            override = chat_request.fusion_override
            custom_config = FusionConfig(
                panel=override.get("panel", fusion_engine.config.panel),
                judge=override.get("judge", fusion_engine.config.judge),
                synthesizer=override.get("synthesizer", fusion_engine.config.synthesizer),
                timeout_seconds=fusion_engine.config.timeout_seconds,
                retry_count=fusion_engine.config.retry_count,
                fallback_model=fusion_engine.config.fallback_model,
            )
            temp_engine = FusionEngine(registry, custom_config)
            return await temp_engine.execute(chat_request)
        else:
            return await fusion_engine.execute(chat_request)
    else:
        # Passthrough mode
        adapter = registry.get(chat_request.model)
        if adapter is None:
            raise HTTPException(
                status_code=404,
                detail=f"Model '{chat_request.model}' not found. Available: {registry.list_models()} + 'fusion'",
            )

        model_request = ModelRequest(
            model=chat_request.model,
            messages=chat_request.messages,
            temperature=chat_request.temperature,
            max_tokens=chat_request.max_tokens or 8192,
            tools=chat_request.tools,
            stream=chat_request.stream,
        )

        model_response = await adapter.chat(model_request)

        return ChatResponse(
            id=f"chatcmpl-{int(time.time())}",
            model=chat_request.model,
            choices=[{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": model_response.content,
                },
                "finish_reason": model_response.finish_reason,
            }],
            usage=model_response.usage,
        )


# ──────────────────────────────────────────────
# OpenAI protocol endpoints
# ──────────────────────────────────────────────

@router.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    registry: AdapterRegistry = Depends(get_registry),
    fusion_engine: FusionEngine = Depends(get_fusion_engine),
):
    """
    OpenAI-compatible chat completions endpoint.

    - model="fusion" -> triggers fusion pipeline
    - model="any-model-id" -> passthrough to that model directly
    - extra_body.fusion -> override fusion config for this request
    """
    body = await request.json()
    chat_request = ChatRequest.from_dict(body)

    logger.info(
        "[OpenAI] Request received | model=%s | messages=%d | stream=%s",
        chat_request.model, len(chat_request.messages), chat_request.stream,
    )

    if chat_request.stream:
        return await _handle_openai_stream(chat_request, registry, fusion_engine)

    response = await _handle_chat_request(chat_request, registry, fusion_engine)
    return JSONResponse(content=response.to_dict())


async def _handle_openai_stream(
    chat_request: ChatRequest,
    registry: AdapterRegistry,
    fusion_engine: FusionEngine,
):
    """Handle OpenAI streaming response."""
    if chat_request.is_fusion:
        # Fusion streaming: collect all panel results, then stream final synthesis
        # (Simplified: stream the synthesizer's output as OpenAI SSE)
        response = await fusion_engine.execute(chat_request)

        async def stream_generator():
            # Stream the final synthesized content as chunks
            content = response.choices[0].get("message", {}).get("content", "")
            chunk_size = 20  # characters per chunk
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i + chunk_size]
                data = {
                    "id": response.id,
                    "object": "chat.completion.chunk",
                    "model": response.model,
                    "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(data)}\n\n"

            # Final chunk with finish_reason
            final = {
                "id": response.id,
                "object": "chat.completion.chunk",
                "model": response.model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(final)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    # Passthrough streaming
    adapter = registry.get(chat_request.model)
    if adapter is None:
        raise HTTPException(status_code=404, detail=f"Model '{chat_request.model}' not found")

    model_request = ModelRequest(
        model=chat_request.model,
        messages=chat_request.messages,
        temperature=chat_request.temperature,
        max_tokens=chat_request.max_tokens or 8192,
        tools=chat_request.tools,
        stream=True,
    )

    async def stream_generator():
        async for chunk in adapter.stream_chat(model_request):
            data = {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion.chunk",
                "model": chat_request.model,
                "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(data)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


# ──────────────────────────────────────────────
# Anthropic protocol endpoints
# ──────────────────────────────────────────────

@router.post("/v1/messages")
async def anthropic_messages(
    request: Request,
    registry: AdapterRegistry = Depends(get_registry),
    fusion_engine: FusionEngine = Depends(get_fusion_engine),
):
    """
    Anthropic Messages API endpoint.

    Supports Claude Code, Anthropic SDK, and any Agent using the Anthropic protocol.
    The request is converted to internal format, processed by fusion engine,
    then the response is converted back to Anthropic format.

    - model="claude-*" -> automatically triggers fusion (Agent thinks it's calling Claude)
    - model="fusion" -> explicit fusion trigger
    - model="deepseek-v4-pro" etc -> passthrough to that model

    Claude Code configuration:
      ANTHROPIC_BASE_URL=http://your-relay-host:8000
      ANTHROPIC_API_KEY=your-relay-api-key
    """
    body = await request.json()
    anthropic_request = AnthropicMessagesRequest.from_dict(body)

    # Convert Anthropic request to internal format
    chat_request = anthropic_to_internal(anthropic_request)

    logger.info(
        "[Anthropic] Request received | original_model=%s | internal_model=%s | messages=%d | stream=%s",
        anthropic_request.model, chat_request.model,
        len(chat_request.messages), chat_request.stream,
    )

    if chat_request.stream:
        return await _handle_anthropic_stream(chat_request, anthropic_request, registry, fusion_engine)

    # Process request through unified handler
    response = await _handle_chat_request(chat_request, registry, fusion_engine)

    # Convert internal response back to Anthropic format
    anthropic_response = internal_to_anthropic(response)

    # Preserve original model name so Claude Code doesn't suspect it's behind a relay
    if chat_request.extra_body.get("_source_protocol") == "anthropic":
        original_model = chat_request.extra_body.get("_original_model", anthropic_request.model)
        anthropic_response.model = original_model

    return JSONResponse(content=anthropic_response.to_dict())


async def _handle_anthropic_stream(
    chat_request: ChatRequest,
    anthropic_request: AnthropicMessagesRequest,
    registry: AdapterRegistry,
    fusion_engine: FusionEngine,
):
    """Handle Anthropic streaming response (SSE with typed events)."""
    message_id = f"msg_{int(time.time())}"
    original_model = chat_request.extra_body.get("_original_model", anthropic_request.model)

    async def stream_generator():
        # 1. Send Anthropic stream start events
        for start_event in anthropic_stream_start(message_id, original_model):
            yield start_event + "\n"

        if chat_request.is_fusion:
            # 2. Fusion: collect results, then stream synthesized output as Anthropic events
            response = await fusion_engine.execute(chat_request)
            content = response.choices[0].get("message", {}).get("content", "")

            # Stream content as Anthropic text deltas
            chunk_size = 20
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i + chunk_size]
                delta_event = json.dumps({
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": chunk},
                })
                yield f"event: content_block_delta\ndata: {delta_event}\n\n"

        else:
            # Passthrough streaming
            adapter = registry.get(chat_request.model)
            if adapter is None:
                yield f"event: error\ndata: {json.dumps({'type': 'error', 'error': {'type': 'not_found', 'message': f'Model {chat_request.model} not found'}})}\n\n"
                return

            model_request = ModelRequest(
                model=chat_request.model,
                messages=chat_request.messages,
                temperature=chat_request.temperature,
                max_tokens=chat_request.max_tokens or 8192,
                tools=chat_request.tools,
                stream=True,
            )

            async for chunk in adapter.stream_chat(model_request):
                delta_event = json.dumps({
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": chunk},
                })
                yield f"event: content_block_delta\ndata: {delta_event}\n\n"

        # 3. Send Anthropic stream stop events
        yield anthropic_stream_stop() + "\n"

        # message_delta with stop_reason and usage
        yield (
            f"event: message_delta\n"
            f"data: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': 0}})}\n\n"
        )
        yield "event: message_stop\ndata: {}\n\n"

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


# ──────────────────────────────────────────────
# Shared endpoints
# ──────────────────────────────────────────────

@router.get("/v1/models")
async def list_models(registry: AdapterRegistry = Depends(get_registry)):
    """List all available models (OpenAI-compatible format)."""
    models = registry.list_models()
    return {
        "object": "list",
        "data": [
            {
                "id": "fusion",
                "object": "model",
                "owned_by": "fusion-relay",
                "fusion": True,
            }
        ] + [
            {
                "id": m,
                "object": "model",
                "owned_by": "fusion-relay",
            }
            for m in models
        ],
    }


@router.get("/admin/fusion/config")
async def get_fusion_config(request: Request):
    """View current fusion configuration."""
    engine: FusionEngine = request.app.state.fusion_engine
    return {
        "strategy": "default",
        "panel": engine.config.panel,
        "judge": engine.config.judge,
        "synthesizer": engine.config.synthesizer,
        "timeout_seconds": engine.config.timeout_seconds,
        "retry_count": engine.config.retry_count,
        "fallback_model": engine.config.fallback_model,
    }


@router.put("/admin/fusion/config")
async def update_fusion_config(request: Request, registry: AdapterRegistry = Depends(get_registry)):
    """Hot-update fusion configuration."""
    body = await request.json()
    new_config = FusionConfig(
        panel=body.get("panel", []),
        judge=body.get("judge", ""),
        synthesizer=body.get("synthesizer", ""),
        timeout_seconds=body.get("timeout_seconds", 30),
        retry_count=body.get("retry_count", 2),
        fallback_model=body.get("fallback_model", ""),
    )
    request.app.state.fusion_engine = FusionEngine(registry, new_config)
    logger.info("Fusion config updated: panel=%s judge=%s synth=%s",
                new_config.panel, new_config.judge, new_config.synthesizer)
    return {"status": "ok", "message": "Fusion config updated", "config": body}


@router.get("/admin/stats")
async def get_stats(request: Request):
    """Get fusion statistics (placeholder)."""
    return {
        "total_requests": 0,
        "fusion_requests": 0,
        "passthrough_requests": 0,
        "fallback_count": 0,
        "avg_latency_ms": 0,
        "total_cost_usd": 0.0,
        "note": "Connect Prometheus for detailed metrics",
    }


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "fusion-relay", "version": "1.0.0"}
