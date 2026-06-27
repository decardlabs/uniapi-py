"""Channel type and metadata API endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.common import GenericApiResponse

router = APIRouter(tags=["channel-types"])

# Known provider metadata for all supported channel types
_PROVIDER_META: dict[int, dict] = {
    39: {
        "name": "DeepSeek",
        "default_base_url": "https://api.deepseek.com/v1",
        "anthropic_base_url": "https://api.deepseek.com/anthropic",
        "base_url_editable": True,
        "capabilities": ["chat_completions", "claude_messages"],
    },
    41: {
        "name": "GLM (Zhipu)",
        "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
        "anthropic_base_url": "https://open.bigmodel.cn/api/anthropic",
        "base_url_editable": True,
        "capabilities": ["chat_completions", "claude_messages"],
    },
    50: {
        "name": "Qwen (AliBailian)",
        "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "anthropic_base_url": "https://dashscope.aliyuncs.com/apps/anthropic",
        "base_url_editable": True,
        "capabilities": ["chat_completions", "claude_messages"],
    },
    25: {
        "name": "Kimi (Moonshot)",
        "default_base_url": "https://api.moonshot.cn/v1",
        "anthropic_base_url": "https://api.moonshot.cn/anthropic",
        "base_url_editable": True,
        "capabilities": ["chat_completions", "claude_messages"],
    },
    27: {
        "name": "MiniMax",
        "default_base_url": "https://api.minimaxi.com/v1",
        "anthropic_base_url": "https://api.minimaxi.com/anthropic",
        "base_url_editable": True,
        "capabilities": ["chat_completions", "claude_messages"],
    },
}


def _get_channel_value(adp) -> int:
    if hasattr(adp, "get_channel_type"):
        return adp.get_channel_type()
    return 0


@router.get("/api/channel/types")
async def get_channel_types():
    """Return available channel type definitions with default base URLs."""
    from app.relay.registry import registry

    types = []
    adaptors = registry.all_adaptors()
    for adp in adaptors:
        channel_value = _get_channel_value(adp)
        meta = _PROVIDER_META.get(channel_value, {})
        models = list(adp.get_supported_models().keys())
        types.append({
            "key": adp.provider_name,
            "text": meta.get("name", adp.provider_name.title()),
            "value": channel_value,
            "models": models,
            "default_base_url": meta.get("default_base_url", adp.DEFAULT_BASE_URL),
        })

    return GenericApiResponse(data=types)


@router.get("/api/channel/metadata")
async def channel_metadata(type: int = Query(0, alias="type")):
    """Return metadata (default base URL, models, capabilities) for a channel type."""
    from app.relay.registry import registry

    adaptor = registry.get(type)
    meta = _PROVIDER_META.get(type, {})
    models = list(adaptor.get_supported_models().keys()) if adaptor else []
    default_base_url = meta.get("default_base_url", adaptor.DEFAULT_BASE_URL if adaptor else "")

    return GenericApiResponse(data={
        "type": type,
        "default_base_url": default_base_url,
        "base_url_editable": meta.get("base_url_editable", True),
        "capabilities": meta.get("capabilities", ["chat_completions", "claude_messages"]),
        "default_endpoints": [default_base_url] if default_base_url else [],
        "models": models,
    })
