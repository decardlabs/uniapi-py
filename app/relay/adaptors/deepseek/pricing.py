"""DeepSeek model pricing configuration.
Ratios match ¥/M token prices from official pricing.
"""
from app.relay.adaptor import ModelConfig

MODEL_PRICING: dict[str, ModelConfig] = {
    "deepseek-v4-pro": ModelConfig(max_tokens=384000),
    "deepseek-v4-flash": ModelConfig(max_tokens=384000),
}
