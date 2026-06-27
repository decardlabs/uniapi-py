"""Token accuracy comparison tests using real DeepSeek API.

Validates that uniapi-py's token estimation and post-consume reconciliation
match the actual token counts returned by DeepSeek's API.

Usage:
    DEEPSEEK_API_KEY=sk-... pytest tests/live/test_token_accuracy.py -v --tb=short

NOTE: The relay tests in group B share a single DB + server instance
(module-scoped fixture) to avoid import-reload complexity. Each test
uses a unique token name so log queries don't collide.
"""

from __future__ import annotations

import json
import os
import time

import httpx
import pytest
from httpx import ASGITransport, AsyncClient


def _deepseek_key():
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        pytest.skip("DEEPSEEK_API_KEY not set")
    return key


def _expected_quota(usage: dict, model: str = "deepseek-v4-flash") -> int:
    """Replicate relay's cache-aware cost calculation.

    Matches the logic in relay.py:_handle_relay post-consume section.
    """
    pricing = {
        "deepseek-v4-flash": (1.0, 2.0, 0.02),  # input, output, cached_input
    }
    input_r, output_r, cached_r = pricing[model]
    pt = usage.get("prompt_tokens", 0) or 0
    ct = usage.get("completion_tokens", 0) or 0

    # Cache parsing — matches relay.py lines 647-660
    cache_hit = usage.get("prompt_cache_hit_tokens") or 0
    cache_miss = usage.get("prompt_cache_miss_tokens") or 0
    if not cache_hit and not cache_miss:
        details = usage.get("prompt_tokens_details") or {}
        cache_hit = details.get("cached_tokens") or 0
        cache_miss = max(0, pt - cache_hit)
    if not cache_hit and not cache_miss:
        cache_hit = usage.get("cached_tokens") or 0
        cache_miss = max(0, pt - cache_hit)

    return int(cache_hit * cached_r + cache_miss * input_r + ct * output_r)


def _estimate_input(body: dict) -> int:
    """Replicate _estimate_input_tokens from relay.py."""
    messages = body.get("messages", body.get("input", []))
    if isinstance(messages, str):
        total_chars = len(messages)
    else:
        total_chars = sum(
            len(str(m.get("content", "")))
            for m in (messages if isinstance(messages, list) else [messages])
        )
    return max(10, total_chars // 4)


# ══════════════════════════════════════════════════════════════════════════════
# Test Group A — Direct API comparison (no relay)
# ══════════════════════════════════════════════════════════════════════════════

ESTIMATE_CASES = [
    ("short_en", {
        "model": "deepseek-v4-flash",
        "messages": [{"role": "user", "content": "Say hello in exactly 3 words."}],
        "max_tokens": 20,
    }),
    ("chinese", {
        "model": "deepseek-v4-flash",
        "messages": [{"role": "user",
            "content": "请详细解释深度学习中的反向传播算法，包括链式法则、梯度计算、以及在实际训练中的应用。"}],
        "max_tokens": 50,
    }),
    ("long_en", {
        "model": "deepseek-v4-flash",
        "messages": [{"role": "user",
            "content": "Explain the difference between TCP and UDP in detail. "
                       "Cover reliability, ordering, congestion control, use cases, "
                       "and header structure. Be thorough."}],
        "max_tokens": 100,
    }),
    ("multi_turn", {
        "model": "deepseek-v4-flash",
        "messages": [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a high-level, interpreted language."},
            {"role": "user", "content": "Summarize in one sentence."},
        ],
        "max_tokens": 50,
    }),
]


@pytest.mark.parametrize("label,body", ESTIMATE_CASES)
@pytest.mark.asyncio
async def test_estimate_accuracy(label, body):
    """Direct DeepSeek API: compare chars//4 estimate to actual prompt_tokens."""
    estimate = _estimate_input(body)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.deepseek.com/v1/chat/completions",
            json={**body, "stream": False},
            headers={"Authorization": f"Bearer {_deepseek_key()}", "Content-Type": "application/json"},
        )
    assert resp.status_code == 200, f"API error: {resp.text}"
    actual = resp.json()["usage"]["prompt_tokens"]
    error_pct = abs(estimate - actual) / actual * 100
    print(f"\n  [{label}] chars={sum(len(str(m.get('content',''))) for m in body['messages'])} "
          f"estimate={estimate} actual={actual} error={error_pct:.1f}%")


# ══════════════════════════════════════════════════════════════════════════════
# Test Group B — Relay reconciliation (each test self-contained)
# ══════════════════════════════════════════════════════════════════════════════

