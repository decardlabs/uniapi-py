"""Test that _reader task is cancelled when client disconnects from SSE stream.

When the client disconnects from a streaming response, _client_stream()
receives a GeneratorExit. The background _reader task must be cancelled
to avoid leaking the upstream HTTP connection until the 300s timeout.
"""
from __future__ import annotations

import inspect


class TestReaderCleanup:
    """_reader task must be cancelled on client disconnect."""

    def test_reader_task_cancelled_when_client_disconnects(self):
        """_client_stream() must cancel reader_task when GeneratorExit is caught."""
        from app.relay import openai_compatible

        source = inspect.getsource(openai_compatible.relay_chat_completion)

        assert "reader_task.cancel()" in source, (
            "reader_task.cancel() must be called in the GeneratorExit handler "
            "to prevent leaking upstream HTTP connections"
        )
