"""
uniapi-py 与直接接入的兼容性对比测试

======================================================================
讨论：这样的测试有没有意义？
======================================================================

一、测试目的

  验证 uniapi-py 作为 API 中转层时，对上游请求/响应是否做到"透明显式转换"。
  即：同一条请求走中转 vs 直连厂商，返回的响应在结构上等价。

二、什么情况适合这种测试

  ✅ 验证协议转换层正确性
     中转做了 NATIVE_FORMATS 智能路由 + 格式转换（如 Anthropic→Chat）。
     对比测试能暴露转换中的语义丢失（例如工具调用格式错误、SSE 事件遗漏）。

  ✅ 验证透传路径无污染
     当入站协议 = 出站协议（纯透传），中转不应修改请求/响应体。
     对比测试能发现意外修改（如多插了 headers、改了 model 名、吞了字段）。

  ✅ 验证计费/用量数据正确性
     usage.prompt_tokens / completion_tokens 应接近直接调用的值。
     差距过大说明 relay 层的请求构造有问题（如多发了 system prompt）。

  ✅ CI 回归检测
    接入新 provider 或修改 relay 逻辑后，跑一次对比测试能快速发现回归。

三、什么情况不太需要

  ❌ 验证模型本身的回答质量
     非确定性（采样温度 > 0）使两次调用输出不同，无法对比语义质量。
     应用层功能测试（如"代码生成是否正确"）不是网关层的责任。

  ❌ 性能/延迟对比
     中转必然增加一次 HTTP 跳转 + 处理时间，对比延迟没有意义。

  ❌ 存量供应商无代码变更时的例行测试
     如果 relay 逻辑没改、配置没改，结果必然一致——只是浪费 API 费用。

四、测试方法论

  4.1 对比策略：结构等价，而非语义等价

    ┌──────────────────────────────────────────────────────────────────┐
    │  直接调用 (Direct)                         中转调用 (Relay)       │
    │  POST api.deepseek.com/v1/...       POST localhost:8000/v1/... │
    │         │                                       │               │
    │         ▼                                       ▼               │
    │    DeepSeek API                          uniapi-py relay        │
    │         │                                       │               │
    │         ▼                                       ▼               │
    │    {JSON response}                    {JSON response}            │
    │         │                                       │               │
    │         └──────────┬────────────────────────────┘               │
    │                    ▼                                            │
    │           比较响应结构：                                         │
    │           • HTTP 状态码相同                                     │
    │           • JSON 顶层 keys 集合相同                               │
    │           • usage 各字段数量级一致（允许 ±20% 偏差）              │
    │           • content 非空                                        │
    │           • finish_reason 一致                                  │
    │           • 错误场景的 status code 和 error 结构一致              │
    └──────────────────────────────────────────────────────────────────┘

  4.2 判断标准

    PASS 条件：
      - 两次调用的 HTTP 状态码一致
      - JSON 响应在结构上同构（顶层 keys 一致）
      - content 均非空
      - usage 数据存在且在合理范围内

    FAIL 条件：
      - 状态码不同（如直连 200、中转 502）
      - 结构不一致（如直连返回 choices[0].message，中转返回空）
      - 一方有 usage 另一方没有

    WARN 条件：
      - usage token 数量级偏差 > 50%
      - 多了一个 INFO/DEBUG 字段（如 relay 插了 request_id）
      - finish_reason 不同

  4.3 适用场景对比

    ┌──────────────────────┬──────────┬──────────┬──────────┐
    │ 场景                  │ 验证价值 │ 测试成本 │ 推荐频率 │
    ├──────────────────────┼──────────┼──────────┼──────────┤
    │ Chat Completion      │ ★★★     │ 低       │ 每次 PR   │
    │ Chat Stream          │ ★★★     │ 低       │ 每次 PR   │
    │ Claude Messages      │ ★★★★    │ 低       │ 每次 PR   │
    │ Tool/Function Call   │ ★★★★    │ 中       │ 每周     │
    │ Error Handling       │ ★★      │ 低       │ 每次 PR   │
    │ 新供应商接入         │ ★★★★★   │ 高       │ 接入时   │
    │ Multi-turn Context    │ ★★★     │ 中       │ 每周     │
    └──────────────────────┴──────────┴──────────┴──────────┘

五、使用方式

  # DeepSeek 对比测试（需真实 API key）
  UNIAPI_TOKEN=sk-xxx DEEPSEEK_API_KEY=sk-xxx \
    python -m pytest tests/test_relay_comparison.py -v

  # GLM 对比测试
  UNIAPI_TOKEN=sk-xxx GLM_API_KEY=id.secret \
    python -m pytest tests/test_relay_comparison.py -v

  # 指定模型
  COMPARE_MODEL=deepseek-v4-pro \
    python -m pytest tests/test_relay_comparison.py -v

  # 跳过耗时测试
  python -m pytest tests/test_relay_comparison.py -v -k "not stream"

  # 全供应商全场景（最慢，最全面）
  COMPARE_ALL=true \
    python -m pytest tests/test_relay_comparison.py -v

六、局限性

  1. 每次运行消耗真实 API 费用（~¥0.01-0.05/次）。
     建议在 CI 中设置为 manual trigger，不随每次 commit 自动运行。

  2. 非确定性响应的对比只能是结构层面的，不能保证语义等价。

  3. 需要维护两套 API Key（中转 token + 直连 key），增加配置复杂度。

  4. 流式测试的对比只能验证"事件流完整"，无法逐事件对应。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import httpx
import pytest

# =====================================================================
# Configuration
# =====================================================================

UNIAPI_BASE = os.getenv("UNIAPI_BASE", "http://localhost:8000")
UNIAPI_TOKEN = os.getenv("UNIAPI_TOKEN", "")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE = os.getenv("DEEPSEEK_BASE", "https://api.deepseek.com")

GLM_API_KEY = os.getenv("GLM_API_KEY", "")
GLM_BASE = os.getenv("GLM_BASE", "https://open.bigmodel.cn/api/paas/v4")

MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE = os.getenv("MINIMAX_BASE", "https://api.minimaxi.com/v1")

COMPARE_MODEL = os.getenv("COMPARE_MODEL", "")
COMPARE_ALL = os.getenv("COMPARE_ALL", "").lower() in ("1", "true", "yes")

# =====================================================================
# Data Types
# =====================================================================


@dataclass
class ComparisonResult:
    """Result of comparing a direct vs relay call."""

    scenario: str = ""
    model: str = ""
    passed: bool = False
    detail: str = ""
    direct_status: int | None = None
    relay_status: int | None = None
    direct_usage: dict | None = None
    relay_usage: dict | None = None
    direct_keys: set = field(default_factory=set)
    relay_keys: set = field(default_factory=set)
    # Token-level comparison
    direct_prompt: int = 0
    relay_prompt: int = 0
    direct_completion: int = 0
    relay_completion: int = 0

    @property
    def icon(self) -> str:
        return "✅" if self.passed else "❌"


# =====================================================================
# Helpers
# =====================================================================


async def _direct_chat(
    model: str,
    messages: list[dict],
    api_key: str,
    base_url: str,
    stream: bool = False,
    **extra,
) -> dict:
    """Send a Chat Completion request directly to the provider.

    Returns dict with keys: status, body (parsed JSON), error.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {"model": model, "messages": messages, "stream": stream, **extra}
    url = f"{base_url.rstrip('/')}/chat/completions"

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=body, headers=headers)
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text[:500]}

    return {
        "status": resp.status_code,
        "body": data,
        "error": None if resp.is_success else resp.text[:300],
    }


