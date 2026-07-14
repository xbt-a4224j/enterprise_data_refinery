"""Read queries powering the admin UI. All UI numbers come from here."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from edr.models import Canonical, DriftEvent, Drop, EvalResult, Run, Source


def overview_metrics(session: Session) -> dict:
    sources = session.scalar(select(func.count()).select_from(Source)) or 0
    enabled = session.scalar(
        select(func.count()).select_from(Source).where(Source.enabled.is_(True))
    ) or 0
    published = session.scalar(
        select(func.count()).select_from(Drop).where(Drop.status == "published")
    ) or 0
    quarantined = session.scalar(
        select(func.count()).select_from(Drop).where(Drop.status == "quarantined")
    ) or 0
    gated = published + quarantined
    pass_rate = (published / gated * 100) if gated else None
    drift = session.scalar(select(func.count()).select_from(DriftEvent)) or 0
    spend = session.scalar(select(func.coalesce(func.sum(Run.cost_usd), 0.0))) or 0.0
    tin = session.scalar(select(func.coalesce(func.sum(Run.tokens_in), 0))) or 0
    tout = session.scalar(select(func.coalesce(func.sum(Run.tokens_out), 0))) or 0
    rows = session.scalar(select(func.count()).select_from(Canonical)) or 0
    return {
        "sources": sources, "enabled": enabled, "published": published,
        "quarantined": quarantined, "pass_rate": pass_rate, "drift": drift,
        "would_be_claude": spend, "tokens_in": tin, "tokens_out": tout, "rows": rows,
    }


def recent_runs(session: Session, limit: int = 12) -> list[Run]:
    return list(session.scalars(select(Run).order_by(Run.id.desc()).limit(limit)))


def quarantined_drops(session: Session) -> list[tuple[Drop, list[EvalResult]]]:
    drops = session.scalars(
        select(Drop).where(Drop.status == "quarantined").order_by(Drop.id.desc())
    ).all()
    out = []
    for d in drops:
        fails = session.scalars(
            select(EvalResult).where(EvalResult.drop_id == d.id, EvalResult.passed.is_(False))
        ).all()
        out.append((d, fails))
    return out


def source_rows(session: Session) -> list[Source]:
    return list(session.scalars(select(Source).order_by(Source.pack_name, Source.name)))
