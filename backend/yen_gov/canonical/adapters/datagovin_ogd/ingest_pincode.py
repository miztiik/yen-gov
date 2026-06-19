"""Pincode Directory ingest — Phase A.1.b.

Reads the operator-staged ``datasets/ephemeral/all_india_pincode_directory_2025.csv``,
runs it through :func:`parse_pincode_directory`, and emits two artifacts:

1. ``datasets/data/entities/pincode.csv`` — the canonical pincode reference
   table. Written directly via :mod:`csv` (no parquet, no DuckDB) per
   plan-doc section 9 ``datasets/reference/`` reshape + section 21.2
   one-format-CSV mandate. G8 (2026-06-08) moved the on-disk file to
   this path; the G8-finish PR (2026-06-08) replaced the legacy
   ``COPY ... TO ... (FORMAT PARQUET)`` writer body with a direct CSV
   emit, closing the prior MIGRATING marker.

2. UPSERT of one citation row into
   ``datasets/taxonomy/sources.parquet`` — the v2.0 sources ledger entry
   per ADR-0032 (``(producer, title, vintage)`` triple ->
   :func:`derive_source_id`).

Source identity (ADR-0032 citation ledger):
    producer = "Department of Posts, Government of India"
    title    = "All India Pincode Directory"
    vintage  = "2025"
    license  = "OGL-IN-1.0"  (data.gov.in OGD default)
    tier     = "gold"
    issuing  = True              (India Post IS the issuing authority)
    method   = "transcribed"     (operator captcha-fetch, NOT live-fetch)

Idempotency: a re-run against byte-identical input yields a
byte-identical output CSV AND a byte-identical sources.parquet
(modulo other adapters' rows in the latter). The Python sort on
``(pincode, officename)`` plus the ``newline=""`` + ``lineterminator="\n"``
+ ``csv.QUOTE_MINIMAL`` writer settings settle ordering and quoting
deterministically across platforms; the citation triple is constant.

Invocation::

    python -m yen_gov.canonical.adapters.datagovin_ogd.ingest_pincode

uses the default ephemeral input + canonical output paths. For tests
and ad-hoc work, call :func:`ingest_pincode_directory` directly with
explicit paths.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import duckdb

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.row_models import SourceRow
from yen_gov.canonical.adapters.datagovin_ogd.pincode_directory import (
    ParsedPincodeDirectory,
    parse_pincode_directory,
)
from yen_gov.canonical.adapters.datagovin_ogd.urls import KNOWN_RESOURCES

__all__ = [
    "DEFAULT_INPUT_REL",
    "DEFAULT_OUTPUT_REL",
    "DEFAULT_SOURCES_REL",
    "IngestResult",
    "PINCODE_OUTPUT_COLUMNS",
    "PINCODE_SOURCE_ID",
    "PINCODE_SOURCE_ROW",
    "PRODUCER",
    "TITLE",
    "VINTAGE",
    "build_pincode_source_row",
    "ingest_pincode_directory",
    "upsert_pincode_source",
    "upsert_pincode_source_to_parquet",
]


# ---------------------------------------------------------------------------
# Source identity (ADR-0032 citation ledger)
# ---------------------------------------------------------------------------

PRODUCER = "Department of Posts, Government of India"
TITLE = "All India Pincode Directory"
VINTAGE = "2025"

PINCODE_SOURCE_ID = derive_source_id(PRODUCER, TITLE, VINTAGE)


# ---------------------------------------------------------------------------
# Default relative paths (caller can override)
# ---------------------------------------------------------------------------

# Operator captcha-fetches the OGD CSV and drops it here; ``.gitignore``
# on ``datasets/ephemeral/`` keeps the file local-only.
DEFAULT_INPUT_REL = Path("datasets/ephemeral/all_india_pincode_directory_2025.csv")

# Canonical output: CSV under data/entities/, the canonical reference home
# (G8 2026-06-08: was datasets/reference/in/pincodes/pincode-directory.parquet;
# moved + transcoded per plan-doc section 9 + section 21.2. The writer body
# was rewritten in the G8-finish PR (2026-06-08) to emit CSV directly via
# the :mod:`csv` module — no DuckDB COPY, no intermediate parquet.)
DEFAULT_OUTPUT_REL = Path("datasets/data/entities/pincode.csv")

# Sources ledger lives at the standard taxonomy path; this PR upserts
# one row into it (alongside whatever other adapters have already
# seeded).
DEFAULT_SOURCES_REL = Path("datasets/taxonomy/sources.parquet")


# ---------------------------------------------------------------------------
# Sources row construction + UPSERT
# ---------------------------------------------------------------------------


def build_pincode_source_row() -> SourceRow:
    """The single SourceRow for the pincode directory.

    Built fresh on each call so callers always see the current
    in-module configuration (producer / title / vintage). The
    ``source_id`` is deterministic via :func:`derive_source_id` so
    re-construction is free.

    ``url_main`` points at the OGD portal landing page rather than the
    direct CSV download — the download URL embeds a per-session token
    that doesn't survive re-fetch; the portal page is the stable
    citation target.
    """
    resource = KNOWN_RESOURCES["reference/pincode_directory"]
    return SourceRow(
        source_id=PINCODE_SOURCE_ID,
        producer=PRODUCER,
        title=TITLE,
        vintage=VINTAGE,
        license="OGL-IN-1.0",
        confidence_tier="gold",
        is_issuing_authority=True,
        verification_method="transcribed",
        url_main=resource.portal_page_url,
        citation_full=None,
        notes=(
            "Operator captcha-fetched the CSV from data.gov.in (the "
            "portal requires a session-bound CAPTCHA per download), "
            "saved under datasets/ephemeral/, and ran the canonical "
            "ingest pipeline. The CSV's identity is the triple "
            "(producer, title, vintage); fetch telemetry lives "
            "out-of-contract per ADR-0032 v2.0."
        ),
    )


# Materialised at module import so test fixtures and callers can read
# the source_id without re-running derive_source_id.
PINCODE_SOURCE_ROW: SourceRow = build_pincode_source_row()


# Standard sources DDL (mirrors ``source.schema.json`` + the energy /
# boundary seeds). Duplicated here rather than imported from another
# seed module to keep adapter modules independent — energy and boundary
# evolve on different cadences and a shared DDL constant would couple
# them artificially.
_SOURCES_DDL = """
CREATE TABLE sources (
    source_id VARCHAR PRIMARY KEY,
    producer VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    vintage VARCHAR NOT NULL,
    license VARCHAR NOT NULL,
    confidence_tier VARCHAR NOT NULL,
    is_issuing_authority BOOLEAN NOT NULL,
    verification_method VARCHAR NOT NULL,
    url_main VARCHAR,
    citation_full VARCHAR,
    notes VARCHAR
)
"""


def upsert_pincode_source(con: duckdb.DuckDBPyConnection) -> int:
    """Idempotent INSERT-OR-REPLACE of the single pincode citation row
    into an in-memory ``sources`` DuckDB table.

    Caller is responsible for creating the ``sources`` table first and
    for emitting the table back to parquet afterwards. Returns ``1``
    (one citation row) so the caller can log row-counts uniformly with
    the energy and boundary seeds.
    """
    row = PINCODE_SOURCE_ROW
    con.execute(
        """
        INSERT OR REPLACE INTO sources (
            source_id, producer, title, vintage,
            license, confidence_tier, is_issuing_authority,
            verification_method, url_main, citation_full, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            row.source_id,
            row.producer,
            row.title,
            row.vintage,
            row.license,
            row.confidence_tier,
            row.is_issuing_authority,
            row.verification_method,
            row.url_main,
            row.citation_full,
            row.notes,
        ],
    )
    return 1


