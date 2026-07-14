"""Auto-discover and load packs from a directory. A broken pack fails loudly."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from edr.packs.base import LoadedPack, PackConfig

PACKS_DIR = Path(__file__).resolve().parent.parent.parent / "packs"


class PackLoadError(Exception):
    pass


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise PackLoadError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_pack(pack_dir: Path) -> LoadedPack:
    yml = pack_dir / "pack.yaml"
    if not yml.exists():
        raise PackLoadError(f"{pack_dir} has no pack.yaml")
    try:
        config = PackConfig.model_validate(yaml.safe_load(yml.read_text()))
    except Exception as e:  # noqa: BLE001
        raise PackLoadError(f"invalid pack.yaml in {pack_dir}: {e}") from e

    schema_mod = _load_module(pack_dir / "schema.py", f"pack_{config.name}_schema")
    schema_model = getattr(schema_mod, config.schema_ref, None)
    if not (isinstance(schema_model, type) and issubclass(schema_model, BaseModel)):
        raise PackLoadError(f"{config.name}: schema_ref '{config.schema_ref}' is not a BaseModel")

    checks: list[Any] = []
    checks_py = pack_dir / "checks.py"
    if checks_py.exists():
        checks_mod = _load_module(checks_py, f"pack_{config.name}_checks")
        checks = list(getattr(checks_mod, "CHECKS", []))

    adapter = None
    adapter_py = pack_dir / "adapter.py"
    if adapter_py.exists():
        adapter_mod = _load_module(adapter_py, f"pack_{config.name}_adapter")
        adapter = getattr(adapter_mod, "ADAPTER", None)

    return LoadedPack(
        config=config, schema_model=schema_model, pack_dir=pack_dir, checks=checks, adapter=adapter
    )


def discover_packs(packs_dir: Path = PACKS_DIR) -> dict[str, LoadedPack]:
    registry: dict[str, LoadedPack] = {}
    if not packs_dir.exists():
        return registry
    for child in sorted(packs_dir.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        pack = load_pack(child)
        registry[pack.config.name] = pack
    return registry
