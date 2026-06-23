"""GLM (Zhipu) model pricing configuration.
Ratios match ¥/M token prices from official pricing.
"""
from app.relay.adaptor import ModelConfig

MODEL_PRICING: dict[str, ModelConfig] = {
    "glm-5.2": ModelConfig(max_tokens=131072),
    "glm-5.1": ModelConfig(max_tokens=131072),
    "glm-5": ModelConfig(max_tokens=131072),
    "glm-4.7": ModelConfig(max_tokens=131072),
    "glm-4.5-air": ModelConfig(max_tokens=131072),
    "glm-4.7-flash": ModelConfig(max_tokens=131072),
    "glm-z1-flash": ModelConfig(max_tokens=131072),
}
