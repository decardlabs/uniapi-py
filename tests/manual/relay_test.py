#!/usr/bin/env python3
"""Comprehensive integration test for UniAPI relay.

Tests authentication, model access, quota consumption, log recording,
channel selection, and streaming in a single pass.

Usage:
    python3 tests/manual/relay_test.py --token sk-xxx --base-url http://localhost:8000
    python3 tests/manual/relay_test.py --token sk-xxx --quick       # skip quota/stream tests
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import sys
import urllib.error
import urllib.request

# ── Test Configuration ────────────────────────────────────────

PASS = 0
FAIL = 0
SKIP = 0
RESULTS: list[str] = []


def ok(msg: str):
    global PASS
    PASS += 1
    RESULTS.append(f"  ✅ {msg}")


def fail(msg: str):
    global FAIL
    FAIL += 1
    RESULTS.append(f"  ❌ {msg}")


def skip(msg: str):
    global SKIP
    SKIP += 1
    RESULTS.append(f"  ⏭️  {msg}")


# ── HTTP Helper ────────────────────────────────────────────────


_COOKIE_JAR = http.cookiejar.CookieJar()
_OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_COOKIE_JAR))

def req(
    method: str,
    url: str,
    headers: dict | None = None,
    body: dict | None = None,
) -> tuple[int, dict]:
    global _OPENER
    """Send HTTP request and return (status_code, response_body_dict)."""
    data = json.dumps(body).encode() if body else None
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    r = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        resp = _OPENER.open(r)
        body_text = resp.read().decode()
        return resp.status, json.loads(body_text) if body_text else {}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        try:
            return e.code, json.loads(body_text)
        except json.JSONDecodeError:
            return e.code, {"detail": body_text}
    except urllib.error.URLError as e:
        return 0, {"detail": str(e.reason)}


def relay(
    token: str,
    base_url: str,
    model: str,
    stream: bool = False,
) -> tuple[int, dict]:
    """Send a relay request."""
    url = f"{base_url}/v1/chat/completions"
    body = {"model": model, "messages": [{"role": "user", "content": "Hi in one word"}], "stream": stream}
    return req("POST", url, {"Authorization": f"Bearer {token}"}, body)


def login(base_url: str):
    """Login as root. Session cookie is stored in _COOKIE_JAR."""
    status, data = req("POST", f"{base_url}/api/user/login", body={"username": "root", "password": "123456"})
    if status != 200:
        print("FATAL: Cannot login as root")
        sys.exit(1)


# get_tokens removed (use session cookie)


def get_logs(base_url: str, _token: str, type_filter: int | None = None) -> list[dict]:
    """Get consumption logs (uses session cookie from login)."""
    url = f"{base_url}/api/log/"
    if type_filter is not None:
        url += f"?type={type_filter}"
    status, data = req("GET", url)
    raw = data.get("data", [])
    if isinstance(raw, dict):
        return raw.get("data", []) if "data" in raw else [raw]
    return raw if isinstance(raw, list) else []


# ── Test Suites ────────────────────────────────────────────────


def test_auth(base_url: str):
    """Test authentication and authorization."""
    global FAIL, PASS, SKIP

    print("\n━━━ 1. 认证测试 ──────────────────────")

    # 1a. No token
    status, data = req("POST", f"{base_url}/v1/chat/completions",
                        body={"model": "test", "messages": [{"role": "user", "content": "hi"}]})
    ok("无 Token 返回 401") if status == 401 else fail(f"期望 401 得到 {status}: {data}")

    # 1b. Invalid token
    status, data = req("POST", f"{base_url}/v1/chat/completions",
                        headers={"Authorization": "Bearer sk-invalid-token"},
                        body={"model": "deepseek-v4-pro", "messages": [{"role": "user", "content": "hi"}]})
    ok("无效 Token 返回 401") if status == 401 else fail(f"期望 401 得到 {status}")

    # 1c. Wrong format
    status, data = req("POST", f"{base_url}/v1/chat/completions",
                        headers={"Authorization": "Basic xxx"},
                        body={"model": "test", "messages": [{"role": "user", "content": "hi"}]})
    ok("非 Bearer 格式返回 401") if status == 401 else fail(f"期望 401 得到 {status}")


def test_model_access(token: str, base_url: str):
    """Test model resolution and permissions."""
    print("\n━━━ 2. 模型访问测试 ──────────────────")

    # 2a. Authorized model
    status, data = relay(token, base_url, "deepseek-v4-pro")
    if status == 200:
        usage = data.get("usage", {})
        ok(f"授权模型 deepseek-v4-pro 成功: {usage.get('total_tokens', '?')} tokens")
    else:
        fail(f"授权模型 deepseek-v4-pro 失败: {status} {data.get('detail','')}")

    # 2b. auto mode
    status, data = relay(token, base_url, "auto")
    if status == 200:
        usage = data.get("usage", {})
        model_used = data.get("model", "?")
        ok(f"Auto 模式成功: model={model_used} tokens={usage.get('total_tokens','?')}")
    else:
        fail(f"Auto 模式失败: {status} {data.get('detail','')}")

    # 2c. Unknown model
    status, data = relay(token, base_url, "nonexistent-model-xxx")
    ok("不存在模型返回 400") if status == 400 else fail(f"期望 400 得到 {status}")


def test_quota_consumption(token: str, base_url: str):
    """Test quota deduction and log recording."""
    print("\n━━━ 3. 配额与日志测试 ────────────────")
    login(base_url)

    # Send a request
    status, data = relay(token, base_url, "deepseek-v4-pro")
    if status != 200:
        skip("上游请求失败，跳过配额验证")
        return

    usage = data.get("usage", {})
    ok(f"上游返回: {usage.get('total_tokens','?')} tokens, "
       f"prompt={usage.get('prompt_tokens','?')}, completion={usage.get('completion_tokens','?')}")

    # Check logs via session auth
    logs = get_logs(base_url, token, type_filter=2)
    if logs:
        latest = logs[0]
        has_elapsed = latest.get("elapsed_time", 0) > 0
        has_tokens = latest.get("prompt_tokens", 0) > 0 or latest.get("completion_tokens", 0) > 0
        has_model = bool(latest.get("model_name"))
        has_channel = latest.get("channel", 0) > 0

        if has_model and has_tokens and has_elapsed and has_channel:
            ok(f"日志完整: model={latest['model_name']} "
               f"prompt={latest['prompt_tokens']} comp={latest['completion_tokens']} "
               f"elapsed={latest.get('elapsed_time')}ms channel={latest.get('channel')}")
        else:
            details = []
            if not has_model: details.append("缺 model_name")
            if not has_tokens: details.append("缺 token 用量")
            if not has_elapsed: details.append("缺延迟")
            if not has_channel: details.append("缺 channel_id")
            fail(f"日志不完整: {', '.join(details)}")
    else:
        fail("未找到任何消费日志")


def test_channel_group_access(token: str, base_url: str):
    """Test channel selection and group-based access."""
    print("\n━━━ 4. 渠道与分组测试 ────────────────")

    # Get channels
    status, data = req("GET", f"{base_url}/api/channel/",
                       headers={"Authorization": f"Bearer {token}"})
    if status != 200:
        skip("无法获取频道列表，跳过")
        return

    channels = data.get("data")
    if channels is None:
        # Response might be a paginated wrapper: {success, data: {data: [...]}}
        if isinstance(data.get("data"), dict):
            channels = data["data"].get("data")
    if not channels:
        skip("无可用频道")
        return

    ok(f"获取到 {len(channels)} 个频道")


def test_responses_endpoint(token: str, base_url: str):
    """Test the /v1/responses endpoint."""
    print("\n━━━ 5. Responses API 测试 ────────────")

    status, data = req("POST", f"{base_url}/v1/responses",
                        headers={"Authorization": f"Bearer {token}"},
                        body={
                            "model": "deepseek-v4-pro",
                            "input": "Hi in one word",
                            "stream": False,
                        })
    if status == 200:
        ok("Responses API 成功")
    else:
        detail = data.get("detail", "")
        if isinstance(detail, str) and "not supported" in detail:
            skip(f"Responses API: {detail[:80]}")
        else:
            fail(f"Responses API 失败: {status} {detail}")


def test_streaming(token: str, base_url: str):
    """Test streaming request."""
    print("\n━━━ 6. 流式测试 ─────────────────────")

    url = f"{base_url}/v1/chat/completions"
    body = {"model": "deepseek-v4-pro", "messages": [{"role": "user", "content": "Hi"}], "stream": True}
    data = json.dumps(body).encode()
    r = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
    }, method="POST")
    try:
        reader = _OPENER.open(r)
        first_line = reader.readline().decode().strip()
        reader.close()
        ok(f"流式请求返回 SSE: {first_line[:60] or '(empty)'}")
    except urllib.error.HTTPError as e:
        fail(f"流式请求 HTTP {e.code}")
    except Exception as e:
        fail(f"流式请求失败: {e}")


def test_messages_endpoint(token: str, base_url: str):
    """Test the /v1/messages endpoint (Claude format)."""
    print("\n━━━ 7. Messages API 测试 ─────────────")

    status, data = req("POST", f"{base_url}/v1/messages",
                        headers={"Authorization": f"Bearer {token}", "anthropic-version": "2023-06-01"},
                        body={
                            "model": "deepseek-v4-pro",
                            "messages": [{"role": "user", "content": [{"type": "text", "text": "Hi"}]}],
                            "max_tokens": 256,
                            "stream": False,
                        })
    if status == 200:
        content = data.get("content", [{}])
        ok("Messages API 成功")
    else:
        detail = data.get("detail", "")
        fail(f"Messages API 失败: {status} {detail}")


# ── Main ───────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="UniAPI relay integration test")
    parser.add_argument("--token", required=True, help="API token for testing")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL")
    parser.add_argument("--quick", action="store_true", help="Skip slow tests")
    args = parser.parse_args()

    token = args.token
    base_url = args.base_url.rstrip("/")

    print("UniAPI 集成测试")
    print(f"Base URL: {base_url}")
    print(f"Token: {token[:20]}...")

    # Run tests
    test_auth(base_url)
    test_model_access(token, base_url)
    test_quota_consumption(token, base_url)
    login(base_url)
    test_channel_group_access(token, base_url)
    test_responses_endpoint(token, base_url)

    if not args.quick:
        test_streaming(token, base_url)
        test_messages_endpoint(token, base_url)

    # Summary
    print("\n━━━ 测试报告 ──────────────────────────")
    total = PASS + FAIL + SKIP
    print(f"总计: {total}  通过: {PASS}  失败: {FAIL}  跳过: {SKIP}")
    for r in RESULTS:
        print(r)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
