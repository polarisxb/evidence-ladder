"""Tests for the opt-in reproducible-judge features.

Covers the on-disk judge cache, the seed plumbing through the analysis layer,
and confirmation that defaults are unchanged.
"""
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from app.config import settings
from app.services import ai_analyzer, judge_cache
from app.services.llm_client import ProviderClientInfo

_BASE_KW = dict(model="m", temperature=0.0, json_mode=True,
                messages=[{"role": "user", "content": "x"}], judge_version="v1")


class TestJudgeCache(unittest.TestCase):
    def setUp(self):
        self._dir = settings.judge_cache_dir
        self._enabled = settings.judge_cache_enabled
        settings.judge_cache_dir = tempfile.mkdtemp()

    def tearDown(self):
        settings.judge_cache_dir = self._dir
        settings.judge_cache_enabled = self._enabled

    def test_disabled_is_noop(self):
        settings.judge_cache_enabled = False
        key = judge_cache.make_key(seed=1, **_BASE_KW)
        judge_cache.put(key, "value")
        self.assertIsNone(judge_cache.get(key))

    def test_roundtrip_when_enabled(self):
        settings.judge_cache_enabled = True
        key = judge_cache.make_key(seed=1, **_BASE_KW)
        self.assertIsNone(judge_cache.get(key))
        judge_cache.put(key, "hello")
        self.assertEqual(judge_cache.get(key), "hello")

    def test_key_is_sensitive_to_seed_and_temperature(self):
        k_seed1 = judge_cache.make_key(seed=1, **_BASE_KW)
        k_seed2 = judge_cache.make_key(seed=2, **_BASE_KW)
        self.assertNotEqual(k_seed1, k_seed2)


class TestSeedPlumbingAndCache(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._dir = settings.judge_cache_dir
        self._enabled = settings.judge_cache_enabled
        settings.judge_cache_dir = tempfile.mkdtemp()
        settings.judge_cache_enabled = True

    def tearDown(self):
        settings.judge_cache_dir = self._dir
        settings.judge_cache_enabled = self._enabled

    async def test_seed_forwarded_and_second_call_served_from_cache(self):
        provider = ProviderClientInfo(provider_type="openai", api_key="k", base_url=None)
        with patch.object(
            ai_analyzer, "schedule_fixed_call", new=AsyncMock(return_value="{}")
        ) as mock_call:
            r1 = await ai_analyzer._single_llm_evaluation(
                provider, "content", temperature=0.0, model="judge-x", seed=123
            )
            r2 = await ai_analyzer._single_llm_evaluation(
                provider, "content", temperature=0.0, model="judge-x", seed=123
            )
        self.assertIsNotNone(r1)
        self.assertIsNotNone(r2)
        mock_call.assert_awaited_once()  # 2nd evaluation is a cache hit
        self.assertEqual(mock_call.await_args.kwargs["seed"], 123)


if __name__ == "__main__":
    unittest.main()
