"""Extract-pack eval checks. Full check library lands in T-022..T-025; these are the
pack-level declarations the gate runner executes."""

from edr.pipeline.gate import CheckOutcome


def required_permit_id(rows, cfg):
    bad = [i for i, r in enumerate(rows) if not r.get("permit_id")]
    return CheckOutcome(
        name="required_permit_id", passed=not bad, blocking=True,
        detail={"missing": len(bad)}, offending=bad,
    )


def valuation_non_negative(rows, cfg):
    bad = [
        i for i, r in enumerate(rows)
        if r.get("valuation_usd") is not None and r["valuation_usd"] < 0
    ]
    return CheckOutcome(
        name="valuation_non_negative", passed=not bad, blocking=True,
        detail={"negative": len(bad)}, offending=bad,
    )


CHECKS = [required_permit_id, valuation_non_negative]
