"""Non-engineer pack creation: infer a schema from a sample document and write it out as
a real packs/<name>/ directory the loader picks up."""

from __future__ import annotations

import keyword
import re
from pathlib import Path

from edr.llm.base import LLMProvider
from edr.packs.loader import PACKS_DIR


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_") or "pack"


def propose_fields(provider: LLMProvider | None, sample: str) -> list[dict]:
    """Ask the model for fields; fall back to a 'Label: value' heuristic offline."""
    fields: list[dict] = []
    if provider is not None:
        try:
            res = provider.extract(
                instructions="List the field names present in this document.",
                schema={"type": "object", "properties": {"fields": {"type": "array"}}},
                content=sample,
            )
            for f in res.data.get("fields", []) or []:
                key = _slug(str(f))
                if key and key not in {x["name"] for x in fields}:
                    fields.append({"name": key, "type": "str"})
        except Exception:  # noqa: BLE001
            fields = []
    if not fields:
        for label in re.findall(r"^([A-Za-z][A-Za-z /]+):", sample, re.M):
            key = _slug(label)
            if key and not keyword.iskeyword(key) and key not in {x["name"] for x in fields}:
                fields.append({"name": key, "type": "str"})
    return fields or [{"name": "id", "type": "str"}, {"name": "value", "type": "str"}]


def write_pack(name: str, fields: list[dict], sample: str, base_dir: Path = PACKS_DIR) -> Path:
    slug = _slug(name)
    d = base_dir / slug
    (d / "fixtures").mkdir(parents=True, exist_ok=True)
    schema_lines = "\n".join(f"    {f['name']}: str | None = None" for f in fields)
    (d / "schema.py").write_text(
        "from pydantic import BaseModel\n\n\nclass CanonicalRecord(BaseModel):\n"
        + schema_lines
        + "\n"
    )
    (d / "checks.py").write_text("CHECKS = []\n")
    (d / "pack.yaml").write_text(
        f"name: {slug}\ntask_type: extract\ncadence: manual\n"
        f"schema_ref: CanonicalRecord\n"
        f"instructions: Extract the listed fields from each document.\n"
        f"sources:\n  - name: {slug}-sample\n    kind: file\n    location: \"fixtures/*.txt\"\n"
        f"checks:\n  null_rate:\n    max: {{}}\n"
    )
    (d / "fixtures" / "sample.txt").write_text(sample)
    return d
