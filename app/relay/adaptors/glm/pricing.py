"""GLM (Zhipu) model pricing configuration."""
from app.relay.adaptor import ModelConfig

MODEL_PRICING: dict[str, ModelConfig] = {
    "glm-5.2": ModelConfig(
        input_ratio=0.6,
        output_ratio=5.0,
        cached_input_ratio=0.1,
        max_tokens=131072,
    ),
    "glm-5.1": ModelConfig(
        input_ratio=0.15,
        output_ratio=5.0,
        cached_input_ratio=0.03,
        max_tokens=131072,
    ),
    "glm-5": ModelConfig(
        input_ratio=0.15,
        output_ratio=5.0,
        cached_input_ratio=0.03,
        max_tokens=131072,
    ),
    "glm-4.7": ModelConfig(
        input_ratio=0.1,
        output_ratio=3.0,
        cached_input_ratio=0.02,
        max_tokens=131072,
    ),
    "glm-4.5-air": ModelConfig(
        input_ratio=0.033,
        output_ratio=1.5,
        cached_input_ratio=0.007,
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
