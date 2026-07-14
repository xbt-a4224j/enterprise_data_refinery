"""Typed application configuration, loaded from the environment (EDR_* vars)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EDR_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Required — missing/blank fails fast at startup with a clear pydantic error.
    database_url: str

    # LLM
    llm_provider: str = "fake"  # ollama | claude | fake
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5"  # fast + cheap for extraction; or claude-sonnet-5

    # App
    admin_token: str = "change-me"
    slack_webhook: str = ""

    # Pipeline
    extract_concurrency: int = 4  # parallel in-flight LLM extractions per source run


@lru_cache
def get_settings() -> Settings:
    return Settings()
