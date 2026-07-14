from pydantic import BaseModel


class PermitRecord(BaseModel):
    permit_id: str | None = None
    address: str | None = None
    jurisdiction: str | None = None
    permit_type: str | None = None
    status: str | None = None
    issued_date: str | None = None
    valuation_usd: float | None = None
    applicant: str | None = None
    description: str | None = None
