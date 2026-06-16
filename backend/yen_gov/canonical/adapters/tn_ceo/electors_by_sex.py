"""Tamil Nadu CEO AC-wise electors-by-sex ingest (2021 electoral roll vintage).

The Tamil Nadu Office of the Chief Electoral Officer publishes an
AC-wise summary of the electoral roll counting Male / Female / Third
Gender electors per Assembly Constituency. The 2021 vintage carries
234 ACs (the current TN AC count for the 2008-delimitation cohort)
with one row per AC, plus 39 rolled-up subtotal rows (per-district
TOTAL and the trailing Grand Total) that are predicate-filtered out.

yen-gov ingests this as a long-format faceted CSV at::

    datasets/data/datapoints/electoral_geo/electors-persons-by-sex.csv

emitting 234 x 3 = 702 rows (one per (AC, sex) pair). The file-class
``datasets/data/datapoints/electoral_geo/*.csv`` was established by
Row C of TODO/20260614-three-ephemeral-ingests-plan.md (Hans + Max +
Fowler unanimous on Path B over Path A 'widen entities/geo.csv to
absorb 14,682 ACs' and Path C 'defer'). The FK target is
``datasets/data/entities/electoral.csv.entity_id`` (NOT
``entities/geo.csv``) because Assembly Constituencies are ECI-issued
electoral-boundary units, not LGD-coded administrative geography;
the LGD-vs-ECI issuing-authority split is cemented at the entities
tier and now mirrored at the datapoints tier.

The publisher's per-row identifier is the ``AC No.`` field
(integer 1..234 in declaration order); this maps 1:1 against the
``eci_no`` column on ``datasets/data/entities/electoral.csv`` for the
``state == 'tamil-nadu' AND delim_year == 2008 AND entity_kind == 'ac'``
filter. The resolver returns ``{eci_no -> entity_id}``; if the
publisher row count after predicate filtering does NOT equal the
resolver size (expected 234), the ingest raises - a structural
contract violation, not a data-quality warning.

Per the L-1 per-row processing-level doctrine (docs/concepts/data-quality.md),
every emitted row carries ``processing_level = "minor"`` (pure mechanical
transcode: rename columns, melt facets, attach source_id; no derived
columns, no normalisation, no joins-against-curator).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv

# Citation identity (writer-side; matches the row appended to source.csv).
PRODUCER: str = "Office of the Chief Electoral Officer, Tamil Nadu"
TITLE: str = "Tamil Nadu Electoral Roll - AC-wise Electors by Sex"
VINTAGE_2021: str = "2021"

# File-class glob (must match the entry in columns.json).
FILE_CLASS: str = (
    "datasets/data/datapoints/electoral_geo/electors-persons-by-sex.csv"
)

# Variable identifier (filename stem); appears as the indicator_id row in
# variables.csv. No grain prefix per CLAUDE.md section 10 anti-pattern +
# Max's verdict on the persona debate (variable identity is the SAME
# across grains; renderer dispatches to AC/PC/district by the entity_kind
# of the resolved FK target).
VARIABLE_ID: str = "electors-persons-by-sex"

# State + delimitation cohort that fixes the AC universe for this ingest.
# When other states ship in FB-2, each gets its own ingest (CEO-published
# vocabularies do not align cross-state; the eci_no -> entity_id resolver
# is rebuilt per state).
STATE_SLUG: str = "tamil-nadu"
DELIM_YEAR: int = 2008
EXPECTED_AC_COUNT: int = 234

# Publisher facet labels -> canonical sex enum values (mirror the
# file-class declaration in columns.json). The publisher uses
# "Third Gender" (two words, title-case); the canonical enum uses
# snake_case "third_gender" per the columns.json file-class enum.
_SEX_FACET_COLUMNS: dict[str, str] = {
    "Male": "male",
    "Female": "female",
    "Third Gender": "third_gender",
}


def is_atomic_ac_row(raw: dict[str, str]) -> bool:
    """Return True when the publisher row is an atomic AC observation.

    The publisher emits 234 atomic rows (one per AC, ``Sl No.`` is a
    1-based positive integer) interleaved with 38 per-district TOTAL
    rows and 1 Grand Total row (``Sl No.`` is ``"Total"`` or
    ``"Grand Total"``). The predicate keeps ONLY the atomic rows.

    >>> is_atomic_ac_row({"Sl No.": "1"})
    True
    >>> is_atomic_ac_row({"Sl No.": "234"})
    True
    >>> is_atomic_ac_row({"Sl No.": "Total"})
    False
    >>> is_atomic_ac_row({"Sl No.": "Grand Total"})
    False
    >>> is_atomic_ac_row({"Sl No.": ""})
    False
    """
    sl = (raw.get("Sl No.") or "").strip()
    return sl.isdigit() and int(sl) >= 1


def parse_ac_no(raw: dict[str, str], *, line_no: int) -> int:
    """Coerce the publisher's ``AC No.`` field to a positive integer.

    Raises ``ValueError`` on a blank or non-integer cell. The publisher
    populates ``AC No.`` 1..234 for atomic rows; the predicate
    :func:`is_atomic_ac_row` is expected to have filtered subtotals
    out BEFORE this is called.
    """
    raw_val = (raw.get("AC No.") or "").strip()
    if not raw_val.isdigit():
        raise ValueError(
            f"line {line_no}: AC No. cell is not a positive integer: "
            f"{raw_val!r}"
        )
    return int(raw_val)


def parse_count(raw: str, *, line_no: int, column: str) -> int:
    """Parse a publisher electors-count cell to a non-negative integer.

    The publisher emits whole-electors counts only (no fractional
    electors); zero IS a valid observation (e.g. a Third Gender bucket
    with zero declared electors) and is preserved verbatim. Blank
    cells are treated as a data-shape error (the publisher always
    populates a count, even when the count is zero); the caller will
    raise to surface the publisher anomaly rather than silently
    substituting None.
    """
    s = (raw or "").strip()
    if not s:
        raise ValueError(
            f"line {line_no}: {column} cell is empty; "
            f"publisher always populates counts (zero is valid, blank is not)."
        )
    # Tolerate the publisher's occasional comma-grouping (e.g. "123,359"
    # in some vintages; the 2021 vintage on disk uses pure integers but
    # this guards forward-compat).
    cleaned = s.replace(",", "")
    if not cleaned.lstrip("-").isdigit():
        raise ValueError(
            f"line {line_no}: {column} cell is not an integer: {s!r}"
        )
    n = int(cleaned)
    if n < 0:
        raise ValueError(
            f"line {line_no}: {column} count is negative: {n}"
        )
    return n


@dataclass(frozen=True)
class _AcResolver:
    """Resolver index built from datasets/data/entities/electoral.csv."""

    by_eci_no: dict[int, str]


def load_tn_ac_index(electoral_csv: Path) -> _AcResolver:
    """Build the ``{eci_no -> entity_id}`` resolver for TN AC universe.

    Filters ``electoral.csv`` to the
    ``state == 'tamil-nadu' AND delim_year == '2008' AND entity_kind == 'ac'``
    cohort, which is the 234-AC universe the publisher targets in
    the 2021 vintage. Raises if the resolver size does NOT equal
    :data:`EXPECTED_AC_COUNT` (a structural contract violation that
    must be surfaced to the operator BEFORE write).
    """
    if not electoral_csv.exists():
        raise FileNotFoundError(electoral_csv)
    by_eci_no: dict[int, str] = {}
    with electoral_csv.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("state") != STATE_SLUG:
                continue
            if row.get("entity_kind") != "ac":
                continue
            try:
                if int(row.get("delim_year", "0")) != DELIM_YEAR:
                    continue
            except ValueError:
                continue
            eci_raw = (row.get("eci_no") or "").strip()
            if not eci_raw.isdigit():
                raise ValueError(
                    f"electoral.csv carries a TN-2008 AC with non-integer "
                    f"eci_no: entity_id={row.get('entity_id')!r}, "
                    f"eci_no={eci_raw!r}"
                )
            eci_no = int(eci_raw)
            if eci_no in by_eci_no:
                raise ValueError(
                    f"electoral.csv carries duplicate eci_no={eci_no} "
                    f"for TN-2008 AC; existing={by_eci_no[eci_no]!r}, "
                    f"duplicate={row.get('entity_id')!r}"
                )
            by_eci_no[eci_no] = row["entity_id"]
    if len(by_eci_no) != EXPECTED_AC_COUNT:
        raise ValueError(
            f"TN-2008 AC universe size mismatch: expected "
            f"{EXPECTED_AC_COUNT}, electoral.csv yielded {len(by_eci_no)}. "
            f"Either the entities catalogue drifted or the EXPECTED_AC_COUNT "
            f"constant in tn_ceo/electors_by_sex.py needs revising."
        )
    return _AcResolver(by_eci_no=by_eci_no)


@dataclass(frozen=True)
class IngestResult:
    """Summary returned to the CLI for operator-visible reporting."""

    output_path: Path
    row_count: int
    unique_entity_ids: int
    unique_sex_facets: int
    grand_total_observed: int


def ingest(
    *,
    input_csv: Path,
    repo_root: Path,
    electoral_csv: Path | None = None,
) -> IngestResult:
    """Read the publisher ephemeral CSV and emit the canonical CSV.

    Args:
        input_csv: path to the publisher ephemeral CSV
            (typically ``datasets/ephemeral/tn_acwise_gendercount.csv``).
        repo_root: repo root used to anchor the canonical output path and
            (when not supplied explicitly) the electoral.csv lookup.
        electoral_csv: optional explicit path to the entities/electoral.csv
            corpus; tests inject a fixture. When ``None``, resolved
            relative to ``repo_root``.

    Returns:
        :class:`IngestResult` carrying the output path and operator-visible
        counts. The CLI echoes these on stdout.

    Raises:
        FileNotFoundError: input or electoral file missing.
        ValueError: any structural violation - atomic-row count mismatch,
            unresolved ``AC No.``, duplicate (entity_id, sex) emission,
            blank publisher count cell.
    """
    if not input_csv.exists():
        raise FileNotFoundError(input_csv)
    ec_path = electoral_csv if electoral_csv is not None else (
        repo_root / "datasets" / "data" / "entities" / "electoral.csv"
    )
    resolver = load_tn_ac_index(ec_path)
    source_id = derive_source_id(PRODUCER, TITLE, VINTAGE_2021)

    rows_out: list[dict[str, Any]] = []
    atomic_rows_seen = 0
    grand_total_seen = 0
    with input_csv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for line_no, raw in enumerate(reader, start=2):  # header is line 1
            sl_no = (raw.get("Sl No.") or "").strip()
            if sl_no == "Grand Total":
                grand_total_seen += 1
                continue
            if not is_atomic_ac_row(raw):
                # Subtotal row (per-district TOTAL); skip silently.
                continue
            atomic_rows_seen += 1
            ac_no = parse_ac_no(raw, line_no=line_no)
            entity_id = resolver.by_eci_no.get(ac_no)
            if entity_id is None:
                raise ValueError(
                    f"line {line_no}: publisher AC No. {ac_no} has no "
                    f"matching entity_id in electoral.csv (TN-2008 cohort)."
                )
            for publisher_col, canonical_sex in _SEX_FACET_COLUMNS.items():
                count = parse_count(
                    raw.get(publisher_col, ""),
                    line_no=line_no,
                    column=publisher_col,
                )
                rows_out.append({
                    "entity_id": entity_id,
                    "time": int(VINTAGE_2021),
                    "value": float(count),
                    "sex": canonical_sex,
                    "source_id": source_id,
                    "processing_level": "minor",
                })

    # Structural oracle 1: atomic-row count must match the expected
    # TN-2008 AC universe size.
    if atomic_rows_seen != EXPECTED_AC_COUNT:
        raise ValueError(
            f"atomic-row count mismatch: expected {EXPECTED_AC_COUNT} "
            f"per the TN-2008 AC universe, publisher emitted "
            f"{atomic_rows_seen} (after predicate filtering subtotals)."
        )

    # Structural oracle 2: the bijection (entity_id, sex) must be 3
    # rows per AC; the (entity_id) frequency must be 3.
    from collections import Counter
    per_entity = Counter(r["entity_id"] for r in rows_out)
    bad_entities = [eid for eid, n in per_entity.items() if n != 3]
    if bad_entities:
        raise ValueError(
            f"sex-facet bijection violated: {len(bad_entities)} AC(s) "
            f"emitted != 3 rows. Sample: {sorted(bad_entities)[:5]}"
        )

    # Structural oracle 3: composite PK uniqueness.
    keys = [(r["entity_id"], r["time"], r["sex"]) for r in rows_out]
    if len(set(keys)) != len(keys):
        dupes = [k for k, c in Counter(keys).items() if c > 1]
        raise ValueError(
            f"duplicate (entity_id, time, sex) keys after ingest: "
            f"{sorted(dupes)[:5]} (total dupes: {len(dupes)})."
        )

    output_path = (
        repo_root
        / "datasets"
        / "data"
        / "datapoints"
        / "electoral_geo"
        / "electors-persons-by-sex.csv"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # File-class glob is the wildcard form; write_csv resolves against it.
    glob_class = "datasets/data/datapoints/electoral_geo/*.csv"
    write_csv(path=output_path, file_class=glob_class, rows=rows_out)

    unique_entities = len({r["entity_id"] for r in rows_out})
    unique_sex = len({r["sex"] for r in rows_out})
    return IngestResult(
        output_path=output_path,
        row_count=len(rows_out),
        unique_entity_ids=unique_entities,
        unique_sex_facets=unique_sex,
        grand_total_observed=grand_total_seen,
    )
