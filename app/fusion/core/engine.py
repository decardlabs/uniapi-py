"""Fusion engine: Panel → Judge → Synthesizer pipeline orchestration."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.fusion.adapters.registry import AdapterRegistry
from app.fusion.core.judge import JudgeModule
from app.fusion.core.synthesizer import SynthesizerModule
from app.fusion.schemas import (
    ChatRequest,
    ChatResponse,
    FusionBreakdown,
    FusionMeta,
    ModelRequest,
    ModelResponse,
    UsageInfo,
)

logger = logging.getLogger(__name__)


@dataclass
class FusionConfig:
    panel: list[str] = field(default_factory=list)
    judge: str = ""
    synthesizer: str = ""
    timeout_seconds: int = 30
    retry_count: int = 2
    fallback_model: str = ""
    max_tokens: int = 8192
    temperature: float = 0.7


class FusionEngine:
    def __init__(self, registry: AdapterRegistry, config: FusionConfig):
        self.registry = registry
        self.config = config
        self.judge = JudgeModule(registry, config.judge)
        self.synthesizer = SynthesizerModule(registry, config.synthesizer)

    async def execute(self, request: ChatRequest) -> ChatResponse:
        start_time = time.monotonic()
        request_id = f"fuse-{int(start_time * 1000) % 1000000:06d}"

        try:
            panel_responses = await self._dispatch_panel(request, request_id)
            valid = [r for r in panel_responses if r is not None]

            if len(valid) == 0:
                return await self._fallback(request, request_id, start_time)
            if len(valid) == 1:
                return self._build_response(request_id, valid[0], panel_responses, None, start_time)

            judge_analysis = await self.judge.analyze(original_prompt=request, panel_responses=valid)
            final_response = await self.synthesizer.synthesize(
                original_prompt=request, panel_responses=valid, judge_analysis=judge_analysis,
            )
            return self._build_response(request_id, final_response, panel_responses, judge_analysis, start_time)

        except Exception as e:
            logger.error("Fusion pipeline failed: %s", e, exc_info=True)
            return await self._fallback(request, request_id, start_time)

    async def _dispatch_panel(self, request: ChatRequest, request_id: str) -> list[ModelResponse | None]:
        tasks = []
        for model_id in self.config.panel:
            adapter = self.registry.get(model_id)
            if adapter is None:
                tasks.append(asyncio.sleep(0, result=None))
                continue
            model_request = ModelRequest(
                model=model_id,
                messages=request.messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                tools=request.tools,
                stream=False,
            )
            tasks.append(self._call_with_retry(adapter, model_request, model_id))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        panel_responses = []
        for model_id, result in zip(self.config.panel, results):
            if isinstance(result, Exception):
                logger.error("Panel model %s failed: %s", model_id, result)
                panel_responses.append(None)
            else:
                panel_responses.append(result)
        return panel_responses

    async def _call_with_retry(self, adapter: Any, model_request: ModelRequest, model_id: str) -> ModelResponse | None:
        for attempt in range(self.config.retry_count + 1):
            try:
                response = await asyncio.wait_for(adapter.chat(model_request), timeout=self.config.timeout_seconds)
                return response
            except asyncio.TimeoutError:
                logger.warning("Model %s timeout (attempt %d/%d)", model_id, attempt + 1, self.config.retry_count + 1)
            except Exception as e:
                logger.warning("Model %s error (attempt %d/%d): %s", model_id, attempt + 1, self.config.retry_count + 1, e)
        return None

    async def _fallback(self, request: ChatRequest, request_id: str, start_time: float) -> ChatResponse:
        fallback_model = self.config.fallback_model or self.config.panel[0]
        adapter = self.registry.get(fallback_model)
        if adapter is None:
            return ChatResponse(
                id=request_id, model=fallback_model,
                choices=[{"index": 0, "message": {"role": "assistant", "content": f"All models unavailable. Fallback '{fallback_model}' not found."}, "finish_reason": "error"}],
                usage=UsageInfo(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                fusion_meta=FusionMeta(panel_models=self.config.panel, judge_model="", synthesizer_model="", judge_confidence=0.0, latency_ms=int((time.monotonic() - start_time) * 1000), fallback_triggered=True),
            )

        model_request = ModelRequest(model=fallback_model, messages=request.messages, temperature=self.config.temperature, max_tokens=self.config.max_tokens, stream=False)
        try:
            response = await adapter.chat(model_request)
        except Exception:
            return self._error_response(request_id, fallback_model, start_time)
        return self._build_response(request_id, response, [], None, start_time, fallback=True)

    def _error_response(self, request_id, model, start_time):
        return ChatResponse(
            id=request_id, model=model,
            choices=[{"index": 0, "message": {"role": "assistant", "content": f"All models unavailable, including fallback '{model}'."}, "finish_reason": "error"}],
            usage=UsageInfo(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            fusion_meta=FusionMeta(
                panel_models=self.config.panel, judge_model="", synthesizer_model="",
                judge_confidence=0.0, latency_ms=int((time.monotonic() - start_time) * 1000),
                fallback_triggered=True,
            ),
        )

    def _build_response(self, request_id: str, final: ModelResponse, panel_responses: list[ModelResponse | None], judge_analysis: dict | None, start_time: float, fallback: bool = False) -> ChatResponse:
        latency_ms = int((time.monotonic() - start_time) * 1000)
        # Save synth-only tokens BEFORE aggregation (used for billing, not double-counted)
        synth_prompt = final.usage.prompt_tokens
        synth_completion = final.usage.completion_tokens
        total_prompt = synth_prompt
        total_completion = synth_completion
        breakdown = {}
        for model_id, resp in zip(self.config.panel, panel_responses):
            if resp is not None:
                total_prompt += resp.usage.prompt_tokens
                total_completion += resp.usage.completion_tokens
                breakdown[model_id] = {"prompt_tokens": resp.usage.prompt_tokens, "completion_tokens": resp.usage.completion_tokens}

        judge_prompt = 0
        judge_completion = 0
        if judge_analysis:
            total_prompt += judge_analysis.get("usage", {}).get("prompt_tokens", 0)
            total_completion += judge_analysis.get("usage", {}).get("completion_tokens", 0)
            judge_prompt = judge_analysis["usage"].get("prompt_tokens", 0)
            judge_completion = judge_analysis["usage"].get("completion_tokens", 0)
            confidence = judge_analysis.get("confidence", 0.0)
        else:
            confidence = 0.0

        return ChatResponse(
            id=request_id, model="fusion",
            choices=[{"index": 0, "message": {"role": "assistant", "content": final.content}, "finish_reason": "stop"}],
            usage=UsageInfo(
                prompt_tokens=total_prompt, completion_tokens=total_completion, total_tokens=total_prompt + total_completion,
                fusion_breakdown=FusionBreakdown(panel=breakdown, judge_model=self.config.judge, synthesizer_model=self.config.synthesizer, fallback_triggered=fallback),
            ),
            fusion_meta=FusionMeta(panel_models=self.config.panel, judge_model=self.config.judge if judge_analysis else "", synthesizer_model=self.config.synthesizer, judge_confidence=confidence, latency_ms=latency_ms, fallback_triggered=fallback, judge_prompt_tokens=judge_prompt, judge_completion_tokens=judge_completion, synth_prompt_tokens=synth_prompt, synth_completion_tokens=synth_completion),
        )
