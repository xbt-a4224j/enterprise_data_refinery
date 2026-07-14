"""Local-model provider via Ollama. Schema-constrained JSON output."""

from __future__ import annotations

import json

import httpx

from edr.llm.base import LLMResult


class OllamaProvider:
    name = "ollama"

    def __init__(self, host: str, model: str):
        self.host = host.rstrip("/")
        self.model = model

    def extract(self, *, instructions: str, schema: dict, content: str) -> LLMResult:
        prompt = (
            f"{instructions}\n\nReturn ONLY JSON matching this schema:\n"
            f"{json.dumps(schema)}\n\nDOCUMENT:\n{content}"
        )
        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0},
        }
        resp = httpx.post(f"{self.host}/api/generate", json=payload, timeout=120)
        resp.raise_for_status()
        body = resp.json()
        try:
            data = json.loads(body.get("response", "{}"))
        except json.JSONDecodeError:
            data = {}
        return LLMResult(
            data=data if isinstance(data, dict) else {"value": data},
            tokens_in=body.get("prompt_eval_count", 0),
            tokens_out=body.get("eval_count", 0),
            provider="ollama",
        )
