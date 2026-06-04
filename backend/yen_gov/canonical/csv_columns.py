"""CSV column contract loader (B1.1).

Public surface for the per-file-class CSV column contract that is the SOLE
machine-readable home of the CSV column shape (csv-column-contract.md section 2;
plan section 23.2). Consumed by:

- B1.2 ``csv_writer.py`` for write-time header + dtype + nullability emission.
- B1.3 ``csv_validator.py`` for FK + closed-enum + ``__`` + sort enforcement.
- F1 frontend codegen for the ``read_csv(columns={...})`` typed-read map.

The artifact lives at ``datasets/data/_schema/columns.json`` and is itself
validated at load against ``datasets/data/_schema/columns.schema.json``
(retained JSON-Schema escape-hatch, plan section 8 / D6).

The loader is read-only and process-cached; it MUST NOT be a write seam.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from fnmatch import fnmatchcase
from functools import lru_cache
from pathlib import Path
from typing import Final

import jsonschema

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
_COLUMNS_PATH: Final[Path] = _REPO_ROOT / "datasets" / "data" / "_schema" / "columns.json"
_COLUMNS_SCHEMA_PATH: Final[Path] = _REPO_ROOT / "datasets" / "data" / "_schema" / "columns.schema.json"


@dataclass(frozen=True)
class Column:
    """One column of one file class."""

    name: str
    dtype: str
    nullable: bool
    pk: bool = False
    fk: str | None = None
    enum: tuple[str, ...] | None = None
    derived: bool = False


@dataclass(frozen=True)
class FileClass:
    """One CSV file class (a glob over the canonical tree)."""

    glob: str
    columns: tuple[Column, ...]
    notes: str | None = None

    @property
    def pk_columns(self) -> tuple[Column, ...]:
        """Columns marked as part of the primary key, in declaration order."""
        return tuple(c for c in self.columns if c.pk)

    def column(self, name: str) -> Column:
        for col in self.columns:
            if col.name == name:
                return col
        raise KeyError(f"file class {self.glob!r} has no column {name!r}")


@dataclass(frozen=True)
class ColumnContract:
    """All file classes, keyed by glob."""

    file_classes: dict[str, FileClass]

    def for_glob(self, glob: str) -> FileClass:
        try:
            return self.file_classes[glob]
        except KeyError as err:
            raise KeyError(f"unknown file class glob: {glob!r}") from err


def _column_from_dict(raw: dict[str, object]) -> Column:
    enum_raw = raw.get("enum")
    return Column(
        name=str(raw["name"]),
        dtype=str(raw["dtype"]),
        nullable=bool(raw["nullable"]),
        pk=bool(raw.get("pk", False)),
        fk=str(raw["fk"]) if "fk" in raw and raw["fk"] is not None else None,
        enum=tuple(str(v) for v in enum_raw) if isinstance(enum_raw, list) else None,
        derived=bool(raw.get("derived", False)),
    )


@lru_cache(maxsize=1)
def load_columns(path: Path | None = None, schema_path: Path | None = None) -> ColumnContract:
    """Load and validate ``columns.json``.

    Args:
        path: Optional override for the columns.json path (tests pass a fixture).
        schema_path: Optional override for the schema-of-schemas path.

    Returns:
        Process-cached ``ColumnContract``. The cache is keyed on the (path,
        schema_path) tuple so tests can inject fixtures without poisoning the
        production-path cache.

    Raises:
        jsonschema.ValidationError: ``columns.json`` violates ``columns.schema.json``.
        FileNotFoundError: either path is absent.
    """
    columns_path = path if path is not None else _COLUMNS_PATH
    schema_path_resolved = schema_path if schema_path is not None else _COLUMNS_SCHEMA_PATH

    with columns_path.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    with schema_path_resolved.open(encoding="utf-8") as fh:
        schema = json.load(fh)
    jsonschema.validate(instance=raw, schema=schema)

    file_classes: dict[str, FileClass] = {}
    for glob, fc_raw in raw["file_classes"].items():
        columns = tuple(_column_from_dict(c) for c in fc_raw["columns"])
        notes = fc_raw.get("notes")
        file_classes[glob] = FileClass(
            glob=glob,
            columns=columns,
            notes=str(notes) if notes is not None else None,
        )
    return ColumnContract(file_classes=file_classes)


def file_class_for(repo_relative_path: str, contract: ColumnContract | None = None) -> FileClass:
    """Resolve a repo-relative POSIX CSV path to its file class.

    Matching uses ``fnmatch`` case-sensitive against the file-class glob keys.
    Datapoint and election globs are wildcard-bearing
    (``datasets/data/datapoints/geo/*.csv``,
    ``datasets/elections/assembly/state=*/election=*/candidacies.csv``);
    catalogue and entity globs are exact paths.

    Args:
        repo_relative_path: POSIX repo-relative path
            (e.g. ``"datasets/data/variables.csv"`` or
            ``"datasets/data/datapoints/geo/literacy-rate-pct-total.csv"``).
        contract: Optional pre-loaded contract (tests pass a fixture).

    Returns:
        The matching ``FileClass``.

    Raises:
        ValueError: no file-class glob matches, or more than one matches
            (ambiguous globs are a contract bug, not a runtime concern).
    """
    if "\\" in repo_relative_path:
        raise ValueError(
            f"path must be POSIX (got backslash): {repo_relative_path!r} "
            "(CLAUDE.md section 2 path rules)"
        )
    resolved_contract = contract if contract is not None else load_columns()
    matches = [
        fc for glob, fc in resolved_contract.file_classes.items()
        if fnmatchcase(repo_relative_path, glob)
    ]
    if not matches:
        raise ValueError(f"no file class matches path: {repo_relative_path!r}")
    if len(matches) > 1:
        ambiguous = ", ".join(fc.glob for fc in matches)
        raise ValueError(
            f"path {repo_relative_path!r} matches multiple file classes: {ambiguous}"
        )
    return matches[0]


__all__ = ["Column", "FileClass", "ColumnContract", "load_columns", "file_class_for"]
