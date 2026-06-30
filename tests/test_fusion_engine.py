"""
Fusion Engine unit tests.

Tests the pipeline orchestration (dispatch -> judge -> synthesize)
and edge cases (fallback, single panel, adapter failures) - all
offline via mocked adapters.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.fusion.adapters.base import BaseAdapter
from app.fusion.adapters.registry import AdapterRegistry
from app.fusion.core.engine import FusionConfig, FusionEngine
from app.fusion.core.judge import JudgeModule
from app.fusion.core.synthesizer import SynthesizerModule
from app.fusion.schemas import (
    ChatRequest,
    ModelResponse,
    UsageInfo,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_adapter(model_id: str, fail: bool = False, timeout: bool = False) -> MagicMock:
    """Create a mock BaseAdapter for *model_id*, registered under that same id."""
    adapter = MagicMock(spec=BaseAdapter)
    adapter.provider_name = model_id.split("-")[0]
    if timeout:
        adapter.chat = AsyncMock(side_effect=TimeoutError("timed out"))
    elif fail:
        adapter.chat = AsyncMock(side_effect=Exception("Connection failed"))
    else:
        adapter.chat = AsyncMock(
            return_value=ModelResponse(
                model=model_id,
                content=f"Answer from {model_id}.",
                usage=UsageInfo(prompt_tokens=100, completion_tokens=50, total_tokens=150),
            )
        )
    return adapter


def _reg(registry: AdapterRegistry, model_id: str, fail: bool = False, timeout: bool = False) -> MagicMock:
    """Register a mock adapter for *model_id* and return it."""
    adapter = _mock_adapter(model_id, fail=fail, timeout=timeout)
    registry.register(model_id, adapter)
    return adapter


@pytest.fixture
def sample_request() -> ChatRequest:
    return ChatRequest(
        model="fusion",
        messages=[{"role": "user", "content": "What is the meaning of life?"}],
    )


@pytest.fixture
def default_config() -> FusionConfig:
    return FusionConfig(
        panel=["result-A", "result-B", "result-C"],
        judge="judge",
        synthesizer="synth",
        timeout_seconds=5,
        retry_count=1,
        fallback_model="result-A",
    )


# ===================================================================
# FusionConfig
# ===================================================================

class TestFusionConfig:
    def test_default_values(self):
        config = FusionConfig()
        assert config.panel == []
        assert config.judge == ""
        assert config.synthesizer == ""
        assert config.timeout_seconds == 30
        assert config.retry_count == 2
        assert config.fallback_model == ""
        assert config.max_tokens == 8192
        assert config.temperature == 0.7

    def test_custom_values(self):
        config = FusionConfig(
            panel=["a", "b"], judge="j", synthesizer="s",
            timeout_seconds=10, retry_count=3, fallback_model="a",
        )
        assert config.panel == ["a", "b"]
        assert config.judge == "j"
        assert config.synthesizer == "s"
        assert config.timeout_seconds == 10
        assert config.retry_count == 3
        assert config.fallback_model == "a"


# ===================================================================
# JudgeModule
# ===================================================================

class TestJudgeModule:
    @pytest.mark.asyncio
    async def test_analyze_returns_structured_analysis(self):
        """Judge model returns valid JSON -> parse into analysis dict."""
        registry = AdapterRegistry()
        judge = _reg(registry, "judge")
        judge.chat.return_value = ModelResponse(
            model="judge",
            content=(
                '{"consensus":["point1"],"contradictions":[],'
                '"coverage_gaps":[],"unique_insights":{},'
                '"blind_spots":[],"confidence":0.85,"recommendation":"pick A"}'
            ),
            usage=UsageInfo(500, 200, 700),
        )

        module = JudgeModule(registry, "judge")
        result = await module.analyze(
            ChatRequest(messages=[{"role": "user", "content": "test?"}]),
            [ModelResponse(model="a", content="A"), ModelResponse(model="b", content="B")],
        )
        assert result["consensus"] == ["point1"]
        assert result["confidence"] == 0.85
        assert result["usage"]["prompt_tokens"] == 500

    @pytest.mark.asyncio
    async def test_analyze_empty_when_adapter_not_found(self):
        """Judge model not in registry -> empty analysis."""
        module = JudgeModule(AdapterRegistry(), "nonexistent")
        result = await module.analyze(
            ChatRequest(messages=[]),
            [ModelResponse(model="a", content="", usage=UsageInfo())],
        )
        assert result["confidence"] == 0.0
        assert result["consensus"] == []

    @pytest.mark.asyncio
    async def test_analyze_empty_on_bad_json(self):
        """Model returns non-JSON -> fallback to empty analysis."""
        registry = AdapterRegistry()
        _reg(registry, "judge").chat.return_value = ModelResponse(
            model="judge", content="Not JSON at all", usage=UsageInfo(),
        )
        result = await JudgeModule(registry, "judge").analyze(
            ChatRequest(messages=[{"role": "user", "content": "?"}]),
            [ModelResponse(model="a", content="x")],
        )
        assert result["confidence"] == 0.0

    @pytest.mark.asyncio
    async def test_analyze_empty_on_chat_exception(self):
        """Adapter.chat() raises -> empty analysis."""
        registry = AdapterRegistry()
        _reg(registry, "judge").chat.side_effect = Exception("API error")
        result = await JudgeModule(registry, "judge").analyze(
            ChatRequest(messages=[{"role": "user", "content": "?"}]),
            [ModelResponse(model="a", content="x")],
        )
        assert result["confidence"] == 0.0

    def test_parse_strips_code_fences(self):
        module = JudgeModule(AdapterRegistry(), "j")
        raw = "```json\n{\"consensus\": [\"ok\"], \"confidence\": 0.9}\n```"
        result = module._parse_judge_response(raw)
        assert result["consensus"] == ["ok"]
        assert result["confidence"] == 0.9

    def test_parse_fills_missing_keys(self):
        module = JudgeModule(AdapterRegistry(), "j")
        result = module._parse_judge_response('{"consensus": ["ok"]}')
        assert result["consensus"] == ["ok"]
        assert result["confidence"] == 0.5
        assert result["contradictions"] == []


# ===================================================================
# SynthesizerModule
# ===================================================================

class TestSynthesizerModule:
    @pytest.mark.asyncio
    async def test_synthesize_returns_model_response(self):
        """Happy path: synth model returns merged answer."""
        registry = AdapterRegistry()
        _reg(registry, "synth").chat.return_value = ModelResponse(
            model="synth", content="Synthesized final answer.",
            usage=UsageInfo(300, 100, 400),
        )
        module = SynthesizerModule(registry, "synth")
        responses = [
            ModelResponse(model="a", content="A says X"),
            ModelResponse(model="b", content="B says Y"),
        ]
        result = await module.synthesize(
            ChatRequest(messages=[{"role": "user", "content": "?"}]),
            responses,
            {"consensus": [], "confidence": 0.9, "usage": {"prompt_tokens": 500, "completion_tokens": 200}},
        )
        assert result.content == "Synthesized final answer."
        assert result.model == "synth"

    @pytest.mark.asyncio
    async def test_synthesize_fallback_on_adapter_not_found(self):
        """Synth model not registered -> return first panel response."""
        module = SynthesizerModule(AdapterRegistry(), "nonexistent")
        responses = [ModelResponse(model="a", content="fallback content")]
        result = await module.synthesize(ChatRequest(messages=[]), responses, {"confidence": 0.0})
        assert result.content == "fallback content"

    @pytest.mark.asyncio
    async def test_synthesize_fallback_on_chat_exception(self):
        """Synth model call fails -> return first panel response."""
        registry = AdapterRegistry()
        _reg(registry, "synth").chat.side_effect = Exception("API error")
        responses = [
            ModelResponse(model="a", content="fallback content"),
            ModelResponse(model="b", content="other"),
        ]
        result = await SynthesizerModule(registry, "synth").synthesize(
            ChatRequest(messages=[]), responses, {"confidence": 0.0},
        )
        assert result.content == "fallback content"


# ===================================================================
# FusionEngine — full pipeline
# ===================================================================

class TestFusionEngine:
    @pytest.mark.asyncio
    async def test_full_pipeline(self, sample_request, default_config):
        """Normal path: dispatch -> judge -> synthesize."""
        registry = AdapterRegistry()
        for m in ["result-A", "result-B", "result-C"]:
            _reg(registry, m)
        _reg(registry, "judge").chat.return_value = ModelResponse(
            model="judge",
            content='{"consensus":["x"],"contradictions":[],"coverage_gaps":[],"unique_insights":{},"blind_spots":[],"confidence":0.8,"recommendation":"ok"}',
            usage=UsageInfo(500, 200, 700),
        )
        _reg(registry, "synth").chat.return_value = ModelResponse(
            model="synth", content="Final fused answer.",
            usage=UsageInfo(800, 400, 1200),
        )

        engine = FusionEngine(registry, default_config)
        response = await engine.execute(sample_request)

        assert response.model == "fusion"
        assert len(response.choices) > 0
        assert response.fusion_meta is not None
        assert len(response.fusion_meta.panel_models) == 3
        assert response.fusion_meta.fallback_triggered is False
        assert response.usage.total_tokens > 0
        assert response.usage.fusion_breakdown is not None
        assert "result-A" in response.usage.fusion_breakdown.panel

    @pytest.mark.asyncio
    async def test_fallback_when_all_panels_fail(self, sample_request):
        """Every panel model fails -> fallback to separate fallback model."""
        registry = AdapterRegistry()
        _reg(registry, "result-A", fail=True)
        _reg(registry, "result-B", fail=True)
        _reg(registry, "result-C", fail=True)
        _reg(registry, "fallback-model")
        config = FusionConfig(
            panel=["result-A", "result-B", "result-C"],
            judge="", synthesizer="",
            fallback_model="fallback-model",
        )
        engine = FusionEngine(registry, config)
        response = await engine.execute(sample_request)
        assert response.fusion_meta.fallback_triggered is True

    @pytest.mark.asyncio
    async def test_single_panel_skips_judge(self):
        """Only 1 panel model -> skip judge, return directly."""
        registry = AdapterRegistry()
        _reg(registry, "m1")
        config = FusionConfig(panel=["m1"], judge="", synthesizer="", fallback_model="m1")
        engine = FusionEngine(registry, config)
        response = await engine.execute(
            ChatRequest(messages=[{"role": "user", "content": "hi"}])
        )
        assert response.fusion_meta.fallback_triggered is False

    @pytest.mark.asyncio
    async def test_single_valid_panel_after_failures(self, default_config, sample_request):
        """2/3 fail, 1 succeeds -> skip judge."""
        registry = AdapterRegistry()
        _reg(registry, "result-A", fail=True)
        _reg(registry, "result-B")
        _reg(registry, "result-C", fail=True)
        _reg(registry, "judge")
        _reg(registry, "synth")
        engine = FusionEngine(registry, default_config)
        response = await engine.execute(sample_request)
        assert response.fusion_meta.fallback_triggered is False

    @pytest.mark.asyncio
    async def test_partial_panel_failure(self, default_config, sample_request):
        """Mix of successes and failures -> still run judge."""
        registry = AdapterRegistry()
        _reg(registry, "result-A")
        _reg(registry, "result-B")
        _reg(registry, "result-C", fail=True)
        _reg(registry, "judge").chat.return_value = ModelResponse(
            model="judge",
            content='{"consensus":["x"],"contradictions":[],"coverage_gaps":[],"unique_insights":{},"blind_spots":[],"confidence":0.8,"recommendation":"ok"}',
            usage=UsageInfo(100, 50, 150),
        )
        _reg(registry, "synth").chat.return_value = ModelResponse(
            model="synth", content="Fused.",
            usage=UsageInfo(200, 100, 300),
        )
        engine = FusionEngine(registry, default_config)
        response = await engine.execute(sample_request)
        assert response.fusion_meta.fallback_triggered is False

    @pytest.mark.asyncio
    async def test_judge_failure_returns_empty_analysis(self, default_config, sample_request):
        """Judge call internally caught -> empty analysis, no fallback, valid response."""
        registry = AdapterRegistry()
        for m in ["result-A", "result-B", "result-C"]:
            _reg(registry, m)
        _reg(registry, "judge").chat.side_effect = Exception("Judge crash")
        _reg(registry, "synth").chat.return_value = ModelResponse(
            model="synth", content="Synthesized response.",
            usage=UsageInfo(300, 100, 400),
        )
        engine = FusionEngine(registry, default_config)
        response = await engine.execute(sample_request)
        # JudgeModule catches exceptions internally, so engine's pipeline
        # proceeds with empty analysis + synthesizer fallback.
        assert response.fusion_meta.fallback_triggered is False
        assert response.fusion_meta.judge_confidence == 0.0

    @pytest.mark.asyncio
    async def test_fallback_model_not_in_registry(self, sample_request):
        """Fallback model not registered -> error response."""
        registry = AdapterRegistry()
        _reg(registry, "result-A", fail=True)
        _reg(registry, "result-B", fail=True)
        config = FusionConfig(
            panel=["result-A", "result-B"],
            judge="", synthesizer="",
            fallback_model="nonexistent",
        )
        engine = FusionEngine(registry, config)
        response = await engine.execute(sample_request)
        assert "not found" in response.choices[0]["message"]["content"]

    @pytest.mark.asyncio
    async def test_unknown_panel_models_skipped(self, default_config, sample_request):
        """Panel models not in registry are skipped."""
        registry = AdapterRegistry()
        _reg(registry, "result-A")
        # "result-B", "result-C" not registered
        _reg(registry, "judge").chat.return_value = ModelResponse(
            model="judge",
            content='{"consensus":[],"contradictions":[],"coverage_gaps":[],"unique_insights":{},"blind_spots":[],"confidence":0.5,"recommendation":""}',
            usage=UsageInfo(10, 5, 15),
        )
        _reg(registry, "synth").chat.return_value = ModelResponse(
            model="synth", content="ok", usage=UsageInfo(10, 5, 15),
        )
        engine = FusionEngine(registry, default_config)
        response = await engine.execute(sample_request)
        assert response is not None

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, default_config, sample_request):
        """Timeout triggers retry before falling back."""
        registry = AdapterRegistry()
        a = _reg(registry, "result-A", timeout=True)
        # Succeed on retry
        a.chat.side_effect = [
            TimeoutError("timeout"),
            ModelResponse(model="result-A", content="After retry.", usage=UsageInfo(100, 50, 150)),
        ]
        _reg(registry, "result-B")
        _reg(registry, "result-C")
        _reg(registry, "judge").chat.return_value = ModelResponse(
            model="judge",
            content='{"consensus":[],"contradictions":[],"coverage_gaps":[],"unique_insights":{},"blind_spots":[],"confidence":0.5,"recommendation":""}',
            usage=UsageInfo(10, 5, 15),
        )
        _reg(registry, "synth").chat.return_value = ModelResponse(
            model="synth", content="ok", usage=UsageInfo(10, 5, 15),
        )
        engine = FusionEngine(registry, default_config)
        response = await engine.execute(sample_request)
        assert response.fusion_meta.fallback_triggered is False

    @pytest.mark.asyncio
    async def test_fallback_double_count(self, sample_request):
        """Fallback should NOT double-count tokens."""
        registry = AdapterRegistry()
        _reg(registry, "result-A", fail=True)
        _reg(registry, "result-B", fail=True)
        _reg(registry, "result-C", fail=True)
        _reg(registry, "fallback-model")
        config = FusionConfig(
            panel=["result-A", "result-B", "result-C"],
            judge="", synthesizer="",
            fallback_model="fallback-model",
        )
        engine = FusionEngine(registry, config)
        response = await engine.execute(sample_request)
        assert response.fusion_meta.fallback_triggered is True
        # Verify tokens: the fallback response has 100 prompt + 50 completion
        assert response.usage.prompt_tokens == 100
        assert response.usage.completion_tokens == 50
        assert response.usage.total_tokens == 150
        # The breakdown should be empty (no panel responses to break down)
        fb = response.usage.fusion_breakdown
        assert fb is not None
        # Panel is not empty — the breakdown dict is empty because panel_responses=[]
        assert len(fb.panel) == 0

    @pytest.mark.asyncio
    async def test_fallback_adapter_exception(self, sample_request):
        """Fallback model adapter exception -> error response."""
        registry = AdapterRegistry()
        _reg(registry, "result-A", fail=True)
        _reg(registry, "fallback-model", fail=True)
        config = FusionConfig(
            panel=["result-A"],
            judge="", synthesizer="",
            fallback_model="fallback-model",
        )
        engine = FusionEngine(registry, config)
        response = await engine.execute(sample_request)
        assert response.fusion_meta.fallback_triggered is True
        assert "unavailable" in response.choices[0]["message"]["content"]
        assert response.usage.total_tokens == 0

    @pytest.mark.asyncio
    async def test_fusion_meta_includes_judge_and_synth_tokens(self, default_config, sample_request):
        """FusionMeta should include judge and synth-only token usage."""
        registry = AdapterRegistry()
        for m in ["result-A", "result-B", "result-C"]:
            _reg(registry, m)
        _reg(registry, "judge").chat.return_value = ModelResponse(
            model="judge",
            content='{"consensus":["x"],"contradictions":[],"coverage_gaps":[],"unique_insights":{},"blind_spots":[],"confidence":0.8,"recommendation":"ok"}',
            usage=UsageInfo(500, 200, 700),
        )
        _reg(registry, "synth").chat.return_value = ModelResponse(
            model="synth", content="Final.", usage=UsageInfo(800, 400, 1200),
        )
        engine = FusionEngine(registry, default_config)
        response = await engine.execute(sample_request)
        meta = response.fusion_meta
        assert meta is not None
        assert meta.judge_prompt_tokens == 500
        assert meta.judge_completion_tokens == 200
        assert meta.synth_prompt_tokens == 800
        assert meta.synth_completion_tokens == 400

    @pytest.mark.asyncio
    async def test_extra_body_passthrough(self, default_config, sample_request):
        """extra_body from ChatRequest should be forwarded to panel models."""
        registry = AdapterRegistry()
        a = _reg(registry, "result-A")
        _reg(registry, "result-B")
        _reg(registry, "result-C")
        _reg(registry, "judge").chat.return_value = ModelResponse(
            model="judge",
            content='{"consensus":[],"contradictions":[],"coverage_gaps":[],"unique_insights":{},"blind_spots":[],"confidence":0.5,"recommendation":""}',
            usage=UsageInfo(10, 5, 15),
        )
        _reg(registry, "synth").chat.return_value = ModelResponse(
            model="synth", content="ok", usage=UsageInfo(10, 5, 15),
        )

        request = ChatRequest(
            model="fusion",
            messages=[{"role": "user", "content": "test"}],
            extra_body={"fusion": {}, "custom_param": "value"},
        )
        engine = FusionEngine(registry, default_config)
        response = await engine.execute(request)
        # Verify the adapter was called with extra_params containing custom_param
        call_kwargs = a.chat.call_args
        assert call_kwargs is not None
        called_request = call_kwargs[0][0]
        assert hasattr(called_request, 'extra_params')
        assert called_request.extra_params.get("custom_param") == "value"

    def test_truncation_in_judge_prompt(self):
        """Judge prompt should include truncation marker for long content."""
        from app.fusion.core.judge import JudgeModule

        module = JudgeModule(AdapterRegistry(), "j")
        prompt = module._build_judge_prompt(
            ChatRequest(messages=[{"role": "user", "content": "test?"}]),
            [ModelResponse(model="a", content="x" * 5000)],  # exceeds 4000 char limit
        )
        assert "[...剩余内容已截断]" in prompt

    def test_truncation_in_synthesizer_prompt(self):
        """Synthesizer prompt should include truncation marker for long content."""
        from app.fusion.core.synthesizer import SynthesizerModule

        module = SynthesizerModule(AdapterRegistry(), "s")
        prompt = module._build_synthesizer_prompt(
            ChatRequest(messages=[{"role": "user", "content": "test?"}]),
            [ModelResponse(model="a", content="x" * 7000)],  # exceeds 6000 char limit
            {"consensus": [], "confidence": 0.5},
        )
        assert "[...剩余内容已截断]" in prompt


# ===================================================================
# ChatRequest helpers
# ===================================================================

class TestChatRequestHelpers:
    def test_is_fusion(self):
        assert ChatRequest(model="FUSION").is_fusion

    def test_is_not_fusion(self):
        assert not ChatRequest(model="gpt-4").is_fusion

    def test_from_dict(self):
        r = ChatRequest.from_dict({"model": "fusion", "messages": [{"role": "u", "content": "hi"}], "temperature": 0.5})
        assert r.model == "fusion"
        assert r.temperature == 0.5

    def test_fusion_override(self):
        r = ChatRequest(extra_body={"fusion": {"panel": ["a", "b"]}})
        assert r.fusion_override == {"panel": ["a", "b"]}
