"""Deterministic, offline provider for tests and the default when no model is configured."""

from __future__ import annotations

from collections.abc import Callable

from edr.llm.base import LLMResult


class FakeProvider:
    name = "fake"

    def __init__(self, responder: Callable[[str], dict] | None = None, canned: dict | None = None):
        self._responder = responder
        self._canned = canned or {}

    def extract(self, *, instructions: str, schema: dict, content: str) -> LLMResult:
        if self._responder is not None:
            data = self._responder(content)
        elif content in self._canned:
            data = self._canned[content]
        else:
            # schema-shaped stub: empty/null values for each property
            props = (schema or {}).get("properties", {})
            data = dict.fromkeys(props)
        return LLMResult(
            data=data,
            tokens_in=max(1, len(content) // 4),
            tokens_out=max(1, len(str(data)) // 4),
            provider="fake",
        )
