"""Dataset publisher: export gate-passed drops to a local data repo (commit + push to a
GitHub data repo out of band) as JSONL. Quarantined drops are never published.

Hugging Face Datasets export is optional and only attempted when `datasets` + a token are
available; the local JSONL export is the always-on, zero-dependency artifact."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from edr.models import Canonical, Drop, Source


def publish_drop(session: Session, drop: Drop, out_dir: Path) -> Path | None:
    """Write a published drop's canonical rows to out_dir/<pack>/<source>/<drop>.jsonl.
    Returns the path, or None if the drop is not published (fail-closed: never export
    quarantined data). Idempotent — re-publishing overwrites the same file."""
    if drop.status != "published":
        return None
    src = session.get(Source, drop.source_id)
    rows = session.scalars(
        select(Canonical).where(Canonical.drop_id == drop.id, Canonical.checks_passed.is_(True))
    ).all()
    target = out_dir / src.pack_name / src.name
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{drop.drop_date}_{drop.content_hash[:8]}.jsonl"
    with path.open("w") as f:
        for c in rows:
            f.write(json.dumps({**c.record, "_provenance": {
                "source": src.name, "run_id": c.run_id,
                "mapping_version": c.mapping_version, "drop_date": drop.drop_date,
            }}) + "\n")
    return path
