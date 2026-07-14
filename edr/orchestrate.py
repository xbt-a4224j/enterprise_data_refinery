"""Dagster orchestration: one asset per reference Pack, a job that materializes all of
them, and a daily schedule. Each asset runs the full ingest pipeline (fetch → extract →
gate → drift → publish) with retries + exponential backoff on transient errors."""

from dagster import (
    AssetExecutionContext,
    Backoff,
    Definitions,
    RetryPolicy,
    ScheduleDefinition,
    asset,
    define_asset_job,
)
from sqlalchemy import select

from edr.llm.base import get_provider
from edr.models import Source
from edr.packs.loader import PACKS_DIR, discover_packs
from edr.pipeline.run import ingest

RETRY = RetryPolicy(max_retries=3, delay=2, backoff=Backoff.EXPONENTIAL)


def _ensure_source(session, pack_name, spec) -> Source:
    src = session.scalar(
        select(Source).where(Source.pack_name == pack_name, Source.name == spec.name)
    )
    if src is None:
        src = Source(pack_name=pack_name, name=spec.name, cadence="scheduled", enabled=True)
        session.add(src)
        session.flush()
    return src


def _run_pack(context: AssetExecutionContext, pack_name: str) -> dict:
    from edr.db import session_factory

    provider = get_provider()
    pack = discover_packs()[pack_name]
    session = session_factory()()
    statuses: list[str] = []
    try:
        for spec in pack.config.sources:
            src = _ensure_source(session, pack_name, spec)
            res = ingest(session, pack, src, provider, pack_dir=PACKS_DIR / pack_name)
            session.commit()
            status = res.drop.status if res.drop else "no-drop"
            statuses.append(status)
            context.log.info(f"{pack_name}/{spec.name}: run={res.run.status} drop={status}")
        return {"pack": pack_name, "drops": statuses}
    finally:
        session.close()


@asset(retry_policy=RETRY, group_name="refine")
def extract_drop(context: AssetExecutionContext) -> dict:
    return _run_pack(context, "extract")


@asset(retry_policy=RETRY, group_name="refine")
def triage_drop(context: AssetExecutionContext) -> dict:
    return _run_pack(context, "triage")


@asset(retry_policy=RETRY, group_name="refine")
def normalize_drop(context: AssetExecutionContext) -> dict:
    return _run_pack(context, "normalize")


refine_all = define_asset_job("refine_all", selection="*")
daily = ScheduleDefinition(job=refine_all, cron_schedule="0 6 * * *")

defs = Definitions(
    assets=[extract_drop, triage_drop, normalize_drop],
    jobs=[refine_all],
    schedules=[daily],
)
