"""Kimi (Moonshot) model pricing configuration.
Ratios match ¥/M token prices from official pricing.
"""
from app.relay.adaptor import ModelConfig

MODEL_PRICING: dict[str, ModelConfig] = {
    "kimi-k2.7-code": ModelConfig(max_tokens=256000),
    "kimi-k2.7-code-highspeed": ModelConfig(max_tokens=256000),
    "kimi-k2.6": ModelConfig(max_tokens=256000),
    "kimi-k2.5": ModelConfig(max_tokens=256000),
    "kimi-k2": ModelConfig(max_tokens=256000),
}
