from edr.pipeline.gate import CheckOutcome

ALLOWED = {"billing", "fraud", "service", "reporting", "other"}


def category_valid(rows, cfg):
    bad = [i for i, r in enumerate(rows) if r.get("category") not in ALLOWED]
    return CheckOutcome(name="category_valid", passed=not bad, offending=bad)


CHECKS = [category_valid]
