"""CSV validator (sub-plan B1.3).

Read-time validator for canonical CSV artifacts: dtype + nullability + sort
determinism are enforced by the writer (B1.2), but cross-file integrity
(FK existence, closed-enum membership, datapoint filename-equals-indicator_id)
can only be checked once sibling files exist on disk. ``validate_csv`` is the
read-time half of the fk-validator gate (parent plan section 22.6).

Public surface:

    from yen_gov.canonical.csv_validator import validate_csv
    validate_csv(path=..., file_class=..., repo_root=...)

Responsibilities (sub-plan B1.3 + parent 22.6 fk-validator):

- Header equals the declared column names exactly, in order.
- Per-cell dtype parses + nullability honoured (empty field iff column is
  ``nullable: true``).
- Closed-enum columns: every non-null value is in the declared enum set.
- FK columns: every non-null value exists in the referenced sibling CSV's
  declared FK target column (loaded relative to ``repo_root``).
- Rows sorted ascending by the file class's PK columns in declaration order
  (matches what ``csv_writer.write_csv`` emits).
- Filename has no ``__`` (parent plan section 21.12).
- For datapoint file classes (``datasets/data/datapoints/**/*.csv``) the file
  stem MUST equal a row's ``indicator_id`` in ``variables.csv`` when present
  (sub-plan B1.3 spec). If ``variables.csv`` is absent in ``repo_root`` the
  check is skipped (fixture trees may omit it; B2a will land it).

Out of scope for B1.3 (follow-ups, noted here so future agents do not
re-discover them):

- "No wall-clock value in content columns": parent 22.6 calls this out for the
  fk-validator gate, but a defensible detector needs a content-column
  taxonomy that the column contract does not yet carry. Land alongside the
  first ingest that would benefit (B1.4 or later).
- Per-indicator facet columns extending the declared list at write time
  (parent 21.6): the validator follows the writer's strictness and rejects
  undeclared columns. Both surfaces will relax together when the first facet
  ingest needs it.

No mocks (Holy Law #7). Caller owns ``repo_root`` so tests can stage fixture
trees under ``tmp_path`` (CLAUDE.md anti-pattern: validators MUST NOT walk the
real on-disk corpus from pytest).
"""

from __future__ import annotations

import csv
import io
from functools import lru_cache
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_columns import (
    Column,
    ColumnContract,
    FileClass,
    load_columns,
)

__all__ = ["validate_csv", "CsvValidationError"]


_DATAPOINTS_GLOB = "datasets/data/datapoints/"
_VARIABLES_FILE = "datasets/data/variables.csv"


class CsvValidationError(ValueError):
    """Raised when a CSV file violates its declared file-class contract."""


def validate_csv(
    *,
    path: Path,
    file_class: str,
    repo_root: Path,
    contract: ColumnContract | None = None,
) -> None:
    """Validate a canonical CSV against its declared file class.

    Args:
        path: target CSV file (must already exist; reader, not writer).
        file_class: glob key into ``columns.json`` (e.g.
            ``"datasets/data/datapoints/geo/*.csv"``).
        repo_root: directory FK targets are resolved against. Tests pass
            ``tmp_path``; production callers pass the repo root.
        contract: optional pre-loaded ``ColumnContract`` (tests pass a fixture).

    Raises:
        FileNotFoundError: ``path`` does not exist.
        KeyError: ``file_class`` is not declared in ``columns.json``.
        CsvValidationError: any contract violation (header, dtype, nullability,
            enum, FK, sort, filename).
    """
    resolved = contract if contract is not None else load_columns()
    fc = resolved.for_glob(file_class)

    if "__" in path.name:
        raise CsvValidationError(
            f"filename must not contain '__' (plan section 21.12): {path.name!r}"
        )

    if not path.exists():
        raise FileNotFoundError(path)

    declared_names = tuple(c.name for c in fc.columns)
    by_name: dict[str, Column] = {c.name: c for c in fc.columns}
    pk_names = tuple(c.name for c in fc.pk_columns)

    text = path.read_text(encoding="utf-8")
    reader = csv.reader(io.StringIO(text, newline=""))
    rows_iter = iter(reader)
    header = tuple(next(rows_iter, []))
    if header != declared_names:
        raise CsvValidationError(
            f"{path.name}: header {list(header)} does not match declared columns "
            f"{list(declared_names)} for file class {fc.glob!r}"
        )

    parsed_rows: list[dict[str, Any]] = []
    for line_no, raw in enumerate(rows_iter, start=2):
        if len(raw) != len(declared_names):
            raise CsvValidationError(
                f"{path.name}:{line_no}: expected {len(declared_names)} fields, "
                f"got {len(raw)}"
            )
        row: dict[str, Any] = {}
        for name, raw_value in zip(declared_names, raw, strict=True):
            col = by_name[name]
            if raw_value == "":
                if not col.nullable:
                    raise CsvValidationError(
                        f"{path.name}:{line_no} column {name!r} is non-nullable "
                        f"but empty"
                    )
                row[name] = None
                continue
            row[name] = _parse(raw_value, col, path=path, line_no=line_no)
            if col.enum is not None and row[name] not in col.enum:
                raise CsvValidationError(
                    f"{path.name}:{line_no} column {name!r}: value "
                    f"{row[name]!r} not in enum {list(col.enum)}"
                )
        parsed_rows.append(row)

    if pk_names:
        prev_key: tuple[Any, ...] | None = None
        for index, row in enumerate(parsed_rows):
            key = tuple(_sort_key(row[n]) for n in pk_names)
            if prev_key is not None and key < prev_key:
                raise CsvValidationError(
                    f"{path.name}: rows not sorted by PK {list(pk_names)} "
                    f"at row {index + 2} (parent plan 22.4 invariant 5)"
                )
            prev_key = key

    _check_fks(fc, parsed_rows, path=path, repo_root=repo_root, contract=resolved)

    if file_class.startswith(_DATAPOINTS_GLOB):
        _check_datapoint_filename(fc, path, repo_root=repo_root)


