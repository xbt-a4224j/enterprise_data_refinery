"""LLM provider interface + cost accounting. Every provider returns token counts so we
can show $0-local vs. would-be-Claude spend."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

# Approximate public Claude list prices (USD per token) for the would-be-cost readout.
CLAUDE_INPUT_PER_TOK = 3.00 / 1_000_000
CLAUDE_OUTPUT_PER_TOK = 15.00 / 1_000_000


class LLMResult(BaseModel):
    data: dict
    tokens_in: int = 0
    tokens_out: int = 0
    provider: str = ""

    @property
    def would_be_claude_usd(self) -> float:
        return self.tokens_in * CLAUDE_INPUT_PER_TOK + self.tokens_out * CLAUDE_OUTPUT_PER_TOK


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def extract(self, *, instructions: str, schema: dict, content: str) -> LLMResult:
        """Return structured data conforming to `schema` extracted from `content`."""
        ...


def get_provider(settings=None) -> LLMProvider:
    from edr.config import get_settings

    settings = settings or get_settings()
    kind = settings.llm_provider
    if kind == "ollama":
        from edr.llm.ollama import OllamaProvider

        return OllamaProvider(settings.ollama_host, settings.ollama_model)
    if kind == "claude":
        from edr.llm.claude import ClaudeProvider

        return ClaudeProvider(settings.anthropic_api_key)
    from edr.llm.fake import FakeProvider

    return FakeProvider()
