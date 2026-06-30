# Full Codebase Fix Plan

> **For agentic workers:** This plan has 5 independent rounds. Each round is self-contained. Implement round by round with subagent-driven-development.

**Goal:** Fix 81 codebase findings (12 Critical, 36 Important, 33 Minor) across security, billing, relay stability, architecture, and documentation.

**Rounds:** The 5 rounds are INDEPENDENT — they can be worked on in any order.

---

## Round 1: Security Fixes (P0/P1 — 4 Critical, 6 Important)

**Files touched:** `app/main.py`, `app/dependencies.py`, `app/routers/api/channel.py`, `app/routers/api/mcp_servers.py`, `app/services/auth.py`, `app/routers/api/verification.py`

### Task R1-1: Fix hardcoded root credentials

**File:** `app/main.py:124-131`

Change the seed to only create default credentials when they don't exist AND no env-var password is set:

```python
# Replace the hardcoded block with:
DEFAULT_PASSWORD = os.environ.get("INITIAL_ROOT_PASSWORD", "")
if DEFAULT_PASSWORD:
    root = User(
        username="root",
        password=hash_password(DEFAULT_PASSWORD),
        display_name="Root",
        role=100, status=1, group="default",
        access_token=secrets.token_urlsafe(32),
        created_at=now, updated_at=now,
    )
    logger.warning("Root user created with INITIAL_ROOT_PASSWORD. Change immediately.")
else:
    # Existing seed code (with hardcoded values) — only for development
    import sys
    if not any("pytest" in arg for arg in sys.argv):
        logger.warning("No INITIAL_ROOT_PASSWORD set. Using dev default credentials.")
```

**Test:** Verify that `INITIAL_ROOT_PASSWORD` env creates credentials from env, not hardcoded values.

### Task R1-2: Fix token expiry unit mismatch

**File:** `app/dependencies.py:127`

```python
# Before:
if token.expired_time > 0 and token.expired_time < time.time():

# After:
if token.expired_time > 0 and token.expired_time < time.time() * 1000:
```

**File:** `app/routers/api/token.py:27` — confirm the `// 1000` division is consistently applied everywhere `expired_time` is read.

**Test:** Add `test_token_expiry_enforced` — create token with 1-second expiry, wait, verify it's rejected.

### Task R1-3: Fix sort parameter injection

**File:** `app/routers/api/channel.py:125`

Add an allowlist:
```python
ALLOWED_SORT_COLUMNS = {"id", "name", "type", "status", "priority", "weight", "created_time", "created_at"}
sort = sort if sort in ALLOWED_SORT_COLUMNS else "id"
```

**File:** `app/routers/api/mcp_servers.py:84` — same fix.

**Test:** `test_sort_injection_rejected` — try to sort by "__class__" or "__init__", expect graceful fallback.

### Task R1-4: Add Pydantic schema validation to MCP endpoints

**File:** `app/routers/api/mcp_servers.py`

Create a Pydantic request schema:
```python
from pydantic import BaseModel, Field

class MCPServerCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    type: int = Field(default=1, ge=0)
    api_key: str | None = Field(None, max_length=256)
    base_url: str | None = Field(None, max_length=512)
    headers: dict | None = None
    priority: int = 0
    weight: int = 1
    status: int = 1
```

Replace `body = await request.json()` with `body = MCPServerCreateRequest(**await request.json())`.

**Test:** `test_mcp_create_invalid_field` — send extra fields, verify rejection.

### Task R1-5: Add session rotation on password change

**File:** `app/services/auth.py:205-209`

After any password update (both self and admin), ALWAYS rotate session:
```python
# In password update path, always:
response.delete_cookie("session")
response.set_cookie(key="session", value=create_session(user))
```

### Task R1-6: Move reset token from URL to body

**File:** `app/routers/api/verification.py:96`

