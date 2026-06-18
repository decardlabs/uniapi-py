#!/usr/bin/env python3
"""
uniapi-py live test harness.

Tests the uniapi-py backend against real upstream providers (DeepSeek, GLM).
Verifies all API formats (Chat Completions, Claude Messages, streaming, tools).

Usage:
    UNIAPI_TOKEN=sk-... python -m tests.live.live_test
    UNIAPI_TOKEN=sk-... DEEPSEEK_API_KEY=sk-... python -m tests.live.live_test
    python -m tests.live.live_test --quick
    python -m tests.live.live_test --stream

Environment variables:
    UNIAPI_BASE           Target server (default: http://localhost:8000)
    UNIAPI_TOKEN          API token (required)
    DEEPSEEK_API_KEY      DeepSeek direct API key (for comparison)
    GLM_API_KEY           GLM API key (id.secret format)
    UNIAPI_PROVIDER       "deepseek", "glm", or "all" (default: all)
    TEST_TIMEOUT          Request timeout (default: 120)
"""

from __future__ import annotations

import sys

from .config import config
from .runner import LiveTestRunner


def main():
    print(r"""
    ╔══════════════════════════════════════════╗
    ║   uniapi-py Live Test Harness            ║
    ║   Targets: DeepSeek, GLM                 ║
    ╚══════════════════════════════════════════╝
    """)

    stream_only = "--stream" in sys.argv
    quick = "--quick" in sys.argv

    if not config.api_token:
        print("❌ UNIAPI_TOKEN is required")
        print()
        print("Usage:")
        print("  UNIAPI_TOKEN=sk-... python -m tests.live.live_test")
        print("  UNIAPI_TOKEN=sk-... python -m tests.live.live_test --quick")
        sys.exit(1)

    runner = LiveTestRunner(stream_only=stream_only, quick=quick)
    ok = runner.run()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
