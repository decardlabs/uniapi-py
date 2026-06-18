"""MiniMax model pricing configuration."""
from app.relay.adaptor import ModelConfig

MODEL_PRICING: dict[str, ModelConfig] = {
    "MiniMax-M3": ModelConfig(
        input_ratio=0.86,
        output_ratio=2.88,
        cached_input_ratio=0.22,
        max_tokens=128000,
    ),
    "MiniMax-M2.7": ModelConfig(
        input_ratio=0.86,
        output_ratio=2.88,
        cached_input_ratio=0.22,
        max_tokens=128000,
    ),
    "MiniMax-M2.7-highspeed": ModelConfig(
        input_ratio=1.72,
        output_ratio=5.76,
        cached_input_ratio=0.22,
        max_tokens=128000,
    ),
    "MiniMax-M2.5": ModelConfig(
        input_ratio=0.86,
        output_ratio=2.88,
        cached_input_ratio=0.22,
        max_tokens=128000,
    ),
    "MiniMax-M2.5-highspeed": ModelConfig(
        input_ratio=1.72,
        output_ratio=5.76,
        cached_input_ratio=0.22,
        max_tokens=128000,
    ),
    "MiniMax-M2.1": ModelConfig(
        input_ratio=0.86,
        output_ratio=2.88,
        cached_input_ratio=0.22,
        max_tokens=128000,
    ),
    "MiniMax-M2.1-highspeed": ModelConfig(
        input_ratio=1.72,
        output_ratio=5.76,
        cached_input_ratio=0.22,
        max_tokens=128000,
    ),
    "MiniMax-M2": ModelConfig(
        input_ratio=0.86,
        output_ratio=2.88,
        cached_input_ratio=0.22,
        max_tokens=128000,
    ),
}

# Backwards-compatible lowercase aliases
_MODEL_ALIASES: dict[str, ModelConfig] = {}
for _name in list(MODEL_PRICING.keys()):
    _lower = _name.lower()
    if _lower != _name:
        _MODEL_ALIASES[_lower] = MODEL_PRICING[_name]
MODEL_PRICING.update(_MODEL_ALIASES)
