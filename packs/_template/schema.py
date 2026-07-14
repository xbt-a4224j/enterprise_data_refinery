from pydantic import BaseModel


class CanonicalRecord(BaseModel):
    # Define your canonical fields here.
    id: str | None = None
    value: str | None = None
