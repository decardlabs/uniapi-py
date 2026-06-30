# Fusion Engine Bug Fix Plan

**Goal:** Fix 4 bugs in Fusion Engine (billing bypass, double counting, fallback exception, breakdown misalignment) and 3 improvements (config dedup, content truncation, extra_body passthrough).

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy async, pytest

## Global Constraints

- No schema changes, no DB migrations
- No changes to relay.py's non-fusion paths
- Existing 21 fusion tests must continue to pass (may need updates for new behavior)
- Fusion billing uses micro-yuan via `calculate_cost_micro` from `app.budget.pricing`
- New tests follow existing patterns: `tests/test_fusion_engine.py` for unit, `tests/phase4/` for integration
- FusionConfig dataclass can be extended but fields must remain backward-compatible

---

### Task 1: Fix fallback double-counting + breakdown misalignment (#2, #4)

**Files:**
- Modify: `app/fusion/core/engine.py`

**Changes:**

1. In `_fallback()` (line 106-119), change the `_build_response` call:
```python
# Before:
return self._build_response(request_id, response, [response], None, start_time, fallback=True)

# After:
return self._build_response(request_id, response, [], None, start_time, fallback=True)
```

This prevents `_build_response` from adding `final.usage` a second time via the `panel_responses` loop.

2. In `_build_response()` (line 121-146), the `total_prompt` and `total_completion` calculation currently starts with `final.usage.*`, then adds `panel_responses` and `judge_analysis`. When `panel_responses=[]`, only `final.usage` is counted once — correct.

3. In `_fallback()`, wrap the `adapter.chat()` call in a try/except:
```python
async def _fallback(self, request, request_id, start_time):
    fallback_model = self.config.fallback_model or self.config.panel[0]
    adapter = self.registry.get(fallback_model)
    if adapter is None:
        return self._error_response(request_id, fallback_model, start_time)
    
    try:
        model_request = ModelRequest(
            model=fallback_model, messages=request.messages,
            temperature=self.config.temperature, max_tokens=self.config.max_tokens, stream=False,
        )
        response = await adapter.chat(model_request)
        return self._build_response(request_id, response, [], None, start_time, fallback=True)
    except Exception:
        return self._error_response(request_id, fallback_model, start_time)
```

4. Add `_error_response()` helper:
```python
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
```

**Tests to add:**
- `test_fallback_double_count`: verify fallback token counts are not doubled
- `test_fallback_adapter_exception`: verify fallback adapter failure returns error response

---

### Task 2: Fix fusion billing bypass (#1)

**Files:**
- Modify: `app/routers/v1/relay.py` (fusion block in `_handle_relay()`)
- Modify: `app/fusion/schemas.py` (add cost computation helper)

**Interfaces:**
- Consumes: `UsageInfo` from fusion response (with `fusion_breakdown.panel`)
- Consumes: `calculate_cost_micro()` from `app.budget.pricing`
- Produces: provisional `Log` entry + `CostRecord` for fusion requests

**Changes in relay.py (lines ~580-637):**

Replace the current fusion block with a billing-aware version:

```python
if model_name == "fusion":
    fusion_registry = getattr(request.app.state, "fusion_registry", None)
    if not fusion_registry:
        raise RelayException(...)
    
    # ... existing panel selection logic ...
    
    if len(panel) < 2:
        # Fallback to single model passthrough (existing code)
        ...
    else:
        # Build fusion config (existing)
        scored = [...]
        fusion_config = FusionConfig(panel=panel, ...)
        engine = FusionEngine(fusion_registry, fusion_config)
        chat_request = ChatRequest.from_dict(body)
        response = await engine.execute(chat_request)
        result = response.to_dict()
        
        # ── NEW: Billing for fusion requests ──
        # Calculate total cost from all model invocations
        total_cost_micro = 0
        fb = response.usage.fusion_breakdown
        if fb:
            for model_id, token_usage in (fb.panel or {}).items():
                try:
                    total_cost_micro += calculate_cost_micro(
                        model_id,
                        token_usage.get("prompt_tokens", 0),
                        token_usage.get("completion_tokens", 0),
                    )
                except KeyError:
                    pass
            # Judge tokens
            if fb.judge_model and response.fusion_meta:
                total_cost_micro += calculate_cost_micro(
                    fb.judge_model,
                    response.fusion_meta.get("judge_prompt_tokens", 0),
                    response.fusion_meta.get("judge_completion_tokens", 0),
                )
            # Synthesizer tokens (the final response IS the synth output)
            if fb.synthesizer_model and response.usage:
                total_cost_micro += calculate_cost_micro(
                    fb.synthesizer_model,
                    response.usage.prompt_tokens or 0,
                    response.usage.completion_tokens or 0,
                )
        
        # Deduct balance
        user.balance -= total_cost_micro
        
        # Write Log
        now_ms = int(time.time() * 1000)
        log = Log(
            user_id=user.id, created_at=now_ms, type=2,
            content=f"Fusion: {model_name}",
            username=user.username, token_name=token.name,
            model_name="fusion", cost=total_cost_micro,
            channel_id=0, request_id=uuid.uuid4().hex,
            is_stream=False,
        )
        db.add(log)
        await db.flush()
        
        # Write CostRecord
        db.add(CostRecord(
            request_id=log.request_id, user_id=user.id,
            model="fusion",
            input_tokens=response.usage.prompt_tokens or 0,
            output_tokens=response.usage.completion_tokens or 0,
            cache_hit_tokens=0,
            cost=round(total_cost_micro / 1_000_000, 6),
            status="success",
            created_at=int(time.time() * 1000),
        ))
        
        await db.commit()
        return result
```

