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


class SocrataAdapter:
    """Discover-at-scale adapter for Socrata open-data endpoints (SF/NYC/Chicago permits,
    etc.). `discover()` pulls a batch of real records; `fetch()` renders one as a text
    document for the extractor. One API call per run, cached on the instance."""

    def __init__(self, spec: SourceSpec, base_dir: Path):
        self.spec = spec
        self.limit = int(spec.options.get("limit", 20))
        self._rows: list[dict] | None = None

    def _load(self) -> list[dict]:
        if self._rows is None:
            sep = "&" if "?" in self.spec.location else "?"
            url = f"{self.spec.location}{sep}$limit={self.limit}"
            resp = httpx.get(url, timeout=30, headers={"accept": "application/json"})
            resp.raise_for_status()
            data = resp.json()
            self._rows = data if isinstance(data, list) else []
        return self._rows

    def discover(self) -> list[str]:
        return [str(i) for i in range(len(self._load()))]

    def fetch(self, ref: str) -> RawDoc:
        row = self._load()[int(ref)]
        lines = [
            f"{k}: {v}"
            for k, v in row.items()
            if not k.startswith(":") and isinstance(v, str | int | float) and str(v).strip()
        ]
        return RawDoc(ref=ref, content="\n".join(lines[:40]), meta={"kind": "socrata"})


def build_adapter(spec: SourceSpec, base_dir: Path):
    if spec.kind == "socrata":
        return SocrataAdapter(spec, base_dir)
    if spec.kind == "http":
        return GenericHTTPAdapter(spec, base_dir)
    return GenericFileAdapter(spec, base_dir)
