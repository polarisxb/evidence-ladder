"""Stage 1.1b: SSRF protection tests for ``app.services.url_guard``.

The url guard is the single chokepoint that every outbound HTTP fetch
of a *user-supplied* URL must pass through. It enforces:

* scheme allow-list (``http`` / ``https`` only)
* host block-list: loopback, RFC1918, link-local (incl. AWS/GCP cloud
  metadata IPs), CGNAT, IPv6 ULA, unspecified addresses
* known cloud metadata hostnames (``metadata.google.internal`` etc.)
  even when DNS does not resolve in this environment

Tests use IP literals where possible to avoid DNS dependency. The
``allow_localhost`` opt-in covers local development against built-in
mock targets (ShopBot, FinanceBot, mock_targets/*).
"""
from __future__ import annotations

import pytest

from app.services.url_guard import UnsafeTargetURL, validate_target_url


# ── 1. Scheme allow-list ─────────────────────────────────────────────────────


class TestSchemeAllowList:
    def test_blocks_file_scheme(self) -> None:
        with pytest.raises(UnsafeTargetURL, match="scheme"):
            validate_target_url("file:///etc/passwd")

    def test_blocks_gopher_scheme(self) -> None:
        with pytest.raises(UnsafeTargetURL, match="scheme"):
            validate_target_url("gopher://example.com/")

    def test_blocks_dict_scheme(self) -> None:
        with pytest.raises(UnsafeTargetURL, match="scheme"):
            validate_target_url("dict://example.com/")

    def test_allows_http_public(self) -> None:
        # 93.184.216.34 = example.com (public, non-private IP literal)
        validate_target_url("http://93.184.216.34/")

    def test_allows_https_public(self) -> None:
        validate_target_url("https://93.184.216.34/")


# ── 2. Loopback ──────────────────────────────────────────────────────────────


class TestLoopback:
    def test_blocks_loopback_ipv4(self) -> None:
        # ``allow_localhost`` defaults to settings (True in test mode);
        # production callers set it False, which is what we test here.
        with pytest.raises(UnsafeTargetURL):
            validate_target_url("http://127.0.0.1/", allow_localhost=False)

    def test_blocks_loopback_ipv6(self) -> None:
        with pytest.raises(UnsafeTargetURL):
            validate_target_url("http://[::1]/", allow_localhost=False)

    def test_blocks_localhost_hostname(self) -> None:
        with pytest.raises(UnsafeTargetURL):
            validate_target_url("http://localhost/", allow_localhost=False)

    def test_allows_loopback_when_opt_in(self) -> None:
        # mock_targets/ServerBot/ etc. live on 127.0.0.1 in dev.
        validate_target_url("http://127.0.0.1:8001/", allow_localhost=True)


# ── 3. Private IPs / metadata services ───────────────────────────────────────


class TestPrivateIp:
    def test_blocks_rfc1918_10(self) -> None:
        with pytest.raises(UnsafeTargetURL):
            validate_target_url("http://10.0.0.1/")

    def test_blocks_rfc1918_172_16(self) -> None:
        with pytest.raises(UnsafeTargetURL):
            validate_target_url("http://172.16.0.1/")

    def test_blocks_rfc1918_192_168(self) -> None:
        with pytest.raises(UnsafeTargetURL):
            validate_target_url("http://192.168.1.1/")

    def test_blocks_link_local_169_254(self) -> None:
        with pytest.raises(UnsafeTargetURL):
            validate_target_url("http://169.254.169.254/latest/meta-data")

    def test_blocks_aws_metadata_even_when_loopback_opted_in(self) -> None:
        # allow_localhost=True must NOT relax the link-local block.
        with pytest.raises(UnsafeTargetURL):
            validate_target_url(
                "http://169.254.169.254/", allow_localhost=True
            )

    def test_blocks_gcp_metadata_hostname(self) -> None:
        # Even if DNS is unavailable in the test env, this hostname must
        # be blocked by static rule.
        with pytest.raises(UnsafeTargetURL):
            validate_target_url("http://metadata.google.internal/")

    def test_blocks_unspecified(self) -> None:
        with pytest.raises(UnsafeTargetURL):
            validate_target_url("http://0.0.0.0/")


# ── 4. Malformed / edge cases ────────────────────────────────────────────────


class TestMalformed:
    def test_rejects_empty_url(self) -> None:
        with pytest.raises(UnsafeTargetURL):
            validate_target_url("")

    def test_rejects_no_scheme(self) -> None:
        with pytest.raises(UnsafeTargetURL):
            validate_target_url("example.com/")

    def test_rejects_no_host(self) -> None:
        with pytest.raises(UnsafeTargetURL):
            validate_target_url("http:///path-only")


# ── 5. Integration: create_scan rejects SSRF target_url ──────────────────────

pytestmark_async = pytest.mark.anyio


class TestCreateScanIntegration:
    @pytest.mark.anyio
    async def test_create_scan_rejects_ssrf_target_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Re-tighten the localhost allowance so production-like behaviour
        # is exercised here (conftest auto-relaxes it for the rest of the
        # suite).
        monkeypatch.setattr(
            "app.config.settings.allow_localhost_targets", False
        )

        async def noop_run_scan(*_args, **_kwargs) -> None:
            return None

        monkeypatch.setattr("app.api.scans.run_scan", noop_run_scan)

        from httpx import ASGITransport, AsyncClient
        from app.main import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post(
                "/api/v1/scans",
                json={
                    "name": "ssrf-attempt",
                    "target_type": "custom",
                    "target_url": "http://169.254.169.254/latest/meta-data",
                    "attack_categories": ["jailbreak"],
                },
            )

        assert resp.status_code == 400, resp.text
        body = resp.text.lower()
        # The error must clearly identify why we refused.
        assert any(token in body for token in ("169.254", "private", "block", "ssrf"))
