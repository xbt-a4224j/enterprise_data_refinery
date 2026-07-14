"""Admin/explorer routes (HTMX + Jinja)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from edr.config import get_settings
from edr.db import get_session
from edr.logging import recent_logs
from edr.models import Canonical, DriftEvent, Drop, EvalResult, Run, Source
from edr.pipeline.drift import provenance
from edr.web import queries as q
from edr.web.auth import COOKIE, is_admin, require_admin
from edr.web.templating import TEMPLATES, page

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def overview(request: Request, s: Session = Depends(get_session)):
    return page(
        request, "overview.html", title="Overview", active="overview",
        m=q.overview_metrics(s), runs=q.recent_runs(s, 8), admin=is_admin(request),
    )


@router.get("/runs", response_class=HTMLResponse)
def runs(request: Request, s: Session = Depends(get_session)):
    return page(request, "runs.html", title="Runs", active="runs", runs=q.recent_runs(s, 50))


@router.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(run_id: int, request: Request, s: Session = Depends(get_session)):
    run = s.get(Run, run_id)
    drops = s.scalars(select(Drop).where(Drop.run_id == run_id)).all() if run else []
    checks = (
        s.scalars(select(EvalResult).where(EvalResult.run_id == run_id)).all() if run else []
    )
    return page(
        request, "run_detail.html", title=f"Run #{run_id}", active="runs",
        crumb="Runs", run=run, drops=drops, checks=checks,
    )


@router.get("/gate", response_class=HTMLResponse)
def gate(request: Request, s: Session = Depends(get_session)):
    return page(request, "gate.html", title="Gate failures", active="gate",
                items=q.quarantined_drops(s))


@router.get("/logs", response_class=HTMLResponse)
def logs(request: Request, level: str = "", s: Session = Depends(get_session)):
    return page(request, "logs.html", title="System logs", active="logs", level=level,
                logs=recent_logs(s, level=level or None, limit=200))


@router.get("/logs/stream", response_class=HTMLResponse)
def logs_stream(request: Request, level: str = "", s: Session = Depends(get_session)):
    return TEMPLATES.TemplateResponse(
        request, "_loglines.html", {"logs": recent_logs(s, level=level or None, limit=200)}
    )


@router.get("/sources", response_class=HTMLResponse)
def sources(request: Request, s: Session = Depends(get_session)):
    rows = q.source_rows(s)
    counts = {
        r.id: s.scalar(
            select(func.count()).select_from(Canonical).where(Canonical.source_id == r.id)
        )
        for r in rows
    }
    return page(request, "sources.html", title="Sources", active="sources",
                rows=rows, counts=counts, admin=is_admin(request))


@router.post("/sources/{sid}/toggle")
def toggle_source(sid: int, request: Request, s: Session = Depends(get_session),
                  _: bool = Depends(require_admin)):
    src = s.get(Source, sid)
    if src:
        src.enabled = not src.enabled
        s.flush()
    return RedirectResponse("/sources", status_code=303)


@router.get("/sources/{sid}", response_class=HTMLResponse)
def source_detail(sid: int, request: Request, s: Session = Depends(get_session)):
    src = s.get(Source, sid)
    drops = s.scalars(
        select(Drop).where(Drop.source_id == sid).order_by(Drop.id.desc())
    ).all() if src else []
    drift = s.scalars(
        select(DriftEvent).where(DriftEvent.source_id == sid).order_by(DriftEvent.id.desc())
    ).all() if src else []
    return page(request, "source_detail.html", title=src.name if src else "Source",
                active="sources", crumb="Sources", src=src, drops=drops, drift=drift)


@router.get("/explore", response_class=HTMLResponse)
def explore(request: Request, source_id: int | None = None, published: str = "1",
            s: Session = Depends(get_session)):
    stmt = select(Canonical).order_by(Canonical.id.desc())
    if source_id:
        stmt = stmt.where(Canonical.source_id == source_id)
    if published == "1":
        stmt = stmt.where(Canonical.checks_passed.is_(True))
    rows = s.scalars(stmt.limit(200)).all()
    return page(request, "explore.html", title="Explorer", active="explore",
                rows=rows, sources=q.source_rows(s), source_id=source_id, published=published)


@router.get("/explore/row/{cid}", response_class=HTMLResponse)
def explore_row(cid: int, request: Request, s: Session = Depends(get_session)):
    return TEMPLATES.TemplateResponse(
        request, "_provenance.html", {"p": provenance(s, cid)}
    )


@router.get("/outputs", response_class=HTMLResponse)
def outputs(request: Request, s: Session = Depends(get_session)):
    # value variation: min/max/spread of a numeric field across published rows
    rows = s.scalars(select(Canonical).where(Canonical.checks_passed.is_(True))).all()
    vals = [r.record.get("valuation_usd") for r in rows
            if isinstance(r.record.get("valuation_usd"), int | float)]
    variation = None
    if vals:
        variation = {"min": min(vals), "max": max(vals),
                     "spread": (max(vals) / min(vals)) if min(vals) else None, "n": len(vals)}
    drift = s.scalars(select(DriftEvent).order_by(DriftEvent.id.desc()).limit(50)).all()
    # data-quality scorecard per source
    scorecard = []
    for src in q.source_rows(s):
        pub = s.scalar(select(func.count()).select_from(Drop).where(
            Drop.source_id == src.id, Drop.status == "published")) or 0
        quar = s.scalar(select(func.count()).select_from(Drop).where(
            Drop.source_id == src.id, Drop.status == "quarantined")) or 0
        total = pub + quar
        scorecard.append({"src": src, "pub": pub, "quar": quar,
                          "rate": (pub / total * 100) if total else None})
    return page(request, "outputs.html", title="Outputs", active="outputs",
                variation=variation, drift=drift, scorecard=scorecard)


@router.get("/cost", response_class=HTMLResponse)
def cost(request: Request, s: Session = Depends(get_session)):
    m = q.overview_metrics(s)
    per_pack = s.execute(
        select(Run.pack_name, func.sum(Run.tokens_in), func.sum(Run.tokens_out),
               func.sum(Run.cost_usd), func.count())
        .group_by(Run.pack_name)
    ).all()
    return page(request, "cost.html", title="Cost", active="cost", m=m, per_pack=per_pack)


@router.get("/wizard", response_class=HTMLResponse)
def wizard(request: Request):
    return page(request, "wizard.html", title="Add a source", active="wizard",
                admin=is_admin(request))


@router.get("/styleguide", response_class=HTMLResponse)
def styleguide(request: Request):
    return page(request, "styleguide.html", title="Style guide", active="styleguide")


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return page(request, "login.html", title="Sign in", active="")


@router.post("/login")
def login(request: Request, token: str = Form("")):
    if token == get_settings().admin_token:
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(COOKIE, token, httponly=True, samesite="lax")
        return resp
    return RedirectResponse("/login?e=1", status_code=303)


@router.post("/wizard/propose", response_class=HTMLResponse)
def wizard_propose(request: Request, name: str = Form(""), sample: str = Form(""),
                   _: bool = Depends(require_admin)):
    from edr.llm.base import get_provider
    from edr.web.wizard import propose_fields
    fields = propose_fields(get_provider() if sample else None, sample)
    return TEMPLATES.TemplateResponse(
        request, "_proposal.html", {"name": name, "sample": sample, "fields": fields}
    )


@router.post("/wizard/save")
def wizard_save(request: Request, name: str = Form(...), sample: str = Form(""),
                _: bool = Depends(require_admin)):
    from edr.web.wizard import propose_fields, write_pack
    write_pack(name, propose_fields(None, sample), sample)
    return RedirectResponse("/sources", status_code=303)
