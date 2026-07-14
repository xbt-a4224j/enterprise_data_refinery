from pydantic import BaseModel


class ContractRecord(BaseModel):
    vendor: str | None = None
    amount_usd: float | None = None
    award_date: str | None = None
    agency: str | None = None
    description: str | None = None
