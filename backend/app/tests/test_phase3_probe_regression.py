import os
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import httpx
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app
from app.models import Adapter, AttackCase, AttackResult, ScanTask
from app.schemas.adapter import AdapterCreate
from app.schemas.report import AnalysisResult
from app.services import adapter_executor, case_executor, probe_executor, scan_runner
from app.services.attack_engine import AttackEngine

REAL_HTTPX_ASYNC_CLIENT = httpx.AsyncClient
ANALYZER_UNAUTHORIZED_ACTION_CLAIM = False


def _template_fixture(self, categories=None):
    return [
        {
            "id": "P3-001",
            "name": "Probe Template",
            "technique": "probe_seed",
            "category": "prompt_injection",
            "category_name": "Prompt Injection",
            "owasp_id": "LLM01",
            "payloads": [{"text": "probe attack payload"}],
        }
    ]


async def _fake_analyze_response(attack_type, attack_payload, target_response, context="", *, skip_confirmation=False):
    return AnalysisResult(
        attack_successful=not str(target_response).startswith("[ERROR]"),
        confidence=0.9,
        risk_level="high",
        evidence="probe evidence",
        leaked_info=None,
        explanation="probe explanation",
        remediation="probe remediation",
        behavior_flags={"unauthorized_action_claim": ANALYZER_UNAUTHORIZED_ACTION_CLAIM},
    )


def _fake_classify_verdict(*, attack_payload, target_response, analysis, target_config, control_assessment=None, **kwargs):
    return {
        "verdict_status": "rule_verified" if analysis.attack_successful else "passed",
        "verdict_reason": "probe verdict",
        "rule_hits": [{"rule": "probe_rule", "evidence": "probe_evidence"}],
    }


def _fake_summarize_control_comparison(*, attack_response, control_results, analysis, target_config=None):
    return {
        "control_assessment": "attack_delta_supported" if analysis.attack_successful else "controls_missing",
        "control_summary": "probe control summary",
    }


class FakeProbeWebSocket:
    def __init__(self):
        self.events: list[dict] = []

    async def send_json(self, data):
        self.events.append(data)


class FakeProbeClient:
    session_counter = 0
    created_sessions: list[str] = []
    closed_sessions: list[str] = []
    requests: list[dict] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    @classmethod
    def reset(cls):
        cls.session_counter = 0
        cls.created_sessions = []
        cls.closed_sessions = []
        cls.requests = []

    async def request(self, method, url, **kwargs):
        parsed = urlparse(url)
        path = parsed.path or "/"
        headers = dict(kwargs.get("headers") or {})
        payload = kwargs.get("json")
        query = parse_qs(parsed.query)
        FakeProbeClient.requests.append(
            {
                "method": method,
                "url": url,
                "path": path,
                "headers": headers,
                "json": payload,
                "query": query,
            }
        )

        if "timeout" in parsed.netloc:
            raise httpx.TimeoutException("probe timeout")

        if headers.get("Authorization") == "Bearer bad-token":
            return httpx.Response(401, json={"error": {"message": "invalid token"}})

        if path.endswith("/sessions") and method == "POST":
            FakeProbeClient.session_counter += 1
            session_id = f"session-{FakeProbeClient.session_counter}"
            FakeProbeClient.created_sessions.append(session_id)
            return httpx.Response(200, json={"data": {"sessionId": session_id}})

        if "/sessions/" in path and method == "DELETE":
            FakeProbeClient.closed_sessions.append(path.rsplit("/", 1)[-1])
            return httpx.Response(200, json={"ok": True})

        if path.endswith("/chat") and method == "POST":
            message = payload.get("message", "") if isinstance(payload, dict) else ""
            session_id = payload.get("sessionId") if isinstance(payload, dict) else None
            suffix = f"::{session_id}" if session_id else ""
            return httpx.Response(200, json={"data": {"reply": f"echo::{message}{suffix}"}})

        if path.endswith("/probe/check") and method == "GET":
            tenant = query.get("tenant", ["unknown"])[0]
            return httpx.Response(200, json={"data": {"verified": True, "message": f"probe-ok::{tenant}"}})

        if path.endswith("/probe/extract-broken") and method == "GET":
            return httpx.Response(200, json={"data": {"unexpected": True}})

        if path.endswith("/probe/bootstrap") and method == "GET":
            return httpx.Response(200, json={"data": {"resourceId": "res-123"}})

        if "/probe/status/" in path and method == "GET":
            resource_id = path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={"data": {"resourceId": resource_id, "status": "done"}})

        return httpx.Response(404, json={"error": {"message": "not found"}})


