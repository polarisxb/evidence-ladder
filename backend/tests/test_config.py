"""Test configuration loading."""
from pathlib import Path

from app.config import settings


class TestConfigLoading:
    def test_settings_loaded(self) -> None:
        assert settings is not None

    def test_app_name(self) -> None:
        assert settings.app_name == "TianJian Libra"

    def test_api_key_loaded(self) -> None:
        assert settings.openai_api_key, "OPENAI_API_KEY should be set (from root .env)"

    def test_base_url_normalized(self) -> None:
        if settings.openai_base_url:
            assert not settings.openai_base_url.endswith("/"), "base_url should not end with /"

    def test_model_defaults(self) -> None:
        assert settings.openai_model, "openai_model should have a value"
        assert settings.openai_mini_model, "openai_mini_model should have a value"

    def test_database_url(self) -> None:
        assert "sqlite" in settings.database_url
        assert "///./data/app.db" not in settings.database_url
        assert "backend/data/app.db" in settings.database_url.replace("\\", "/")

    def test_cors_origins(self) -> None:
        assert isinstance(settings.cors_origins, list)
        assert len(settings.cors_origins) > 0

    def test_root_env_exists(self) -> None:
        from app.config import _ROOT_ENV
        assert Path(_ROOT_ENV).is_file(), f"Root .env not found at {_ROOT_ENV}"
