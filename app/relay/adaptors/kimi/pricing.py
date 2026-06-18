"""Kimi (Moonshot) model pricing configuration."""
from app.relay.adaptor import ModelConfig

MODEL_PRICING: dict[str, ModelConfig] = {
    "kimi-k2.6": ModelConfig(
        input_ratio=2.6,
        output_ratio=9.0,
        cached_input_ratio=0.65,
        max_tokens=128000,
    ),
    "kimi-k2.5": ModelConfig(
        input_ratio=1.6,
        output_ratio=7.0,
        cached_input_ratio=0.4,
        max_tokens=128000,
    ),
}
