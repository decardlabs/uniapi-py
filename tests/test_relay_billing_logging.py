"""Test that billing path exceptions are logged, not silently swallowed."""
import inspect
import logging

import pytest

# Module where the fixes are applied
MODULE_UNDER_TEST = "app.routers.v1.relay"


class TestBillingExceptionLogging:
    """Verify except Exception: pass in billing paths emits a warning log."""

    # ── Source code inspection tests ────────────────────────────

    def _get_source_lines(self, func_name: str) -> list[str]:
        """Get the source lines of a function from the relay module."""
        import importlib
        mod = importlib.import_module(MODULE_UNDER_TEST)
        func = getattr(mod, func_name, None)
        if func is None:
            # Might be a nested function - search by name
            for name, obj in inspect.getmembers(mod):
                if name == func_name:
                    func = obj
                    break
        if func is None:
            raise NameError(f"Function {func_name} not found in {MODULE_UNDER_TEST}")
        try:
            return inspect.getsource(func).split("\n")
        except (TypeError, OSError):
            # Nested function - search parent module source
            return []

    def test_stream_callback_costrecord_uses_logger_warning(self):
        """Stream usage callback must log CostRecord write failures, not silently pass."""
        import app.routers.v1.relay as relay_mod
        source = inspect.getsource(relay_mod)
        # Find all except Exception in the file
        lines = source.split("\n")
        costrecord_exceptions = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "except Exception:" and i > 0:
                prev = lines[i - 1].strip()
                # Look for context around CostRecord
                context = "\n".join(lines[max(0, i - 5):i + 3])
                if "CostRecord" in context or "cost_record" in context.lower() or "cr)" in context or "session.add" in context:
                    costrecord_exceptions.append((i + 1, lines[i + 1].strip() if i + 1 < len(lines) else ""))

        # Each CostRecord exception handler should have logger.warning, not pass
        for lineno, handler in costrecord_exceptions:
            assert "logger.warning" in handler or "logger.warning" in handler, \
                f"Line {lineno}: expected logger.warning, got: '{handler}'"

    def test_stream_callback_pool_sync_uses_logger_warning(self):
        """Stream usage callback must log pool sync failures, not silently pass."""
        import app.routers.v1.relay as relay_mod
        source = inspect.getsource(relay_mod)
        lines = source.split("\n")
        pool_exceptions = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "except Exception:" and i > 0:
                prev = lines[i - 1].strip()
                context = "\n".join(lines[max(0, i - 5):i + 3])
                if "sync_consumption_to_pool" in context or "pool_sync" in context:
                    pool_exceptions.append((i + 1, lines[i + 1].strip() if i + 1 < len(lines) else ""))

        for lineno, handler in pool_exceptions:
            assert "logger.warning" in handler, \
                f"Line {lineno}: expected logger.warning, got: '{handler}'"

    def test_non_stream_costrecord_uses_logger_warning(self):
        """Non-stream path must log CostRecord calculation failures."""
        import app.routers.v1.relay as relay_mod
        source = inspect.getsource(relay_mod)
        lines = source.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "except Exception:" and i > 0:
                context = "\n".join(lines[max(0, i - 8):i + 3])
                if "yuan_cost" in context or "calculate_cost" in context:
                    handler = lines[i + 1].strip() if i + 1 < len(lines) else ""
                    assert "logger.warning" in handler, \
                        f"Line {i + 1}: expected logger.warning, got: '{handler}'"
                    return
        pytest.fail("No CostRecord exception handler found in non-stream path")

    def test_non_stream_pool_sync_already_logs(self):
        """Non-stream pool sync path should already have logger.warning."""
        import app.routers.v1.relay as relay_mod
        source = inspect.getsource(relay_mod)
        lines = source.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == "except Exception:" and i > 0:
                context = "\n".join(lines[max(0, i - 8):i + 3])
                if "sync_consumption_to_pool" in context:
                    handler = lines[i + 1].strip() if i + 1 < len(lines) else ""
                    if "Pool sync failed" in handler:
                        return  # Already has logger.warning ✅
        pytest.fail("Non-stream pool sync handler not found or missing logger.warning")
