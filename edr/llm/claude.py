"""Frontier-model provider (Anthropic). Config-gated: only used when a key is set.
Same interface as the local provider, so swapping is a one-line config change."""

from __future__ import annotations

import json
import re

import httpx

from edr.llm.base import LLMResult

API_URL = "https://api.anthropic.com/v1/messages"


def _parse_json(text: str) -> dict:
    """Robustly extract a JSON object — Claude often wraps it in ```json fences or prose."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        block = re.search(r"\{.*\}", text, re.S)
        if not block:
            return {}
        try:
            obj = json.loads(block.group(0))
        except json.JSONDecodeError:
            return {}
    return obj if isinstance(obj, dict) else {"value": obj}


class ClaudeProvider:
    name = "claude"

    def __init__(
        self, api_key: str, model: str = "claude-haiku-4-5", client: httpx.Client | None = None
    ):
        if not api_key:
            raise ValueError("ClaudeProvider requires EDR_ANTHROPIC_API_KEY")
        self.api_key = api_key
        self.model = model
        self._client = client or httpx.Client(timeout=120)

    def extract(self, *, instructions: str, schema: dict, content: str) -> LLMResult:
        prompt = (
            f"{instructions}\n\nReturn raw JSON only — no markdown, no code fences, no prose. "
            f"Match this schema:\n{json.dumps(schema)}\n\nDOCUMENT:\n{content}"
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
        data = _parse_json(text)
        usage = body.get("usage", {})
        return LLMResult(
            data=data,
            tokens_in=usage.get("input_tokens", 0),
            tokens_out=usage.get("output_tokens", 0),
            provider="claude",
            model=self.model,
        )