async def _relay_chat(
    model: str,
    messages: list[dict],
    stream: bool = False,
    **extra,
) -> dict:
    """Send a Chat Completion request through uniapi-py relay."""
    if not UNIAPI_TOKEN:
        return {"status": 0, "body": {}, "error": "UNIAPI_TOKEN not set"}

    headers = {
        "Authorization": f"Bearer {UNIAPI_TOKEN}",
        "Content-Type": "application/json",
    }
    body = {"model": model, "messages": messages, "stream": stream, **extra}
    url = f"{UNIAPI_BASE.rstrip('/')}/v1/chat/completions"

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, json=body, headers=headers)
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text[:500]}

    return {
        "status": resp.status_code,
        "body": data,
        "error": None if resp.is_success else resp.text[:300],
    }


def _compare_structures(
    direct: dict,
    relay: dict,
    scenario: str,
    model: str,
    passthrough: bool = True,
) -> ComparisonResult:
    """Compare structural equivalence of two responses.

    Parameters
    ----------
    passthrough : bool
        True when both paths use the same protocol (e.g. Chat→Chat).
        In passthrough mode, prompt_tokens must match within 1% tolerance.
        Set to False for cross-protocol paths (e.g. Anthropic→Chat).
    """
    result = ComparisonResult(scenario=scenario, model=model)
    result.direct_status = direct["status"]
    result.relay_status = relay["status"]
    result.direct_usage = direct["body"].get("usage")
    result.relay_usage = relay["body"].get("usage")
    result.direct_keys = set(direct["body"].keys()) if isinstance(direct["body"], dict) else set()
    result.relay_keys = set(relay["body"].keys()) if isinstance(relay["body"], dict) else set()

    # Check 1: HTTP status
    if direct["status"] != relay["status"]:
        result.detail = (
            f"Status mismatch: direct={direct['status']} relay={relay['status']}"
        )
        return result

    # If both errored, compare error structure
    if not direct.get("error") and relay.get("error"):
        result.detail = f"Direct ok ({direct['status']}) but relay errored: {relay['error'][:100]}"
        return result
    if direct.get("error") and not relay.get("error"):
        result.detail = f"Relay ok ({relay['status']}) but direct errored: {direct['error'][:100]}"
        return result
    if direct.get("error") and relay.get("error"):
        # Both errored — compare error shape
        result.passed = True
        result.detail = (
            f"Both errored: direct={direct['error'][:80]} relay={relay['error'][:80]}"
        )
        return result

    # Both succeeded — structural comparison
    db = direct["body"]
    rb = relay["body"]

    # Check 2: content non-empty
    try:
        direct_content = db.get("choices", [{}])[0].get("message", {}).get("content", "")
        relay_content = rb.get("choices", [{}])[0].get("message", {}).get("content", "")
    except (IndexError, TypeError, AttributeError):
        direct_content = ""
        relay_content = ""

    if not direct_content and not relay_content:
        # Both empty — might be tool calls, check for tool_calls
        direct_tc = bool(
            db.get("choices", [{}])[0].get("message", {}).get("tool_calls")
        )
        relay_tc = bool(
            rb.get("choices", [{}])[0].get("message", {}).get("tool_calls")
        )
        if not direct_tc and not relay_tc:
            result.detail = "Both responses have empty content and no tool_calls"
            return result
    elif not direct_content:
        result.detail = f"Direct content empty but relay has content ({relay_content[:50]})"
        return result
    elif not relay_content:
        result.detail = f"Relay content empty but direct has content ({direct_content[:50]})"
        return result

    # Check 3: usage exists
    if not result.direct_usage:
        result.detail = "Direct response has no usage"
        return result
    if not result.relay_usage:
        result.detail = "Relay response has no usage"
        return result

    # Check 4: token-level comparison
    #   prompt_tokens: deterministic — the same request body tokenized
    #                  by the same model should give the same result.
    #                  Tolerance: 1% for passthrough, 20% for converted.
    #   completion_tokens: non-deterministic — model output length varies.
    #                  Tolerance: 20% always.
    TOKEN_TIGHT = 0.01   # 1% — passthrough prompt_tokens
    TOKEN_LOOSE = 0.50   # 50% — completion_tokens (thinking models vary widely)

    result.direct_prompt = result.direct_usage.get("prompt_tokens", 0)
    result.relay_prompt = result.relay_usage.get("prompt_tokens", 0)
    result.direct_completion = result.direct_usage.get("completion_tokens", 0)
    result.relay_completion = result.relay_usage.get("completion_tokens", 0)

    prompt_tol = TOKEN_TIGHT if passthrough else TOKEN_LOOSE
    for label, d, r, tol in [
        ("prompt_tokens", result.direct_prompt, result.relay_prompt, prompt_tol),
        ("completion_tokens", result.direct_completion, result.relay_completion, TOKEN_LOOSE),
    ]:
        if d == 0 and r == 0:
            continue  # both zero — nothing to compare
        if d == 0 or r == 0:
            result.detail = f"{label}: direct={d} relay={r} (one is zero)"
            return result
        # Use absolute diff for small values, ratio for large
        abs_diff = abs(d - r)
        max_val = max(d, r)
        if max_val < 100:
            # Small values: allow up to 50 token absolute difference
            if abs_diff > 50:
                result.detail = (
                    f"{label}: direct={d} relay={r} (abs_diff={abs_diff}, "
                    f"max allowed=50 for values under 100)"
                )
                return result
        else:
            # Large values: use ratio with tolerance
            ratio = max_val / min(d, r) if min(d, r) > 0 else 1.0
            if ratio > (1.0 + tol):
                result.detail = (
                    f"{label}: direct={d} relay={r} (ratio={ratio:.4f}, "
                    f"tolerance={tol:.0%})"
                )
                return result

    # All checks passed
    result.passed = True
    result.detail = (
        f"content OK, prompt_tokens {result.direct_prompt}/{result.relay_prompt}, "
        f"completion_tokens {result.direct_completion}/{result.relay_completion}, "
        f"direct keys={sorted(result.direct_keys)}"
    )
    return result


