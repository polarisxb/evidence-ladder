import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlparse

import httpx
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.adapters import router as adapters_router  # noqa: F401
from app.database import Base
from app.main import app
from app.models import Adapter, AttackCase, AttackCaseVariant, AttackResult, ScanTask
from app.schemas.adapter import AdapterCreate
from app.schemas.report import AnalysisResult
from app.services import adapter_executor, case_executor, scan_runner
from app.services.attack_engine import AttackEngine

REAL_HTTPX_ASYNC_CLIENT = httpx.AsyncClient


def _template_fixture(self, categories=None):
    return [
        {
            "id": "A-001",
            "name": "Adapter Template",
            "technique": "adapter_seed",
            "category": "prompt_injection",
            "category_name": "Prompt Injection",
            "owasp_id": "LLM01",
            "payloads": [{"text": "adapter attack payload"}],
        }
    ]


async def _fake_analyze_response(attack_type, attack_payload, target_response, context="", *, skip_confirmation=False):
    return AnalysisResult(
        attack_successful=not str(target_response).startswith("[ERROR]"),
        confidence=0.88,
        risk_level="medium",
        evidence="adapter evidence",
        leaked_info=None,
        explanation="adapter explanation",
        remediation="adapter remediation",
    )


def _fake_classify_verdict(*, attack_payload, target_response, analysis, target_config, control_assessment=None):
    return {
        "verdict_status": "rule_verified" if analysis.attack_successful else "passed",
        "verdict_reason": "adapter verdict",
        "rule_hits": [{"rule": "adapter_rule", "evidence": "adapter_evidence"}],
    }


def _fake_summarize_control_comparison(*, attack_response, control_results, analysis, target_config=None):
    return {
        "control_assessment": "attack_delta_supported" if analysis.attack_successful else "controls_missing",
        "control_summary": "adapter control summary",
    }


class FakeAdapterClient:
    requests: list[dict] = []
    created_sessions: list[str] = []
    closed_sessions: list[str] = []
    session_counter = 0

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    @classmethod
    def reset(cls):
        cls.requests = []
        cls.created_sessions = []
        cls.closed_sessions = []
        cls.session_counter = 0

    async def request(self, method, url, **kwargs):
        parsed = urlparse(url)
        path = parsed.path or "/"
        headers = dict(kwargs.get("headers") or {})
        payload = kwargs.get("json")
        timeout = kwargs.get("timeout")
        FakeAdapterClient.requests.append(
            {
                "method": method,
                "url": url,
                "path": path,
                "headers": headers,
                "json": payload,
                "timeout": timeout,
            }
        )

        if "timeout" in parsed.netloc:
            raise httpx.ReadTimeout("", request=httpx.Request(method, url))

        if path.endswith("/sessions") and method == "POST":
            if headers.get("Authorization") == "Bearer bad-token":
                return httpx.Response(401, json={"error": {"message": "invalid token"}})
            FakeAdapterClient.session_counter += 1
            session_id = f"session-{FakeAdapterClient.session_counter}"
            FakeAdapterClient.created_sessions.append(session_id)
            return httpx.Response(200, json={"data": {"sessionId": session_id}})

        if path.endswith("/chat") and method == "POST":
            if headers.get("Authorization") == "Bearer bad-token":
                return httpx.Response(401, json={"error": {"message": "invalid token"}})
            message = ""
            if isinstance(payload, dict):
                message = str(payload.get("message") or payload.get("input") or "")
                session_id = payload.get("sessionId")
                if session_id:
                    message = f"{message}::{session_id}"
            if "broken-extract" in parsed.netloc:
                return httpx.Response(200, json={"data": {"unexpected": True}})
            if "fallback-message" in parsed.netloc:
                return httpx.Response(
                    200,
                    json={"data": {"reply": "I'm experiencing technical difficulties. Please contact our support line."}},
                )
            return httpx.Response(200, json={"data": {"reply": f"echo::{message}"}})

        if path.endswith("/chat/completions") and method == "POST":
            messages = payload.get("messages", []) if isinstance(payload, dict) else []
            final_message = ""
            if messages:
                final_message = str(messages[-1].get("content") or "")
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": f"openai::{final_message}",
                                "tool_calls": [{"name": "mock_tool"}],
                            }
                        }
                    ]
                },
            )

        if "/sessions/" in path and method == "DELETE":
            FakeAdapterClient.closed_sessions.append(path.rsplit("/", 1)[-1])
            return httpx.Response(200, json={"ok": True})

        if method == "POST":
            message = payload.get("message", "") if isinstance(payload, dict) else ""
            return httpx.Response(200, text=f"legacy::{message}")

        return httpx.Response(404, json={"error": {"message": "not found"}})


