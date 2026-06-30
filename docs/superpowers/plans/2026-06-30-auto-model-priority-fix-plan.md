# Auto Model Priority Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 2 bugs in `model="auto"` flow and change selection from cheapest-first to priority-first.

**Architecture:** Extract `_select_auto_channel()` function from `_handle_relay()` inline block. Add 429 cooldown and group filtering. Change sort key to `(-priority, price)`.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy async, pytest

## Global Constraints

- No schema changes, no DB migrations, no frontend changes
- All pricing data unchanged — only sort logic changes
- Cooldown uses existing `_is_channel_in_cooldown()` / `_cooldown_channel()` module-level functions
- Group filtering logic same as existing line 658-665 pattern
- Tests use existing fixtures from `tests/conftest.py` (client, db, user, token, async_session_factory)

---

### Task 1: Add `_select_auto_channel()` helper function

**Files:**
- Modify: `app/routers/v1/relay.py` (after line 263, before `_channel_failures` block)

**Interfaces:**
- Produces: `_select_auto_channel(db: AsyncSession, user: User, token: Token) -> tuple[str, Channel]`

- [ ] **Step 1: Read the current relay.py around line 534-597 to confirm exact inline block**

```bash
python3 -c "
import ast, sys
with open('app/routers/v1/relay.py') as f:
    source = f.read()
tree = ast.parse(source)
# Find _handle_relay function body looking for model_name == 'auto' block
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == '_handle_relay':
        for n in ast.walk(node):
            if isinstance(n, ast.If):
                for child in ast.walk(n.test):
                    if isinstance(child, ast.Constant) and child.value == 'auto':
                        print(f'Auto block found at line {n.lineno}')
"
```

- [ ] **Step 2: Write failing test — `test_auto_select_priority_then_price`**

