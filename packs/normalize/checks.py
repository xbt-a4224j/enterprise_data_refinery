from edr.pipeline.gate import CheckOutcome


def amount_non_negative(rows, cfg):
    bad = [i for i, r in enumerate(rows)
           if isinstance(r.get("amount_usd"), int | float) and r["amount_usd"] < 0]
    return CheckOutcome(name="amount_non_negative", passed=not bad, offending=bad)


CHECKS = [amount_non_negative]
