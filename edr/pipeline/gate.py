"""Eval-gate primitives. The runner is expanded in T-021; this defines the check
contract that packs' checks.py depend on."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel


class CheckOutcome(BaseModel):
    name: str
    passed: bool
    blocking: bool = True
    detail: dict = {}
    offending: list[int] = []  # indices of offending rows


# A check takes the drop's rows and its config, returns an outcome.
CheckFn = Callable[[list[dict], dict], CheckOutcome]
