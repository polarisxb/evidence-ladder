import logging

import httpx
import pytest

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("query", [
    "access_token=synthetic-query-secret&page=2",
    "X-Custom-Credential=synthetic-query-secret",
    "api_key=synthetic-query-secret&api_key=synthetic-second-secret",
    "auth%5Ftoken=synthetic-query-secret",
])
async def test_httpx_request_logs_redact_query_values(caplog, query):
    caplog.set_level(logging.INFO, logger="httpx")
    sent = []

    def respond(request):
        sent.append(request)
        return httpx.Response(200)

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        await client.get(f"https://fixture.example.com/audit?{query}")

    assert "synthetic-query-secret" in str(sent[0].url)
    assert "synthetic-query-secret" not in caplog.text
    assert "synthetic-second-secret" not in caplog.text
    assert "fixture.example.com/audit" in caplog.text
    assert "200 OK" in caplog.text


async def test_httpx_request_logs_preserve_url_without_query(caplog):
    caplog.set_level(logging.INFO, logger="httpx")
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(503))) as client:
        await client.get("https://fixture.example.com/health")
    assert "https://fixture.example.com/health" in caplog.text
    assert "503 Service Unavailable" in caplog.text
