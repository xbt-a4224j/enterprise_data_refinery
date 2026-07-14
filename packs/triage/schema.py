from typing import Literal

from pydantic import BaseModel


class ComplaintTriage(BaseModel):
    category: Literal["billing", "fraud", "service", "reporting", "other"] | None = None
    severity: Literal["low", "medium", "high"] | None = None
    routing_team: str | None = None
    summary: str | None = None
