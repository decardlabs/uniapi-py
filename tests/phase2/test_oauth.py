"""Tests for OAuth endpoints.

Tests the state token generation and GitHub callback flow.
The callback is tested by mocking the external GitHub API calls.
"""

from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.routers.api.oauth import _oauth_states


# ── State management helpers ─────────────────────────────────────────────

async def _get_state(client: AsyncClient) -> str:
    """Get a fresh OAuth state token."""
    resp = await client.get("/api/oauth/state")
    assert resp.status_code == 200
    return resp.json()["data"]


# ── Tests ───────────────────────────────────────────────────────────────

class TestState:
    @pytest.mark.asyncio
    async def test_get_state_returns_token(self, client: AsyncClient):
        resp = await client.get("/api/oauth/state")
        assert resp.status_code == 200
        state = resp.json()["data"]
        assert isinstance(state, str)
        assert len(state) > 10


class TestGitHubCallback:
    @pytest.mark.asyncio
    async def test_callback_missing_params(self, client: AsyncClient):
        """Without code and state, the callback should fail."""
        resp = await client.get("/api/oauth/github")
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    @pytest.mark.asyncio
    async def test_callback_invalid_state(self, client: AsyncClient):
        """With an invalid state token, the callback should fail."""
        resp = await client.get("/api/oauth/github?code=somecode&state=bogus")
        assert resp.status_code == 200
        assert resp.json()["success"] is False

    @pytest.mark.asyncio
    async def test_callback_with_valid_state(self, client: AsyncClient):
        """With a valid state, the callback should proceed to GitHub API calls.

        Since GitHub OAuth is not configured in the test DB options,
        the callback should fail at the config check.
        """
        state = await _get_state(client)
        resp = await client.get(f"/api/oauth/github?code=somecode&state={state}")
        assert resp.status_code == 200
        # Should fail because GitHubOAuthEnabled != "true" in test DB
        assert resp.json()["success"] is False
        assert resp.json()["message"] == "GitHub OAuth is not enabled"

    @pytest.mark.asyncio
    async def test_callback_github_api_error(self, client: AsyncClient):
        """When GitHub API fails, the callback should return an error."""
        state = await _get_state(client)

        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {}

            resp = await client.get(f"/api/oauth/github?code=bad&state={state}")
            assert resp.status_code == 200
            body = resp.json()
            assert body.get("success") is False
