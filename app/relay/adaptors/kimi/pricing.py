"""Kimi (Moonshot) model pricing configuration.
Ratios match ¥/M token prices from official pricing.
"""
from app.relay.adaptor import ModelConfig

MODEL_PRICING: dict[str, ModelConfig] = {
    "kimi-k2.7-code": ModelConfig(
        input_ratio=6.5,
        output_ratio=27.0,
        cached_input_ratio=1.3,
        max_tokens=256000,
    ),
    "kimi-k2.7-code-highspeed": ModelConfig(
        input_ratio=13.0,
        output_ratio=54.0,
        cached_input_ratio=2.6,
        max_tokens=256000,
    ),
    "kimi-k2.6": ModelConfig(
        input_ratio=6.5,
        output_ratio=27.0,
        cached_input_ratio=1.1,
        max_tokens=256000,
    ),
    "kimi-k2.5": ModelConfig(
        input_ratio=4.0,
        output_ratio=21.0,
        cached_input_ratio=0.7,
        max_tokens=256000,
    ),
    "kimi-k2": ModelConfig(
        input_ratio=2.0,
        output_ratio=10.0,
        cached_input_ratio=0.4,
        max_tokens=256000,
    ),
}