async def _relay_setup(deepseek_key: str, token_name: str):
    """One-shot setup: fresh DB + app + client + channel + token. Returns (client, token_key, initial_quota, db_path)."""
    import uuid as _uuid
    db_path = f"/tmp/uniapi_test_{_uuid.uuid4().hex}.db"
    os.environ["SQLITE_PATH"] = db_path
    os.environ["DEEPSEEK_API_KEY"] = deepseek_key

    try:
        os.unlink(db_path)
    except OSError:
        pass

    from app.database import async_session_factory, engine
    from app.main import app
    from app.models.base import Base
    from app.models.user import User
    from app.services.auth import create_default_token, hash_password

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_factory() as db:
        now = int(time.time() * 1000)
        root = User(username="root", password=hash_password("123456"),
                    display_name="Root", role=100, status=1,
                    quota=10_000_000, group="default",
                    access_token="root-access-token-test",
                    created_at=now, updated_at=now)
        db.add(root)
        await db.flush()
        await create_default_token(db, root.id)
        await db.commit()

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")

    # Login + create channel + create token
    login = await client.post("/api/user/login", json={"username": "root", "password": "123456"})
    cookies = login.cookies

    await client.post("/api/channel/", json={
        "name": "DS Test", "type": 39, "key": deepseek_key,
        "base_url": "https://api.deepseek.com/v1",
        "models": "deepseek-v4-flash", "group": "default",
    }, cookies=cookies)

    token_resp = await client.post("/api/token/", json={
        "name": token_name,
        "remain_quota": 500000,
        "unlimited_quota": False,
    }, cookies=cookies)
    data = token_resp.json()["data"]
    token_key = data["key"]
    initial_quota = data["remain_quota"]

    return client, token_key, initial_quota, db_path, engine


async def _relay_teardown(client, db_path, engine):
    await client.aclose()
    from app.models.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.mark.asyncio
async def test_relay_nonstreaming():
    """Non-streaming: DB log prompt_tokens/completion_tokens/quota must match upstream."""
    key = _deepseek_key()
    client, token_key, initial_quota, db_path, engine = await _relay_setup(key, "ns-acc")
    try:
        body = {
            "model": "deepseek-v4-flash",
            "messages": [{"role": "user",
                "content": "Explain TCP vs UDP briefly. Cover reliability and ordering."}],
            "max_tokens": 150, "stream": False,
        }
        resp = await client.post("/v1/chat/completions", json=body,
                                 headers={"Authorization": f"Bearer {token_key}"})
        assert resp.status_code == 200, f"Relay error: {resp.text}"
        usage = resp.json()["usage"]
        pt, ct = usage["prompt_tokens"], usage["completion_tokens"]

        from sqlalchemy import select

        from app.database import async_session_factory
        from app.models.log import Log
        from app.models.token import Token

        async with async_session_factory() as db:
            log_entry = (await db.execute(
                select(Log).where(Log.token_name == "ns-acc", Log.type == 2)
                .order_by(Log.created_at.desc()).limit(1)
            )).scalars().first()

            print(f"\n  [nonstream] upstream: prompt={pt} completion={ct} | "
                  f"log: type={log_entry.type} quota={log_entry.quota} "
                  f"pt={log_entry.prompt_tokens} ct={log_entry.completion_tokens}")

            assert log_entry.prompt_tokens == pt, \
                f"log.prompt_tokens={log_entry.prompt_tokens} != upstream {pt}"
            assert log_entry.completion_tokens == ct, \
                f"log.completion_tokens={log_entry.completion_tokens} != upstream {ct}"

            expected_quota = _expected_quota(usage)
            assert log_entry.quota == expected_quota, \
                f"log.quota={log_entry.quota} != expected={expected_quota}"

            token = (await db.execute(
                select(Token).where(Token.name == "ns-acc").order_by(Token.created_at.desc())
            )).scalars().first()
            assert token.remain_quota >= initial_quota - expected_quota, \
                f"token.remain_quota={token.remain_quota} < {initial_quota - expected_quota}"
    finally:
        await _relay_teardown(client, db_path, engine)


@pytest.mark.asyncio
async def test_relay_streaming():
    """Streaming: DB log must be patched with real usage after stream completes."""
    key = _deepseek_key()
    client, token_key, _, db_path, engine = await _relay_setup(key, "stream-acc")
    try:
        body = {
            "model": "deepseek-v4-flash",
            "messages": [{"role": "user", "content": "Count from 1 to 10, one per line."}],
            "max_tokens": 100, "stream": True,
        }
        resp = await client.post("/v1/chat/completions", json=body,
                                 headers={"Authorization": f"Bearer {token_key}"})
        assert resp.status_code == 200
        content = resp.text
        assert "data: [DONE]" in content, "Stream incomplete"

        # Extract usage from SSE
        sse_lines = [l for l in content.split("\n") if l.startswith("data: ") and l != "data: [DONE]"]
        last_usage = None
        for line in reversed(sse_lines):
            try:
                chunk = json.loads(line[6:])
                if chunk.get("usage"):
                    last_usage = chunk["usage"]
                    break
            except json.JSONDecodeError:
                continue
        assert last_usage is not None, "No usage found in SSE stream"
        pt, ct = last_usage["prompt_tokens"], last_usage["completion_tokens"]

        # Wait for async usage callback to complete
        await __import__("asyncio").sleep(1.5)

        from sqlalchemy import select

        from app.database import async_session_factory
        from app.models.log import Log

        async with async_session_factory() as db:
            log_entry = (await db.execute(
                select(Log).where(Log.token_name == "stream-acc", Log.type == 2)
                .order_by(Log.created_at.desc()).limit(1)
            )).scalars().first()

            print(f"\n  [stream] upstream: prompt={pt} completion={ct} | "
                  f"log: type={log_entry.type} quota={log_entry.quota} "
                  f"pt={log_entry.prompt_tokens} ct={log_entry.completion_tokens}")

            assert log_entry.type == 2, \
                f"Log type should be 2 (consumed), got {log_entry.type}"
            assert log_entry.prompt_tokens == pt, \
                f"log.prompt_tokens={log_entry.prompt_tokens} != upstream {pt}"
            assert log_entry.completion_tokens == ct, \
                f"log.completion_tokens={log_entry.completion_tokens} != upstream {ct}"

            expected_quota = _expected_quota(last_usage)
            assert log_entry.quota == expected_quota, \
                f"log.quota={log_entry.quota} != expected={expected_quota}"
    finally:
        await _relay_teardown(client, db_path, engine)