# --- helpers ----------------------------------------------------------------


def _parse(raw: str, col: Column, *, path: Path, line_no: int) -> Any:
    dtype = col.dtype
    try:
        if dtype == "string":
            return raw
        if dtype == "integer":
            return int(raw)
        if dtype == "number":
            return float(raw)
        if dtype == "boolean":
            if raw in ("true", "false"):
                return raw == "true"
            raise ValueError(f"expected 'true'|'false', got {raw!r}")
        raise ValueError(f"unsupported dtype {dtype!r}")
    except ValueError as err:
        raise CsvValidationError(
            f"{path.name}:{line_no} column {col.name!r} dtype={dtype!r}: {err}"
        ) from err


def _sort_key(value: Any) -> tuple[int, Any]:
    if value is None:
        return (0, "")
    return (1, value)


def _check_fks(
    fc: FileClass,
    rows: list[dict[str, Any]],
    *,
    path: Path,
    repo_root: Path,
    contract: ColumnContract,
) -> None:
    for col in fc.columns:
        if col.fk is None:
            continue
        target_path_str, target_col = _split_fk(col.fk)
        target_ids = _load_fk_targets(repo_root, target_path_str, target_col, contract)
        if target_ids is None:
            # Target file absent from repo_root; record as a violation only if
            # any non-null value exists for the FK column (callers staging
            # fixture trees may legitimately omit catalogue files).
            if not any(row[col.name] is not None for row in rows):
                continue
            raise CsvValidationError(
                f"{path.name}: column {col.name!r} has FK to "
                f"{target_path_str} but that file is missing under "
                f"{repo_root}"
            )
        for index, row in enumerate(rows):
            value = row[col.name]
            if value is None:
                continue
            value_str = str(value)
            if value_str not in target_ids:
                raise CsvValidationError(
                    f"{path.name}:{index + 2} column {col.name!r}: value "
                    f"{value_str!r} missing from {target_path_str}.{target_col}"
                )


def _split_fk(fk: str) -> tuple[str, str]:
    marker = ".csv."
    pos = fk.rfind(marker)
    if pos < 0:
        raise CsvValidationError(
            f"malformed fk spec {fk!r} (expected '<csv-path>.<column>')"
        )
    return fk[: pos + len(".csv")], fk[pos + len(marker):]


@lru_cache(maxsize=64)
def _load_fk_targets_cached(
    repo_root_str: str,
    target_path_str: str,
    target_col: str,
) -> frozenset[str] | None:
    target_path = Path(repo_root_str) / target_path_str
    if not target_path.exists():
        return None
    text = target_path.read_text(encoding="utf-8")
    reader = csv.reader(io.StringIO(text, newline=""))
    header = next(reader, [])
    if target_col not in header:
        raise CsvValidationError(
            f"fk target {target_path_str} missing column {target_col!r} "
            f"(header is {header})"
        )
    col_index = header.index(target_col)
    values: set[str] = set()
    for row in reader:
        if col_index < len(row) and row[col_index] != "":
            values.add(row[col_index])
    return frozenset(values)


def _load_fk_targets(
    repo_root: Path,
    target_path_str: str,
    target_col: str,
    contract: ColumnContract,
) -> frozenset[str] | None:
    del contract  # contract is unused today but kept for future enum-resolution
    return _load_fk_targets_cached(str(repo_root), target_path_str, target_col)


def _check_datapoint_filename(
    fc: FileClass,
    path: Path,
    *,
    repo_root: Path,
) -> None:
    variables_csv = repo_root / _VARIABLES_FILE
    if not variables_csv.exists():
        return  # fixture tree may omit; B2a lands it; skip is intentional.
    indicator_ids = _load_fk_targets_cached(
        str(repo_root), _VARIABLES_FILE, "indicator_id"
    )
    if indicator_ids is None:
        return
    stem = path.stem
    if stem not in indicator_ids:
        raise CsvValidationError(
            f"{path.name}: datapoint filename stem {stem!r} is not a known "
            f"indicator_id in {_VARIABLES_FILE} (file class {fc.glob!r})"
        )


def clear_caches() -> None:
    """Clear the FK-target cache (test fixtures recycle ``tmp_path`` dirs)."""
    _load_fk_targets_cached.cache_clear()
