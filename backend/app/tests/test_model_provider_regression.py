import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.scans import create_scan
from app.api.model_providers import test_provider as run_provider_test
from app.database import Base
from app.core.exceptions import AppException
from app.models import ScanTask
from app.models.model_provider import ModelProvider
from app.schemas.scan import ScanCreate, TargetConfig
from app.services.llm_client import LLMAPIError


def _safe_unlink(path: str) -> None:
    try:
        if os.path.exists(path):
            os.unlink(path)
    except PermissionError:
        pass


class _FakeChatCompletions:
    def __init__(self, expected_model: str):
        self.expected_model = expected_model

    async def create(self, *, model, messages, max_tokens):
        if model != self.expected_model:
            raise AssertionError(f"Expected model {self.expected_model}, got {model}")
        return SimpleNamespace(model=model, choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])


class _FakeOpenAIClient:
    def __init__(self, expected_model: str):
        self.chat = SimpleNamespace(completions=_FakeChatCompletions(expected_model))


class ModelProviderRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.db_path = tmp.name
        self.engine = create_async_engine("sqlite+aiosqlite:///" + self.db_path.replace("\\", "/"))
        self.session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()
        _safe_unlink(self.db_path)

    async def test_non_openai_provider_without_saved_model_auto_detects_model(self):
        async with self.session_factory() as session:
            provider = ModelProvider(
                name="Qwen",
                provider_type="qwen",
                api_key="test-key",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                judge_model=None,
                mini_model=None,
                enabled=True,
            )
            session.add(provider)
            await session.commit()
            await session.refresh(provider)

            with patch(
                "app.api.model_providers._fetch_openai_compatible_model_ids",
                return_value=["qwen-plus", "qwen-turbo"],
            ), patch(
                "openai.AsyncOpenAI",
                return_value=_FakeOpenAIClient("qwen-plus"),
            ):
                result = await run_provider_test(provider.id, session)

        self.assertTrue(result["data"]["connected"])
        self.assertEqual(result["data"]["model"], "qwen-plus")
        self.assertEqual(result["data"]["resolved_model"], "qwen-plus")
        self.assertTrue(result["data"]["auto_detected_model"])

    async def test_non_openai_provider_without_detectable_model_returns_clear_error(self):
        async with self.session_factory() as session:
            provider = ModelProvider(
                name="Qwen",
                provider_type="qwen",
                api_key="test-key",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                judge_model=None,
                mini_model=None,
                enabled=True,
            )
            session.add(provider)
            await session.commit()
            await session.refresh(provider)

            with patch(
                "app.api.model_providers._fetch_openai_compatible_model_ids",
                return_value=[],
            ):
                result = await run_provider_test(provider.id, session)

        self.assertFalse(result["data"]["connected"])
        self.assertIn(
            "Unable to auto-detect models for this provider",
            result["data"]["error"],
        )

    async def test_create_scan_resolves_provider_models_when_left_auto(self):
        async with self.session_factory() as session:
            provider = ModelProvider(
                name="Qwen",
                provider_type="qwen",
                api_key="test-key",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                judge_model=None,
                mini_model=None,
                enabled=True,
            )
            session.add(provider)
            await session.commit()
            await session.refresh(provider)

            with patch(
                "app.api.scans.get_provider_by_id",
                side_effect=[
                    (SimpleNamespace(provider_type="qwen", api_key="test-key", base_url=provider.base_url), "qwen-plus"),
                    (SimpleNamespace(provider_type="qwen", api_key="test-key", base_url=provider.base_url), "qwen-plus"),
                    (SimpleNamespace(provider_type="qwen", api_key="test-key", base_url=provider.base_url), "qwen-plus"),
                ],
            ), patch(
                "app.api.scans.fetch_openai_compatible_model_ids",
                return_value=["qwen-plus", "qwen-turbo"],
            ), patch(
                "app.api.scans.call_chat",
                new=AsyncMock(return_value="ok"),
            ):
                response = await create_scan(
                    ScanCreate(
                        name="auto model scan",
                        target_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                        target_type="openai_compatible",
                        target_config=TargetConfig(provider_id=provider.id),
                        attack_categories=["prompt_injection"],
                        judge_provider_id=provider.id,
                        generation_provider_id=provider.id,
                    ),
                    BackgroundTasks(),
                    session,
                )

            task_id = response["data"]["task_id"]
            task = await session.get(ScanTask, task_id)

        self.assertIsNotNone(task)
        assert task is not None
        self.assertEqual(task.judge_model, "qwen-plus")
        self.assertEqual(task.generation_model, "qwen-plus")
        self.assertEqual(task.target_config["model"], "qwen-plus")

    async def test_create_scan_rejects_provider_model_mismatch(self):
        async with self.session_factory() as session:
            provider = ModelProvider(
                name="Qwen",
                provider_type="qwen",
                api_key="test-key",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                judge_model=None,
                mini_model=None,
                enabled=True,
            )
            session.add(provider)
            await session.commit()
            await session.refresh(provider)

            with patch(
                "app.api.scans.get_provider_by_id",
                return_value=(
                    SimpleNamespace(provider_type="qwen", api_key="test-key", base_url=provider.base_url),
                    "qwen-plus",
                ),
            ), patch(
                "app.api.scans.fetch_openai_compatible_model_ids",
                return_value=["qwen-plus", "qwen-turbo"],
            ):
                with self.assertRaises(AppException) as ctx:
                    await create_scan(
                        ScanCreate(
                            name="mismatched provider model scan",
                            target_url="http://localhost:8002/chat",
                            target_type="custom",
                            target_config=TargetConfig(),
                            attack_categories=["prompt_injection"],
                            judge_provider_id=provider.id,
                            judge_model="glm-5.1",
                        ),
                        BackgroundTasks(),
                        session,
                    )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("not available for selected provider", ctx.exception.detail)

    async def test_create_scan_rejects_listed_but_unusable_provider_model(self):
        async with self.session_factory() as session:
            provider = ModelProvider(
                name="Qwen",
                provider_type="qwen",
                api_key="test-key",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                judge_model=None,
                mini_model=None,
                enabled=True,
            )
            session.add(provider)
            await session.commit()
            await session.refresh(provider)

            with patch(
                "app.api.scans.get_provider_by_id",
                return_value=(
                    SimpleNamespace(provider_type="qwen", api_key="test-key", base_url=provider.base_url),
                    "glm-5.1",
                ),
            ), patch(
                "app.api.scans.fetch_openai_compatible_model_ids",
                return_value=["glm-5.1", "qwen-plus"],
            ), patch(
                "app.api.scans.call_chat",
                new=AsyncMock(side_effect=LLMAPIError("API error from qwen: product is not activated")),
            ):
                with self.assertRaises(AppException) as ctx:
                    await create_scan(
                        ScanCreate(
                            name="unusable provider model scan",
                            target_url="http://localhost:8002/chat",
                            target_type="custom",
                            target_config=TargetConfig(),
                            attack_categories=["prompt_injection"],
                            judge_provider_id=provider.id,
                            judge_model="glm-5.1",
                        ),
                        BackgroundTasks(),
                        session,
                    )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("failed provider probe", ctx.exception.detail)

    async def test_create_scan_rejects_custom_openai_target_without_model(self):
        async with self.session_factory() as session:
            with self.assertRaises(AppException) as ctx:
                await create_scan(
                    ScanCreate(
                        name="custom target without model",
                        target_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                        target_type="openai_compatible",
                        target_config=TargetConfig(api_key="test-key"),
                        attack_categories=["prompt_injection"],
                    ),
                    BackgroundTasks(),
                    session,
                )

        self.assertIn("explicit model", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