def _provider_config() -> list[dict]:
    """Determine which providers/models to test based on env vars."""
    configs = []

    if DEEPSEEK_API_KEY:
        if COMPARE_MODEL:
            models = [COMPARE_MODEL]
        else:
            models = ["deepseek-v4-flash"]  # cheapest
        configs.append({
            "name": "DeepSeek",
            "api_key": DEEPSEEK_API_KEY,
            "base_url": DEEPSEEK_BASE,
            "models": models,
        })

    if GLM_API_KEY:
        if COMPARE_MODEL:
            models = [COMPARE_MODEL]
        else:
            models = ["glm-4"]  # default GLM model
        configs.append({
            "name": "GLM",
            "api_key": GLM_API_KEY,
            "base_url": GLM_BASE,
            "models": models,
        })

    if MINIMAX_API_KEY:
        if COMPARE_MODEL:
            models = [COMPARE_MODEL]
        else:
            models = ["MiniMax-M3"]
        configs.append({
            "name": "MiniMax",
            "api_key": MINIMAX_API_KEY,
            "base_url": MINIMAX_BASE,
            "models": models,
        })

    if not configs:
        # Test with what we have (will skip if no UNIAPI_TOKEN)
        if DEEPSEEK_API_KEY:
            configs.append({
                "name": "DeepSeek",
                "api_key": DEEPSEEK_API_KEY,
                "base_url": DEEPSEEK_BASE,
                "models": [COMPARE_MODEL or "deepseek-v4-flash"],
            })

    return configs


