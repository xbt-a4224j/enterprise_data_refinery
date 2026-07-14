"""Frontier-model provider (Anthropic). Config-gated: only used when a key is set.
Same interface as the local provider, so swapping is a one-line config change."""

from __future__ import annotations

import json

import httpx

from edr.llm.base import LLMResult

API_URL = "https://api.anthropic.com/v1/messages"


class ClaudeProvider:
    name = "claude"

    def __init__(
        self, api_key: str, model: str = "claude-sonnet-5", client: httpx.Client | None = None
    ):
        if not api_key:
            raise ValueError("ClaudeProvider requires EDR_ANTHROPIC_API_KEY")
        self.api_key = api_key
        self.model = model
        self._client = client or httpx.Client(timeout=120)

    def extract(self, *, instructions: str, schema: dict, content: str) -> LLMResult:
        prompt = (
            f"{instructions}\n\nReturn ONLY JSON matching this schema:\n{json.dumps(schema)}"
            f"\n\nDOCUMENT:\n{content}"
        )
        resp = self._client.post(
            API_URL,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        body = resp.json()
        text = "".join(b.get("text", "") for b in body.get("content", []))
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {}
        usage = body.get("usage", {})
        return LLMResult(
            data=data if isinstance(data, dict) else {"value": data},
            tokens_in=usage.get("input_tokens", 0),
            tokens_out=usage.get("output_tokens", 0),
            provider="claude",
        )
