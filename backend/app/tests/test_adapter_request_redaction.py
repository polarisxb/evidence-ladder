import json

import httpx
import pytest

from app.config import settings
from app.main import app

pytestmark = [pytest.mark.anyio, pytest.mark.parametrize("anyio_backend", ["asyncio"])]


@pytest.mark.parametrize("operation", ["test", "probe/test"])
@pytest.mark.parametrize("status", [200, 401])
@pytest.mark.parametrize("auth_type,auth_name", [
    ("bearer", "X-Custom-Credential"),
    ("header", "X-Custom-Credential"),
    ("query", "X-Custom-Credential"),
    ("header", "  X-Custom-Credential  "),
    ("query", "  X-Custom-Credential  "),
])
async def test_api_request_preview_masks_credentials_but_transport_keeps_them(
    monkeypatch, operation, status, auth_type, auth_name,
):
    secret = "synthetic-adapter-credential"
    monkeypatch.setenv("ADAPTER_TEST_CREDENTIAL", secret)
    monkeypatch.setattr(settings, "auth_required", False)
    sent = []

    def respond(request):
        sent.append(request)
        return httpx.Response(status, text="fixture response")

    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(respond),
    ))
    request_config = {
        "method": "GET", "path": "/audit?api_key=synthetic-url-credential",
        "headers": {"aUtHoRiZaTiOn": "Bearer synthetic-inline-credential", "X-Trace": "trace"},
        "query": {"access_token": "synthetic-query-credential", "page": "2"},
    }
    adapter = {
        "name": "redaction fixture", "mode": "direct_http_adapter", "transport": "http_json",
        "base_url": "https://public.example.com",
        "auth_config": {"type": auth_type, "name": auth_name, "secret_ref": "ADAPTER_TEST_CREDENTIAL"},
        "invoke_config": request_config, "response_extract": {"mode": "raw_text"},
        "probe_config": {
            "enabled": True, "steps": [{"name": "audit", **request_config}],
            "assertions": [{"type": "status_code_is", "step": "audit", "status_code": 200}],
        },
    }
    body = {"adapter": adapter, "prompt": "fixture"}
    async with real_client(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/adapters/{operation}", json=body)
    assert response.status_code == 200, response.text
    assert len(sent) == 1
    if auth_type == "bearer":
        assert f"Bearer {secret}" in sent[0].headers["authorization"]
    elif auth_type == "header":
        assert sent[0].headers["X-Custom-Credential"] == secret
    else:
        assert sent[0].url.params["X-Custom-Credential"] == secret
    data = response.json()["data"]
    preview = data["rendered_request"] if operation == "test" else data["step_results"][0]["rendered_request"]
    serialized = json.dumps(preview)
    for credential in [secret, "synthetic-inline-credential", "synthetic-query-credential", "synthetic-url-credential"]:
        assert credential not in serialized
    assert preview["headers"]["X-Trace"] == "trace"
    assert preview["query"]["page"] == "2"
    assert adapter["invoke_config"]["headers"]["aUtHoRiZaTiOn"] == "Bearer synthetic-inline-credential"