Send token via email body/JSON rather than URL query parameter:
```python
# Before:
url = f"/reset-password?email={email}&token={token}"

# After:
url = f"/reset-password?token={token}"
```
The email address should already be known from the session when the user clicks the link.

---

## Round 2: Billing & Budget Fixes (P0/P1 — 4 Critical, 4 Important)

**Files touched:** `app/routers/v1/relay.py`, `app/budget/arbiter.py`, `app/fusion/core/engine.py`, `app/fusion/adapters/glm.py`, `app/routers/api/cache_analytics.py`

### Task R2-1: Add FOR UPDATE locking on balance operations

**File:** `app/routers/v1/relay.py`

Replace the read+write pattern with a locked select:
```python
# Before:
user.balance -= estimated_micro

# After:
result = await db.execute(
    select(User).where(User.id == user.id).with_for_update()
)
user = result.scalar_one()
user.balance -= estimated_micro
```

Apply this pattern at all balance mutation points (lines ~505, ~675, ~840, ~1114, ~1250).

**Test:** `test_concurrent_deduction` — use `asyncio.gather` with 10 concurrent relay requests, verify total deduction ≤ balance.

### Task R2-2: Pass channel_model_configs to non-stream billing

**File:** `app/routers/v1/relay.py:1240-1244`

```python
# Before:
actual_micro = calculate_cost_micro(model_name, prompt_tokens, completion_tokens, cache_hit)

# After:
actual_micro = calculate_cost_micro(
    model_name, prompt_tokens, completion_tokens, cache_hit,
    channel_model_configs=_channel_model_configs,
)
```

### Task R2-3: Add budget arbiter pre-check to fusion path

**File:** `app/routers/v1/relay.py:577-703`

Before the fusion engine call, add:
```python
# Estimate fusion cost: worst case = all panel + judge + synth at max_tokens
estimated_fusion_cost = 0
for m_name in panel:
    try:
        p = get_model_pricing(m_name)
        estimated_fusion_cost += p["input"] + p["output"]
    except KeyError:
        estimated_fusion_cost += 1.0
estimated_fusion_cost *= min(body.get("max_tokens", 4096), 8192) / 1_000_000 * 1.2  # safety margin

if budget_arbiter and settings.budget_enabled:
    decision = await budget_arbiter.pre_check(
        user_id=user.id, model="fusion",
        estimated_input_tokens=int(_estimate_input_tokens(body, None)),
        estimated_output_tokens=min(body.get("max_tokens", body.get("max_output_tokens", 256)), 4096),
    )
    if decision.status == "rejected":
        raise RelayException(code="UNIAPI_QUOTA_EXHAUSTED", message=decision.error_message or "Budget exceeded for fusion")

# After fusion execution + billing:
if budget_arbiter and settings.budget_enabled:
    fb = response.usage.fusion_breakdown
    panel_tokens = sum(t.get("prompt_tokens", 0) + t.get("completion_tokens", 0) for t in (fb.panel or {}).values()) if fb else 0
    judge_tokens = (response.fusion_meta.judge_prompt_tokens + response.fusion_meta.judge_completion_tokens) if response.fusion_meta else 0
    await budget_arbiter.post_settle(..., actual_usage=ActualUsage(model="fusion", input_tokens=panel_tokens + judge_tokens, output_tokens=0))
```

### Task R2-4: Fix GLM fusion adapter auth

**File:** `app/fusion/adapters/glm.py`

```python
class GLMAdapter(BaseAdapter):
    async def chat(self, request: ModelRequest) -> ModelResponse:
        payload = self.adapt_request(request.to_dict())
        url = f"{self.openai_base_url}/chat/completions"
        # Use JWT token like the relay GLM adaptor
        from app.relay.adaptors.glm.auth import generate_glm_token
        token = generate_glm_token(self.api_key)
        headers = {"Authorization": token, "Content-Type": "application/json"}
        ...
```

### Task R2-5: Fix budget arbiter DB fallback race

