"""Run a source end to end: fetch → (cache?) extract → write canonical. The eval gate
(T-021+) decides publish vs. quarantine; here the spine produces canonical rows."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from edr.llm.base import LLMProvider
from edr.models import Canonical, Drop, MappingCache, Run, Source
from edr.packs.adapters import build_adapter
from edr.packs.base import LoadedPack
from edr.pipeline.drift import detect_drift
from edr.pipeline.extract import extract_document
from edr.pipeline.gate import evaluate_drop


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


@dataclass
class RunResult:
    drop: Drop | None
    run: Run
    llm_calls: int = 0
    cache_hits: int = 0
    records: list[dict] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def run_source(
    session: Session,
    pack: LoadedPack,
    source: Source,
    provider: LLMProvider,
    *,
    pack_dir: Path,
    drop_date: str | None = None,
) -> RunResult:
    drop_date = drop_date or date.today().isoformat()
    spec = next(s for s in pack.config.sources if s.name == source.name)
    adapter = pack.adapter or build_adapter(spec, pack_dir)

    run = Run(pack_name=pack.config.name, source_id=source.id, status="running")
    session.add(run)
    session.flush()

    refs = adapter.discover()
    doc_hashes, records, low_flags = [], [], []
    llm_calls = cache_hits = 0
    tokens_in = tokens_out = 0
    cost = 0.0
    failures: list[str] = []

    for ref in refs:
        try:
            doc = adapter.fetch(ref)
        except Exception as e:  # noqa: BLE001  one bad doc must not sink the whole run
            failures.append(f"fetch {ref}: {e}")
            continue
        dh = _hash(doc.content)
        cached = session.scalar(
            select(MappingCache).where(
                MappingCache.source_id == source.id, MappingCache.schema_hash == dh
            )
        )
        if cached is not None:
            doc_hashes.append(dh)
            records.append(cached.plan["record"])
            low_flags.append(cached.plan.get("low_confidence", False))
            cache_hits += 1
            continue
        try:
            record, low_conf, res = extract_document(pack, provider, doc)
        except Exception as e:  # noqa: BLE001
            failures.append(f"extract {ref}: {e}")
            continue
        doc_hashes.append(dh)
        llm_calls += 1
        tokens_in += res.tokens_in
        tokens_out += res.tokens_out
        cost += res.would_be_claude_usd
        records.append(record)
        low_flags.append(low_conf)
        session.add(
            MappingCache(
                source_id=source.id, schema_hash=dh,
                plan={"record": record, "low_confidence": low_conf},
            )
        )

    # Every document failed -> failed run, no drop, last-good published data untouched.
    if refs and not records:
        run.status = "failed"
        run.meta = {"failures": failures}
        session.flush()
        return RunResult(
            drop=None, run=run, llm_calls=llm_calls, cache_hits=cache_hits, failures=failures
        )

    content_hash = _hash("|".join(sorted(doc_hashes)))

    existing = session.scalar(
        select(Drop).where(Drop.source_id == source.id, Drop.content_hash == content_hash)
    )
    if existing is not None:
        run.status = "ok"
        run.meta = {"idempotent_skip": True}
        session.flush()
        return RunResult(drop=existing, run=run, llm_calls=llm_calls, cache_hits=cache_hits)

    drop = Drop(
        source_id=source.id, run_id=run.id, drop_date=drop_date,
        content_hash=content_hash, status="pending",
    )
    session.add(drop)
    session.flush()

    out_records = []
    for record, low in zip(records, low_flags, strict=True):
        session.add(
            Canonical(
                drop_id=drop.id, source_id=source.id, run_id=run.id,
                mapping_version=drop.mapping_version, checks_passed=False,
                low_confidence=low, record=record,
            )
        )
        out_records.append(record)

    # Some docs failed but others succeeded -> degraded (drop still produced + gated).
    run.status = "degraded" if failures else "ok"
    run.meta = {"failures": failures} if failures else {}
    run.tokens_in, run.tokens_out, run.cost_usd = tokens_in, tokens_out, cost
    session.flush()
    return RunResult(
        drop=drop, run=run, llm_calls=llm_calls, cache_hits=cache_hits,
        records=out_records, failures=failures,
    )


def ingest(
    session: Session,
    pack: LoadedPack,
    source: Source,
    provider: LLMProvider,
    *,
    pack_dir: Path,
    drop_date: str | None = None,
) -> RunResult:
    """Full pipeline: spine (fetch → extract → canonical) → eval gate → drift.

    Fail-closed: the gate publishes or quarantines the drop before it is queryable
    as published data.
    """
    res = run_source(session, pack, source, provider, pack_dir=pack_dir, drop_date=drop_date)
    if res.drop is not None and res.drop.status == "pending":  # fresh drop, not a skip/failure
        evaluate_drop(session, res.drop, pack, res.run)
        detect_drift(session, res.drop, pack)
    return res
