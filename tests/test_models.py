import pytest
from sqlalchemy.exc import IntegrityError

from edr.logging import log, recent_logs
from edr.models import Canonical, Drop, Source


def _source(db):
    s = Source(pack_name="extract", name="permits-demo")
    db.add(s)
    db.flush()
    return s


def test_canonical_carries_provenance(db_session):
    s = _source(db_session)
    d = Drop(source_id=s.id, drop_date="2026-07-01", content_hash="abc", mapping_version="v1")
    db_session.add(d)
    db_session.flush()
    c = Canonical(
        drop_id=d.id, source_id=s.id, run_id=None, mapping_version="v1",
        checks_passed=True, record={"permit_id": "P-1"},
    )
    db_session.add(c)
    db_session.flush()
    assert c.source_id == s.id and c.mapping_version == "v1" and c.checks_passed is True


def test_drop_idempotent_by_source_and_hash(db_session):
    s = _source(db_session)
    db_session.add(Drop(source_id=s.id, drop_date="2026-07-01", content_hash="h1"))
    db_session.flush()
    db_session.add(Drop(source_id=s.id, drop_date="2026-07-02", content_hash="h1"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_log_persists_and_reads_back(db_session):
    log(db_session, "warning", "gate blocked drop", logger="gate", drop_id=7)
    rows = recent_logs(db_session, level="warning")
    assert len(rows) == 1 and rows[0].context["drop_id"] == 7