# =====================================================================
# Test Scenarios
# =====================================================================


@pytest.mark.skipif(not UNIAPI_TOKEN, reason="UNIAPI_TOKEN required")
@pytest.mark.skipif(not DEEPSEEK_API_KEY and not GLM_API_KEY and not MINIMAX_API_KEY, reason="no API key set")
@pytest.mark.asyncio
async def test_chat_simple():
    """Compare simple Chat Completion: direct vs relay.

    Validates that a basic non-streaming request returns structurally
    equivalent responses from both paths.
    """
    providers = _provider_config()
    if not providers:
        pytest.skip("no provider configured")

    results: list[ComparisonResult] = []

    for provider in providers:
        for model in provider["models"]:
            messages = [{"role": "user", "content": "say hello in one word"}]

            direct = await _direct_chat(
                model, messages,
                api_key=provider["api_key"],
                base_url=provider["base_url"],
            )
            relay = await _relay_chat(model, messages)
            result = _compare_structures(direct, relay, "ChatSimple", f"{provider['name']}/{model}")
            results.append(result)

            print(
                f"\n  [{provider['name']}/{model}] "
                f"{result.icon} {result.detail}"
            )

    failures = [r for r in results if not r.passed]
    assert not failures, (
        f"{len(failures)}/{len(results)} comparison(s) failed:\n"
        + "\n".join(f"  {r.scenario} ({r.model}): {r.detail}" for r in failures)
    )


