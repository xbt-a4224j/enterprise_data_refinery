"""LLM provider interface + cost accounting. Every provider returns token counts so we
can show $0-local vs. would-be-Claude spend."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

# Public Claude list prices (USD per 1M tokens) → per-token, for the cost readout.
CLAUDE_PRICING = {
    "claude-haiku-4-5": (1.00 / 1_000_000, 5.00 / 1_000_000),
    "claude-sonnet-5": (3.00 / 1_000_000, 15.00 / 1_000_000),
    "claude-opus-4-8": (5.00 / 1_000_000, 25.00 / 1_000_000),
}
# Reference model for the "would-be Claude" number shown while running locally.
REFERENCE_MODEL = "claude-sonnet-5"


class LLMResult(BaseModel):
    data: dict
    tokens_in: int = 0
    tokens_out: int = 0
    provider: str = ""
    model: str = ""  # set by the Claude provider; blank for local providers

    @property
    def would_be_claude_usd(self) -> float:
        """Actual cost when run on Claude (self.model); a Sonnet-5 reference locally."""
        rin, rout = CLAUDE_PRICING.get(self.model) or CLAUDE_PRICING[REFERENCE_MODEL]
        return self.tokens_in * rin + self.tokens_out * rout


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

        return ClaudeProvider(settings.anthropic_api_key, settings.anthropic_model)
    from edr.llm.fake import FakeProvider

    return FakeProvider()