def _adapter_payload(base_url: str, *, secret_ref: str = "good_token", transport: str = "http_json") -> dict:
    if transport == "openai_chat":
        invoke_config = {"method": "POST", "path": "/chat/completions", "model": "gpt-4o-mini"}
        response_extract = {
            "mode": "json_paths",
            "text_path": "$.choices[0].message.content",
            "error_path": "$.error.message",
            "tool_calls_path": "$.choices[0].message.tool_calls",
        }
    else:
        invoke_config = {
            "method": "POST",
            "path": "/chat",
            "body_template": {
                "sessionId": "{{session.id}}",
                "message": "{{input.prompt}}",
                "history": "{{input.history}}",
            },
        }
        response_extract = {
            "mode": "json_paths",
            "text_path": "$.data.reply",
            "error_path": "$.error.message",
        }

    return {
        "name": "CRM Copilot",
        "description": "Adapter test fixture",
        "mode": "direct_http_adapter",
        "transport": transport,
        "base_url": base_url,
        "auth_config": {"type": "bearer", "secret_ref": secret_ref},
        "session_config": {
            "mode": "per_variant_isolated",
            "create": {
                "method": "POST",
                "path": "/sessions",
                "extract": {"session_id": "$.data.sessionId"},
            },
            "close": {
                "method": "DELETE",
                "path": "/sessions/{{session.id}}",
            },
        },
        "invoke_config": invoke_config,
        "response_extract": response_extract,
        "enabled": True,
    }


def _safe_unlink(path: str) -> None:
    try:
        if os.path.exists(path):
            os.unlink(path)
    except PermissionError:
        pass  # Windows: SQLite file still held by aiosqlite