def _default_probe_config():
    return {
        "enabled": True,
        "steps": [
            {
                "name": "check_effect",
                "method": "GET",
                "path": "/probe/check",
                "query": {"tenant": "{{runtime.tenant_id}}"},
                "captures": {
                    "message": {"json_path": "$.data.message"},
                },
            }
        ],
        "assertions": [
            {
                "type": "status_code_is",
                "step": "check_effect",
                "status_code": 200,
            },
            {
                "type": "json_path_equals",
                "step": "check_effect",
                "path": "$.data.verified",
                "expected": True,
            },
            {
                "type": "text_contains",
                "step": "check_effect",
                "contains": "probe-ok",
            },
        ],
    }


def _adapter_payload(base_url: str, *, secret_ref: str = "good_token", include_probe: bool = True) -> dict:
    payload = {
        "name": "Probe Adapter",
        "description": "Phase 3 probe fixture",
        "mode": "direct_http_adapter",
        "transport": "http_json",
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
        "invoke_config": {
            "method": "POST",
            "path": "/chat",
            "body_template": {
                "sessionId": "{{session.id}}",
                "message": "{{input.prompt}}",
                "history": "{{input.history}}",
            },
        },
        "response_extract": {
            "mode": "json_paths",
            "text_path": "$.data.reply",
            "error_path": "$.error.message",
        },
        "enabled": True,
    }
    if include_probe:
        payload["probe_config"] = _default_probe_config()
    return payload


