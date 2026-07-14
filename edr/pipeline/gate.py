"""Eval gate: the trust layer. Runs a pack's checks plus built-in checks derived from
pack.yaml, persists outcomes, and decides publish (fail-closed) vs. quarantine."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from edr.logging import log
from edr.models import Canonical, Drop, EvalResult, Run


class CheckOutcome(BaseModel):
    name: str
    passed: bool
    blocking: bool = True
    detail: dict = {}
    offending: list[int] = []  # indices of offending rows


# A check takes the drop's rows and its config, returns an outcome.
CheckFn = Callable[[list[dict], dict], CheckOutcome]


# ---- built-in checks (T-022..T-025), constructed from pack.yaml `checks` ----


def schema_conformance(schema_model: type[BaseModel]) -> CheckFn:
    def _check(rows: list[dict], cfg: dict) -> CheckOutcome:
        bad = []
        for i, r in enumerate(rows):
            try:
                schema_model.model_validate(r)
            except Exception:  # noqa: BLE001
                bad.append(i)
        return CheckOutcome(
            name="schema_conformance", passed=not bad,
            detail={"nonconforming": len(bad)}, offending=bad,
        )

    return _check


def null_rate(cfg: dict) -> CheckFn:
    limits: dict[str, float] = (cfg.get("null_rate") or {}).get("max", {})

    def _check(rows: list[dict], _cfg: dict) -> CheckOutcome:
        n = len(rows) or 1
        failures = {}
        for field, max_rate in limits.items():
            nulls = sum(1 for r in rows if r.get(field) in (None, ""))
            rate = nulls / n
            if rate > max_rate:
                failures[field] = round(rate, 3)
        return CheckOutcome(name="null_rate", passed=not failures, detail={"exceeded": failures})

    return _check


def row_count_delta(cfg: dict, prev_count: int | None) -> CheckFn:
    max_growth = (cfg.get("row_count_delta") or {}).get("max_growth")

    def _check(rows: list[dict], _cfg: dict) -> CheckOutcome:
        if max_growth is None or not prev_count:
            return CheckOutcome(name="row_count_delta", passed=True, detail={"prev": prev_count})
        growth = (len(rows) - prev_count) / prev_count
        return CheckOutcome(
            name="row_count_delta", passed=growth <= max_growth,
            detail={"prev": prev_count, "now": len(rows), "growth": round(growth, 3)},
        )

    return _check


def _prev_published_count(session: Session, source_id: int, exclude_drop: int) -> int | None:
    prev = session.scalar(
        select(Drop)
        .where(Drop.source_id == source_id, Drop.status == "published", Drop.id != exclude_drop)
        .order_by(Drop.id.desc())
        .limit(1)
    )
    if prev is None:
        return None
    return session.scalar(
        select(func.count()).select_from(Canonical).where(Canonical.drop_id == prev.id)
    )


def evaluate_drop(session: Session, drop: Drop, pack, run: Run | None = None) -> bool:
    """Run the gate for a drop's canonical rows. Fail-closed: publish only if every
    blocking check passes; otherwise quarantine and alert. Returns True if published."""
    rows_obj = list(session.scalars(select(Canonical).where(Canonical.drop_id == drop.id)))
    rows = [c.record for c in rows_obj]
    cfg = pack.config.checks or {}

    checks: list[CheckFn] = [
        schema_conformance(pack.schema_model),
        null_rate(cfg),
        row_count_delta(cfg, _prev_published_count(session, drop.source_id, drop.id)),
        *pack.checks,
    ]

    outcomes = [c(rows, cfg) for c in checks]
    for o in outcomes:
        session.add(
            EvalResult(
                run_id=run.id if run else None, drop_id=drop.id, check_name=o.name,
                passed=o.passed, blocking=o.blocking,
                detail={**o.detail, "offending": o.offending},
            )
        )

    passed = all(o.passed for o in outcomes if o.blocking)
    if passed:
        drop.status = "published"
        for c in rows_obj:
            c.checks_passed = True
    else:
        drop.status = "quarantined"
        failed = [o.name for o in outcomes if o.blocking and not o.passed]
        from edr.alerts import alert

        alert(session, f"drop {drop.id} quarantined", failed_checks=failed,
              source_id=drop.source_id)
        log(session, "warning", f"gate quarantined drop {drop.id}", logger="gate",
            drop_id=drop.id, failed=failed)
    session.flush()
    return passed