**File:** `app/budget/arbiter.py:90-96`

```python
# Use with_for_update or SELECT FOR UPDATE when reading budget from DB
async def pre_check(self, user_id, model, estimated_input_tokens, estimated_output_tokens, db_session=None):
    if not self.redis.available or ...:
        async with self.db_session_factory() as session:
            budget = await session.execute(
                select(Budget).where(Budget.user_id == user_id).with_for_update()
            )
            budget = budget.scalar_one_or_none()
            if budget:
                consumed = budget.consumed + budget.frozen
```

### Task R2-6: Fix cache analytics fallback pricing

**File:** `app/routers/api/cache_analytics.py:122-133`

Replace the 1:1 fallback with a weighted average:
```python
def _estimate_savings_rate_from_row(row):
    ...
    # Fallback: use average of known model prices
    avg_price = sum(p["input"] + p["output"] for p in MODEL_PRICING_YUAN.values()) / max(len(MODEL_PRICING_YUAN), 1)
    pt_price, ct_price = avg_price / 1_000_000, avg_price / 1_000_000
```

---

## Round 3: Relay Stability Fixes (P0/P1 — 3 Critical, 6 Important)

**Files touched:** `app/routers/v1/relay.py`, `app/relay/openai_compatible.py`

### Task R3-1: Fix _channel_failures race condition

**File:** `app/routers/v1/relay.py`

Add an asyncio.Lock:
```python
_channel_failures: dict[int, int] = {}
_channel_429_counts: dict[int, int] = {}
_channel_lock = asyncio.Lock()  # NEW

async def _record_channel_failure(channel_id, db) -> bool:
    async with _channel_lock:
        count = _channel_failures.get(channel_id, 0) + 1
        _channel_failures[channel_id] = count
    # ... rest unchanged
```

Apply `async with _channel_lock` in `_cooldown_channel()`, `_is_channel_in_cooldown()`, `_reset_channel_failures()`, `_reset_channel_429_count()`.

### Task R3-2: Fix fallback not resetting original channel failures

**File:** `app/routers/v1/relay.py`

At lines 974 and 1053 (fallback success handlers), the `failed_channel_id` variable is already captured. Reset it explicitly:
```python
# After fallback succeeds:
_reset_channel_failures(_channel_id)  # reset fallback channel
_reset_channel_failures(failed_channel_id)  # ALSO reset original failed channel
```

### Task R3-3: Fix _is_channel_in_cooldown TOCTOU

**File:** `app/routers/v1/relay.py:307-316`

```python
def _is_channel_in_cooldown(channel_id: int) -> bool:
    expiry = _channel_cooldowns.get(channel_id)
    if expiry is None:
        return False
    if time.monotonic() > expiry:
        # Don't pop — let _cooldown_channel or periodic cleanup handle it
        return False
    return True
```
Remove the `.pop()` from this check. Add a periodic cleanup helper.

### Task R3-4: Fix supported[model_name] potential KeyError

**File:** `app/routers/v1/relay.py:759`

```python
# Before:
model_config = supported[model_name]

# After:
model_config = supported.get(model_name)
if model_config is None:
    raise RelayException(
        code="UNIAPI_MODEL_NOT_SUPPORTED",
        message=f"Model '{model_name}' not found in adaptor's supported models",
    )
```

### Task R3-5: Fix post_settle with empty model

**File:** `app/routers/v1/relay.py:519`

```python
# Before:
actual_usage=ActualUsage(model="", ...)

# After:
actual_usage=ActualUsage(model=model_name or "unknown", ...)
```
Capture `model_name` from the current scope before it's shadowed.

### Task R3-6: Fix stream usage callback in GeneratorExit (Python 3.14)

**File:** `app/relay/openai_compatible.py:58-70`

