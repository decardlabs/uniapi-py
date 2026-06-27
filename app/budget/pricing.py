"""Real-currency pricing data and cost calculation for BudgetArbiter.

Pricing in yuan (¥) per million tokens.
Aligned with app/relay/adaptors/*/pricing.py.

Micro-yuan functions (calculate_cost_micro / estimate_cost_micro) return
Integer micro-yuan (10^-6 yuan) — the unified internal unit for all billing.
¥1.00 = 1,000,000 micro-yuan. Overdraft limit: ¥1.00 = 1,000,000 micro-yuan.
"""
from __future__ import annotations

import datetime

# Per-million-token prices in yuan (Float, for backward compat).
# These feed into calculate_cost() which rounds to 6 decimal places.
MODEL_PRICING_YUAN: dict[str, dict[str, float]] = {
    # DeepSeek
    "deepseek-v4-pro": {"input": 3.0, "output": 6.0, "cache_hit": 0.025},
    "deepseek-v4-flash": {"input": 1.0, "output": 2.0, "cache_hit": 0.02},
    # GLM
    "glm-5.2": {"input": 0, "output": 0, "cache_hit": 0},
    "glm-5.1": {"input": 10.1, "output": 31.7, "cache_hit": 2.0},
    "glm-5": {"input": 7.2, "output": 23.0, "cache_hit": 1.44},
    "glm-4.7": {"input": 4.3, "output": 15.8, "cache_hit": 0.86},
    "glm-4.5-air": {"input": 1.4, "output": 7.9, "cache_hit": 0.28},
    "glm-4.7-flash": {"input": 0, "output": 0, "cache_hit": 0},
    "glm-z1-flash": {"input": 0, "output": 0, "cache_hit": 0},
    # Qwen
    "qwen3.7-max": {"input": 12.0, "output": 36.0, "cache_hit": 2.4},
    "qwen3.7-plus": {"input": 2.0, "output": 8.0, "cache_hit": 0.4},
    "qwen3.6-plus": {"input": 2.0, "output": 12.0, "cache_hit": 0.4},
    "qwen3.6-flash": {"input": 0.5, "output": 2.0, "cache_hit": 0.1},
    "qwen3.5-plus": {"input": 0.8, "output": 4.8, "cache_hit": 0.16},
    "qwen3.5-flash": {"input": 0.35, "output": 1.4, "cache_hit": 0.07},
    "qwen3-coder-plus": {"input": 7.34, "output": 36.7, "cache_hit": 1.47},
    "qwen3-coder-flash": {"input": 2.0, "output": 8.0, "cache_hit": 0.4},
    "qwen-turbo": {"input": 0.3, "output": 1.2, "cache_hit": 0.06},
    # Kimi
    "kimi-k2.7-code": {"input": 6.5, "output": 27.0, "cache_hit": 1.3},
    "kimi-k2.7-code-highspeed": {"input": 13.0, "output": 54.0, "cache_hit": 2.6},
    "kimi-k2.6": {"input": 6.5, "output": 27.0, "cache_hit": 1.1},
    "kimi-k2.5": {"input": 4.0, "output": 21.0, "cache_hit": 0.7},
    "kimi-k2": {"input": 2.0, "output": 10.0, "cache_hit": 0.4},
    # MiniMax
    "MiniMax-M3": {"input": 2.16, "output": 8.64, "cache_hit": 0.43},
    "MiniMax-M2.7": {"input": 2.16, "output": 8.64, "cache_hit": 0.43},
    "MiniMax-M2.7-highspeed": {"input": 4.32, "output": 17.28, "cache_hit": 0.43},
    "MiniMax-M2.5": {"input": 2.16, "output": 8.64, "cache_hit": 0.22},
    "MiniMax-M2.5-highspeed": {"input": 4.32, "output": 17.28, "cache_hit": 0.22},
    "MiniMax-M2.1": {"input": 2.16, "output": 8.64, "cache_hit": 0.22},
    "MiniMax-M2.1-highspeed": {"input": 4.32, "output": 17.28, "cache_hit": 0.22},
    "MiniMax-M2": {"input": 2.16, "output": 8.64, "cache_hit": 0.22},
}

# Backwards-compatible lowercase aliases
_MODEL_ALIASES: dict[str, dict[str, float]] = {}
for _name in list(MODEL_PRICING_YUAN.keys()):
    _lower = _name.lower()
    if _lower != _name:
        _MODEL_ALIASES[_lower] = MODEL_PRICING_YUAN[_name]
