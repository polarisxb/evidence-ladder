"""``extra_body`` passthrough for OpenAI-compatible providers.

DeepSeek V4 and Qwen3.5 default to thinking mode and expose the switch as a
non-OpenAI request field; the platform must be able to forward it verbatim.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.config import Settings
from app.services import llm_client
from app.services.llm_client import ProviderClientInfo, _call_openai_compatible


class _RecordingCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])


class _RecordingClient:
    def __init__(self, *args, **kwargs) -> None:
        self.chat = SimpleNamespace(completions=_RecordingCompletions())


class ExtraBodyPassthroughTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        llm_client._openai_clients.clear()

    async def _call(self, info: ProviderClientInfo) -> dict:
        with patch("openai.AsyncOpenAI", _RecordingClient):
            await _call_openai_compatible(
                info,
                "deepseek-v4-flash",
                [{"role": "user", "content": "hi"}],
                max_tokens=16,
                temperature=0.0,
                json_mode=True,
            )
        client = llm_client._openai_clients[(info.api_key, info.base_url)]
        return client.chat.completions.calls[0]

    async def test_extra_body_is_forwarded_verbatim(self):
        info = ProviderClientInfo(
            provider_type="deepseek",
            api_key="test-key-extra",
            base_url="https://api.deepseek.com",
            extra={"extra_body": {"thinking": {"type": "disabled"}}},
        )
        kwargs = await self._call(info)
        self.assertEqual(kwargs["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertEqual(kwargs["response_format"], {"type": "json_object"})

    async def test_no_extra_body_when_unset(self):
        info = ProviderClientInfo(
            provider_type="deepseek",
            api_key="test-key-plain",
            base_url="https://api.deepseek.com",
        )
        kwargs = await self._call(info)
        self.assertNotIn("extra_body", kwargs)

    def test_settings_parse_and_reject_extra_body_json(self):
        ok = Settings(_env_file=None, openai_extra_body_json='{"thinking": {"type": "disabled"}}')
        self.assertEqual(ok.openai_extra_body, {"thinking": {"type": "disabled"}})

        empty = Settings(_env_file=None, openai_extra_body_json="   ")
        self.assertIsNone(empty.openai_extra_body)

        with self.assertRaises(ValueError):
            Settings(_env_file=None, openai_extra_body_json="[1, 2]")

    def test_platform_provider_carries_extra_body(self):
        fake = Settings(_env_file=None, openai_api_key="k", openai_extra_body_json='{"thinking": {"type": "disabled"}}')
        with patch("app.config.settings", fake):
            info = llm_client.make_platform_provider()
        self.assertEqual(info.extra.get("extra_body"), {"thinking": {"type": "disabled"}})

    async def test_builtin_vulnerable_target_carries_platform_extra_body(self):
        # The builtin target calls the platform provider directly. Without the
        # switch, DeepSeek V4 spends max_tokens on reasoning and returns "".
        from app.services import vulnerable_ai

        for extra_json, expected in (('{"thinking": {"type": "disabled"}}', {"thinking": {"type": "disabled"}}), (None, None)):
            fake = Settings(_env_file=None, openai_api_key="k", openai_extra_body_json=extra_json)
            client = _RecordingClient()
            with patch.object(vulnerable_ai, "settings", fake), \
                    patch.object(vulnerable_ai, "get_platform_openai_client", lambda: client):
                reply = await vulnerable_ai.chat_with_vulnerable_ai("hi", level=1)
            self.assertEqual(reply, "ok")
            self.assertEqual(client.chat.completions.calls[0].get("extra_body"), expected)


if __name__ == "__main__":
    unittest.main()
