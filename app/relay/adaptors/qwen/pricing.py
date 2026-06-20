"""Qwen (百炼) model pricing configuration.
Ratios match ¥/M token prices from official pricing.
"""
from app.relay.adaptor import ModelConfig

MODEL_PRICING: dict[str, ModelConfig] = {
    "qwen3.7-max": ModelConfig(
        input_ratio=12.0,
        output_ratio=36.0,
        cached_input_ratio=2.4,
        max_tokens=128000,
    ),
    "qwen3.7-plus": ModelConfig(
        input_ratio=2.0,
        output_ratio=8.0,
        cached_input_ratio=0.4,
        max_tokens=128000,
    ),
    "qwen3.6-plus": ModelConfig(
        input_ratio=2.0,
        output_ratio=12.0,
        cached_input_ratio=0.4,
        max_tokens=128000,
    ),
    "qwen3.6-flash": ModelConfig(
        input_ratio=0.5,
        output_ratio=2.0,
        cached_input_ratio=0.1,
        max_tokens=128000,
    ),
    "qwen3.5-plus": ModelConfig(
        input_ratio=0.8,
        output_ratio=4.8,
        cached_input_ratio=0.16,
        max_tokens=128000,
    ),
    "qwen3.5-flash": ModelConfig(
        input_ratio=0.35,
        output_ratio=1.4,
        cached_input_ratio=0.07,
        max_tokens=128000,
    ),
    "qwen3-coder-plus": ModelConfig(
        input_ratio=7.34,
        output_ratio=36.70,
        cached_input_ratio=1.47,
        max_tokens=128000,
    ),
    "qwen3-coder-flash": ModelConfig(
        input_ratio=2.0,
        output_ratio=8.0,
        cached_input_ratio=0.4,
        max_tokens=128000,
    ),
    "qwen-turbo": ModelConfig(
        input_ratio=0.3,
        output_ratio=1.2,
        cached_input_ratio=0.06,
        max_tokens=128000,
    ),
}