MODEL_PRICING_YUAN.update(_MODEL_ALIASES)

# Safety margin for cost estimation (20% buffer)
PRICING_SAFETY_MARGIN = 1.2


def get_model_pricing(
    model_name: str,
    channel_model_configs: dict | None = None,
) -> dict[str, float]:
    """Get pricing dict for a model.

    Channel-level ``channel_model_configs`` (parsed from the channel's
    ``model_configs`` JSON field) take precedence over the global
    ``MODEL_PRICING_YUAN`` table.

    The override dict format per model::

        {"input_price": 1.0, "output_price": 2.0, "cache_hit_price": 0.02}

    Legacy field names ``ratio`` / ``completion_ratio`` / ``cached_input_price``
    are also accepted for backward compatibility with the default-pricing API.

    ``cache_hit_price`` (or ``cached_input_price``) defaults to 0 when not
    explicitly set in an override.

    Raises ``KeyError`` when no pricing source covers the model.
    """
    # 1. Channel-level override (if provided and model is present)
    if channel_model_configs and model_name in channel_model_configs:
        ov = channel_model_configs[model_name]
        return {
            "input": ov.get("input_price") or ov.get("ratio", 0),
            "output": ov.get("output_price") or ov.get("completion_ratio", 0),
            "cache_hit": ov.get("cache_hit_price") or ov.get("cached_input_price", 0),
        }

    # 2. Fall back to global pricing
    if not model_name or not model_name.strip():
        raise KeyError(f"Unknown model: {model_name!r} (empty model name)")
    if model_name not in MODEL_PRICING_YUAN:
        raise KeyError(f"Unknown model: {model_name}")
    return MODEL_PRICING_YUAN[model_name]


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_hit_tokens: int = 0,
    channel_model_configs: dict | None = None,
) -> float:
    """Calculate actual cost in yuan for a completed request.

    cache_hit_tokens is a subset of input_tokens (not additive).
    Pass ``channel_model_configs`` to use channel-level pricing overrides.
    """
    pricing = get_model_pricing(model, channel_model_configs=channel_model_configs)
    input_miss = input_tokens - cache_hit_tokens

    cost = (
        (input_miss / 1_000_000) * pricing["input"]
        + (cache_hit_tokens / 1_000_000) * pricing["cache_hit"]
        + (output_tokens / 1_000_000) * pricing["output"]
    )
    return round(cost, 6)


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int = 1000,
    channel_model_configs: dict | None = None,
) -> float:
    """Conservative cost estimate for pre-check (includes safety margin).

    Pass ``channel_model_configs`` to use channel-level pricing overrides.
    """
    pricing = get_model_pricing(model, channel_model_configs=channel_model_configs)
    base = (
        (input_tokens / 1_000_000) * pricing["input"]
        + (output_tokens / 1_000_000) * pricing["output"]
    )
    return round(base * PRICING_SAFETY_MARGIN, 6)


# ── Micro-yuan variants (Integer, unified billing unit) ────────────────
# 1 micro-yuan = 10^-6 yuan. ¥1.00 = 1,000,000 micro-yuan.
# Used by relay.py as the PRIMARY cost unit, replacing ModelConfig ratios.

def calculate_cost_micro(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_hit_tokens: int = 0,
    channel_model_configs: dict | None = None,
) -> int:
    """Calculate actual cost in micro-yuan (Integer).

    Delegates to calculate_cost() to avoid duplicating the formula.
    Pass ``channel_model_configs`` to use channel-level pricing overrides.
    """
    yuan = calculate_cost(
        model, input_tokens, output_tokens, cache_hit_tokens,
        channel_model_configs=channel_model_configs,
    )
    return max(1, int(round(yuan * 1_000_000)))


def estimate_cost_micro(
    model: str,
    input_tokens: int,
    output_tokens: int = 1000,
    channel_model_configs: dict | None = None,
) -> int:
    """Conservative cost estimate in micro-yuan (includes 20% safety margin).

    Delegates to estimate_cost() to avoid duplicating the formula.
    Pass ``channel_model_configs`` to use channel-level pricing overrides.
    """
    yuan = estimate_cost(model, input_tokens, output_tokens, channel_model_configs=channel_model_configs)
    return max(1, int(round(yuan * 1_000_000)))


# Default overdraft in micro-yuan: ¥1.00
MAX_OVERDRAFT_MICRO = 1_000_000


def compute_period() -> str:
    """Return current budget period as 'YYYY-MM'."""
    now = datetime.datetime.now(datetime.UTC)
    return f"{now.year}-{now.month:02d}"
