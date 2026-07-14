import httpx
import pytest

from edr.llm.ollama import OllamaProvider

HOST = "http://localhost:11434"
MODEL = "qwen2.5:7b"


def _model_available() -> bool:
    """Only run if Ollama is up AND the model is actually pulled — a bare server
    (e.g. a fresh container without the model) answers /api/tags but 404s on generate."""
    try:
        resp = httpx.get(f"{HOST}/api/tags", timeout=2)
        if resp.status_code != 200:
            return False
        names = {m.get("name", "") for m in resp.json().get("models", [])}
        return any(n == MODEL or n.startswith(MODEL.split(":")[0]) for n in names)
    except Exception:
        return False


@pytest.mark.skipif(not _model_available(), reason=f"ollama model {MODEL} not available")
def test_ollama_extracts_permit():
    prov = OllamaProvider(HOST, MODEL)
    schema = {
        "type": "object",
        "properties": {"permit_id": {"type": "string"}, "valuation_usd": {"type": "number"}},
    }
    doc = "Permit No: BLD-2026-00417\nEstimated Valuation: $48,500\nStatus: Issued"
    r = prov.extract(instructions="Extract the permit fields.", schema=schema, content=doc)
    assert r.provider == "ollama"
    assert r.tokens_in > 0 and r.tokens_out > 0
    assert "417" in str(r.data.get("permit_id", ""))
