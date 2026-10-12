from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
GENERATE_SECRET = 'python -c "import secrets; print(secrets.token_urlsafe(32))"'


@pytest.mark.parametrize("filename", [".env.example", "README.md"])
def test_install_instructions_require_generated_app_secret(filename: str) -> None:
    text = (ROOT / filename).read_text(encoding="utf-8")
    assert GENERATE_SECRET in text
    assert "APP_SECRET" in text
    assert "AUTH_REQUIRED=true" in text
