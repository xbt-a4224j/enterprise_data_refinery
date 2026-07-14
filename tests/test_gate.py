from pathlib import Path

from sqlalchemy import func, select

from edr.models import Canonical, Drop, MappingCache, Source
from edr.packs.loader import discover_packs
from edr.pipeline.drift import detect_drift, provenance
from edr.pipeline.gate import evaluate_drop

ROOT = Path(__file__).resolve().parent.parent


def _pack():
    return discover_packs(ROOT / "packs")["extract"]


def _src(session):
    s = Source(pack_name="extract", name="permits-demo")
    session.add(s)
    session.flush()
    return s


def _drop(session, src, records, h):
    d = Drop(source_id=src.id, drop_date="2026-07-01", content_hash=h, status="pending")
    session.add(d)
    session.flush()
    for r in records:
        session.add(Canonical(drop_id=d.id, source_id=src.id, mapping_version="v1", record=r))
    session.flush()
    return d


def test_gate_publishes_good_data(db_session):
    s = _src(db_session)
    d = _drop(db_session, s, [{"permit_id": "P1", "valuation_usd": 1000}], "h1")
    assert evaluate_drop(db_session, d, _pack()) is True
    assert d.status == "published"
    assert all(c.checks_passed for c in db_session.scalars(select(Canonical)))


def test_fail_closed_quarantine_leaves_last_good_untouched(db_session):
    s = _src(db_session)
    good = _drop(db_session, s, [{"permit_id": "P1", "valuation_usd": 10}], "h1")
    assert evaluate_drop(db_session, good, _pack()) is True
    bad = _drop(db_session, s, [{"permit_id": None, "valuation_usd": 10}], "h2")
    assert evaluate_drop(db_session, bad, _pack()) is False
    assert bad.status == "quarantined"
    db_session.refresh(good)
    assert good.status == "published"  # last-good untouched


def test_null_rate_blocks(db_session):
    s = _src(db_session)
    rows = [{"permit_id": "P1", "valuation_usd": None}, {"permit_id": "P2", "valuation_usd": None}]
    d = _drop(db_session, s, rows, "h1")
    assert evaluate_drop(db_session, d, _pack()) is False  # valuation null-rate 1.0 > 0.5


def test_row_count_delta_anomaly(db_session):
    s = _src(db_session)
    d1 = _drop(db_session, s, [{"permit_id": f"P{i}", "valuation_usd": 5} for i in range(2)], "h1")
    assert evaluate_drop(db_session, d1, _pack()) is True
    d2 = _drop(db_session, s, [{"permit_id": f"Q{i}", "valuation_usd": 5} for i in range(10)], "h2")
    assert evaluate_drop(db_session, d2, _pack()) is False  # 2 -> 10 = 400% growth


def test_schema_conformance_blocks(db_session):
    s = _src(db_session)
    d = _drop(db_session, s, [{"permit_id": "P1", "valuation_usd": "not-a-number"}], "h1")
    assert evaluate_drop(db_session, d, _pack()) is False


def test_schema_drift_invalidates_cache(db_session):
    s = _src(db_session)
    db_session.add(MappingCache(source_id=s.id, schema_hash="x", plan={"record": {}}))
    d1 = _drop(db_session, s, [{"permit_id": "P1", "valuation_usd": 5}], "h1")
    evaluate_drop(db_session, d1, _pack())
    d2 = _drop(db_session, s, [{"permit_id": "P2", "valuation_usd": 5, "extra": "new"}], "h2")
    evaluate_drop(db_session, d2, _pack())
    events = detect_drift(db_session, d2, _pack())
    assert any(e.kind == "schema" for e in events)
    assert db_session.scalar(select(func.count()).select_from(MappingCache)) == 0


def test_value_drift_recorded(db_session):
    s = _src(db_session)
    d1 = _drop(db_session, s, [{"permit_id": "A", "valuation_usd": 1000},
                               {"permit_id": "B", "valuation_usd": 1000}], "h1")
    evaluate_drop(db_session, d1, _pack())
    d2 = _drop(db_session, s, [{"permit_id": "C", "valuation_usd": 20000},
                               {"permit_id": "D", "valuation_usd": 20000}], "h2")
    evaluate_drop(db_session, d2, _pack())
    events = detect_drift(db_session, d2, _pack())
    assert any(e.kind == "value" and e.detail["field"] == "valuation_usd" for e in events)


def test_provenance(db_session):
    s = _src(db_session)
    d = _drop(db_session, s, [{"permit_id": "P1", "valuation_usd": 5}], "h1")
    evaluate_drop(db_session, d, _pack())
    cid = db_session.scalar(select(Canonical.id))
    p = provenance(db_session, cid)
    assert p["checks_passed"] is True
    assert p["source"]["pack"] == "extract"
    assert any(c["name"] == "schema_conformance" for c in p["checks"])


def test_alert_emitted_on_quarantine(db_session):
    from edr.models import LogEvent

    s = _src(db_session)
    d = _drop(db_session, s, [{"permit_id": None, "valuation_usd": 1}], "h1")
    evaluate_drop(db_session, d, _pack())
    alerts = list(db_session.scalars(select(LogEvent).where(LogEvent.logger == "alert")))
    assert alerts and alerts[0].context.get("failed_checks")
