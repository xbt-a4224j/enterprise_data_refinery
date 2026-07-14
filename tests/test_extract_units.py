from pathlib import Path

from edr.packs.adapters import GenericFileAdapter
from edr.packs.base import SourceSpec
from edr.pipeline.extract import chunk

ROOT = Path(__file__).resolve().parent.parent


def test_chunk_small_is_single_window():
    assert chunk("hello") == ["hello"]


def test_chunk_large_overlaps_and_covers():
    text = "abcdefghij" * 1000  # 10k chars
    parts = chunk(text, size=4000, overlap=200)
    assert len(parts) >= 3
    assert "".join(p if i == 0 else p[200:] for i, p in enumerate(parts)) == text


def test_generic_file_adapter_discovers_and_fetches():
    spec = SourceSpec(name="permits-demo", kind="file", location="fixtures/*.txt")
    ad = GenericFileAdapter(spec, ROOT / "packs" / "extract")
    refs = ad.discover()
    assert len(refs) == 3
    doc = ad.fetch(refs[0])
    assert "Permit" in doc.content and doc.meta["kind"] == "file"
