from pathlib import Path

from sqlalchemy import select

from edr.llm.fake import FakeProvider
from edr.models import Drop, Source
from edr.packs.base import RawDoc
from edr.packs.loader import discover_packs
from edr.pipeline.run import ingest, run_source

ROOT = Path(__file__).resolve().parent.parent


class StubAdapter:
    def __init__(self, refs, fail=()):
        self._refs, self._fail = refs, set(fail)

    def discover(self):
        return self._refs

    def fetch(self, ref):
        if ref in self._fail:
            raise RuntimeError("source unavailable")
        return RawDoc(ref=ref, content=ref, meta={})


def _pack_with(adapter):
    pack = discover_packs(ROOT / "packs")["extract"]
    pack.adapter = adapter
    return pack


def _prov():
    return FakeProvider(responder=lambda c: {"permit_id": c.strip(), "valuation_usd": 100})


def test_partial_failure_is_degraded(db_session):
    s = Source(pack_name="extract", name="permits-demo")
    db_session.add(s)
    db_session.flush()
    pack = _pack_with(StubAdapter(["P1", "BAD", "P2"], fail=["BAD"]))
    res = run_source(db_session, pack, s, _prov(), pack_dir=pack.pack_dir)
    assert res.run.status == "degraded"
    assert len(res.records) == 2 and len(res.failures) == 1


def test_total_failure_keeps_last_good(db_session):
    s = Source(pack_name="extract", name="permits-demo")
    db_session.add(s)
    db_session.flush()
    # first: a good run that publishes
    good_pack = _pack_with(StubAdapter(["P1", "P2"]))
    ingest(db_session, good_pack, s, _prov(), pack_dir=good_pack.pack_dir)
    published = db_session.scalars(select(Drop).where(Drop.status == "published")).all()
    assert len(published) == 1

    # then: all docs fail -> failed run, no new drop, last-good still published
    bad_pack = _pack_with(StubAdapter(["X", "Y"], fail=["X", "Y"]))
    res = run_source(db_session, bad_pack, s, _prov(), pack_dir=bad_pack.pack_dir)
    assert res.run.status == "failed" and res.drop is None
    still = db_session.scalars(select(Drop).where(Drop.status == "published")).all()
    assert len(still) == 1 and still[0].id == published[0].id
