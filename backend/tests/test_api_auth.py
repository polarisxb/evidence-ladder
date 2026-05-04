"""Stage 1.1a: default-deny API authentication tests.

Behavior under test:
- Default: settings.auth_required = True. Anonymous requests are rejected
  with 401 unless the path is a public path (/health, /docs, ...).
- Opt-out: settings.auth_required = False disables auth (parity with prior
  empty-APP_SECRET behavior, but now explicit).
- Startup guard: auth_required=True with empty app_secret must fail fast
  via _validate_auth_config().
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestDefaultAuthRequired:
    async def test_anonymous_request_rejected(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """auth_required=True + valid app_secret + no X-API-Key → 401."""
        monkeypatch.setattr("app.config.settings.auth_required", True)
        monkeypatch.setattr("app.config.settings.app_secret", "test-secret-xyz")
        resp = await client.get("/api/v1/scans")
        assert resp.status_code == 401, resp.text

    async def test_authenticated_request_allowed(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """auth_required=True + correct X-API-Key → request passes auth."""
        monkeypatch.setattr("app.config.settings.auth_required", True)
        monkeypatch.setattr("app.config.settings.app_secret", "test-secret-xyz")
        resp = await client.get(
            "/api/v1/scans", headers={"X-API-Key": "test-secret-xyz"}
        )
        # 200 expected; the route succeeds with empty list
        assert resp.status_code == 200, resp.text

    async def test_wrong_api_key_rejected(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """auth_required=True + wrong X-API-Key → 401."""
        monkeypatch.setattr("app.config.settings.auth_required", True)
        monkeypatch.setattr("app.config.settings.app_secret", "test-secret-xyz")
        resp = await client.get(
            "/api/v1/scans", headers={"X-API-Key": "wrong-key"}
        )
        assert resp.status_code == 401, resp.text


class TestPublicPaths:
    async def test_health_always_public(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """auth_required=True still lets /health through without a token."""
        monkeypatch.setattr("app.config.settings.auth_required", True)
        monkeypatch.setattr("app.config.settings.app_secret", "test-secret-xyz")
        resp = await client.get("/health")
        assert resp.status_code == 200


class TestOptOut:
    async def test_opt_out_disables_auth(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """auth_required=False → no token required, request succeeds."""
        monkeypatch.setattr("app.config.settings.auth_required", False)
        # app_secret left empty deliberately
        monkeypatch.setattr("app.config.settings.app_secret", "")
        resp = await client.get("/api/v1/scans")
        assert resp.status_code == 200, resp.text


class TestStartupGuard:
    def test_validate_auth_config_fails_when_required_but_no_secret(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """auth_required=True + app_secret='' → _validate_auth_config raises RuntimeError."""
        from app.main import _validate_auth_config

        monkeypatch.setattr("app.config.settings.auth_required", True)
        monkeypatch.setattr("app.config.settings.app_secret", "")
        with pytest.raises(RuntimeError, match="APP_SECRET"):
            _validate_auth_config()

    def test_validate_auth_config_passes_when_required_with_secret(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """auth_required=True + app_secret set → no exception."""
        from app.main import _validate_auth_config

        monkeypatch.setattr("app.config.settings.auth_required", True)
        monkeypatch.setattr("app.config.settings.app_secret", "non-empty-secret")
        _validate_auth_config()

    def test_validate_auth_config_passes_when_opted_out(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """auth_required=False → no exception even with empty secret."""
        from app.main import _validate_auth_config

        monkeypatch.setattr("app.config.settings.auth_required", False)
        monkeypatch.setattr("app.config.settings.app_secret", "")
        _validate_auth_config()