```python
async def _capture_stream_usage(...):
    """Use a queue-based approach like raw_passthrough."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    
    async def _reader():
        """Read stream, queue chunks, report usage at end."""
        usage = {}
        try:
            async for chunk in response_stream:
                # ... process chunk ...
                await queue.put(chunk)
        finally:
            # Report usage after stream ends
            if on_stream_usage:
                await on_stream_usage(usage)
    
    reader_task = asyncio.create_task(_reader())
    # Yield from queue until reader finishes
    while True:
        try:
            chunk = await asyncio.wait_for(queue.get(), timeout=0.1)
            yield chunk
        except asyncio.TimeoutError:
            if reader_task.done():
                break
```

### Task R3-7: Fix _eager_sse_stream GeneratorExit handling

**File:** `app/relay/openai_compatible.py:246-263`

```python
try:
    async for line in resp.aiter_lines():
        yield line
except GeneratorExit:
    # Client disconnected — cancel upstream iteration
    await resp.aclose()
    await client.aclose()
    raise
finally:
    await resp.aclose()
    await client.aclose()
```

---

## Round 4: Architecture & Code Quality (P1/P2 — 20 Important, 15 Minor)

**Files touched:** Multiple files — see individual tasks.

### Task R4-1: Fix CORS config

**File:** `app/main.py:209-210`
Add `CORS_ORIGINS` to settings, default `*` but reject wildcard with credentials.

### Task R4-2: Make session_secret required in production

**File:** `app/config.py:77-80`
Add startup validation:
```python
if not self.session_secret and not any("pytest" in a for a in sys.argv):
    raise ValueError("SESSION_SECRET must be set in production")
```

### Task R4-3: Fix rate limiter for proxy deployments

**File:** `app/middleware.py:53`
```python
client_ip = (
    request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    or request.headers.get("X-Real-IP", "")
    or request.client.host
)
```

### Task R4-4: Fix channel bulk-delete by name

**File:** `app/routers/api/channel.py:68`
```python
# Before:
sa_delete(Channel).where(Channel.name == current_channel.name)

# After:
sa_delete(Channel).where(Channel.id == current_channel.id)
```

### Task R4-5: Add reset-password rate limiting

**File:** `app/routers/api/verification.py:115`
Track attempts per email in session/redis, max 3 per hour.

### Task R4-6: Fix _get_path_for_mode return absolute URLs

**File:** All adaptors (`deepseek/adaptor.py`, `kimi/adaptor.py`, `minimax/adaptor.py`, `qwen/adaptor.py`)
```python
# Change from:
return f"{ANTHROPIC_BASE_URL}/v1/messages"
# To:
return "/v1/messages"  # path only — base domain is in get_request_url
```

### Task R4-7: Fix downgrade_response_format schema bug

**File:** `app/relay/adaptors/deepseek/request.py:133-135`
```python
# Before:
schema_instruction = f"Schema instruction: {schema.get('strict', False)}"
# After:
json_schema = schema.get("schema", {})
schema_instruction = f"Schema instruction: {json.dumps(json_schema, ensure_ascii=False)}"
```

### Task R4-8: Remove unused ANTHROPIC_BASE_URL constants

**File:** `app/relay/adaptors/kimi/adaptor.py`, `app/relay/adaptors/qwen/adaptor.py`
Either use the constant in `get_request_url()` / `_get_path_for_mode()`, or remove it.

### Task R4-9: Fix _seed_defaults error handling

**File:** `app/main.py:112-196`
```python
async def _seed_defaults():
    try:
        async with async_session_factory() as db:
            ...
    except Exception as e:
        logger.error("Seed failed: %s", e, exc_info=True)
```

### Task R4-10: Minor remaining items

