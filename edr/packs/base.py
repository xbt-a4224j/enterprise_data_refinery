"""Pack abstraction: the pack.yaml schema, adapter/check protocols, and the loaded-pack
container. A Pack is one document domain — adding one requires zero core changes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

TaskType = Literal["extract", "triage", "normalize"]


class SourceSpec(BaseModel):
    name: str
    kind: Literal["file", "http", "socrata"] = "file"
    location: str  # directory/glob for file, base URL for http/socrata
    options: dict[str, Any] = Field(default_factory=dict)


class PackConfig(BaseModel):
    """Validated shape of a pack.yaml."""

    name: str
    task_type: TaskType
    cadence: str = "manual"
    schema_ref: str = "CanonicalRecord"  # attribute name in the pack's schema.py
    instructions: str = ""  # extraction/mapping guidance for the LLM
    sources: list[SourceSpec] = Field(default_factory=list)
    checks: dict[str, Any] = Field(default_factory=dict)  # per-check thresholds/config


class RawDoc(BaseModel):
    ref: str
    content: str
    meta: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class SourceAdapter(Protocol):
    def discover(self) -> list[str]: ...
    def fetch(self, ref: str) -> RawDoc: ...


class Check(BaseModel):
    """A declarative eval check result contribution. Packs return a list of Check specs
    from checks.py; the gate runner executes them."""

    name: str
    blocking: bool = True


class LoadedPack(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    config: PackConfig
    schema_model: type[BaseModel]
    pack_dir: Path
    checks: list[Any] = Field(default_factory=list)  # callables (rows, cfg) -> CheckOutcome
    adapter: Any | None = None
