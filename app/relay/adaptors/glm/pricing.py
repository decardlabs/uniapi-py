"""GLM (Zhipu) model pricing configuration.
Ratios match ¥/M token prices from official pricing.
"""
from app.relay.adaptor import ModelConfig

MODEL_PRICING: dict[str, ModelConfig] = {
    "glm-5.2": ModelConfig(
        input_ratio=0,
        output_ratio=0,
        cached_input_ratio=0,
        max_tokens=131072,
    ),
    "glm-5.1": ModelConfig(
        input_ratio=10.1,
        output_ratio=31.7,
        cached_input_ratio=2.0,
        max_tokens=131072,
    ),
    "glm-5": ModelConfig(
        input_ratio=7.2,
        output_ratio=23.0,
        cached_input_ratio=1.44,
        max_tokens=131072,
    ),
    "glm-4.7": ModelConfig(
        input_ratio=4.3,
        output_ratio=15.8,
        cached_input_ratio=0.86,
        max_tokens=131072,
    ),
    "glm-4.5-air": ModelConfig(
        input_ratio=1.4,
        output_ratio=7.9,
        cached_input_ratio=0.28,
        max_tokens=131072,
    ),
    "glm-4.7-flash": ModelConfig(
        input_ratio=0,
        output_ratio=0,
        cached_input_ratio=0,
        max_tokens=131072,
    ),
    "glm-z1-flash": ModelConfig(
        input_ratio=0,
        output_ratio=0,
        cached_input_ratio=0,
        max_tokens=131072,
    ),
}
