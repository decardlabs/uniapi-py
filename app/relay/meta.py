from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RelayMeta:
    mode: int = 0
    channel_type: int = 0
    channel_id: int = 0
    token_id: int = 0
    token_name: str = ""
    user_id: int = 0
    group: str = "default"
    model_mapping: dict[str, str] = field(default_factory=dict)
    base_url: str = ""
    api_key: str = ""
    api_type: int = 0
    is_stream: bool = False
    origin_model_name: str = ""
    actual_model_name: str = ""
    request_url_path: str = ""
    prompt_tokens: int = 0
