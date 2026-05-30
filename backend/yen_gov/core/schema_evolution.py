"""Schema-evolution release metadata helpers.

Row H defines the public ledger that lets validators resolve an artifact by
its declared schema version without guessing from git history. The helper is
small on purpose: current schemas still live at datasets/schemas/, while old
schemas are only used when a ledger release names a retained schema file.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_EVOLUTION_LEDGER = Path("datasets/schema-evolution.json")
SCHEMA_EVOLUTION_SCHEMA = Path("datasets/schemas/schema-evolution.schema.json")
SCHEMAS_DIR = Path("datasets/schemas")


class SchemaEvolutionError(Exception):
    """Raised when schema-evolution metadata is missing or inconsistent."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SchemaEvolutionError(f"file not found: {path.as_posix()}") from exc
    except json.JSONDecodeError as exc:
        raise SchemaEvolutionError(
            f"invalid JSON in {path.as_posix()}: {exc.msg} (line {exc.lineno})"
        ) from exc
    if not isinstance(data, dict):
        raise SchemaEvolutionError(f"top-level JSON must be an object: {path.as_posix()}")
    return data


def _posix_rel(path_text: str) -> PurePosixPath:
    if "\\" in path_text:
        raise SchemaEvolutionError(f"path must use POSIX separators: {path_text!r}")
    rel = PurePosixPath(path_text)
    if rel.is_absolute() or ".." in rel.parts:
        raise SchemaEvolutionError(f"path must be repo-relative: {path_text!r}")
    return rel


def _schema_errors(schema: dict[str, Any], data: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda err: list(err.absolute_path))
    out: list[str] = []
    for err in errors:
        pointer = "/".join(str(part) for part in err.absolute_path) or "(root)"
        out.append(f"{pointer}: {err.message}")
    return out


def load_schema_evolution_ledger(root: Path, ledger_rel: Path = SCHEMA_EVOLUTION_LEDGER) -> dict[str, Any]:
    """Load and schema-validate the public schema-evolution ledger."""
    schema = _load_json(root / SCHEMA_EVOLUTION_SCHEMA)
    ledger = _load_json(root / ledger_rel)
    errors = _schema_errors(schema, ledger)
    if errors:
        joined = "; ".join(errors)
        raise SchemaEvolutionError(f"schema-evolution ledger invalid: {joined}")
    return ledger


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _current_schema_doc(root: Path, schema_file: str) -> dict[str, Any]:
    return _load_json(root / SCHEMAS_DIR / schema_file)


def retained_schema_ref(
    ledger: dict[str, Any],
    schema_file: str,
    declared_version: str,
) -> dict[str, Any] | None:
    """Return the retained-schema reference for a historical version, if any."""
    releases = ledger.get("releases")
    if not isinstance(releases, list):
        return None
    for release in releases:
        if not isinstance(release, dict):
            continue
        if release.get("schema_file") != schema_file:
            continue
        retained = release.get("retained_schema")
        if not isinstance(retained, dict):
            continue
        if retained.get("version") == declared_version:
            return retained
    return None


def resolve_schema_for_declared_version(
    root: Path,
    schema_file: str,
    declared_version: str,
    ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve the JSON Schema document that should validate a declared version.

    The current top-level schema is used only when its ``x-version`` equals the
    declared version. Older versions must be named in ``datasets/schema-evolution.json``
    and must point at a retained schema file under ``datasets/schemas/archive/``.
    """
    current = _current_schema_doc(root, schema_file)
    if current.get("x-version") == declared_version:
        return current

    ledger_doc = ledger if ledger is not None else load_schema_evolution_ledger(root)
    retained = retained_schema_ref(ledger_doc, schema_file, declared_version)
    if retained is None:
        raise SchemaEvolutionError(
            f"no retained schema reference for {schema_file} version {declared_version}"
        )

    retained_path = root / Path(_posix_rel(str(retained["path"])))
    if not retained_path.is_file():
        raise SchemaEvolutionError(
            f"retained schema file not found for {schema_file} version {declared_version}: "
            f"{retained['path']}"
        )
    actual_hash = _sha256(retained_path)
    expected_hash = retained.get("sha256")
    if actual_hash != expected_hash:
        raise SchemaEvolutionError(
            f"retained schema hash mismatch for {schema_file} version {declared_version}: "
            f"expected {expected_hash}, got {actual_hash}"
        )

    historical = _load_json(retained_path)
    if historical.get("x-version") != declared_version:
        raise SchemaEvolutionError(
            f"retained schema {retained['path']} declares x-version "
            f"{historical.get('x-version')!r}, expected {declared_version!r}"
        )
    return historical
