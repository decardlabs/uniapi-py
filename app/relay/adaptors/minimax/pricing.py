"""MiniMax model pricing configuration.
Ratios match ¥/M token prices (at 7.2 CNY/USD).
"""
from app.relay.adaptor import ModelConfig

MODEL_PRICING: dict[str, ModelConfig] = {
    "MiniMax-M3": ModelConfig(max_tokens=128000),
    "MiniMax-M2.7": ModelConfig(max_tokens=128000),
    "MiniMax-M2.7-highspeed": ModelConfig(max_tokens=128000),
    "MiniMax-M2.5": ModelConfig(max_tokens=128000),
    "MiniMax-M2.5-highspeed": ModelConfig(max_tokens=128000),
    "MiniMax-M2.1": ModelConfig(max_tokens=128000),
    "MiniMax-M2.1-highspeed": ModelConfig(max_tokens=128000),
    "MiniMax-M2": ModelConfig(max_tokens=128000),
}

# Backwards-compatible lowercase aliases (used for model resolution, not for listing)
MODEL_ALIASES: dict[str, str] = {}
for _name in list(MODEL_PRICING.keys()):
    _lower = _name.lower()
    if _lower != _name:
        MODEL_ALIASES[_lower] = _name
