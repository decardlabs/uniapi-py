# Core orchestration: Panel -> Judge -> Synthesizer
# Reference: agentfw fusion pipeline + OpenRouter Fusion architecture

import asyncio
import time
import logging
from typing import Any
from dataclasses import dataclass, field

from src.adapters.registry import AdapterRegistry
from src.models.schemas import (
    ChatRequest,
    ChatResponse,
    ModelRequest,
    ModelResponse,
    FusionMeta,
    FusionBreakdown,
    UsageInfo,
)
from src.core.judge import JudgeModule
from src.core.synthesizer import SynthesizerModule

logger = logging.getLogger(__name__)


@dataclass
class FusionConfig:
    """Fusion strategy config loaded from fusion.yaml"""
    panel: list[str]
    judge: str
    synthesizer: str
    timeout_seconds: int = 30
    retry_count: int = 2
    fallback_model: str = ""
    max_tokens: int = 8192
    temperature: float = 0.7


class FusionEngine:
    """
    Core orchestration engine.

    Pipeline:
      1. Request Cloner   -> replicate request for each panel model
      2. Parallel Dispatch -> asyncio.gather to all panel models
      3. Judge            -> structured analysis (consensus/contradictions/gaps)
      4. Synthesizer      -> merge into final OpenAI-compatible response

    If any step fails catastrophically, falls back to single-model passthrough.
    """

    def __init__(
        self,
        registry: AdapterRegistry,
        config: FusionConfig,
    ):
        self.registry = registry
        self.config = config
        self.judge = JudgeModule(registry, config.judge)
        self.synthesizer = SynthesizerModule(registry, config.synthesizer)

    async def execute(self, request: ChatRequest) -> ChatResponse:
        """Main entry: run the full fusion pipeline."""
        start_time = time.monotonic()
        request_id = f"fuse-{int(start_time * 1000) % 1000000:06d}"

        logger.info(
            "Fusion started | id=%s | panel=%s | judge=%s | synth=%s",
            request_id,
            self.config.panel,
            self.config.judge,
            self.config.synthesizer,
        )

        try:
            # Step 1+2: Clone & dispatch in parallel
            panel_responses = await self._dispatch_panel(request, request_id)

            # If only 1 panel model responded, skip judge and return directly
            valid = [r for r in panel_responses if r is not None]
            if len(valid) == 0:
                logger.error("All panel models failed, falling back")
                return await self._fallback(request, request_id, start_time)

            if len(valid) == 1:
                logger.info("Only 1 panel model succeeded, returning directly")
                return self._build_response(
                    request_id, valid[0], panel_responses, None, start_time
                )

            # Step 3: Judge — structured analysis
            judge_analysis = await self.judge.analyze(
                original_prompt=request,
                panel_responses=valid,
            )

            # Step 4: Synthesizer — merge into final answer
            final_response = await self.synthesizer.synthesize(
                original_prompt=request,
                panel_responses=valid,
                judge_analysis=judge_analysis,
            )

            return self._build_response(
                request_id, final_response, panel_responses, judge_analysis, start_time
            )

        except Exception as e:
            logger.error("Fusion pipeline failed: %s", e, exc_info=True)
            return await self._fallback(request, request_id, start_time)

    async def _dispatch_panel(
        self, request: ChatRequest, request_id: str
    ) -> list[ModelResponse | None]:
        """Clone request and dispatch to all panel models in parallel."""
        tasks = []
        for model_id in self.config.panel:
            adapter = self.registry.get(model_id)
            if adapter is None:
                logger.warning("No adapter for model %s, skipping", model_id)
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

        panel_responses: list[ModelResponse | None] = []
        for model_id, result in zip(self.config.panel, results):
            if isinstance(result, Exception):
                logger.error("Panel model %s failed: %s", model_id, result)
                panel_responses.append(None)
            else:
                panel_responses.append(result)

        return panel_responses

    async def _call_with_retry(
        self,
        adapter: Any,
        model_request: ModelRequest,
        model_id: str,
    ) -> ModelResponse | None:
        """Call a model adapter with retry + timeout."""
        for attempt in range(self.config.retry_count + 1):
            try:
                response = await asyncio.wait_for(
                    adapter.chat(model_request),
                    timeout=self.config.timeout_seconds,
                )
                return response
            except asyncio.TimeoutError:
                logger.warning(
                    "Model %s timeout (attempt %d/%d)",
                    model_id,
                    attempt + 1,
                    self.config.retry_count + 1,
                )
            except Exception as e:
                logger.warning(
                    "Model %s error (attempt %d/%d): %s",
                    model_id,
                    attempt + 1,
                    self.config.retry_count + 1,
                    e,
                )

        logger.error("Model %s exhausted retries", model_id)
        return None

    async def _fallback(
        self, request: ChatRequest, request_id: str, start_time: float
    ) -> ChatResponse:
        """Fallback to single-model passthrough when fusion fails."""
        fallback_model = self.config.fallback_model or self.config.panel[0]
        logger.warning("Falling back to single model: %s", fallback_model)

        adapter = self.registry.get(fallback_model)
        if adapter is None:
            # Last resort: return an error response
            return ChatResponse(
                id=request_id,
                model=fallback_model,
                choices=[{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"[Fusion Relay] All models unavailable. Fallback model '{fallback_model}' not found.",
                    },
                    "finish_reason": "error",
                }],
                usage=UsageInfo(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                fusion_meta=FusionMeta(
                    panel_models=self.config.panel,
                    judge_model="",
                    synthesizer_model="",
                    judge_confidence=0.0,
                    latency_ms=int((time.monotonic() - start_time) * 1000),
                    fallback_triggered=True,
                ),
            )

        model_request = ModelRequest(
            model=fallback_model,
            messages=request.messages,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            stream=False,
        )
        response = await adapter.chat(model_request)

        return self._build_response(
            request_id, response, [response], None, start_time, fallback=True
        )

    def _build_response(
        self,
        request_id: str,
        final: ModelResponse,
        panel_responses: list[ModelResponse | None],
        judge_analysis: dict | None,
        start_time: float,
        fallback: bool = False,
    ) -> ChatResponse:
        """Build the final OpenAI-compatible response with fusion metadata."""
        latency_ms = int((time.monotonic() - start_time) * 1000)

        # Calculate total usage
        total_prompt = final.usage.prompt_tokens
        total_completion = final.usage.completion_tokens
        breakdown = {}
        for model_id, resp in zip(self.config.panel, panel_responses):
            if resp is not None:
                total_prompt += resp.usage.prompt_tokens
                total_completion += resp.usage.completion_tokens
                breakdown[model_id] = {
                    "prompt_tokens": resp.usage.prompt_tokens,
                    "completion_tokens": resp.usage.completion_tokens,
                }

        if judge_analysis:
            total_prompt += judge_analysis.get("usage", {}).get("prompt_tokens", 0)
            total_completion += judge_analysis.get("usage", {}).get("completion_tokens", 0)

        confidence = 0.0
        if judge_analysis and "confidence" in judge_analysis:
            confidence = judge_analysis["confidence"]

        return ChatResponse(
            id=request_id,
            model="fusion",
            choices=[{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": final.content,
                },
                "finish_reason": "stop",
            }],
            usage=UsageInfo(
                prompt_tokens=total_prompt,
                completion_tokens=total_completion,
                total_tokens=total_prompt + total_completion,
                fusion_breakdown=FusionBreakdown(
                    panel=breakdown,
                    judge_model=self.config.judge,
                    synthesizer_model=self.config.synthesizer,
                    fallback_triggered=fallback,
                ),
            ),
            fusion_meta=FusionMeta(
                panel_models=self.config.panel,
                judge_model=self.config.judge if judge_analysis else "",
                synthesizer_model=self.config.synthesizer,
                judge_confidence=confidence,
                latency_ms=latency_ms,
                fallback_triggered=fallback,
            ),
        )