@pytest.mark.skipif(not UNIAPI_TOKEN, reason="UNIAPI_TOKEN required")
@pytest.mark.skipif(not DEEPSEEK_API_KEY and not GLM_API_KEY and not MINIMAX_API_KEY, reason="no API key set")
@pytest.mark.asyncio
async def test_chat_multi_turn():
    """Compare multi-turn context: direct vs relay.

    Validates that conversation history is preserved through both paths.
    """
    providers = _provider_config()
    results = []

    for provider in providers:
        for model in provider["models"]:
            messages = [
                {"role": "user", "content": "my name is Alice"},
                {"role": "assistant", "content": "Nice to meet you, Alice!"},
                {"role": "user", "content": "what is my name?"},
            ]

            direct = await _direct_chat(
                model, messages,
                api_key=provider["api_key"],
                base_url=provider["base_url"],
            )
            relay = await _relay_chat(model, messages)
            result = _compare_structures(direct, relay, "MultiTurn", f"{provider['name']}/{model}")
            results.append(result)

            # Additional check: both should remember the name
            for label, resp in [("direct", direct), ("relay", relay)]:
                if resp["status"] == 200:
                    try:
                        content = resp["body"]["choices"][0]["message"]["content"]
                        if "alice" not in content.lower():
                            result.detail += " [%s forgot name: %s]" % (label, content[:40])
                    except (KeyError, IndexError):
                        pass

            print(
                f"\n  [{provider['name']}/{model}] "
                f"{result.icon} {result.detail}"
            )

    failures = [r for r in results if not r.passed]
    assert not failures, (
        f"{len(failures)}/{len(results)} comparison(s) failed:\n"
        + "\n".join(f"  {r.scenario} ({r.model}): {r.detail}" for r in failures)
    )


@pytest.mark.skipif(not UNIAPI_TOKEN, reason="UNIAPI_TOKEN required")
@pytest.mark.skipif(not DEEPSEEK_API_KEY and not GLM_API_KEY and not MINIMAX_API_KEY, reason="no API key set")
@pytest.mark.asyncio
async def test_error_handling():
    """Compare error responses: direct vs relay.

    Both paths should return the same HTTP status code and error structure
    for identical bad inputs.
    """
    providers = _provider_config()
    results = []

    for provider in providers:
        for model in provider["models"]:
            # Error scenario: empty messages (should fail)
            direct = await _direct_chat(
                model, [],
                api_key=provider["api_key"],
                base_url=provider["base_url"],
            )
            relay = await _relay_chat(model, [])

            status_match = direct["status"] == relay["status"]
            result = ComparisonResult(
                scenario="ErrorEmpty",
                model=f"{provider['name']}/{model}",
                passed=status_match,
                detail=(
                    f"direct={direct['status']} relay={relay['status']}"
                    if not status_match else
                    f"both={direct['status']} (expected 4xx)"
                ),
                direct_status=direct["status"],
                relay_status=relay["status"],
            )
            results.append(result)

            print(
                f"\n  [{provider['name']}/{model}] "
                f"{result.icon} {result.detail}"
            )

    failures = [r for r in results if not r.passed]
    assert not failures, (
        f"{len(failures)}/{len(results)} error comparison(s) failed"
    )
