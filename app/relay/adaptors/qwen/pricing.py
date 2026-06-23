"""Qwen (百炼) model pricing configuration.
Ratios match ¥/M token prices from official pricing.
"""
from app.relay.adaptor import ModelConfig

MODEL_PRICING: dict[str, ModelConfig] = {
    "qwen3.7-max": ModelConfig(max_tokens=128000),
    "qwen3.7-plus": ModelConfig(max_tokens=128000),
    "qwen3.6-plus": ModelConfig(max_tokens=128000),
    "qwen3.6-flash": ModelConfig(max_tokens=128000),
    "qwen3.5-plus": ModelConfig(max_tokens=128000),
    "qwen3.5-flash": ModelConfig(max_tokens=128000),
    "qwen3-coder-plus": ModelConfig(max_tokens=128000),
    "qwen3-coder-flash": ModelConfig(max_tokens=128000),
    "qwen-turbo": ModelConfig(max_tokens=128000),
}
