"""Qwen (百炼) model pricing configuration."""
from app.relay.adaptor import ModelConfig

MODEL_PRICING: dict[str, ModelConfig] = {
    "qwen3.7-max": ModelConfig(
        input_ratio=4.8,
        output_ratio=12.0,
        cached_input_ratio=1.2,
        max_tokens=128000,
    ),
    "qwen3.7-plus": ModelConfig(
        input_ratio=0.8,
        output_ratio=2.7,
        cached_input_ratio=0.2,
        max_tokens=128000,
    ),
    "qwen3-coder-plus": ModelConfig(
        input_ratio=2.9,
        output_ratio=12.2,
        cached_input_ratio=0.7,
        max_tokens=128000,
    ),
    "qwen3-coder-flash": ModelConfig(
        input_ratio=0.2,
        output_ratio=0.7,
        cached_input_ratio=0.05,
        max_tokens=128000,
    ),
}
