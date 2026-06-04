"""B2a.1 source.csv emitter.

Lift ``datasets/taxonomy/sources.parquet`` (citation ledger, 11 columns)
to ``datasets/data/entities/source.csv`` (5-column retained contract per
parent plan section 7 / O3).

The 6 dropped columns (license, confidence_tier, is_issuing_authority,
verification_method, citation_full, notes) have no home in the new contract;
they retire with the parquet at X1b.

``source_id`` MUST be re-derived from the ``(producer, title, vintage)``
triple via :func:`yen_gov.canonical.citation.derive_source_id` per
CLAUDE.md section 12 + Holy Law #9. This is the chicken-and-egg seed
path; downstream callers MUST use :func:`citation.lookup_source_id` against
the emitted CSV (B2b reingest), not re-derive at every call site.

Columns retained (per ``datasets/data/_schema/columns.json``):

- ``source_id`` (derived)
- ``owner``    <- parquet ``producer``
- ``title``    <- parquet ``title``
- ``vintage``  <- parquet ``vintage``
- ``url``      <- parquet ``url_main``
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv


FILE_CLASS = "datasets/data/entities/source.csv"


def _read_rows(sources_parquet: Path) -> list[dict[str, Any]]:
    import duckdb  # lazy: keep module import surface stdlib-only

    con = duckdb.connect(":memory:")
    try:
        result = con.execute(
            "SELECT producer, title, vintage, url_main "
            "FROM read_parquet(?) "
            "ORDER BY producer, title, vintage",
            [str(sources_parquet)],
        ).fetchall()
    finally:
        con.close()
    return [
        {"producer": producer, "title": title, "vintage": vintage, "url_main": url_main}
        for producer, title, vintage, url_main in result
    ]


def emit(*, sources_parquet: Path, out_path: Path) -> Path:
    """Emit ``out_path`` from ``sources_parquet``; return the resolved path.

    Raises:
        FileNotFoundError: ``sources_parquet`` does not exist.
        ValueError: re-derivation of ``source_id`` would collide on a
            duplicate ``(producer, title, vintage)`` triple - the citation
            ledger MUST have one row per identity triple (ADR-0032).
    """
    if not sources_parquet.exists():
        raise FileNotFoundError(sources_parquet)

    parquet_rows = _read_rows(sources_parquet)
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for row in parquet_rows:
        producer = row["producer"] or ""
        title = row["title"] or ""
        vintage = row["vintage"] or ""
        if not producer or not title:
            raise ValueError(
                f"sources parquet row missing producer/title: {row!r}"
            )
        source_id = derive_source_id(producer, title, vintage)
        if source_id in seen:
            raise ValueError(
                f"duplicate source_id {source_id!r} derived from "
                f"(producer={producer!r}, title={title!r}, vintage={vintage!r}); "
                "citation ledger is one-row-per-identity-triple (ADR-0032)"
            )
        seen.add(source_id)
        rows.append(
            {
                "source_id": source_id,
                "owner": producer or None,
                "title": title or None,
                "vintage": vintage or None,
                "url": row["url_main"] or None,
            }
        )

    return write_csv(path=out_path, file_class=FILE_CLASS, rows=rows)
