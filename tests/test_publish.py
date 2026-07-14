import json
from pathlib import Path

from sqlalchemy import select

from edr.llm.fake import FakeProvider
from edr.models import Drop, Source
from edr.packs.loader import discover_packs
from edr.pipeline.run import ingest
from edr.publish import publish_drop

ROOT = Path(__file__).resolve().parent.parent


def test_publishes_clean_drop_and_skips_quarantined(db_session, tmp_path):
    pack = discover_packs(ROOT / "packs")["extract"]
    src = Source(pack_name="extract", name="permits-demo")
    db_session.add(src)
    db_session.flush()
    ingest(db_session, pack, src,
           FakeProvider(responder=lambda c: {"permit_id": c.strip()[:12], "valuation_usd": 5}),
           pack_dir=pack.pack_dir)
    drop = db_session.scalar(select(Drop))
    path = publish_drop(db_session, drop, tmp_path)
    assert path and path.exists()
    lines = path.read_text().strip().splitlines()
    assert lines and "_provenance" in json.loads(lines[0])

    # quarantined drop is never exported
    drop.status = "quarantined"
    db_session.flush()
    assert publish_drop(db_session, drop, tmp_path) is None
