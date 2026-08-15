"""Regression tests for the adapter credential-exfiltration and SSRF fixes.

The chain these close: an adapter's ``auth_config.secret_ref`` used to resolve
any ``Settings`` attribute, and ``invoke_config.path`` can replace ``base_url``
with an absolute URL that no guard validated. Together that shipped the
platform's own credentials to a host the adapter names.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

import pytest

from app.core.exceptions import AppException
from app.services import adapter_executor
from app.services.url_guard import UnsafeTargetURL


class ResolveSecretRefTests(unittest.TestCase):
    """``_resolve_secret_ref`` must read environment variables and nothing else."""

    def test_env_prefixed_reference_resolves(self):
        with patch.dict("os.environ", {"MY_TARGET_TOKEN": "tok-123"}, clear=False):
            self.assertEqual(adapter_executor._resolve_secret_ref("env:MY_TARGET_TOKEN"), "tok-123")

    def test_bare_reference_resolves_from_environment(self):
        with patch.dict("os.environ", {"MY_TARGET_TOKEN": "tok-456"}, clear=False):
            self.assertEqual(adapter_executor._resolve_secret_ref("MY_TARGET_TOKEN"), "tok-456")

    def test_settings_prefix_is_refused_and_names_the_alternative(self):
        """``settings:app_secret`` used to return the platform's own auth secret.

        The guidance must point at a *dedicated* variable, not at
        ``env:app_secret`` -- that name is refused too, since it is what
        populates the setting in the first place.
        """
        with patch.object(adapter_executor.settings, "app_secret", "super-secret-value"):
            with self.assertRaises(AppException) as ctx:
                adapter_executor._resolve_secret_ref("settings:app_secret")
        message = str(ctx.exception.detail)
        self.assertNotIn("super-secret-value", message)
        self.assertIn("dedicated environment variable", message)

    def test_platform_setting_names_are_refused_through_the_env_path_too(self):
        """Removing the ``settings:`` reflection alone would not have been enough.

        ``Settings`` has no ``env_prefix``, so pydantic-settings loads
        ``openai_api_key`` from the ``OPENAI_API_KEY`` environment variable --
        which means the platform's own key stays reachable through the ordinary
        environment lookup unless that name is refused as well. The env var is
        genuinely set on a configured machine, so this test would silently pass
        for the wrong reason if it only checked the Settings attribute.
        """
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-should-not-leak"}, clear=False):
            for ref in ("openai_api_key", "OPENAI_API_KEY", "openai-api-key", "env:OPENAI_API_KEY"):
                with self.subTest(ref=ref):
                    with self.assertRaises(AppException) as ctx:
                        adapter_executor._resolve_secret_ref(ref)
                    self.assertNotIn("sk-should-not-leak", str(ctx.exception.detail))

    def test_refused_set_is_derived_from_settings_not_hand_listed(self):
        """A hand-maintained denylist on another branch already missed database_url."""
        from app.config import Settings

        self.assertEqual(
            adapter_executor._PLATFORM_SECRET_NAMES,
            frozenset(name.lower() for name in Settings.model_fields),
        )
        for name in ("app_secret", "openai_api_key", "database_url"):
            self.assertIn(name, adapter_executor._PLATFORM_SECRET_NAMES)

    def test_database_url_is_not_reachable_either(self):
        with patch.object(adapter_executor.settings, "database_url", "postgres://u:pw@host/db"):
            with self.assertRaises(AppException) as ctx:
                adapter_executor._resolve_secret_ref("settings:database_url")
            self.assertNotIn("pw@host", str(ctx.exception.detail))

    def test_empty_reference_is_refused(self):
        for ref in ("", "   ", "env:"):
            with self.subTest(ref=ref):
                with self.assertRaises(AppException):
                    adapter_executor._resolve_secret_ref(ref)


class AbsoluteUrlDetectionTests(unittest.TestCase):
    """Scheme detection must agree with ``urljoin``, which is case-insensitive."""

    def test_scheme_matching_is_case_insensitive(self):
        for value in ("http://h/x", "HTTP://h/x", "HtTp://h/x", "https://h/x", "HTTPS://h/x"):
            with self.subTest(value=value):
                self.assertTrue(adapter_executor._is_absolute_http_url(value))

    def test_relative_paths_are_not_absolute(self):
        for value in ("/chat/completions", "chat", "//host/x", "ftp://h/x", ""):
            with self.subTest(value=value):
                self.assertFalse(adapter_executor._is_absolute_http_url(value))

    def test_mixed_case_absolute_path_no_longer_slips_through_as_relative(self):
        """Before the fix ``_request_path`` prefixed a '/' and ``_request_url``
        still resolved it as absolute, so it escaped base_url through a branch
        the code believed could not escape."""
        path = adapter_executor._request_path("/chat/completions", "HTTP://evil.example.com/x")
        self.assertEqual(path, "HTTP://evil.example.com/x")
        self.assertNotIn("/HTTP:", path)

    def test_resolved_url_for_relative_path_stays_under_base_url(self):
        url = adapter_executor._request_url("https://good.example.com", "/chat/completions")
        self.assertEqual(url, "https://good.example.com/chat/completions")


@pytest.mark.anyio
class RequestJsonGuardTests(unittest.IsolatedAsyncioTestCase):
    """The resolved URL, not base_url, is what must be validated."""

    @staticmethod
    def _adapter(base_url: str = "https://good.example.com") -> dict:
        return {"transport": "http_json", "base_url": base_url, "auth_config": None}

    async def _call(self, path: str):
        return await adapter_executor._request_json(
            None,  # the guard must reject before the client is ever touched
            adapter=self._adapter(),
            request_config={"method": "POST", "path": path},
            context={},
            is_invoke=False,
        )

    async def test_absolute_path_to_link_local_is_blocked(self):
        """Literal IPs bypass the conftest DNS stub, so this asserts real policy."""
        with self.assertRaises(UnsafeTargetURL):
            await self._call("http://169.254.169.254/latest/meta-data/")

    async def test_mixed_case_absolute_path_to_link_local_is_also_blocked(self):
        with self.assertRaises(UnsafeTargetURL):
            await self._call("HTTP://169.254.169.254/latest/meta-data/")

    async def test_absolute_path_to_loopback_literal_is_blocked_when_disallowed(self):
        with patch.object(adapter_executor.settings, "allow_localhost_targets", False):
            with self.assertRaises(UnsafeTargetURL):
                await self._call("http://127.0.0.1:8080/admin")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
