"""Genericness: two more packs (triage, normalize) run through the SAME core pipeline
with zero core changes — the whole thesis of the Pack abstraction."""

from pathlib import Path

from sqlalchemy import func, select

from edr.llm.fake import FakeProvider
from edr.models import Canonical, Source
from edr.packs.loader import discover_packs
from edr.pipeline.run import ingest

ROOT = Path(__file__).resolve().parent.parent


def _run(db, pack_name, record):
    pack = discover_packs(ROOT / "packs")[pack_name]
    src = Source(pack_name=pack_name, name=pack.config.sources[0].name)
    db.add(src)
    db.flush()
    prov = FakeProvider(responder=lambda _c: record)
    return ingest(db, pack, src, prov, pack_dir=pack.pack_dir)


def test_all_three_packs_discovered():
    reg = discover_packs(ROOT / "packs")
    assert {"extract", "triage", "normalize"} <= set(reg)


def test_triage_pack_runs_through_core(db_session):
    res = _run(db_session, "triage",
               {"category": "billing", "severity": "high", "routing_team": "B", "summary": "s"})
    assert res.drop.status == "published"
    assert db_session.scalar(select(func.count()).select_from(Canonical)) == 3


def test_normalize_pack_runs_through_core(db_session):
    res = _run(db_session, "normalize",
               {"vendor": "Acme", "amount_usd": 100.0, "award_date": "2026-01-01",
                "agency": "X", "description": "y"})
    assert res.drop.status == "published"
    assert db_session.scalar(select(func.count()).select_from(Canonical)) == 2
