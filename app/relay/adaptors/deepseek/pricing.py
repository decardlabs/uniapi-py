"""DeepSeek model pricing configuration.
Ratios match ¥/M token prices from official pricing.
"""
from app.relay.adaptor import ModelConfig

MODEL_PRICING: dict[str, ModelConfig] = {
    "deepseek-v4-pro": ModelConfig(
        input_ratio=3.0,
        output_ratio=6.0,
        cached_input_ratio=0.025,
        max_tokens=384000,
    ),
    "deepseek-v4-flash": ModelConfig(
        input_ratio=1.0,
        output_ratio=2.0,
        cached_input_ratio=0.02,
        max_tokens=384000,
    ),
}
