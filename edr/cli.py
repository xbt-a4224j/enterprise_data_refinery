"""Command-line entrypoint: run the pipeline for a pack against the configured DB + LLM.

    python -m edr.cli ingest extract
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from edr.db import session_factory
from edr.llm.base import get_provider
from edr.models import Source
from edr.packs.loader import PACKS_DIR, discover_packs
from edr.pipeline.run import ingest


def _ensure_source(session, pack_name: str, spec) -> Source:
    src = session.scalar(
        select(Source).where(Source.pack_name == pack_name, Source.name == spec.name)
    )
    if src is None:
        src = Source(pack_name=pack_name, name=spec.name, cadence="manual", enabled=True)
        session.add(src)
        session.flush()
    return src


def cmd_ingest(pack_name: str) -> int:
    provider = get_provider()
    packs = discover_packs()
    if pack_name not in packs:
        print(f"unknown pack '{pack_name}'. available: {', '.join(packs) or '(none)'}")
        return 2
    pack = packs[pack_name]
    sess = session_factory()()
    try:
        for spec in pack.config.sources:
            src = _ensure_source(sess, pack_name, spec)
            res = ingest(sess, pack, src, provider, pack_dir=PACKS_DIR / pack_name)
            sess.commit()
            status = res.drop.status if res.drop else "no-drop"
            print(
                f"[{pack_name}/{spec.name}] run={res.run.status} drop={status} "
                f"llm_calls={res.llm_calls} cache_hits={res.cache_hits} "
                f"tokens={res.run.tokens_in}/{res.run.tokens_out} "
                f"would_be_claude=${res.run.cost_usd:.4f}"
            )
        return 0
    finally:
        sess.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="edr")
    sub = parser.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest", help="run a pack's pipeline")
    ing.add_argument("pack")
    args = parser.parse_args(argv)
    if args.cmd == "ingest":
        return cmd_ingest(args.pack)
    return 1


if __name__ == "__main__":
    sys.exit(main())
