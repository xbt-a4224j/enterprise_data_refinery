import httpx
import pytest

from edr.llm.ollama import OllamaProvider

HOST = "http://localhost:11434"


def _ollama_up() -> bool:
    try:
        return httpx.get(f"{HOST}/api/tags", timeout=2).status_code == 200
    except Exception:
        return False


@pytest.mark.skipif(not _ollama_up(), reason="ollama not reachable")
def test_ollama_extracts_permit():
    prov = OllamaProvider(HOST, "qwen2.5:7b")
    schema = {
        "type": "object",
        "properties": {"permit_id": {"type": "string"}, "valuation_usd": {"type": "number"}},
    }
    doc = "Permit No: BLD-2026-00417\nEstimated Valuation: $48,500\nStatus: Issued"
    r = prov.extract(instructions="Extract the permit fields.", schema=schema, content=doc)
    assert r.provider == "ollama"
    assert r.tokens_in > 0 and r.tokens_out > 0
    assert "417" in str(r.data.get("permit_id", ""))
