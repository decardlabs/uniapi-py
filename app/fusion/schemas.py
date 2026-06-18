"""Data schemas for the fusion pipeline (request/response models)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UsageInfo:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    fusion_breakdown: FusionBreakdown | None = None


@dataclass
class FusionBreakdown:
    panel: dict[str, dict[str, int]] = field(default_factory=dict)
    judge_model: str = ""
    synthesizer_model: str = ""
    fallback_triggered: bool = False


@dataclass
class FusionMeta:
    panel_models: list[str] = field(default_factory=list)
    judge_model: str = ""
    synthesizer_model: str = ""
    judge_confidence: float = 0.0
    latency_ms: int = 0
    fallback_triggered: bool = False


@dataclass
class ModelRequest:
    model: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 8192
    tools: list[dict[str, Any]] | None = None
    stream: bool = False
    extra_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "model": self.model,
            "messages": self.messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.tools:
            d["tools"] = self.tools
        if self.stream:
            d["stream"] = True
        return d


@dataclass
class ModelResponse:
    model: str = ""
    content: str = ""
    reasoning: str = ""
    usage: UsageInfo = field(default_factory=UsageInfo)
    finish_reason: str = "stop"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatRequest:
    model: str = ""
    messages: list[dict[str, Any]] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int | None = None
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    extra_body: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChatRequest:
        return cls(
            model=data.get("model", ""),
            messages=data.get("messages", []),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens"),
            stream=data.get("stream", False),
            tools=data.get("tools"),
            extra_body=data.get("extra_body", {}),
        )

    @property
    def is_fusion(self) -> bool:
        return self.model.lower() == "fusion"

    @property
    def fusion_override(self) -> dict[str, Any] | None:
        return self.extra_body.get("fusion")


@dataclass
class ChatResponse:
    id: str = ""
    model: str = ""
    choices: list[dict[str, Any]] = field(default_factory=list)
    usage: UsageInfo = field(default_factory=UsageInfo)
    fusion_meta: FusionMeta | None = None

    def to_dict(self) -> dict[str, Any]:
        d = {
            "id": self.id,
            "object": "chat.completion",
            "model": self.model,
            "choices": self.choices,
            "usage": {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
                "total_tokens": self.usage.total_tokens,
            },
        }
        if self.usage.fusion_breakdown:
            d["usage"]["fusion_breakdown"] = {
                "panel": self.usage.fusion_breakdown.panel,
                "judge_model": self.usage.fusion_breakdown.judge_model,
                "synthesizer_model": self.usage.fusion_breakdown.synthesizer_model,
                "fallback_triggered": self.usage.fusion_breakdown.fallback_triggered,
            }
        if self.fusion_meta:
            d["fusion_meta"] = {
                "panel_models": self.fusion_meta.panel_models,
                "judge_model": self.fusion_meta.judge_model,
                "synthesizer_model": self.fusion_meta.synthesizer_model,
                "judge_confidence": self.fusion_meta.judge_confidence,
                "latency_ms": self.fusion_meta.latency_ms,
                "fallback_triggered": self.fusion_meta.fallback_triggered,
            }
        return d
