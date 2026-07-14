"""Generic source adapters usable by any pack that doesn't need bespoke fetching."""

from __future__ import annotations

import glob
from pathlib import Path

import httpx

from edr.packs.base import RawDoc, SourceSpec


class GenericFileAdapter:
    """Reads files from a directory/glob. `location` is a glob relative to the pack dir."""

    def __init__(self, spec: SourceSpec, base_dir: Path):
        self.spec = spec
        self.base_dir = base_dir

    def discover(self) -> list[str]:
        pattern = str(self.base_dir / self.spec.location)
        return sorted(glob.glob(pattern))

    def fetch(self, ref: str) -> RawDoc:
        data = Path(ref).read_text(errors="replace")
        return RawDoc(ref=ref, content=data, meta={"kind": "file"})


class GenericHTTPAdapter:
    def __init__(self, spec: SourceSpec, base_dir: Path):
        self.spec = spec
        self.base_dir = base_dir

    def discover(self) -> list[str]:
        return list(self.spec.options.get("refs", []))

    def fetch(self, ref: str) -> RawDoc:
        url = ref if ref.startswith("http") else self.spec.location.rstrip("/") + "/" + ref
        resp = httpx.get(url, timeout=30)
        resp.raise_for_status()
        return RawDoc(ref=ref, content=resp.text, meta={"kind": "http", "url": url})


def build_adapter(spec: SourceSpec, base_dir: Path):
    if spec.kind == "http":
        return GenericHTTPAdapter(spec, base_dir)
    return GenericFileAdapter(spec, base_dir)
