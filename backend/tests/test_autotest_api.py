import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestAutoTestPlanEndpoint:
    async def test_create_small_plan(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/autotest/plan", json={
            "target_type": "openai_compatible",
            "attack_categories": ["prompt_injection"],
            "budget": "small",
        })

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["plan"]["budget"] == "small"
        assert data["plan"]["risk_categories"] == ["prompt_injection"]
        assert "template_scan" in data["plan"]["phases"]
        assert "pair" not in data["plan"]["strategies"]

    async def test_adapter_probe_is_reflected_in_plan(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/autotest/plan", json={
            "target_type": "adapter",
            "budget": "full",
            "adapter": {"probe_config": {"enabled": True}},
        })

        assert resp.status_code == 200
        plan = resp.json()["data"]["plan"]
        assert plan["probe_available"] is True
        assert "probe_verification" in plan["phases"]
        assert "tap" in plan["strategies"]

    async def test_invalid_budget_is_rejected(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/autotest/plan", json={
            "target_type": "openai_compatible",
            "budget": "huge",
        })

        assert resp.status_code == 422

    async def test_create_builtin_scan_draft(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/autotest/draft", json={
            "name": "Evidence draft",
            "target_type": "builtin_vulnerable",
            "attack_categories": ["jailbreak"],
            "budget": "small",
        })

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["plan"]["budget"] == "small"
        assert data["scan_config"]["name"] == "Evidence draft"
        assert data["scan_config"]["target_type"] == "builtin_vulnerable"
        assert data["scan_config"]["target_url"] == "builtin"
        assert data["scan_config"]["advanced"]["quartet_mode"] == "full"

    async def test_adapter_scan_draft_requires_adapter_id(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/autotest/draft", json={
            "target_type": "adapter",
            "budget": "full",
        })

        assert resp.status_code == 422
