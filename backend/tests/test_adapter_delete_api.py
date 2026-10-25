"""Adapters can be deleted, unless a scan still refers to them."""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select

from app.database import async_session
from app.main import app
from app.models import Adapter, ScanTask

pytestmark = pytest.mark.anyio

ADAPTER_BODY = {
    "name": "delete-fixture-adapter",
    "transport": "http_json",
    "base_url": "http://127.0.0.1:18080",
    "invoke_config": {"method": "POST", "path": "/chat", "body_template": {"message": "{{input.prompt}}"}},
    "response_extract": {"mode": "json_paths", "text_path": "$.response"},
}


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    async with async_session() as db:
        await db.execute(delete(ScanTask).where(ScanTask.name == "delete-fixture-scan"))
        await db.execute(delete(Adapter).where(Adapter.name == ADAPTER_BODY["name"]))
        await db.commit()


async def _create_adapter(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/adapters", json=ADAPTER_BODY)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


async def test_delete_unused_adapter(client: AsyncClient) -> None:
    adapter_id = await _create_adapter(client)

    resp = await client.delete(f"/api/v1/adapters/{adapter_id}")

    assert resp.status_code == 200
    assert resp.json()["data"] == {"id": adapter_id}
    assert (await client.get(f"/api/v1/adapters/{adapter_id}")).status_code == 404
    listed = (await client.get("/api/v1/adapters")).json()["data"]
    assert adapter_id not in {item["id"] for item in listed}


async def test_delete_refuses_adapter_used_by_a_scan(client: AsyncClient) -> None:
    adapter_id = await _create_adapter(client)
    async with async_session() as db:
        db.add(ScanTask(
            name="delete-fixture-scan", target_url=ADAPTER_BODY["base_url"],
            target_type="adapter", adapter_id=adapter_id, status="completed",
        ))
        await db.commit()

    resp = await client.delete(f"/api/v1/adapters/{adapter_id}")

    assert resp.status_code == 409
    assert "used by 1 scan" in resp.json()["error"]
    async with async_session() as db:
        still_there = await db.scalar(select(Adapter.id).where(Adapter.id == adapter_id))
    assert still_there == adapter_id


async def test_delete_unknown_adapter_is_404(client: AsyncClient) -> None:
    resp = await client.delete("/api/v1/adapters/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
