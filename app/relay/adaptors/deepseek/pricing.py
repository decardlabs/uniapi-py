from __future__ import annotations

"""DeepSeek model pricing configuration."""

from app.relay.adaptor import ModelConfig

# Billing ratio constant (quota per million tokens)
# Matches Go's billingratio.MilliTokensUsd = 0.5
QUOTA_PER_MILLION_INPUT = 500000
QUOTA_PER_USD = 500000

MODEL_PRICING: dict[str, ModelConfig] = {
    "deepseek-v4-pro": ModelConfig(
        input_ratio=1.2,
        output_ratio=2.0,
        cached_input_ratio=0.12,
        max_tokens=128000,
    ),
    "deepseek-v4-flash": ModelConfig(
        input_ratio=0.3,
        output_ratio=2.0,
        cached_input_ratio=0.03,
        max_tokens=128000,
    ),
}