- `app/exceptions.py:115-116`: Move import to module level (restructure to avoid circular)
- `app/exceptions.py:286-310`: Replace `_http_status_to_code` with lookup against `ERROR_CODE_MAP`
- `app/relay/registry.py:44-54`: Wrap adaptor imports in try/except ImportError
- `app/relay/mode.py:59`: Return `RelayMode.UNKNOWN` instead of defaulting to CHAT_COMPLETIONS
- `app/relay/adaptors/minimax/pricing.py`: Use budget/pricing.py aliasing pattern
- `app/services/email.py:20`: Add periodic cleanup for stale verification codes
- `app/routers/api/auth.py:92`: Move Turnstile token to body

---

## Round 5: Tests & Documentation (P1/P2 — 6 Important, 16 Minor)

### Task R5-1: Add concurrent billing test

**File:** New in `tests/phase4/test_concurrent_billing.py`
```python
@pytest.mark.asyncio
async def test_concurrent_balance_deduction(client):
    """10 concurrent relay requests should not over-deduct balance."""
    # Setup: create root user with known balance
    # Use mock upstream to make all 10 requests succeed
    # Dispatch 10 concurrent POST /v1/chat/completions
    # Verify final balance >= 0 (no overdraft)
```

### Task R5-2: Add SSE disconnect test

**File:** `tests/phase4/test_sse_disconnect.py`
```python
@pytest.mark.asyncio
async def test_stream_client_disconnect_cleanup(client):
    """Client disconnect during streaming cleans up upstream connection."""
    # Mock upstream SSE stream
    # Use httpx stream with timeout
    # Cancel mid-stream
    # Verify usage callback was called (even on disconnect)
```

### Task R5-3: Add token expiry test

**File:** `tests/phase4/test_token_expiry.py`
```python
@pytest.mark.asyncio
async def test_token_expired_is_rejected(client):
    """Token past expired_time should be rejected."""
    # Create a token with expired_time in the past
    # Try using it → 401/403
```

### Task R5-4: Add FOR UPDATE locking test

**File:** `tests/phase4/test_concurrent_billing.py`
```python
@pytest.mark.asyncio
async def test_balance_for_update_locking():
    """Verify SELECT ... FOR UPDATE is used in balance deduction."""
    # Inspect SQL queries OR use mock to verify with_for_update() is called
```

### Task R5-5: Add MCP server validation test

**File:** `tests/phase2/test_mcp_servers.py`
```python
@pytest.mark.asyncio
async def test_mcp_create_rejects_invalid_fields(client):
    """MCP server create should reject unexpected fields."""
    cookies = await login(client)
    resp = await client.post("/api/mcp/", json={
        "name": "valid", "extra_hidden_field": "injection",
        "__init__": "dangerous",
    }, cookies=cookies)
    assert resp.status_code == 422
```

### Task R5-6: Fix documentation

- Update `CLAUDE.md` — fix test directory paths (`phase3-6/` → `phase3/`, `phase4/`)
- Update `CHANGELOG.md` — sync with current version + git tags
- Update `docs/API中转站_费用控制方案设计.md` — document `calculate_cost_micro` instead of `ModelConfig.ratio`
- Update `docs/企业级API中转站优化架构设计.md` — remove references to non-existent Prometheus endpoint
- Add env var documentation for `INITIAL_ROOT_PASSWORD`, `CORS_ORIGINS`, `SESSION_SECRET`
- Add test env documentation for `tests/live/live_test.py`

---

## Priority & Effort Summary

| Round | Focus | Critical | Important | Minor | Est. Effort |
|-------|-------|----------|-----------|-------|-------------|
| R1 | Security | 4 | 6 | 0 | 4-6 hours |
| R2 | Billing/Budget | 4 | 4 | 0 | 5-8 hours |
| R3 | Relay Stability | 3 | 6 | 0 | 6-10 hours |
| R4 | Architecture/QA | 0 | 20 | 15 | 8-12 hours |
| R5 | Tests/Docs | 0 | 6 | 16 | 4-6 hours |
| **Total** | | **11** | **42** | **31** | **27-42 hours** |

Note: 12 Critical initial, but GLM fusion auth appears twice in findings (duplicate), so effectively 11.
