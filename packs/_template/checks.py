from edr.pipeline.gate import CheckOutcome


def example_check(rows, cfg):
    return CheckOutcome(name="example_check", passed=True)


CHECKS = [example_check]