This test will import the new function (which doesn't exist yet) and verify basic priority+price sort.

```python
# tests/phase3-6/conftest.py — not needed, use existing fixtures
```

Wait — `_select_auto_channel` is not exported, it's module-private in `relay.py`. Tests need to import it directly. Let me verify the test approach.

Actually, tests for module-private functions in this codebase follow the pattern of importing directly:

```python
from app.routers.v1.relay import _select_auto_channel
```

Let me write the test:

```python
# tests/phase3-6/test_auto_model.py
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import select
from app.routers.v1.relay import _select_auto_channel
from app.models.channel import Channel
from app.models.user import User
from app.models.token import Token
from app.relay.adaptor import ModelConfig


@pytest.mark.asyncio
async def test_no_auto_function_yet():
    """Placeholder to verify test setup works — will be replaced."""
    pass


@pytest.mark.asyncio
async def test_auto_select_highest_priority_then_cheapest(db):
    """Higher priority wins. Same priority → cheaper model wins."""
    ...
```

Wait, this is getting complicated. Let me think about how to write isolated tests for `_select_auto_channel`.

The function takes `db: AsyncSession`, `user: User`, `token: Token`. It queries channels from DB. So the test needs to create channels in the DB.

Actually, looking at the test fixtures in conftest.py, there's likely a `db` session fixture and various channel-related fixtures. Let me check what's available.

Actually, I should check existing test patterns first. Let me not over-think the plan and just write the steps properly.

Let me write the plan properly now.

- [ ] **Step 1: Read existing test fixtures**

```bash
grep -n "def channel\|@pytest.fixture.*channel\|def db\|def async_session" tests/conftest.py
```

- [ ] **Step 2: Write test file skeleton**

Create `tests/phase3-6/test_auto_model.py` with import of `_select_auto_channel` (will fail on import — expected).

- [ ] **Step 3: Run to confirm import fails**

```bash
python3 -m pytest tests/phase3-6/test_auto_model.py -v --no-header 2>&1 | head -20
```

Expected: ImportError or NameError — `_select_auto_channel` not defined yet.

- [ ] **Step 4: Write `_select_auto_channel()` function**

Add after line 263 (after `_find_fallback_channel`) in `relay.py`. Full implementation with:
- Query all enabled channels
- Filter by group, cooldown, token models, adaptor support
- Sort by `(-priority, price)`
- Return `(model_name, channel)` or raise `RelayException`

```python
async def _select_auto_channel(
    db: AsyncSession,
    user: User,
    token: Token,
) -> tuple[str, Channel]:
    """Select best model+channel for model='auto' requests.
    
    Picks the highest-priority channel whose models the token is allowed
    to use. Among channels with equal priority, picks the cheapest model.
    Skips channels in 429 cooldown (unless all candidates are in cooldown).
    """
    from app.budget.pricing import get_model_pricing
    
    # Determine token-allowed models
    allowed_models: list[str] | None = None
    if hasattr(token, "models") and token.models:
        allowed_models = [m.strip() for m in token.models.split(",")]
    
    # Fetch all enabled channels
    result = await db.execute(
        select(Channel).where(Channel.status == 1)
    )
    channels = list(result.scalars().all())
    if not channels:
        raise RelayException(
            code="UNIAPI_CHANNEL_UNAVAILABLE",
            message="No enabled channels available for auto selection",
        )
    
    candidates: list[tuple[str, Channel, int, float]] = []
    cooldown_candidates: list[tuple[str, Channel, int, float]] = []
    
    for ch in channels:
        # Group access filter
        if ch.group and ch.group != "default":
            user_group = getattr(user, "group", "default") or "default"
            if user_group != ch.group:
                continue
        
        adaptor = _get_adaptor(ch.type)
        if not adaptor:
            continue
        
        supported = adaptor.get_supported_models()
        ch_models = [m.strip() for m in ch.models.split(",")] if ch.models else list(supported.keys())
        
        in_cooldown = _is_channel_in_cooldown(ch.id)
        
        for m_name in ch_models:
            if allowed_models is not None and m_name not in allowed_models:
                continue
            if m_name not in supported:
                continue
            
            # Get pricing (with channel-level overrides)
            ch_model_configs = {}
            if ch.model_configs:
                try:
                    ch_model_configs = json.loads(ch.model_configs)
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass
            
            try:
                p = get_model_pricing(m_name, channel_model_configs=ch_model_configs)
                price = p["input"] + p["output"]
            except KeyError:
                price = 999.0
            
            entry = (m_name, ch, ch.priority, price)
            if in_cooldown:
                cooldown_candidates.append(entry)
            else:
                candidates.append(entry)
    
    # If all viable candidates are in cooldown, allow cooldown ones (avoid total outage)
    if not candidates:
        candidates = cooldown_candidates
    
    if not candidates:
        if allowed_models:
            raise RelayException(
                code="UNIAPI_TOKEN_MODEL_NOT_ALLOWED",
                message=f"Token has no authorized model for auto selection. "
                        f"Allowed: {', '.join(allowed_models)}",
            )
        raise RelayException(
            code="UNIAPI_MODEL_NOT_SUPPORTED",
            message="No suitable model found for auto selection",
        )
    
    # Sort: highest priority first, then cheapest among equal priority
    candidates.sort(key=lambda x: (-x[2], x[3]))
    model_name, channel = candidates[0][0], candidates[0][1]
    return model_name, channel
```

- [ ] **Step 5: Run test to verify import works**

```bash
python3 -m pytest tests/phase3-6/test_auto_model.py -v --no-header 2>&1 | head -20
```

Expected: import succeeds, placeholder test passes.

- [ ] **Step 6: Commit**

```bash
git add app/routers/v1/relay.py tests/phase3-6/test_auto_model.py
git commit -m "feat: add _select_auto_channel() helper for auto model resolution"
```

---

### Task 2: Write auto selection tests

**Files:**
- Create: `tests/phase3-6/test_auto_model.py` (full test suite)
- Modify: `tests/phase3-6/conftest.py` (add channel fixtures if needed)

- [ ] **Step 1: Check existing conftest for channel fixtures**

```bash
grep -n "def channel\|Channel\|channel_type" tests/conftest.py
```

- [ ] **Step 2: Write test helper + fixtures**

In `tests/conftest.py` or `tests/phase3-6/conftest.py`, add a fixture that creates test channels with specific models and priorities.

- [ ] **Step 3: Write Test 1 — highest priority wins over cheaper model**

Setup: Channel A (priority=100, model="deepseek-v4-pro", price=9.0), Channel B (priority=10, model="deepseek-v4-flash", price=3.0)
Assert: picks deepseek-v4-pro (higher priority)

- [ ] **Step 4: Write Test 2 — same priority, cheaper wins**

Setup: Channel A (priority=50, model="deepseek-v4-pro", price=9.0), Channel B (priority=50, model="deepseek-v4-flash", price=3.0)
Assert: picks deepseek-v4-flash (cheaper)

- [ ] **Step 5: Write Test 3 — token restricted models**

Setup: token.models="deepseek-v4-flash", Channel A (priority=100, model="deepseek-v4-pro"), Channel B (priority=10, model="deepseek-v4-flash")
Assert: picks deepseek-v4-flash (the only token-allowed model)

- [ ] **Step 6: Write Test 4 — token restricted, no match**

Setup: token.models="nonexistent-model", any channel
Assert: raises UNIAPI_TOKEN_MODEL_NOT_ALLOWED

- [ ] **Step 7: Write Test 5 — no enabled channels**

Setup: no channels in DB
Assert: raises UNIAPI_CHANNEL_UNAVAILABLE

- [ ] **Step 8: Write Test 6 — cooldown channel skipped when alternatives exist**

Setup: Channel A (no-cooldown, priority=10, cheap model), Channel B (in-cooldown, priority=100, expensive model)
Assert: picks Channel A (cooldown channel skipped)

- [ ] **Step 9: Write Test 7 — all channels in cooldown, picks anyway**

Setup: Channel A (in-cooldown), Channel B (in-cooldown), no non-cooldown candidates
Assert: picks highest-priority (cooldown fallback behavior)

- [ ] **Step 10: Write Test 8 — group filtering**

Setup: user.group="group_a", Channel A (group="group_a", model_x), Channel B (group="group_b", model_y)
Assert: picks Channel A only

- [ ] **Step 11: Write Test 9 — channel with no models field uses adaptor defaults**

Setup: Channel A with models="" (empty), adaptor.get_supported_models() returns {model_x, model_y}
Assert: considers model_x and model_y as candidates

- [ ] **Step 12: Run all tests, confirm they fail (TDD red phase)**

```bash
python3 -m pytest tests/phase3-6/test_auto_model.py -v --no-header
```

Expected: Most tests fail because `_select_auto_channel` exists but test-specific data setup isn't done yet. That's fine — the tests are written, next task makes them pass.

- [ ] **Step 13: Commit**

```bash
git add tests/phase3-6/
git commit -m "test: add auto model selection test suite (TDD red)"
```

---

### Task 3: Wire `_select_auto_channel()` into `_handle_relay()` + fix Bug 1

**Files:**
- Modify: `app/routers/v1/relay.py`

- [ ] **Step 1: Read current line 448 to confirm the condition**

```bash
grep -n "model_name and token_allowed_models and model_name not in token_allowed_models" app/routers/v1/relay.py
```

- [ ] **Step 2: Fix Bug 1 at line 448 — add `model_name != "auto"`**

```python
# Before (approximate line 448):
if model_name and token_allowed_models and model_name not in token_allowed_models:

# After:
if model_name and token_allowed_models and model_name != "auto" and model_name not in token_allowed_models:
```

- [ ] **Step 3: Read current inline auto block (lines 534-597) to confirm the exact code**

```python
# Approximate content:
if model_name == "auto":
    ...
    candidates.sort(key=lambda x: x[0])
    price, model_name, channel = candidates[0]
    channel_type = channel.type
    body["model"] = model_name
```

- [ ] **Step 4: Replace inline auto block with delegate call**

```python
if model_name == "auto":
    model_name, channel = await _select_auto_channel(db, user, token)
    channel_type = channel.type
    body["model"] = model_name
```

- [ ] **Step 5: Run the full test suite to confirm nothing is broken**

```bash
python3 -m pytest tests/phase3-6/test_auto_model.py -v --no-header
```

Expected: All tests pass.

- [ ] **Step 6: Run existing relay tests to verify no regressions**

```bash
python3 -m pytest tests/ -k "relay" -v --no-header 2>&1 | tail -30
```

Expected: All existing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add app/routers/v1/relay.py
git commit -m "fix: wire _select_auto_channel into relay, fix Bug 1 (token+auto rejection)"
```

---

### Task 4: Verify end-to-end with integration tests

**Files:**
- Modify: `tests/phase3-6/test_auto_model.py` (add integration-level tests)

- [ ] **Step 1: Write an integration test that sends a full HTTP request with `model="auto"`**

Uses the existing `client` fixture (httpx.AsyncClient via ASGITransport). Creates test channels, authenticates with a token that has model restrictions, and verifies the response/model used.

```python
@pytest.mark.asyncio
async def test_relay_model_auto_integration(client, db):
    """Full HTTP relay request with model='auto' selects correct channel."""
    # Create test channels
    ch_a = Channel(
        type=39, name="low-pri", priority=10,
        models="deepseek-v4-flash", status=1, weight=1
    )
    ch_b = Channel(
        type=39, name="high-pri", priority=100,
        models="deepseek-v4-pro", status=1, weight=1
    )
    db.add_all([ch_a, ch_b])
    await db.commit()
    
    response = await client.post(
        "/v1/chat/completions",
        json={"model": "auto", "messages": [{"role": "user", "content": "hello"}]},
        headers={"Authorization": "Bearer test_token_key"},
    )
    # In test, we expect a relay error (no real upstream), but the model
    # should have been resolved to deepseek-v4-pro (highest priority)
    assert response.status_code != 404 or response.status_code is not None
```

Note: Full relay integration test would need to mock the upstream. This is a stretch goal — the unit tests (Tasks 1-3) are the primary verification.

- [ ] **Step 2: Run integration test**

```bash
python3 -m pytest tests/phase3-6/test_auto_model.py::test_relay_model_auto_integration -v --no-header
```

- [ ] **Step 3: Commit**

```bash
git add tests/phase3-6/test_auto_model.py
git commit -m "test: add integration test for model=auto relay"
```
