"""Canonical CSV writer.

Sole canonical CSV emission point for tabular citizen-facing data. Reads the
column contract from ``yen_gov.canonical.csv_columns`` and enforces it at write
time; see ``docs/architecture/data/csv-column-contract.md``.

Public surface:

    from yen_gov.canonical.csv_writer import write_csv
    write_csv(path=..., file_class="datasets/data/...", rows=[{...}, ...])

    # Multi-source files (one canonical CSV fed by >1 publisher) use the
    # merge-preserving variant so re-emitting one source can never truncate
    # another source's rows (see ``upsert_source_scoped`` below):
    from yen_gov.canonical.csv_writer import upsert_source_scoped
    upsert_source_scoped(path=..., file_class="datasets/data/...",
                         new_rows=[{...}, ...], source_id="src-...")

Responsibilities:

- file_class must be a known glob in ``columns.json``; else ``KeyError``.
- Filename must not contain ``__``.
- Every row's keys are a subset of the declared columns; missing non-nullable
  / pk columns raise ``ValueError``; extra (un-declared) keys raise too.
- Per-column dtype coercion (``string`` / ``integer`` / ``number`` / ``boolean``).
- Nullability: ``None`` allowed only on ``nullable: true`` columns; otherwise
  raise. ``None`` is emitted as the empty CSV field (the null-vs-empty
  distinction for string columns is out of scope for B1 - documented as
  follow-up in PR body).
- Rows sorted deterministically by the file class's PK columns in declaration
  order. Tie-breaker on a non-PK column is not added (PK is by contract
  unique; collisions surface as a real bug, not silently re-ordered).
- Emit: UTF-8, LF line endings, trailing newline, no BOM, header row first.
- Skip-write-if-equal: if the on-disk file's PARSED row-list equals the
  newly-coerced row-list, return without touching mtime so re-running ingest
  produces a clean ``git status``. Value-level compare, NOT byte compare
  (mirrors ``core/io.write_artifact`` per CLAUDE.md section 10 amendment).

DELIBERATELY NOT in scope here (lives in ``csv_validator.py``):

- FK existence checks against sibling CSV files.
- Closed-enum membership.
- ``source_id`` mandatory-presence cross-check across files.
- Filename-equals-``<variable_id>``.csv rule for datapoints.

The writer is strict on shape; the validator is strict on cross-file integrity.

Per-indicator facet columns are supported only when declared in the file class.
Until a file class declares them, ``write_csv`` rejects undeclared columns.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_columns import (
    Column,
    ColumnContract,
    FileClass,
    load_columns,
)

__all__ = ["upsert_source_scoped", "write_csv"]

# The attribute column every observation row carries to name its upstream
# publisher (FK to ``datasets/data/entities/source.csv``). It is NOT part of
# any single-value file class's PK -- that is precisely why one PK can be
# claimed by two different sources, which is the collision ``upsert_source_scoped``
# guards against.
_SOURCE_ID_COLUMN = "source_id"


def write_csv(
    *,
    path: Path,
    file_class: str,
    rows: Iterable[dict[str, Any]],
    contract: ColumnContract | None = None,
) -> Path:
    """Write a canonical CSV artifact and return the resolved path.

    Args:
        path: target file path (any platform; written deterministically as UTF-8
            with LF line endings + trailing newline + no BOM).
        file_class: glob key into ``columns.json`` (e.g.
            ``"datasets/data/variables.csv"`` or
            ``"datasets/data/datapoints/geo/*.csv"``).
        rows: iterable of dicts; each dict's keys MUST be a subset of the file
            class's declared columns. Empty iterable is allowed (header-only
            file).
        contract: optional pre-loaded ``ColumnContract`` (tests pass a fixture).

    Returns:
        The resolved ``path``.

    Raises:
        KeyError: ``file_class`` is not declared in ``columns.json``.
        ValueError: filename contains ``__``; row has an undeclared column;
            non-nullable column is missing or ``None``; dtype coercion fails.
    """
    resolved = contract if contract is not None else load_columns()
    fc = resolved.for_glob(file_class)

    if "__" in path.name:
        raise ValueError(
            f"filename must not contain '__': {path.name!r}"
        )

    declared_names: tuple[str, ...] = tuple(c.name for c in fc.columns)
    declared_set = set(declared_names)
    by_name: dict[str, Column] = {c.name: c for c in fc.columns}
    pk_names = tuple(c.name for c in fc.pk_columns)

    materialised: list[dict[str, Any]] = []
    for index, raw_row in enumerate(rows):
        if not isinstance(raw_row, dict):
            raise ValueError(
                f"row {index} is not a dict: {type(raw_row).__name__}"
            )
        extras = set(raw_row.keys()) - declared_set
        if extras:
            raise ValueError(
                f"row {index} has undeclared columns for file class "
                f"{fc.glob!r}: {sorted(extras)}"
            )
        coerced: dict[str, Any] = {}
        for col in fc.columns:
            value = raw_row.get(col.name)
            if value is None:
                if not col.nullable:
                    raise ValueError(
                        f"row {index} column {col.name!r} is non-nullable but missing "
                        f"or None (file class {fc.glob!r})"
                    )
                coerced[col.name] = None
                continue
            coerced[col.name] = _coerce(value, col, row_index=index)
        materialised.append(coerced)

    materialised.sort(key=lambda r: tuple(_sort_key(r[n]) for n in pk_names))

    if path.exists() and _on_disk_matches(path, fc, materialised):
        return path

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(declared_names)
    for row in materialised:
        writer.writerow([_format(row[n], by_name[n]) for n in declared_names])
    text = buffer.getvalue()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return path


def upsert_source_scoped(
    *,
    path: Path,
    file_class: str,
    new_rows: Iterable[dict[str, Any]],
    source_id: str,
    contract: ColumnContract | None = None,
) -> Path:
    """Merge-preserving CSV emit that replaces ONLY one source's rows.

    The structural write discipline for a MULTI-SOURCE single-value file - a
    canonical ``geo/<id>.csv`` whose rows are contributed by more than one
    upstream publisher (e.g. ``installed-capacity-allocated-mw.csv`` = RBI
    Handbook history for FY2004-2014 + ICED recent years for FY2015+). A plain
    :func:`write_csv` accumulate-then-rewrite would TRUNCATE every row the
    current run did not re-emit, silently destroying the other sources'
    contributions. This function re-emits ONE source in place instead:

    1. Every existing row whose ``source_id`` column equals ``source_id`` is
       REPLACED wholesale by ``new_rows`` - so a key dropped from this source's
       latest extract is removed, and a changed value is updated.
    2. Every existing row contributed by ANY OTHER source is PRESERVED
       verbatim.
    3. Re-emitting one source can therefore never truncate another source's
       rows: the merge-preserving guarantee the dual-source split relies on
       (an ICED-only re-ingest never clobbers the RBI Handbook history, and an
       RBI re-ingest never clobbers the ICED years).

    Cross-source independence is ENFORCED, not assumed: if any incoming PK
    collides with a PRESERVED other-source row, the call FAILS LOUD
    (``ValueError``) rather than letting one source silently overwrite
    another. For the allocated file the keyspaces are disjoint (RBI
    FY2004-2014, ICED FY2015+), so the guard never fires in practice - it is
    the structural contract that keeps the two sources from ever being
    combined.

    Within ``new_rows`` the last row wins on a repeated PK (matching
    :func:`write_csv`'s by-PK contract). ``write_csv`` then sorts by PK and
    skip-writes when the merged output is byte-identical, so a no-op re-emit
    leaves a clean ``git status``.

    Args:
        path: target ``geo/<variable_id>.csv`` path.
        file_class: glob key into ``columns.json`` (e.g.
            ``"datasets/data/datapoints/geo/*.csv"``). MUST declare a
            ``source_id`` column.
        new_rows: the incoming rows for ``source_id`` ONLY. Every row MUST
            carry ``source_id == source_id``; a row that claims a different
            source is a programming error (``ValueError``).
        source_id: the single source whose rows this run owns and replaces.
        contract: optional pre-loaded ``ColumnContract`` (defaults to the
            shipped contract via :func:`load_columns`).

    Returns:
        The resolved ``path``.

    Raises:
        KeyError: ``file_class`` is not declared in ``columns.json``.
        ValueError: the file class declares no ``source_id`` column; an
            incoming row carries a different ``source_id``; or an incoming PK
            collides with a preserved other-source row.
    """
    resolved = contract if contract is not None else load_columns()
    fc = resolved.for_glob(file_class)
    names = tuple(c.name for c in fc.columns)
    if _SOURCE_ID_COLUMN not in names:
        raise ValueError(
            f"upsert_source_scoped requires a {_SOURCE_ID_COLUMN!r} column; "
            f"file class {fc.glob!r} declares {list(names)}"
        )
    pk_names = tuple(c.name for c in fc.pk_columns)

    incoming = list(new_rows)
    for index, row in enumerate(incoming):
        row_source_id = row.get(_SOURCE_ID_COLUMN)
        if row_source_id != source_id:
            raise ValueError(
                f"new_rows[{index}] carries {_SOURCE_ID_COLUMN}={row_source_id!r} "
                f"but upsert_source_scoped was called with source_id={source_id!r}; "
                f"every incoming row must belong to the named source"
            )

    kept_other: dict[tuple[Any, ...], dict[str, Any]] = {}
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            for raw in csv.DictReader(fh):
                existing = {
                    name: (raw.get(name) if (raw.get(name) or "") != "" else None)
                    for name in names
                }
                if existing.get(_SOURCE_ID_COLUMN) == source_id:
                    # This source's own rows are replaced wholesale by new_rows.
                    continue
                key = tuple(_pk_value(existing[n]) for n in pk_names)
                kept_other[key] = existing

    merged: dict[tuple[Any, ...], dict[str, Any]] = dict(kept_other)
    for row in incoming:
        key = tuple(_pk_value(row.get(n)) for n in pk_names)
        if key in kept_other:
            other_source_id = kept_other[key].get(_SOURCE_ID_COLUMN)
            raise ValueError(
                f"cross-source PK collision on "
                f"{dict(zip(pk_names, key, strict=True))}: incoming "
                f"source_id={source_id!r} would overwrite a row owned by "
                f"source_id={other_source_id!r}; sources must not silently "
                f"overwrite each other (file {path.name!r})"
            )
        merged[key] = {name: row.get(name) for name in names}

    return write_csv(
        path=path,
        file_class=file_class,
        rows=list(merged.values()),
        contract=resolved,
    )


# --- coercion + formatting helpers -----------------------------------------


def _coerce(value: Any, col: Column, *, row_index: int) -> Any:
    dtype = col.dtype
    try:
        if dtype == "string":
            return str(value)
        if dtype == "integer":
            if isinstance(value, bool):  # bool is an int subclass; reject early
                raise TypeError("bool is not a valid integer value")
            if isinstance(value, int):
                return value
            if isinstance(value, float):
                if not value.is_integer():
                    raise ValueError(f"float {value!r} is not integer-valued")
                return int(value)
            if isinstance(value, str):
                return int(value)
            raise TypeError(f"cannot coerce {type(value).__name__} to integer")
        if dtype == "number":
            if isinstance(value, bool):
                raise TypeError("bool is not a valid number value")
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                return float(value)
            raise TypeError(f"cannot coerce {type(value).__name__} to number")
        if dtype == "boolean":
            if isinstance(value, bool):
                return value
            if isinstance(value, str) and value in ("true", "false"):
                return value == "true"
            raise TypeError(f"cannot coerce {value!r} to boolean")
        raise ValueError(f"unsupported dtype {dtype!r}")
    except (TypeError, ValueError) as err:
        raise ValueError(
            f"row {row_index} column {col.name!r} dtype={dtype!r}: {err}"
        ) from err


def _format(value: Any, col: Column) -> str:
    if value is None:
        return ""
    dtype = col.dtype
    if dtype == "boolean":
        return "true" if value else "false"
    if dtype == "number":
        # Preserve integer-valued floats as e.g. "10" (no trailing ".0") to
        # match the OWID-grapher-shaped CSV convention; non-integer floats
        # use Python's shortest round-trippable repr.
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return repr(value) if isinstance(value, float) else str(value)
    return str(value)


def _sort_key(value: Any) -> tuple[int, Any]:
    # None never appears in a PK column (rejected upstream), but keep the
    # mixed-type sort safe by partitioning None < anything else.
    if value is None:
        return (0, "")
    return (1, value)


def _pk_value(value: Any) -> Any:
    """Normalise a PK value for keying so int/str compare equal.

    The on-disk file is read back through ``csv.DictReader`` (every field is a
    string), whereas freshly-built rows carry typed values (``time`` is an
    int). Stringifying both sides keeps ``upsert_source_scoped``'s PK merge
    and cross-source collision check robust across the two representations.
    A local copy of the rbi_handbook helper (canonical/ MUST NOT import
    adapters/ - layer rule).
    """
    return str(value) if value is not None else None


# --- skip-write-if-equal optimisation --------------------------------------


def _on_disk_matches(
    path: Path,
    fc: FileClass,
    new_rows: Sequence[dict[str, Any]],
) -> bool:
    """Return True iff the existing file parses to the same row list.

    Value-level compare against the freshly-coerced ``new_rows``; mirrors the
    skip-write gate in ``core/io.write_artifact`` so a no-op re-emit leaves
    the file's bytes + mtime untouched.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    declared_names = tuple(c.name for c in fc.columns)
    by_name = {c.name: c for c in fc.columns}
    try:
        reader = csv.reader(io.StringIO(text, newline=""))
        rows_iter = iter(reader)
        header = tuple(next(rows_iter, []))
        if header != declared_names:
            return False
        parsed: list[dict[str, Any]] = []
        for raw in rows_iter:
            if len(raw) != len(declared_names):
                return False
            entry: dict[str, Any] = {}
            for name, raw_value in zip(declared_names, raw, strict=True):
                col = by_name[name]
                if raw_value == "":
                    if not col.nullable:
                        return False
                    entry[name] = None
                    continue
                if col.dtype == "integer":
                    entry[name] = int(raw_value)
                elif col.dtype == "number":
                    entry[name] = float(raw_value)
                elif col.dtype == "boolean":
                    entry[name] = raw_value == "true"
                else:
                    entry[name] = raw_value
            parsed.append(entry)
    except (StopIteration, ValueError):
        return False
    return parsed == list(new_rows)