class Phase2AdapterRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.prev_good = os.environ.get("good_token")
        self.prev_bad = os.environ.get("bad_token")
        os.environ["good_token"] = "good-token"
        os.environ["bad_token"] = "bad-token"
        FakeAdapterClient.reset()

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.addCleanup(lambda p=tmp.name: _safe_unlink(p))
        self.db_path = tmp.name
        self.engine = create_async_engine("sqlite+aiosqlite:///" + self.db_path.replace("\\", "/"))
        self.session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        self.patchers = [
            patch.object(scan_runner, "async_session", self.session_factory),
            patch.object(case_executor, "analyze_response", _fake_analyze_response),
            patch.object(case_executor, "classify_verdict", _fake_classify_verdict),
            patch.object(case_executor, "summarize_control_comparison", _fake_summarize_control_comparison),
            patch.object(AttackEngine, "get_all_templates", _template_fixture),
            patch.object(adapter_executor.httpx, "AsyncClient", FakeAdapterClient),
        ]
        for patcher in self.patchers:
            patcher.start()

    async def asyncTearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        await self.engine.dispose()
        if self.prev_good is None:
            os.environ.pop("good_token", None)
        else:
            os.environ["good_token"] = self.prev_good
        if self.prev_bad is None:
            os.environ.pop("bad_token", None)
        else:
            os.environ["bad_token"] = self.prev_bad

    async def test_schema_rejects_unknown_variable_and_invalid_transport(self):
        with self.assertRaises(Exception):
            AdapterCreate.model_validate(
                {
                    **_adapter_payload("https://api.example.com"),
                    "transport": "grpc",
                }
            )

        with self.assertRaises(Exception):
            AdapterCreate.model_validate(
                {
                    **_adapter_payload("https://api.example.com"),
                    "invoke_config": {
                        "method": "POST",
                        "path": "/chat",
                        "body_template": {"message": "{{evil.expr}}"},
                    },
                }
            )

    async def test_adapter_test_api_reports_auth_failure(self):
        transport = ASGITransport(app=app)
        async with REAL_HTTPX_ASYNC_CLIENT(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/adapters/test",
                json={
                    "adapter": _adapter_payload("https://auth-failure.example.com", secret_ref="bad_token"),
                    "prompt": "hello",
                    "history": [],
                    "runtime_vars": {},
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()["data"]
        self.assertFalse(body["success"])
        self.assertIn("Session create failed", body["response_error"])

    async def test_adapter_test_api_reports_extract_failure(self):
        transport = ASGITransport(app=app)
        async with REAL_HTTPX_ASYNC_CLIENT(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/adapters/test",
                json={
                    "adapter": _adapter_payload("https://broken-extract.example.com"),
                    "prompt": "hello",
                    "history": [],
                    "runtime_vars": {},
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()["data"]
        self.assertFalse(body["success"])
        self.assertIn("did not match", body["response_error"])

    async def test_adapter_scan_dual_writes_and_isolates_quartet_sessions(self):
        async with self.session_factory() as session:
            adapter = Adapter(**_adapter_payload("https://scan.example.com"))
            session.add(adapter)
            await session.flush()
            task = ScanTask(
                name="adapter-scan",
                target_url=adapter.base_url,
                target_type="adapter",
                adapter_id=adapter.id,
                runtime_vars={"tenant_id": "tenant-a", "user_id": "user-a"},
                attack_categories=["all"],
                advanced_config={"enable_control_variants": True},
            )
            session.add(task)
            await session.commit()
            task_id = task.id

        await scan_runner.run_scan(task_id, {})

        async with self.session_factory() as session:
            stored_task = await session.get(ScanTask, task_id)
            cases = (await session.execute(select(AttackCase).where(AttackCase.scan_task_id == task_id))).scalars().all()
            results = (await session.execute(select(AttackResult).where(AttackResult.scan_task_id == task_id))).scalars().all()
            variants = (
                await session.execute(
                    select(AttackCaseVariant).join(AttackCase).where(AttackCase.scan_task_id == task_id)
                )
            ).scalars().all()

        self.assertEqual(stored_task.total_attacks, 1)
        self.assertEqual(stored_task.completed_attacks, 1)
        self.assertEqual(len(cases), 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(len(variants), 4)
        self.assertEqual(results[0].analysis_raw["case_summary"]["quartet_present"], True)
        self.assertEqual(stored_task.target_health, "healthy")
        self.assertTrue(stored_task.health_probe_passed)
        self.assertEqual(len(FakeAdapterClient.created_sessions), 6)
        self.assertEqual(len(FakeAdapterClient.closed_sessions), 6)

    async def test_custom_target_compatibility_auto_maps_to_minimal_adapter(self):
        async with self.session_factory() as session:
            task = ScanTask(
                name="custom-compat-scan",
                target_url="https://legacy.example.com",
                target_type="custom",
                target_config={"headers": {"X-App-Id": "compat"}},
                attack_categories=["all"],
                advanced_config={"enable_control_variants": True},
            )
            session.add(task)
            await session.commit()
            task_id = task.id

        await scan_runner.run_scan(task_id, {})

        async with self.session_factory() as session:
            result = (
                await session.execute(select(AttackResult).where(AttackResult.scan_task_id == task_id))
            ).scalar_one()

        self.assertTrue(result.target_response.startswith("legacy::adapter attack payload"))
        compat_request = next(item for item in FakeAdapterClient.requests if item["url"] == "https://legacy.example.com")
        self.assertEqual(compat_request["timeout"], adapter_executor.CUSTOM_COMPAT_TIMEOUT_S)

    async def test_custom_target_compatibility_honors_configured_timeout(self):
        FakeAdapterClient.reset()
        result = await adapter_executor.execute_adapter_request(
            adapter_executor.build_custom_compat_adapter(
                "https://legacy.example.com",
                {"headers": {"X-App-Id": "compat"}, "timeout_s": 75},
            ),
            prompt="hello",
            history=[],
            runtime_vars={},
            scan_id="scan-1",
            case_id="case-1",
            variant_type="attack",
        )

        self.assertTrue(result["success"])
        compat_request = next(item for item in FakeAdapterClient.requests if item["url"] == "https://legacy.example.com")
        self.assertEqual(compat_request["timeout"], 75.0)

    async def test_adapter_timeout_error_retains_non_empty_detail(self):
        result = await adapter_executor.execute_adapter_request(
            AdapterCreate.model_validate(_adapter_payload("https://timeout.example.com")),
            prompt="chat prompt",
            history=[],
            runtime_vars={},
            scan_id="scan-1",
            case_id="case-1",
            variant_type="attack",
        )

        self.assertFalse(result["success"])
        self.assertEqual(result["response_error"], "Request timed out")

    async def test_known_fallback_response_becomes_not_evaluable_without_calling_judge(self):
        """When every response matches a known fallback signature, every case is
        screened as ``not_evaluable`` before the judge is invoked.

        The preflight probe flags the target as ``unhealthy`` (diagnostic
        banner only) but the scan still runs every case. Both the adaptive
        pre-analysis and the final analysis short-circuit on
        ``not_evaluable`` responses, so ``analyze_response`` is never called.
        Cases are still persisted (with ``attack_successful=False``) so the
        user sees the scan completed and why every case was non-evaluable.
        """
        async with self.session_factory() as session:
            adapter = Adapter(**_adapter_payload("https://fallback-message.example.com"))
            session.add(adapter)
            await session.flush()
            task = ScanTask(
                name="adapter-fallback-scan",
                target_url=adapter.base_url,
                target_type="adapter",
                adapter_id=adapter.id,
                attack_categories=["all"],
            )
            session.add(task)
            await session.commit()
            task_id = task.id

        with patch.object(case_executor, "analyze_response", side_effect=AssertionError("judge should not run")):
            await scan_runner.run_scan(task_id, {})

        async with self.session_factory() as session:
            refreshed = await session.get(ScanTask, task_id)
            results = (
                await session.execute(select(AttackResult).where(AttackResult.scan_task_id == task_id))
            ).scalars().all()

        # Preflight banner still surfaces the unhealthy classification.
        self.assertEqual(refreshed.target_health, "unhealthy")
        self.assertFalse(refreshed.health_probe_passed)
        # But the scan was NOT aborted — every case ran and counters aligned.
        self.assertEqual(refreshed.completed_attacks, refreshed.total_attacks)
        self.assertEqual(refreshed.status, "completed")
        # Cases are persisted as non-evaluable (no successful attacks).
        self.assertGreater(len(results), 0)
        for result in results:
            self.assertFalse(result.attack_successful)

    async def test_openai_chat_adapter_test_path_succeeds(self):
        result = await adapter_executor.execute_adapter_request(
            AdapterCreate.model_validate(_adapter_payload("https://openai.example.com", transport="openai_chat")),
            prompt="chat prompt",
            history=[{"role": "assistant", "content": "history item"}],
            runtime_vars={"tenant_id": "tenant"},
            scan_id="scan-1",
            case_id="case-1",
            variant_type="attack",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["response_text"], "openai::chat prompt")