def upsert_pincode_source_to_parquet(sources_parquet: Path) -> int:
    """Read-modify-write wrapper around :func:`upsert_pincode_source`.

    Opens an in-memory DuckDB, loads the existing sources parquet (if
    any), upserts the pincode citation row, writes the parquet back
    sorted on ``source_id`` for byte-determinism. Returns ``1``.
    """
    sources_parquet = Path(sources_parquet)
    sources_parquet.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(":memory:")
    try:
        con.execute(_SOURCES_DDL)
        if sources_parquet.is_file():
            con.execute(
                f"INSERT INTO sources SELECT * FROM "
                f"read_parquet('{sources_parquet.as_posix()}')"
            )
        n = upsert_pincode_source(con)
        con.execute(
            f"""
            COPY (
                SELECT * FROM sources ORDER BY source_id
            ) TO '{sources_parquet.as_posix()}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()
    return n


# ---------------------------------------------------------------------------
# Pincode parquet emission
# ---------------------------------------------------------------------------


# 12 columns — the 11 upstream fields plus the source_id FK. Column
# order is hand-chosen for read-side ergonomics: pincode + officename
# first (the lookup keys), then the postal hierarchy, then the
# admin-geography fields, then the geometry, then the FK.
PINCODE_OUTPUT_COLUMNS: tuple[str, ...] = (
    "pincode",
    "officename",
    "officetype",
    "delivery",
    "divisionname",
    "regionname",
    "circlename",
    "district",
    "statename",
    "latitude",
    "longitude",
    "source_id",
)


@dataclass(frozen=True)
class IngestResult:
    """Summary of one pincode-ingest run."""

    parsed: ParsedPincodeDirectory
    output_csv: Path
    sources_parquet: Path
    source_id: str
    row_count: int  # rows actually written to the output CSV


def _write_pincode_csv(rows, dest: Path) -> None:
    """Write sorted parsed rows directly to ``dest`` as the canonical
    deterministic CSV in :data:`PINCODE_OUTPUT_COLUMNS` order.

    Determinism contract (the byte-stable shape consumers can rely on):

    - Column order matches :data:`PINCODE_OUTPUT_COLUMNS` exactly.
    - ``newline=""`` + ``lineterminator="\\n"`` so Windows does not
      inject ``\\r\\n`` and break byte-equivalence with a Linux re-run.
    - ``csv.QUOTE_MINIMAL`` so only cells containing the delimiter / a
      quote / a newline are quoted; matches DuckDB's default-friendly
      setting (which was the source of the prior committed bytes).
    - ``latitude`` / ``longitude`` are emitted via ``repr(float)`` so
      the full DOUBLE precision survives the round-trip; missing values
      become empty cells.
    - Optional textual fields (``officetype``, ``delivery``,
      ``district``, ``statename``) write the empty string when None,
      again to match the prior DuckDB COPY output.
    """
    with dest.open("w", encoding="utf-8", newline="") as fp:
        w = csv.writer(fp, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        w.writerow(PINCODE_OUTPUT_COLUMNS)
        for r in rows:
            w.writerow(
                [
                    r.pincode,
                    r.officename,
                    r.officetype if r.officetype is not None else "",
                    r.delivery if r.delivery is not None else "",
                    r.divisionname,
                    r.regionname,
                    r.circlename,
                    r.district if r.district is not None else "",
                    r.statename if r.statename is not None else "",
                    "" if r.latitude is None else repr(r.latitude),
                    "" if r.longitude is None else repr(r.longitude),
                    PINCODE_SOURCE_ID,
                ]
            )


def ingest_pincode_directory(
    *,
    input_csv: Path,
    output_csv: Path,
    sources_parquet: Path,
) -> IngestResult:
    """Parse the operator-staged CSV, emit the canonical pincode CSV
    (sorted), and UPSERT the citation row into the sources ledger.

    Idempotent: re-running against byte-identical ``input_csv`` yields
    byte-identical bytes at ``output_csv`` and ``sources_parquet``
    (modulo other adapters' rows in the latter). The sort key is
    ``(pincode, officename)``; the citation triple is module-level
    constant.

    Writer strategy: pure :mod:`csv` write — no parquet, no DuckDB.
    Python's stdlib CSV writer at 165k rows finishes in well under a
    second; the prior intermediate-CSV-then-DuckDB-COPY-to-parquet
    detour existed only to materialise the parquet output, which plan
    section 21.2 retired.
    """
    input_csv = Path(input_csv)
    output_csv = Path(output_csv)
    sources_parquet = Path(sources_parquet)

    if not input_csv.is_file():
        raise FileNotFoundError(
            f"pincode directory input not found at {input_csv.as_posix()!r}. "
            "Operator must captcha-fetch the CSV from data.gov.in and "
            "drop it at the expected path before running ingest."
        )

    raw = input_csv.read_bytes()
    parsed = parse_pincode_directory(raw)

    # Sort for byte-deterministic CSV output. (pincode, officename) is a
    # stable composite key: pincode partitions the table 9-way by
    # leading digit (geographic regions); officename disambiguates the
    # multi-PO pincodes (a single pincode can serve many post offices,
    # esp. metropolitan ones).
    sorted_rows = sorted(parsed.rows, key=lambda r: (r.pincode, r.officename))

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    _write_pincode_csv(sorted_rows, output_csv)

    # Side-effect the citation row. Done AFTER the CSV emit so a crash
    # during emit does not leave a citation pointing at no data.
    upsert_pincode_source_to_parquet(sources_parquet)

    return IngestResult(
        parsed=parsed,
        output_csv=output_csv,
        sources_parquet=sources_parquet,
        source_id=PINCODE_SOURCE_ID,
        row_count=len(sorted_rows),
    )


# ---------------------------------------------------------------------------
# CLI entry — `python -m yen_gov.canonical.adapters.datagovin_ogd.ingest_pincode`
# ---------------------------------------------------------------------------


def _resolve_repo_root() -> Path:
    """Walk up from this file until we hit the repo root.

    Repo root = the first parent that contains a ``datasets/`` directory
    AND a ``backend/`` directory. Works whether invoked from the repo
    root or from a sibling worker worktree.
    """
    here = Path(__file__).resolve()
    for candidate in here.parents:
        if (candidate / "datasets").is_dir() and (candidate / "backend").is_dir():
            return candidate
    raise RuntimeError(
        f"unable to locate repo root from {here.as_posix()!r}; "
        "neither datasets/ nor backend/ found in any ancestor"
    )


def main() -> None:
    repo_root = _resolve_repo_root()
    input_csv = repo_root / DEFAULT_INPUT_REL
    output_csv = repo_root / DEFAULT_OUTPUT_REL
    sources_parquet = repo_root / DEFAULT_SOURCES_REL

    result = ingest_pincode_directory(
        input_csv=input_csv,
        output_csv=output_csv,
        sources_parquet=sources_parquet,
    )
    print(
        f"ingest_pincode: parsed {result.parsed.record_count} records "
        f"(skipped {result.parsed.invalid_pincode_count} invalid pincodes, "
        f"{result.parsed.invalid_coordinate_count} invalid coord cells); "
        f"wrote {result.row_count} rows to "
        f"{result.output_csv.relative_to(repo_root).as_posix()}; "
        f"upserted source_id={result.source_id} into "
        f"{result.sources_parquet.relative_to(repo_root).as_posix()}"
    )


if __name__ == "__main__":
    main()
