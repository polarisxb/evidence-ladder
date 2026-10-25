"""Sample adapters for the bundled agent targets can be imported without the CLI.

MailBot and ShopBot only produce tool-log (E4) and business-probe (E5) evidence
when scanned through their adapter. The definitions used to be reachable only
through the undocumented ``seed_*_adapter`` scripts; the Adapters page and the
New Scan presets now import them through ``/adapters/samples``.
"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.database import async_session
from app.main import app
from app.models import Adapter
from app.scripts import seed_mailbot_adapter

pytestmark = pytest.mark.anyio

SAMPLE_NAMES = ("mailbot-agent", "shopbot-agent")


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch):
    # Pin the mock-target addresses so a developer .env cannot change them.
    monkeypatch.setattr("app.config.settings.mock_financebot_url", "http://localhost:8001")
    monkeypatch.setattr("app.config.settings.mock_shopbot_url", "http://localhost:8002")
    monkeypatch.setattr("app.config.settings.mock_mailbot_url", "http://localhost:8003")

    async def _drop_samples():
        async with async_session() as db:
            await db.execute(delete(Adapter).where(Adapter.name.in_(SAMPLE_NAMES)))
            await db.commit()

    await _drop_samples()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await _drop_samples()


async def _samples(client: AsyncClient) -> dict[str, dict]:
    resp = await client.get("/api/v1/adapters/samples")
    assert resp.status_code == 200
    return {item["key"]: item for item in resp.json()["data"]}


async def test_samples_list_points_at_configured_mock_targets(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.config.settings.mock_mailbot_url", "http://127.0.0.1:18003")

    samples = await _samples(client)

    assert set(samples) == {"mailbot", "shopbot"}
    assert samples["mailbot"]["name"] == "mailbot-agent"
    assert samples["mailbot"]["base_url"] == "http://127.0.0.1:18003"
    assert samples["shopbot"]["base_url"] == "http://localhost:8002"
    assert samples["mailbot"]["has_probe"] is True
    assert samples["mailbot"]["installed_adapter_id"] is None


async def test_install_creates_adapter_once_and_keeps_user_edits(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.config.settings.mock_mailbot_url", "http://127.0.0.1:18003")

    first = await client.post("/api/v1/adapters/samples/mailbot/install")
    assert first.status_code == 200
    body = first.json()["data"]
    assert body["created"] is True
    adapter = body["adapter"]
    assert adapter["name"] == "mailbot-agent"
    assert adapter["base_url"] == "http://127.0.0.1:18003"
    assert adapter["invoke_config"]["query"] == {"format": "json"}
    assert adapter["response_extract"]["tool_calls_path"] == "$.tool_calls"
    assert adapter["probe_config"]["steps"][0]["path"] == "/audit/email-ops"

    patched = await client.patch(f"/api/v1/adapters/{adapter['id']}", json={"enabled": False})
    assert patched.status_code == 200

    second = await client.post("/api/v1/adapters/samples/mailbot/install")
    assert second.status_code == 200
    again = second.json()["data"]
    assert again["created"] is False
    assert again["adapter"]["id"] == adapter["id"]
    assert again["adapter"]["enabled"] is False  # import never overwrites an existing adapter

    samples = await _samples(client)
    assert samples["mailbot"]["installed_adapter_id"] == adapter["id"]
    assert samples["mailbot"]["installed_enabled"] is False


async def test_seed_script_resets_existing_sample_to_fixture(client: AsyncClient) -> None:
    installed = (await client.post("/api/v1/adapters/samples/mailbot/install")).json()["data"]["adapter"]
    await client.patch(f"/api/v1/adapters/{installed['id']}", json={"enabled": False})

    adapter_id = await seed_mailbot_adapter.seed_adapter(seed_mailbot_adapter.DEFAULT_FIXTURE)

    assert adapter_id == installed["id"]
    reset = (await client.get(f"/api/v1/adapters/{adapter_id}")).json()["data"]
    assert reset["enabled"] is True
    assert reset["base_url"] == "http://localhost:8003"


async def test_unknown_sample_is_404(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/adapters/samples/financebot/install")
    assert resp.status_code == 404


async def test_mock_targets_report_configured_addresses(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.config.settings.mock_financebot_url", "http://financebot:8001")

    resp = await client.get("/api/v1/targets/mock")

    assert resp.status_code == 200
    targets = {item["key"]: item for item in resp.json()["data"]}
    assert targets["financebot"] == {
        "key": "financebot",
        "base_url": "http://financebot:8001",
        "chat_url": "http://financebot:8001/chat",
        "sample_adapter": None,
    }
    assert targets["mailbot"]["sample_adapter"] == "mailbot"
    assert targets["shopbot"]["chat_url"] == "http://localhost:8002/chat"
