"""Document loading, chunking, and LLM extraction into a pack's canonical schema."""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

from edr.llm.base import LLMProvider, LLMResult
from edr.packs.base import LoadedPack, RawDoc


def chunk(text: str, size: int = 6000, overlap: int = 200) -> list[str]:
    """Deterministic character-window chunking."""
    if len(text) <= size:
        return [text]
    out, start = [], 0
    while start < len(text):
        out.append(text[start : start + size])
        start += size - overlap
    return out


def extract_document(
    pack: LoadedPack, provider: LLMProvider, doc: RawDoc
) -> tuple[dict, bool, LLMResult]:
    """Extract one document into the pack's canonical schema.

    Returns (record, low_confidence, llm_result).
    """
    model: type[BaseModel] = pack.schema_model
    schema = model.model_json_schema()
    # Single-window for now; multi-window packs merge upstream.
    content = chunk(doc.content)[0]
    result = provider.extract(
        instructions=pack.config.instructions, schema=schema, content=content
    )
    low_conf = False
    try:
        record = model.model_validate(result.data).model_dump()
    except ValidationError:
        # keep raw data but flag it; the eval gate is the real safety net
        record = {k: result.data.get(k) for k in model.model_fields}
        low_conf = True
    # heuristic confidence: many empty fields => low confidence
    filled = sum(1 for v in record.values() if v not in (None, ""))
    if filled < max(1, len(record) // 3):
        low_conf = True
    return record, low_conf, result
