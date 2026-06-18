from __future__ import annotations

from fastapi import APIRouter
from app.schemas.common import GenericApiResponse

router = APIRouter(tags=["channel-types"])


def _get_channel_value(adp) -> int:
    """Attempt to get channel type constant from adaptor."""
    if hasattr(adp, "get_channel_type"):
        return adp.get_channel_type()
    return 0


@router.get("/api/channel/types")
async def get_channel_types():
    """Return available channel type definitions - used by frontend for dynamic form."""
    from app.relay.registry import registry

    types = []
    adaptors = registry.all_adaptors()
    for adp in adaptors:
        models = list(adp.get_supported_models().keys())
        types.append({
            "key": adp.provider_name,
            "text": adp.provider_name.title(),
            "value": _get_channel_value(adp),
            "models": models,
        })

    return GenericApiResponse(data=types)
