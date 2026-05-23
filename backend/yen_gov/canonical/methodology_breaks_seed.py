"""Compile ``datasets/taxonomy/methodology_breaks.json`` to a Parquet
sibling for DuckDB-WASM consumption.

Mirrors the ``methodology-break.schema.json`` v1.0 row shape verbatim.
Per the elections-pivot ledger (and Phase 2 P.1.A pre-flight), the
canonical store reads the broken series from this parquet so the chart
shell can plot a vertical splice-marker at each break (D32) and surface
the prose narrative (kind + note) to the citizen.

Idempotent: re-running with byte-identical input yields byte-identical
output (no timestamps, no random IDs, deterministic row order).

P.1.A C3 seed (2026-05-22).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "METHODOLOGY_BREAK_KINDS",
    "MethodologyBreakRow",
    "compile_to_parquet",
]


# Mirrors methodology-break.schema.json `kind` enum.
METHODOLOGY_BREAK_KINDS = (
    "rebase",
    "definition_change",
    "frame_change",
    "coverage_change",
    "reclassification",
)


class MethodologyBreakRow(BaseModel):
    """One row of taxonomy/methodology_breaks.parquet.

    PK = ``methodology_version``. Mirrors the JSON Schema item shape.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    methodology_version: str = Field(min_length=1)
    at_year: int = Field(ge=1850, le=2100)
    at_period_seq: int = Field(ge=1)
    kind: Literal[
        "rebase",
        "definition_change",
        "frame_change",
        "coverage_change",
        "reclassification",
    ]
    note: str = Field(min_length=20)
    publisher_url: str | None = None
    supersedes_methodology_version: str | None = None


def _row_to_tuple(
    row: MethodologyBreakRow,
) -> tuple[str, int, int, str, str, str | None, str | None]:
    return (
        row.methodology_version,
        row.at_year,
        row.at_period_seq,
        row.kind,
        row.note,
        row.publisher_url,
        row.supersedes_methodology_version,
    )


_DDL = """
CREATE TABLE methodology_breaks (
    methodology_version VARCHAR PRIMARY KEY,
    at_year INTEGER NOT NULL,
    at_period_seq INTEGER NOT NULL,
    kind VARCHAR NOT NULL,
    note VARCHAR NOT NULL,
    publisher_url VARCHAR,
    supersedes_methodology_version VARCHAR
)
"""


def compile_to_parquet(json_in: Path, parquet_out: Path) -> int:
    """Read ``json_in``, validate, write ``parquet_out``.

    Returns the number of rows written. Caller is responsible for
    ensuring ``parquet_out.parent`` exists.
    """
    parquet_out = Path(parquet_out)
    payload = json.loads(Path(json_in).read_text(encoding="utf-8"))
    raw_rows = payload.get("methodology_breaks", [])
    rows = [MethodologyBreakRow.model_validate(r) for r in raw_rows]

    # Deterministic order: by methodology_version (PK).
    rows.sort(key=lambda r: r.methodology_version)

    con = duckdb.connect(":memory:")
    try:
        con.execute(_DDL)
        if rows:
            con.executemany(
                "INSERT INTO methodology_breaks VALUES (?, ?, ?, ?, ?, ?, ?)",
                [_row_to_tuple(r) for r in rows],
            )
        con.execute(
            f"""
            COPY (
                SELECT * FROM methodology_breaks ORDER BY methodology_version
            ) TO '{parquet_out.as_posix()}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()

    return len(rows)
