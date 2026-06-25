"""Tests for middleware: PII masking, rate limiting, request ID, timing."""
from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient


class TestPIIMaskMiddleware:
    """PIIMaskMiddleware must mask sensitive fields in request bodies."""

    def test_mask_pii_phone(self):
        from app.middleware import PIIMaskMiddleware

        mw = PIIMaskMiddleware(app := FastAPI())
        result = mw._mask_pii("Contact: 13800138000")
        assert "[PHONE]" in result
        assert "13800138000" not in result

    def test_mask_pii_email(self):
        from app.middleware import PIIMaskMiddleware

        mw = PIIMaskMiddleware(app := FastAPI())
        result = mw._mask_pii("Email: test@example.com")
        assert "[EMAIL]" in result
        assert "test@example.com" not in result

    def test_mask_pii_api_key(self):
        from app.middleware import PIIMaskMiddleware

        mw = PIIMaskMiddleware(app := FastAPI())
        result = mw._mask_pii("sk-abcdefghijklmnopqrstuvwxyz1234567890abcdefgh")
        assert "[API_KEY]" in result

    def test_mask_pii_id_card(self):
        from app.middleware import PIIMaskMiddleware

        mw = PIIMaskMiddleware(app := FastAPI())
        result = mw._mask_pii("ID: 110101199001011234")
        assert "[ID_CARD]" in result
        assert "110101199001011234" not in result

    def test_mask_pii_dict_values(self):
        from app.middleware import PIIMaskMiddleware

        mw = PIIMaskMiddleware(app := FastAPI())
        data = {"user": {"email": "alice@example.com", "phone": "13800138000"}}
        result = mw._mask_pii(data)
        assert result["user"]["email"] == "[EMAIL]"
        assert result["user"]["phone"] == "[PHONE]"

    def test_mask_pii_list_items(self):
        from app.middleware import PIIMaskMiddleware

        mw = PIIMaskMiddleware(app := FastAPI())
        data = ["test@example.com", "sk-abcdefghijklmnopqrstuvwxyz1234567890abcdefgh"]
        result = mw._mask_pii(data)
        assert result[0] == "[EMAIL]"
        assert result[1] == "[API_KEY]"

    def test_mask_nested_structure(self):
        from app.middleware import PIIMaskMiddleware

        mw = PIIMaskMiddleware(app := FastAPI())
        data = {"messages": [{"content": "My email is user@example.com"}], "model": "gpt-4"}
        result = mw._mask_pii(data)
        assert "[EMAIL]" in result["messages"][0]["content"]
        assert "user@example.com" not in result["messages"][0]["content"]

    def test_mask_pii_preserves_non_pii(self):
        from app.middleware import PIIMaskMiddleware

        mw = PIIMaskMiddleware(app := FastAPI())
        data = {"model": "gpt-4", "messages": [{"role": "user", "content": "hello"}]}
        result = mw._mask_pii(data)
        assert result["model"] == "gpt-4"
        assert result["messages"][0]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_middleware_sets_masked_body_on_request_state(self):
        """dispatch() must call _mask_pii and store result in request.state.masked_body."""
        from app.middleware import PIIMaskMiddleware

        test_app = FastAPI()

        @test_app.post("/test")
        async def echo_masked(request: Request):
            masked = request.state.masked_body
            return {"masked": masked}

        test_app.add_middleware(PIIMaskMiddleware)

        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/test", json={
                "email": "alice@example.com",
                "phone": "13800138000",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["masked"]["email"] == "[EMAIL]"
        assert data["masked"]["phone"] == "[PHONE]"

    @pytest.mark.asyncio
    async def test_middleware_is_registered_in_main_app(self):
        """PIIMaskMiddleware must be registered in the main FastAPI app."""
        from app.main import app as main_app
        from app.middleware import PIIMaskMiddleware

        classes = [m.cls for m in main_app.user_middleware]
        assert PIIMaskMiddleware in classes, "PIIMaskMiddleware not registered in app/main.py"
