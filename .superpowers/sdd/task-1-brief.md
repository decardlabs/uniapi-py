# Task 1: Fix fallback double-counting + breakdown misalignment (#2, #4)

**Files:**
- Modify: `app/fusion/core/engine.py`

## Changes

### 1. Fix double-counting in `_fallback()`
Change the `_build_response` call to pass `panel_responses=[]` instead of `[response]`:
```python
# Before:
return self._build_response(request_id, response, [response], None, start_time, fallback=True)

# After:
return self._build_response(request_id, response, [], None, start_time, fallback=True)
```

### 2. Add try/except in `_fallback()` for adapter exception
```python
# Before:
response = await adapter.chat(model_request)

# After:
try:
    response = await adapter.chat(model_request)
except Exception:
    return self._error_response(request_id, fallback_model, start_time)
```

### 3. Add `_error_response()` helper method
Add a new method to `FusionEngine` class:
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

### 4. Fix `_build_response()` breakdown loop for empty panel_responses
The current code at line 126 `zip(self.config.panel, panel_responses)` will produce 0 iterations when panel_responses=[], so the breakdown dict will be empty. This is correct — no double counting, no misaligned zip.

## Tests to modify/add in `tests/test_fusion_engine.py`

### Test: `test_fallback_double_count`
Verify that fallback token counts are correct (not doubled):
```python
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
```

### Test: `test_fallback_adapter_exception`
Verify that when the fallback model itself fails, an error response is returned:
```python
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
```

### Test: Update existing `test_fallback_when_all_panels_fail`
The existing test at line 265 expects the fallback to work. It still should — only the fallback model succeeds, and `_fallback()` is called. The assertion `response.fusion_meta.fallback_triggered is True` should still pass. But the token count assertion might change. Let me check...

The existing test:
```python
_reg(registry, "fallback-model")
```
This registers a working adapter. The _fallback() path should succeed and return a ModelResponse with usage 100/50. With our fix, the breakdown is empty and tokens are 100/50/150.

The existing test checks `response.fusion_meta.fallback_triggered is True` — that's it. No token assertions. So the existing test should still pass.

## Implementation steps

1. Read `app/fusion/core/engine.py` to confirm current state
2. Make all 4 changes described above
3. Read `tests/test_fusion_engine.py` to find the right insertion point
4. Add two new test methods to `TestFusionEngine` class
5. Run all fusion tests: `python3 -m pytest tests/test_fusion_engine.py -v --no-header`
6. Commit: `git add app/fusion/core/engine.py tests/test_fusion_engine.py && git commit -m "fix: fallback double-counting, breakdown misalignment, fallback exception safety"`

## Report

Write report to `.superpowers/sdd/task-1-report.md`
