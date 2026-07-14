import re
from pathlib import Path

from sqlalchemy import func, select

from edr.llm.fake import FakeProvider
from edr.models import Canonical, Source
from edr.packs.loader import discover_packs
from edr.pipeline.run import run_source

ROOT = Path(__file__).resolve().parent.parent


def _parse_permit(text: str) -> dict:
    def find(*pats):
        for p in pats:
            m = re.search(p, text, re.I)
            if m:
                return m.group(1).strip()
        return None

    pid = find(r"Permit No:\s*(\S+)", r"Permit ID:\s*(\S+)", r"No\.\s*(\S+)")
    val = find(r"(?:Valuation|Job Value)[^$]*\$([\d,]+)")
    return {
        "permit_id": pid,
        "address": find(r"(?:Site Address|Address|Location):\s*(.+)"),
        "valuation_usd": float(val.replace(",", "")) if val else None,
        "status": find(r"(?:Current Status|Status):\s*(.+)"),
    }


def test_spine_fetch_extract_canonical_then_cache_and_idempotent(db_session):
    reg = discover_packs(ROOT / "packs")
    pack = reg["extract"]
    src = Source(pack_name="extract", name="permits-demo")
    db_session.add(src)
    db_session.flush()

    provider = FakeProvider(responder=_parse_permit)

    r1 = run_source(db_session, pack, src, provider, pack_dir=pack.pack_dir)
    n_canonical = db_session.scalar(select(func.count()).select_from(Canonical))
    assert n_canonical == 3
    assert r1.llm_calls == 3 and r1.cache_hits == 0
    ids = {c.record["permit_id"] for c in db_session.scalars(select(Canonical))}
    assert ids == {"BLD-2026-00417", "DEL-BP-2026-1188", "CARY-2026-0932"}

    # second run: unchanged docs -> cache hit, ZERO llm calls, and drop is idempotent
    r2 = run_source(db_session, pack, src, provider, pack_dir=pack.pack_dir)
    assert r2.llm_calls == 0 and r2.cache_hits == 3
    assert r2.drop.id == r1.drop.id
    assert db_session.scalar(select(func.count()).select_from(Canonical)) == 3