**Also modify `FusionMeta` in schemas.py** to include judge token usage:
```python
@dataclass
class FusionMeta:
    panel_models: list[str] = field(default_factory=list)
    judge_model: str = ""
    synthesizer_model: str = ""
    judge_confidence: float = 0.0
    latency_ms: int = 0
    fallback_triggered: bool = False
    judge_prompt_tokens: int = 0      # NEW
    judge_completion_tokens: int = 0  # NEW
```

**And update `JudgeModule.analyze()`** to store token usage in the analysis dict (already does! `analysis["usage"]` exists at line 76-79).

**Then update `_build_response()`** to read judge tokens from `judge_analysis` and store in FusionMeta:
```python
judge_prompt = (judge_analysis or {}).get("usage", {}).get("prompt_tokens", 0)
judge_completion = (judge_analysis or {}).get("usage", {}).get("completion_tokens", 0)

# In FusionMeta construction:
fusion_meta=FusionMeta(
    ...
    judge_prompt_tokens=judge_prompt,
    judge_completion_tokens=judge_completion,
)
```

**Tests to add:**
- `test_fusion_billing_deduction`: verify user balance is deducted after fusion
- `test_fusion_log_created`: verify Log entry created for fusion request

---

### Task 3: Config consolidation + content truncation + extra_body (#5, #6, #8)

**Files:**
- Modify: `app/main.py` (config consolidation)
- Modify: `app/fusion/core/judge.py` (truncation marker)
- Modify: `app/fusion/core/synthesizer.py` (truncation marker)
- Modify: `app/fusion/core/engine.py` (extra_body passthrough)

**Change 1 (judge.py:93):**
```python
# Before:
parts.append(f"### {resp.model} 的回答\n{content}\n")

# After:
content = resp.content[:4000]
if len(resp.content) > 4000:
    content += "\n\n[...剩余内容已截断]"
parts.append(f"### {resp.model} 的回答\n{content}\n")
```

**Change 2 (synthesizer.py:72):**
```python
# Before:
panel_parts = [f"### {r.model}\n{r.content[:6000]}" for r in panel_responses]

# After:
def _truncate(content, limit):
    if len(content) > limit:
        return content[:limit] + "\n\n[...剩余内容已截断]"
    return content
panel_parts = [f"### {r.model}\n{_truncate(r.content, 6000)}" for r in panel_responses]
```

**Change 3 (engine.py:75-83):** Pass extra_body from ChatRequest into panel ModelRequest:
```python
model_request = ModelRequest(
    model=model_id,
    messages=request.messages,
    temperature=self.config.temperature,
    max_tokens=self.config.max_tokens,
    tools=request.tools,
    stream=False,
    extra_params=dict(request.extra_body),  # NEW
)
```

**Tests to add:**
- `test_judge_truncated_content`: verify truncation marker in judge prompt
- `test_synthesizer_truncated_content`: verify truncation marker in synth prompt
- `test_panel_receives_extra_body`: verify extra_params forwarded

---

### Task 4: Run full regression suite

- Run all fusion tests: `python3 -m pytest tests/test_fusion_engine.py -v --no-header`
- Run all phase4 tests: `python3 -m pytest tests/phase4/ -v --no-header`
- Run all relay tests: `python3 -m pytest tests/ -k "relay" -v --no-header`
- Verify no regressions