class Phase3ProbeRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        global ANALYZER_UNAUTHORIZED_ACTION_CLAIM
        ANALYZER_UNAUTHORIZED_ACTION_CLAIM = False

        self.prev_good = os.environ.get("good_token")
        self.prev_bad = os.environ.get("bad_token")
        os.environ["good_token"] = "good-token"
        os.environ["bad_token"] = "bad-token"
        FakeProbeClient.reset()

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

        async def _override_get_db():
            async with self.session_factory() as session:
                yield session

        app.dependency_overrides[get_db] = _override_get_db

        self.patchers = [
            patch.object(scan_runner, "async_session", self.session_factory),
            patch.object(case_executor, "analyze_response", _fake_analyze_response),
            patch.object(case_executor, "classify_verdict", _fake_classify_verdict),
            patch.object(case_executor, "summarize_control_comparison", _fake_summarize_control_comparison),
            patch.object(AttackEngine, "get_all_templates", _template_fixture),
            patch.object(adapter_executor.httpx, "AsyncClient", FakeProbeClient),
            patch.object(probe_executor.httpx, "AsyncClient", FakeProbeClient),
        ]
        for patcher in self.patchers:
            patcher.start()

    async def asyncTearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        app.dependency_overrides.pop(get_db, None)
        await self.engine.dispose()
        try:
            if os.path.exists(self.db_path):
                os.unlink(self.db_path)
        except PermissionError:
            pass  # Windows: SQLite file still held by aiosqlite
        if self.prev_good is None:
            os.environ.pop("good_token", None)
        else:
            os.environ["good_token"] = self.prev_good
        if self.prev_bad is None:
            os.environ.pop("bad_token", None)
        else:
            os.environ["bad_token"] = self.prev_bad

    async def _create_adapter_scan(self, *, adapter_payload: dict, runtime_vars: dict | None = None) -> str:
        async with self.session_factory() as session:
            adapter = Adapter(**adapter_payload)
            session.add(adapter)
            await session.flush()
            task = ScanTask(
                name="phase3-adapter-scan",
                target_url=adapter.base_url,
                target_type="adapter",
                adapter_id=adapter.id,
                runtime_vars=runtime_vars or {"tenant_id": "tenant-a"},
                attack_categories=["all"],
                advanced_config={"enable_control_variants": True},
            )
            session.add(task)
            await session.commit()
            return task.id

    async def test_probe_schema_rejects_illegal_probe_variable(self):
        with self.assertRaises(Exception):
            AdapterCreate.model_validate(
                {
                    **_adapter_payload("https://probe.example.com"),
                    "probe_config": {
                        "enabled": True,
                        "steps": [
                            {
                                "name": "bad_step",
                                "method": "GET",
                                "path": "/probe/check",
                                "query": {"raw": "{{probe.steps.bootstrap.raw}}"},
                            }
                        ],
                        "assertions": [{"type": "status_code_is", "step": "bad_step", "status_code": 200}],
                    },
                }
            )

    async def test_probe_test_requires_stored_or_override_probe_config(self):
        transport = ASGITransport(app=app)
        async with REAL_HTTPX_ASYNC_CLIENT(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/adapters/probe/test",
                json={
                    "adapter": _adapter_payload("https://probe.example.com", include_probe=False),
                    "runtime_vars": {"tenant_id": "tenant-a"},
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("probe_config is required", response.text)

    async def test_probe_test_api_succeeds_for_single_step_probe(self):
        transport = ASGITransport(app=app)
        async with REAL_HTTPX_ASYNC_CLIENT(transport=transport, base_url="http://testserver") as client:
            response = await client.post(
                "/api/v1/adapters/probe/test",
                json={
                    "adapter": _adapter_payload("https://probe.example.com"),
                    "runtime_vars": {"tenant_id": "tenant-a"},
                    "session_id": "session-inline",
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()["data"]
        self.assertTrue(body["verified"])
        self.assertEqual(body["failure_type"], None)
        self.assertEqual(len(body["assertion_results"]), 3)
        self.assertGreaterEqual(len(body["evidence"]), 2)
        self.assertEqual(body["step_results"][0]["status_code"], 200)

    async def test_probe_executor_supports_multistep_capture_flow(self):
        result = await probe_executor.execute_probe(
            AdapterCreate.model_validate(_adapter_payload("https://probe.example.com")),
            probe_config={
                "enabled": True,
                "steps": [
                    {
                        "name": "bootstrap",
                        "method": "GET",
                        "path": "/probe/bootstrap",
                        "captures": {"resource_id": {"json_path": "$.data.resourceId"}},
                    },
                    {
                        "name": "status",
                        "method": "GET",
                        "path": "/probe/status/{{probe.steps.bootstrap.captures.resource_id}}",
                    },
                ],
                "assertions": [
                    {"type": "status_code_is", "step": "status", "status_code": 200},
                    {"type": "json_path_equals", "step": "status", "path": "$.data.resourceId", "expected": "res-123"},
                ],
            },
            runtime_vars={"tenant_id": "tenant-a"},
            session_id="probe-session",
            scan_id="scan-1",
            case_id="case-1",
            variant_type="attack",
        )

        self.assertTrue(result.verified)
        self.assertEqual(result.step_results[0].captures["resource_id"], "res-123")
        self.assertEqual(result.step_results[1].status_code, 200)

    async def test_probe_failures_are_classified(self):
        auth_result = await probe_executor.execute_probe(
            AdapterCreate.model_validate(_adapter_payload("https://probe.example.com", secret_ref="bad_token")),
            runtime_vars={"tenant_id": "tenant-a"},
            session_id="probe-session",
            scan_id="scan-1",
            case_id="case-1",
            variant_type="attack",
        )
        self.assertFalse(auth_result.verified)
        self.assertEqual(auth_result.failure_type, "auth_error")

        extract_result = await probe_executor.execute_probe(
            AdapterCreate.model_validate(_adapter_payload("https://probe.example.com")),
            probe_config={
                "enabled": True,
                "steps": [
                    {
                        "name": "broken_extract",
                        "method": "GET",
                        "path": "/probe/extract-broken",
                        "captures": {"resource_id": {"json_path": "$.data.resourceId"}},
                    }
                ],
                "assertions": [{"type": "status_code_is", "step": "broken_extract", "status_code": 200}],
            },
            runtime_vars={"tenant_id": "tenant-a"},
            session_id="probe-session",
            scan_id="scan-1",
            case_id="case-1",
            variant_type="attack",
        )
        self.assertFalse(extract_result.verified)
        self.assertEqual(extract_result.failure_type, "extract_error")

        timeout_result = await probe_executor.execute_probe(
            AdapterCreate.model_validate(_adapter_payload("https://timeout.example.com")),
            runtime_vars={"tenant_id": "tenant-a"},
            session_id="probe-session",
            scan_id="scan-1",
            case_id="case-1",
            variant_type="attack",
        )
        self.assertFalse(timeout_result.verified)
        self.assertEqual(timeout_result.failure_type, "timeout")

    async def test_adapter_scan_persists_probe_verified_and_read_paths(self):
        task_id = await self._create_adapter_scan(
            adapter_payload=_adapter_payload("https://probe.example.com"),
            runtime_vars={"tenant_id": "tenant-a"},
        )
        ws = FakeProbeWebSocket()

        await scan_runner.run_scan(task_id, {task_id: [ws]})

        async with self.session_factory() as session:
            attack_case = (
                await session.execute(select(AttackCase).where(AttackCase.scan_task_id == task_id))
            ).scalar_one()
            legacy_result = (
                await session.execute(select(AttackResult).where(AttackResult.scan_task_id == task_id))
            ).scalar_one()

        self.assertEqual(attack_case.business_verification_status, "probe_verified")
        self.assertIsInstance(attack_case.probe_summary, dict)
        self.assertIsInstance(attack_case.probe_evidence_json, dict)
        self.assertEqual(legacy_result.analysis_raw["business_verification_status"], "probe_verified")
        self.assertIn("probe_summary", legacy_result.analysis_raw)
        self.assertTrue(any(event.get("probe_runtime_state") == "pending" for event in ws.events))
        self.assertTrue(any(event.get("probe_runtime_state") == "verified" for event in ws.events))

        transport = ASGITransport(app=app)
        async with REAL_HTTPX_ASYNC_CLIENT(transport=transport, base_url="http://testserver") as client:
            cases_response = await client.get(f"/api/v1/scans/{task_id}/cases")
            self.assertEqual(cases_response.status_code, 200)
            case_row = cases_response.json()["data"][0]
            self.assertEqual(case_row["business_verification_status"], "probe_verified")
            self.assertTrue(case_row["probe_evidence_preview"])

            case_detail_response = await client.get(f"/api/v1/cases/{attack_case.id}")
            self.assertEqual(case_detail_response.status_code, 200)
            self.assertIsInstance(case_detail_response.json()["data"]["probe_evidence_json"], dict)

            results_response = await client.get(f"/api/v1/reports/{task_id}/results")
            self.assertEqual(results_response.status_code, 200)
            result_row = results_response.json()["data"][0]
            self.assertEqual(result_row["business_verification_status"], "probe_verified")
            self.assertTrue(result_row["probe_evidence_preview"])

    async def test_scan_without_probe_falls_back_to_text_claim_only(self):
        global ANALYZER_UNAUTHORIZED_ACTION_CLAIM
        ANALYZER_UNAUTHORIZED_ACTION_CLAIM = True
        task_id = await self._create_adapter_scan(
            adapter_payload=_adapter_payload("https://probe.example.com", include_probe=False),
            runtime_vars={"tenant_id": "tenant-a"},
        )

        await scan_runner.run_scan(task_id, {})

        async with self.session_factory() as session:
            attack_case = (
                await session.execute(select(AttackCase).where(AttackCase.scan_task_id == task_id))
            ).scalar_one()
            legacy_result = (
                await session.execute(select(AttackResult).where(AttackResult.scan_task_id == task_id))
            ).scalar_one()

        self.assertEqual(attack_case.business_verification_status, "text_claim_only")
        self.assertEqual(legacy_result.analysis_raw["business_verification_status"], "text_claim_only")
        self.assertEqual(attack_case.probe_summary["status"], "text_claim_only")

    async def test_scan_without_probe_claim_falls_back_to_not_applicable(self):
        global ANALYZER_UNAUTHORIZED_ACTION_CLAIM
        ANALYZER_UNAUTHORIZED_ACTION_CLAIM = False
        task_id = await self._create_adapter_scan(
            adapter_payload=_adapter_payload("https://probe.example.com", include_probe=False),
            runtime_vars={"tenant_id": "tenant-a"},
        )

        await scan_runner.run_scan(task_id, {})

        async with self.session_factory() as session:
            attack_case = (
                await session.execute(select(AttackCase).where(AttackCase.scan_task_id == task_id))
            ).scalar_one()

        self.assertEqual(attack_case.business_verification_status, "not_applicable")
