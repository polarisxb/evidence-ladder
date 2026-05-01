"""Basic API endpoint smoke tests."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthEndpoint:
    async def test_health(self, client: AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200


class TestSettingsEndpoint:
    async def test_get_settings(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/settings")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "openai_model" in data
        assert "database_url" in data


class TestTemplatesEndpoint:
    async def test_list_templates(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/templates")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data, list)
        assert len(data) > 0

    async def test_get_category(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/templates/jailbreak")
        assert resp.status_code == 200

    async def test_invalid_category_404(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/templates/nonexistent_category")
        assert resp.status_code == 404


class TestScansEndpoint:
    async def test_list_scans(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/scans")
        assert resp.status_code == 200

    async def test_create_scan_builtin(self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
        async def noop_run_scan(*_args, **_kwargs) -> None:
            return None

        monkeypatch.setattr("app.api.scans.run_scan", noop_run_scan)

        resp = await client.post("/api/v1/scans", json={
            "name": "Test Scan",
            "target_type": "builtin_vulnerable",
            "target_url": "builtin",
            "target_config": {"vulnerable_level": 1},
            "attack_categories": ["jailbreak"],
        })
        assert resp.status_code == 200
        assert "task_id" in resp.json()["data"]


class TestModelProvidersEndpoint:
    async def test_list_providers(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/model-providers")
        assert resp.status_code == 200
        assert isinstance(resp.json()["data"], list)
