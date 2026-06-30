# Auto Model Selection: Priority-based Selection & Bug Fixes

## Problem

When users send `model="auto"` in relay requests, the current implementation has three issues:

1. **Bug (line 448):** Tokens with model restrictions (`token.models != ""`) cannot use `model="auto"` — the early validation check rejects "auto" because it's not in the token's allowed model list, before reaching the auto selection logic.

2. **Bug (line 554-580):** The auto selection loops over ALL enabled channels without checking 429 cooldown state. If the cheapest channel is currently in cooldown (recently returned 429), it gets selected anyway, causing an immediate upstream failure.

3. **Wrong semantics:** Auto selects the **cheapest** model (`input + output` price ascending). The user expects it to select the **highest-priority** model (by channel `priority` field).

## Scope

- Only `app/routers/v1/relay.py` — no changes to adaptors, models, or APIs.
- New test file: `tests/phase3-6/test_auto_model.py`.

## Design

### Approach: Extract `_select_auto_channel()` Function

Rather than modifying the inline block within the 800-line `_handle_relay()`, extract the auto selection logic into a standalone async function. This makes the function testable in isolation (no relay pipeline mock needed) and leaves the main handler clean.

### `_select_auto_channel(db, user, token) -> (model_name, channel)`

**Inputs:**
- `db: AsyncSession` — database session
- `user: User` — authenticated user (for `user.group`)
- `token: Token` — auth token (for `token.models` restriction)

**Output:**
- `model_name: str` — the selected model name (canonical)
- `channel: Channel` — the channel that hosts the selected model

**Raises:**
- `RelayException(UNIAPI_CHANNEL_UNAVAILABLE)` — no enabled channels at all
- `RelayException(UNIAPI_TOKEN_MODEL_NOT_ALLOWED)` — token restricts models but none are available in any channel
- `RelayException(UNIAPI_MODEL_NOT_SUPPORTED)` — no suitable candidate found

**Algorithm (pseudocode):**

```python
async def _select_auto_channel(db, user, token):
    # 1. Determine token-allowed models
    allowed_models = [m.strip() for m in token.models.split(",")] if token.models else None

    # 2. Fetch ALL enabled channels
    channels = await db.execute(select(Channel).where(Channel.status == 1))

    if not channels:
        raise UNIAPI_CHANNEL_UNAVAILABLE

    candidates = []
    for ch in channels:
        # Filter: group access
        if ch.group and ch.group != "default" and user.group != ch.group:
            continue

        # Filter: 429 cooldown
        if _is_channel_in_cooldown(ch.id):
            continue

        adaptor = _get_adaptor(ch.type)
        if not adaptor:
            continue

        supported = adaptor.get_supported_models()
        ch_models = [m.strip() for m in ch.models.split(",")] if ch.models else list(supported.keys())

        for m_name in ch_models:
            # Filter: token model allowlist
            if allowed_models is not None and m_name not in allowed_models:
                continue
            # Filter: must be supported by adaptor
            if m_name not in supported:
                continue

            # Get pricing (with channel-level overrides)
            ch_model_configs = {}
            if ch.model_configs:
                try: ch_model_configs = json.loads(ch.model_configs)
                except: pass
            try:
                p = get_model_pricing(m_name, channel_model_configs=ch_model_configs)
                price = p["input"] + p["output"]
            except KeyError:
                price = 999.0

            candidates.append((m_name, ch, ch.priority, price))

    if not candidates:
        if allowed_models:
            raise UNIAPI_TOKEN_MODEL_NOT_ALLOWED(...)
        raise UNIAPI_MODEL_NOT_SUPPORTED(...)

    # Sort: highest priority first, then cheapest among equal priority
    candidates.sort(key=lambda x: (-x[2], x[3]))
    model_name, channel = candidates[0][0], candidates[0][1]
    return model_name, channel
```

### Changes in `_handle_relay()` (relay.py)

**1. Fix Bug 1 — line 448:**

```python
# Before:
if model_name and token_allowed_models and model_name not in token_allowed_models:

# After:
if model_name and token_allowed_models and model_name != "auto" and model_name not in token_allowed_models:
```

**2. Replace inline auto block (lines 534-597):**

```python
# Before (~60 lines of inline logic):
if model_name == "auto":
    ...  # candidate building, pricing, cheapest pick

# After (~5 lines, delegates to extracted function):
if model_name == "auto":
    model_name, channel = await _select_auto_channel(db, user, token)
    channel_type = channel.type
    body["model"] = model_name
```

### Cooldown + Group Interaction

- **Cooldown:** `_is_channel_in_cooldown()` already exists as a module-level function (relay.py:302). The extracted `_select_auto_channel()` calls it directly.
- **Group:** Uses `user.group` vs `channel.group`, matching the pattern in lines 658-665. The group check in `_select_auto_channel()` replaces the downstream check for the auto path, since we can filter at candidate-build time.

### Error Handling

The new function raises specific `RelayException` codes that the main handler already catches:

| Condition | Exception Code |
|-----------|---------------|
| No enabled channels | `UNIAPI_CHANNEL_UNAVAILABLE` |
| Token-restricted but no match | `UNIAPI_TOKEN_MODEL_NOT_ALLOWED` |
| No valid candidate found | `UNIAPI_MODEL_NOT_SUPPORTED` |

### Testing Strategy (TDD)

New file: `tests/phase3-6/test_auto_model.py`

Use existing fixtures (`client`, `db`, `user`, `token`). The function `_select_auto_channel` is async — test it directly with `db` session + user/token objects.

| Test | What it verifies |
|------|-----------------|
| `test_auto_select_cheapest` | With only price info, picks model with lowest input+output |
| `test_auto_select_highest_priority` | Higher priority channel preferred over cheaper model |
| `test_auto_priority_then_price` | Same priority → cheaper model wins |
| `test_auto_token_restricted` | Token with `models="model_a"` only considers `model_a` |
| `test_auto_token_restricted_no_match` | Token allows model not in any channel → raises |
| `test_auto_no_channels` | No enabled channels → raises |
| `test_auto_cooldown_channel_skipped` | Channel in 429 cooldown is skipped if alternatives exist |
| `test_auto_cooldown_all_in_cooldown` | All candidates in cooldown → selects anyway (avoids total outage) |
| `test_auto_group_filter` | User in "group_a" skips channels with group="group_b" |
| `test_auto_no_model_supported` | Channel exists but no model matches → raises |

## Files Changed

| File | Change Type | Lines |
|------|-------------|-------|
| `app/routers/v1/relay.py` | Modify | ~+40 / -50 (extract function + Bug 1 fix) |
| `tests/phase3-6/test_auto_model.py` | Create | ~+200 (9 test cases) |

## Non-Goals

- No schema changes (no new API fields)
- No database migrations
- No frontend changes
- No pricing data changes

## Risks

- **Low:** The extracted function is a pure refactor of existing inline logic with 3 targeted behavioral changes (Bug 1, Bug 2, sort order). No new dependencies.
- **Minimal:** `_is_channel_in_cooldown()` is a module-level function with no side effects.
