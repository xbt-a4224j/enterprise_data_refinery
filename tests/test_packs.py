from pathlib import Path

import pytest

from edr.llm.base import LLMResult
from edr.llm.fake import FakeProvider
from edr.packs.loader import PackLoadError, discover_packs, load_pack

ROOT = Path(__file__).resolve().parent.parent


def test_discovers_extract_pack():
    reg = discover_packs(ROOT / "packs")
    assert "extract" in reg
    p = reg["extract"]
    assert p.config.task_type == "extract"
    assert p.schema_model.__name__ == "PermitRecord"
    assert len(p.checks) == 2
    assert "_template" not in reg  # underscore dirs skipped


def test_template_is_loadable(tmp_path):
    src = ROOT / "packs" / "_template"
    dst = tmp_path / "mypack"
    dst.mkdir()
    for f in ("pack.yaml", "schema.py", "checks.py", "adapter.py"):
        (dst / f).write_text((src / f).read_text().replace("_template", "mypack"))
    pack = load_pack(dst)
    assert pack.config.name == "mypack"
    assert pack.schema_model.__name__ == "CanonicalRecord"


def test_broken_pack_fails_loud(tmp_path):
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "pack.yaml").write_text("name: bad\n")  # missing task_type
    with pytest.raises(PackLoadError):
        load_pack(bad)


def test_fake_provider_deterministic_and_costed():
    prov = FakeProvider(responder=lambda c: {"permit_id": "X"})
    r = prov.extract(instructions="", schema={"properties": {"permit_id": {}}}, content="doc")
    assert isinstance(r, LLMResult)
    assert r.data == {"permit_id": "X"}
    assert r.tokens_in > 0 and r.would_be_claude_usd > 0
