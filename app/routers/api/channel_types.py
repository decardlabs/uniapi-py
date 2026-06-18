from __future__ import annotations

from fastapi import APIRouter
from app.schemas.common import GenericApiResponse

router = APIRouter(tags=["channel-types"])


@router.get("/api/channel/types")
async def get_channel_types():
    """Return available channel type definitions - used by frontend for dynamic form."""
    from app.relay.adaptors.deepseek.adaptor import DEEPSEEK_CHANNEL_TYPE, DeepSeekAdaptor
    from app.relay.registry import registry

    types = []

    # Return all registered adaptor types
    adaptors = registry.all_adaptors()
    for adp in adaptors:
        models = list(adp.get_supported_models().keys())
        types.append({
            "key": adp.provider_name,
            "text": adp.provider_name.title(),
            "value": DEEPSEEK_CHANNEL_TYPE if adp.provider_name == "deepseek" else 0,
            "models": models,
        })

    # Always include DeepSeek
    if not any(t["key"] == "deepseek" for t in types):
        types.append({
            "key": "deepseek",
            "text": "DeepSeek",
            "value": DEEPSEEK_CHANNEL_TYPE,
            "models": list(DeepSeekAdaptor().get_supported_models().keys()),
        })

    return GenericApiResponse(data=types)
