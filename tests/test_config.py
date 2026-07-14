import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from edr.config import Settings


def test_loads_from_env(monkeypatch):
    monkeypatch.setenv("EDR_DATABASE_URL", "postgresql+psycopg://x:y@h:5432/db")
    monkeypatch.setenv("EDR_LLM_PROVIDER", "ollama")
    s = Settings()
    assert s.database_url.endswith("/db")
    assert s.llm_provider == "ollama"


class _NoFileSettings(Settings):
    # same fields, but no .env fallback so a missing var truly fails
    model_config = SettingsConfigDict(env_prefix="EDR_", extra="ignore")


def test_missing_required_fails_fast(monkeypatch):
    monkeypatch.delenv("EDR_DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        _NoFileSettings()