@pytest.mark.asyncio
async def test_relay_high_max_tokens():
    """max_tokens=4096: verify pre-estimate cap doesn't break final reconciliation."""
    key = _deepseek_key()
    client, token_key, _, db_path, engine = await _relay_setup(key, "highmax-acc")
    try:
        body = {
            "model": "deepseek-v4-flash",
            "messages": [{"role": "user", "content": "Write a short poem about AI."}],
            "max_tokens": 4096, "stream": False,
        }
        resp = await client.post("/v1/chat/completions", json=body,
                                 headers={"Authorization": f"Bearer {token_key}"})
        assert resp.status_code == 200, f"Relay error: {resp.text}"
        usage = resp.json()["usage"]
        pt, ct = usage["prompt_tokens"], usage["completion_tokens"]

        from sqlalchemy import select

        from app.database import async_session_factory
        from app.models.log import Log

        async with async_session_factory() as db:
            log_entry = (await db.execute(
                select(Log).where(Log.token_name == "highmax-acc", Log.type == 2)
                .order_by(Log.created_at.desc()).limit(1)
            )).scalars().first()

            expected_quota = _expected_quota(usage)
            print(f"\n  [highmax] prompt={pt} completion={ct} "
                  f"log.quota={log_entry.quota} expected={expected_quota}")
            assert log_entry.quota == expected_quota, \
                f"log.quota={log_entry.quota} != expected={expected_quota}"
    finally:
        await _relay_teardown(client, db_path, engine)


@pytest.mark.asyncio
async def test_relay_claude_messages_usage():
    """Claude Messages: input_tokens/output_tokens must be parsed from upstream response.

    DeepSeek natively supports /v1/messages (Anthropic format). The response
    uses ``input_tokens`` / ``output_tokens``, not ``prompt_tokens`` / ``completion_tokens``.
    The relay must handle both.
    """
    key = _deepseek_key()
    client, token_key, _, db_path, engine = await _relay_setup(key, "claude-msg-acc")
    try:
        body = {
            "model": "deepseek-v4-flash",
            "max_tokens": 50,
            "messages": [{"role": "user", "content": "Say hello in one word."}],
        }
        resp = await client.post("/v1/messages", json=body,
                                 headers={"Authorization": f"Bearer {token_key}"})
        assert resp.status_code == 200, f"Relay error: {resp.text}"
        upstream = resp.json()
        usage = upstream.get("usage", {})

        # Claude Messages uses input_tokens/output_tokens
        pt = usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0)
        ct = usage.get("output_tokens", 0) or usage.get("completion_tokens", 0)
        assert pt > 0 and ct > 0, f"Expected non-zero usage, got {usage}"

        from sqlalchemy import select

        from app.database import async_session_factory
        from app.models.log import Log

        async with async_session_factory() as db:
            log_entry = (await db.execute(
                select(Log).where(Log.token_name == "claude-msg-acc", Log.type == 2)
                .order_by(Log.created_at.desc()).limit(1)
            )).scalars().first()

            expected_quota = int(pt * 1.0 + ct * 2.0)
            print(f"\n  [claude_msg] upstream: input={pt} output={ct} | "
                  f"log: quota={log_entry.quota} pt={log_entry.prompt_tokens} ct={log_entry.completion_tokens}")

            assert log_entry.prompt_tokens == pt, \
                f"log.prompt_tokens={log_entry.prompt_tokens} != upstream input_tokens={pt}"
            assert log_entry.completion_tokens == ct, \
                f"log.completion_tokens={log_entry.completion_tokens} != upstream output_tokens={ct}"
            assert log_entry.quota == expected_quota, \
                f"log.quota={log_entry.quota} != expected={expected_quota}"
    finally:
        await _relay_teardown(client, db_path, engine)
