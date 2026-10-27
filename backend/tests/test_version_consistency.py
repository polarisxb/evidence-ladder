"""One software name and one version across API, UI and exported reports.

The software-copyright filing requires the registered name and version to
match on every artefact a reviewer sees: the API, the page title, the UI and
the HTML report. ``app/version.py`` is the backend source; the frontend keeps
its own copy in ``package.json``, so this test is what keeps the two in step.
"""
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.report_generator import generate_report, render_html_report
from app.version import APP_FULL_NAME, APP_VERSION, APP_VERSION_LABEL, version_label

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
needs_frontend = pytest.mark.skipif(
    not (FRONTEND / "package.json").exists(), reason="frontend sources not present (backend-only image)"
)


def test_version_label_uses_major_and_minor() -> None:
    assert version_label("1.0.0") == "V1.0"
    assert version_label("2.3.4") == "V2.3"
    assert APP_VERSION_LABEL == version_label(APP_VERSION)


def test_openapi_carries_name_and_version() -> None:
    assert app.version == APP_VERSION
    assert APP_FULL_NAME in app.title


@pytest.mark.anyio
async def test_health_reports_version() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        body = (await client.get("/health")).json()
    assert body["version"] == APP_VERSION


def test_html_report_footer_names_the_software() -> None:
    scan = SimpleNamespace(
        id="version-scan", name="version fixture", target_url="https://fixture.example.com",
        status="completed", results=[], total_attacks=0, completed_attacks=0,
    )
    html = render_html_report(generate_report(scan))
    assert f"{APP_FULL_NAME}（Evidence-Ladder）{APP_VERSION_LABEL}" in html


@needs_frontend
def test_frontend_package_version_matches_backend() -> None:
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    assert package["version"] == APP_VERSION


@needs_frontend
def test_page_title_and_ui_name_match_backend() -> None:
    title = re.search(r"<title>(.*?)</title>", (FRONTEND / "index.html").read_text(encoding="utf-8"))
    assert title is not None
    assert APP_FULL_NAME in title.group(1)
    assert APP_VERSION_LABEL in title.group(1)

    zh = (FRONTEND / "src" / "i18n" / "zh.ts").read_text(encoding="utf-8")
    assert f'fullName: "{APP_FULL_NAME}"' in zh
