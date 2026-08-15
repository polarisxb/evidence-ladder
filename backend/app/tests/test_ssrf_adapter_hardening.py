"""Regression tests for SSRF / secret-exfiltration hardening of adapters.

Covers two gaps closed in the egress layer:

1. An absolute-URL ``invoke_config.path`` overrides the ingress-validated
   ``base_url`` and must itself pass the SSRF guard before any request fires.
2. ``auth_config.secret_ref`` must not be able to read arbitrary platform
   settings (no reflective ``getattr(settings, ...)``; sensitive attributes
   are explicitly blocked).
"""
import unittest
from unittest.mock import AsyncMock, patch

from app.core.exceptions import AppException
from app.services import adapter_executor
from app.services.adapter_executor import _resolve_secret_ref, execute_adapter_request


def _adapter_with_path(path: str) -> dict:
    return {
        "name": "ssrf-fixture",
        "mode": "direct_http_adapter",
        "transport": "http_json",
        "base_url": "https://api.example.com",
        "auth_config": {"type": "none"},
        "session_config": {"mode": "per_variant_isolated"},
        "invoke_config": {
            "method": "POST",
            "path": path,
            "body_template": {"message": "{{input.prompt}}"},
        },
        "response_extract": {"mode": "raw_text"},
        "enabled": True,
    }


class TestAdapterPathSSRF(unittest.IsolatedAsyncioTestCase):
    async def test_absolute_path_override_to_metadata_is_blocked(self):
        # An absolute path pointing at the cloud metadata service escapes the
        # validated base_url and must be refused before any HTTP call.
        with patch.object(
            adapter_executor.httpx.AsyncClient, "request", new=AsyncMock()
        ) as mock_request:
            result = await execute_adapter_request(
                _adapter_with_path("http://169.254.169.254/latest/meta-data/"),
                prompt="hi",
                history=None,
                runtime_vars=None,
                scan_id=None,
                case_id=None,
                variant_type="attack",
            )
        self.assertFalse(result["success"])
        self.assertFalse(result["transport_ok"])
        self.assertIn("Refused unsafe target URL", result["response_error"])
        mock_request.assert_not_called()

    async def test_relative_path_is_not_extra_validated(self):
        # A normal relative path must still reach the (mocked) transport; the
        # new guard only fires for host-changing absolute overrides.
        fake_response = unittest.mock.MagicMock()
        fake_response.is_success = True
        fake_response.status_code = 200
        fake_response.text = "pong"
        fake_response.content = b"pong"
        fake_response.headers = {"content-type": "text/plain"}
        with patch.object(
            adapter_executor.httpx.AsyncClient,
            "request",
            new=AsyncMock(return_value=fake_response),
        ) as mock_request:
            result = await execute_adapter_request(
                _adapter_with_path("/chat"),
                prompt="hi",
                history=None,
                runtime_vars=None,
                scan_id=None,
                case_id=None,
                variant_type="attack",
            )
        mock_request.assert_called_once()
        self.assertTrue(result["success"])


class TestSecretRefHardening(unittest.TestCase):
    def test_settings_sensitive_ref_is_rejected(self):
        with self.assertRaises(AppException):
            _resolve_secret_ref("settings:app_secret")
        with self.assertRaises(AppException):
            _resolve_secret_ref("settings:openai_api_key")

    def test_bare_ref_no_longer_reflects_settings(self):
        # Previously a bare ref fell back to getattr(settings, ref); that
        # reflective lookup is removed, so a settings attribute name now fails.
        with self.assertRaises(AppException):
            _resolve_secret_ref("openai_model")


if __name__ == "__main__":
    unittest.main()
