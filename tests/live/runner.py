"""ScenarioResult and runner for live tests."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

from .config import config
from .scenarios import ScenarioResult

ProviderTest = Callable[..., ScenarioResult]


def _provider_models() -> list[tuple[str, str]]:
    """Return list of (provider_name, model_name) to test."""
    results: list[tuple[str, str]] = []
    provider = config.provider
    if provider in ("all", "deepseek") and config.has_deepseek:
        for m in config.models_deepseek:
            results.append(("DeepSeek", m))
    if provider in ("all", "glm") and config.has_glm:
        for m in config.models_glm:
            results.append(("GLM", m))
    # Fallback: test with token auth only (no direct comparison)
    if not results:
        models = config.models_deepseek
        for m in models:
            results.append(("DeepSeek", m))
    return results


def _api_base_for(provider: str) -> str:
    return config.api_base


def _headers_for(model: str) -> dict:
    return config.headers()


def _timeout_for(_model: str) -> int:
    return config.timeout


def _log(msg: str, level: str = "INFO"):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)


class LiveTestRunner:
    """Runs live test scenarios against uniapi-py."""

    def __init__(self, *, stream_only: bool = False, quick: bool = False):
        self.stream_only = stream_only
        self.quick = quick
        self.results: list[ScenarioResult] = []
        self.start_time: float = 0.0

    def _scenarios(self) -> list[tuple[str, ProviderTest]]:
        if self.stream_only:
            from .scenarios.stream import test_stream_chat, test_stream_claude_messages

            return [
                ("Stream Chat", test_stream_chat),
                ("Stream Claude", test_stream_claude_messages),
            ]

        if self.quick:
            from .scenarios.chat import test_chat_simple

            return [
                ("Chat Simple", test_chat_simple),
            ]

        from .scenarios.chat import test_chat_multi_turn, test_chat_reasoning_replay, test_chat_simple
        from .scenarios.claude_messages import (
            test_claude_messages_multi_turn,
            test_claude_messages_simple,
            test_claude_messages_tool,
        )
        from .scenarios.stream import test_stream_chat, test_stream_claude_messages
        from .scenarios.tools import test_tool_call_basic, test_tool_call_history

        return [
            ("Chat Simple", test_chat_simple),
            ("Chat Multi-turn", test_chat_multi_turn),
            ("Chat Reasoning Replay", test_chat_reasoning_replay),
            ("Stream Chat", test_stream_chat),
            ("Claude Messages", test_claude_messages_simple),
            ("Claude Messages Tool", test_claude_messages_tool),
            ("Claude Messages Multi-turn", test_claude_messages_multi_turn),
            ("Stream Claude Messages", test_stream_claude_messages),
            ("Tool Call Basic", test_tool_call_basic),
            ("Tool Call History", test_tool_call_history),
        ]

    def run(self):
        """Run all test scenarios."""
        self.start_time = time.time()
        _log(f"uniapi-py live test — {config.api_base}")
        _log(f"Provider filter: {config.provider}")
        _log(f"DeepSeek key: {'✓' if config.has_deepseek else '✗'}")
        _log(f"GLM key: {'✓' if config.has_glm else '✗'}")
        _log(f"Token: {'✓' if config.api_token else '✗'}")
        print()

        if not config.api_token:
            _log("UNIAPI_TOKEN is required", "ERROR")
            return False

        scenarios = self._scenarios()
        providers = _provider_models()

        for provider_name, model in providers:
            _log(f"── [{provider_name}] {model} ──")
            headers = _headers_for(model)
            api_base = _api_base_for(provider_name)

            for scenario_name, test_fn in scenarios:
                try:
                    start = time.time()
                    result = test_fn(model, headers, api_base, _timeout_for(model))
                    result.duration = time.time() - start
                    result.name = f"{scenario_name}"  # model is in the scenario name
                    self.results.append(result)

                    dur = f"{result.duration:.1f}s"
                    _log(f"  {result.icon} {scenario_name}: {result.detail} [{dur}]")
                    if result.warn:
                        _log("    ⚠️ Passed with caveat", "WARN")
                except Exception as e:
                    import traceback

                    _log(f"  ❌ {scenario_name}: exception: {e}", "ERROR")
                    traceback.print_exc()

            print()

        return self._report()

    def _report(self) -> bool:
        """Print summary report."""
        elapsed = time.time() - self.start_time
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        warned = sum(1 for r in self.results if r.warn)
        failed = total - passed

        print()
        _log("=" * 60)
        _log(f"  RESULTS: {passed}/{total} passed", "INFO" if failed == 0 else "ERROR")
        if warned:
            _log(f"  ({warned} passed with caveats)")
        _log(f"  Duration: {elapsed:.1f}s")
        _log("=" * 60)
        print()

        # Print failures
        failures = [r for r in self.results if not r.passed]
        if failures:
            _log("Failures:", "ERROR")
            for r in failures:
                _log(f"  ❌ {r.name}: {r.detail}", "ERROR")

        return failed == 0
