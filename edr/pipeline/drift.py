"""Drift detection + cache invalidation + provenance.

Schema drift (record shape changed) invalidates the mapping cache so the next run
re-derives the extraction (re-map). Value drift (distribution shift on numeric fields)
is recorded for the longitudinal view. Provenance answers "what produced this row?"."""

from __future__ import annotations

from statistics import mean

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from edr.models import Canonical, DriftEvent, Drop, EvalResult, MappingCache, Run, Source

VALUE_DRIFT_THRESHOLD = 0.25  # 25% relative shift in a numeric field's mean


def _rows(session: Session, drop_id: int) -> list[dict]:
    stmt = select(Canonical).where(Canonical.drop_id == drop_id)
    return [c.record for c in session.scalars(stmt)]


def _prev_drop(session: Session, source_id: int, exclude: int) -> Drop | None:
    return session.scalar(
        select(Drop)
        .where(Drop.source_id == source_id, Drop.id != exclude, Drop.status == "published")
        .order_by(Drop.id.desc())
        .limit(1)
    )


def invalidate_cache(session: Session, source_id: int) -> int:
    res = session.execute(delete(MappingCache).where(MappingCache.source_id == source_id))
    return res.rowcount or 0


def detect_drift(session: Session, drop: Drop, pack) -> list[DriftEvent]:
    events: list[DriftEvent] = []
    prev = _prev_drop(session, drop.source_id, drop.id)
    if prev is None:
        return events

    new_rows, old_rows = _rows(session, drop.id), _rows(session, prev.id)
    new_keys = {k for r in new_rows for k in r}
    old_keys = {k for r in old_rows for k in r}

    if new_keys != old_keys:
        ev = DriftEvent(
            source_id=drop.source_id, drop_id=drop.id, kind="schema",
            detail={"added": sorted(new_keys - old_keys), "removed": sorted(old_keys - new_keys)},
        )
        session.add(ev)
        events.append(ev)
        invalidate_cache(session, drop.source_id)  # trigger re-map next run

    for field in new_keys & old_keys:
        new_vals = [r[field] for r in new_rows if isinstance(r.get(field), int | float)]
        old_vals = [r[field] for r in old_rows if isinstance(r.get(field), int | float)]
        if len(new_vals) < 2 or len(old_vals) < 2:
            continue
        om = mean(old_vals) or 1e-9
        shift = abs(mean(new_vals) - om) / abs(om)
        if shift > VALUE_DRIFT_THRESHOLD:
            ev = DriftEvent(
                source_id=drop.source_id, drop_id=drop.id, kind="value",
                detail={"field": field, "old_mean": round(mean(old_vals), 2),
                        "new_mean": round(mean(new_vals), 2), "shift": round(shift, 3)},
            )
            session.add(ev)
            events.append(ev)
    session.flush()
    return events


def provenance(session: Session, canonical_id: int) -> dict:
    c = session.get(Canonical, canonical_id)
    if c is None:
        raise ValueError(f"no canonical row {canonical_id}")
    src = session.get(Source, c.source_id)
    run = session.get(Run, c.run_id) if c.run_id else None
    checks = session.scalars(select(EvalResult).where(EvalResult.drop_id == c.drop_id)).all()
    return {
        "canonical_id": c.id,
        "source": {"id": src.id, "name": src.name, "pack": src.pack_name} if src else None,
        "run_id": c.run_id,
        "run_status": run.status if run else None,
        "mapping_version": c.mapping_version,
        "checks_passed": c.checks_passed,
        "checks": [
            {"name": e.check_name, "passed": e.passed, "blocking": e.blocking} for e in checks
        ],
    }
