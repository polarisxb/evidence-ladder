"""Stage 1.1c: credentials never round-trip back in API responses.

We enforce two properties:

1. ``POST /api/v1/targets/test-connection`` accepts credentials only in
   a JSON **body** (not as query parameters). The response must not
   echo the submitted ``api_key`` under any field.

2. A scan created with sensitive ``target_config`` fields
   (``api_key``, ``system_prompt``) must not echo those values back in
   ``GET /api/v1/scans/{task_id}``. ``ScanResponse`` intentionally
   omits ``target_config`` — these tests pin that contract so future
   schema changes cannot silently regress it.
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


# ── 1. /targets/test-connection ──────────────────────────────────────────────


class TestTestConnectionEndpoint:
    async def test_no_api_key_in_response(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """POST body {target_url, api_key=<marker>} → response JSON
        must not contain the api_key anywhere."""
        # Marker deliberately does NOT match real API-key regex (no
        # sk-/key-/Bearer prefix) so external secret scanners do not
        # flag this file. What matters is that the marker must not
        # appear verbatim in the response body.
        secret = "LEAK-MARKER-api-key-do-not-echo-0123456789"

        # Patch httpx so we don't actually hit the network; also prove
        # the endpoint returns a successful shape without echoing the key.
        import httpx

        class _FakeResp:
            status_code = 200

        class _FakeAsyncClient:
            def __init__(self, *_a, **_kw) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_a) -> None:
                return None

            async def get(self, *_a, **_kw):
                return _FakeResp()

        monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

        resp = await client.post(
            "/api/v1/targets/test-connection",
            json={
                "target_url": "https://93.184.216.34/",
                "api_key": secret,
            },
        )
        assert resp.status_code == 200, resp.text
        body_text = resp.text
        assert secret not in body_text, (
            f"Response leaked api_key: {body_text}"
        )
        # Field name is OK; value must not be.
        assert "LEAK-MARKER" not in body_text

    async def test_api_key_as_query_parameter_is_ignored_or_rejected(
        self, client: AsyncClient
    ) -> None:
        """After 1.1c, credentials must not be accepted via query string.
        Empty JSON body must 422, proving the body is required (ergo
        the ``?api_key=`` query form no longer has a recognised slot)."""
        resp = await client.post(
            "/api/v1/targets/test-connection"
            "?target_url=https://93.184.216.34/&api_key=LEAK-MARKER-via-query"
        )
        # FastAPI returns 422 on missing required body.
        assert resp.status_code == 422, resp.text
        assert "LEAK-MARKER-via-query" not in resp.text


# ── 2. ScanResponse pins: target_config must not leak ────────────────────────


class TestScanResponseSanitization:
    async def test_scan_get_omits_target_config_api_key(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Create a scan with target_config.api_key; GET should NOT echo it."""
        api_key_value = "LEAK-MARKER-target-config-api-key-xyz789"

        async def noop_run_scan(*_args, **_kwargs) -> None:
            return None

        monkeypatch.setattr("app.api.scans.run_scan", noop_run_scan)

        create = await client.post(
            "/api/v1/scans",
            json={
                "name": "leak-check",
                "target_type": "builtin_vulnerable",
                "target_url": "builtin",
                "target_config": {
                    "api_key": api_key_value,
                    "vulnerable_level": 1,
                },
                "attack_categories": ["jailbreak"],
            },
        )
        assert create.status_code == 200, create.text
        task_id = create.json()["data"]["task_id"]

        # Verify neither POST response nor GET response echo the key.
        assert api_key_value not in create.text

        detail = await client.get(f"/api/v1/scans/{task_id}")
        assert detail.status_code == 200, detail.text
        assert api_key_value not in detail.text, (
            f"GET /scans/{{id}} leaked api_key: {detail.text}"
        )

    async def test_scan_get_omits_target_config_system_prompt(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """system_prompt often contains operational secrets; must not leak."""
        system_prompt_value = "SYS-PROMPT-SECRET-INSTRUCTIONS-marker-42"

        async def noop_run_scan(*_args, **_kwargs) -> None:
            return None

        monkeypatch.setattr("app.api.scans.run_scan", noop_run_scan)

        create = await client.post(
            "/api/v1/scans",
            json={
                "name": "sysprompt-leak-check",
                "target_type": "builtin_vulnerable",
                "target_url": "builtin",
                "target_config": {
                    "system_prompt": system_prompt_value,
                    "vulnerable_level": 1,
                },
                "attack_categories": ["jailbreak"],
            },
        )
        assert create.status_code == 200, create.text
        task_id = create.json()["data"]["task_id"]
        assert system_prompt_value not in create.text

        detail = await client.get(f"/api/v1/scans/{task_id}")
        assert detail.status_code == 200, detail.text
        assert system_prompt_value not in detail.text, (
            f"GET /scans/{{id}} leaked system_prompt: {detail.text}"
        )
