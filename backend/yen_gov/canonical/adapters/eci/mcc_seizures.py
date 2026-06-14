"""ECI MCC-period daily enforcement-seizures ingest (17th LS General Election 2019).

The Election Commission of India publishes daily press notes during the Model
Code of Conduct (MCC) period of a general election summarising enforcement
seizures (cash, liquor, drugs/narcotics, precious metals, other freebies) by
state/UT. yen-gov ingests one such press-note series per election as a
per-event CSV at::

    datasets/elections/parliament/election=<year>/mcc_seizures.csv

(File-class declared in ``datasets/data/_schema/columns.json``; schema bump
in PR-A of ``TODO/20260614-three-ephemeral-ingests-plan.md``.)

The 2019 ephemeral input (``datasets/ephemeral/2019_eci_seizures.csv``) carries
360 rows = 36 states/UTs x 10 dates (29-Mar-2019 through 07-Apr-2019). The
publisher uses two spellings for Andaman & Nicobar Islands (one with the space
before ``(UT)``, one without) which collapse to the same canonical slug on
ingest. Dadra and Nagar Haveli and Daman and Diu are kept on their HISTORICAL
slugs (``dadra-and-nagar-haveli``, ``daman-and-diu``) - NOT merged into the
post-2020 ``dadra-and-nagar-haveli-and-daman-and-diu`` slug - because the 2019
press-note rows are historically distinct (the merger happened in Jan 2020).
The new file-class has no FK declared on ``state_slug`` for exactly this
reason: per-event publisher-distinct identity, not a state_codes.csv reference.

Per D3 ('no derived totals'), the publisher's TOTAL is preserved verbatim;
``total_seizure_inr_crore`` is NOT computed from components. Empty publisher
cells map to NULL (NOT zero) since the press note uses blank for 'no action
reported' (publisher silence, not zero-seizure).
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv

# Citation identity (writer-side; matches the row appended to source.csv).
PRODUCER: str = "Election Commission of India"
TITLE: str = (
    "Press Note - Daily Enforcement Seizures during 17th Lok Sabha "
    "General Election (MCC)"
)
VINTAGE_2019: str = "2019"

# File-class glob (must match the new entry in columns.json).
FILE_CLASS: str = "datasets/elections/parliament/election=*/mcc_seizures.csv"

# Publisher header -> canonical column name. Built once, reused in tests.
_PUBLISHER_COLUMN_MAP: dict[str, str] = {
    "Date": "date",
    "STATE/UT": "_state_raw",
    "CASH (in Rs. Cr.)": "cash_inr_crore",
    "LIQUOR Qty in Lakh litres": "liquor_qty_lakh_litres",
    "LIQUOR value in Rs. Cr.": "liquor_value_inr_crore",
    "DRUGS/ NARCOTICS Quantity in Kg": "drugs_qty_kg",
    "DRUGS/ NARCOTICS value in Rs. Cr.": "drugs_value_inr_crore",
    "PRECIOUS METALS GOLD, SILVER etc. Qty in Kg": "precious_metals_qty_kg",
    "PRECIOUS METALS GOLD, SILVER etc. value in Rs. Cr.": (
        "precious_metals_value_inr_crore"
    ),
    "OTHER ITEMS/ FREEBIES seizure": "other_items_seizure_value_inr_crore",
    "TOTAL seizure (value in Rs. Cr.)": "total_seizure_inr_crore",
}

# Publisher state-name remap (UPPER, with (UT) suffix stripped, leading/trailing
# whitespace normalised). Covers the 4 cases the bhukya-style state-codes
# alias resolver does NOT cover for the 2019 press note:
#   - Andaman & Nicobar Islands: state_codes lgd_name uses "And" not "&";
#     and the canonical slug is "andaman-and-nicobar" (no "-islands" suffix
#     - this is a known operator-vs-runtime divergence captured in
#     user-memory lessons-2026-06-12).
#   - NCT of Delhi: state_codes lgd_name is just "Delhi".
#   - Dadra/Daman: kept on HISTORICAL slugs since 2019 rows are pre-merger.
_PUBLISHER_STATE_REMAP: dict[str, str] = {
    "ANDAMAN & NICOBAR ISLANDS": "andaman-and-nicobar",
    "NCT OF DELHI": "delhi",
    "DADRA AND NAGAR HAVELI": "dadra-and-nagar-haveli",
    "DAMAN AND DIU": "daman-and-diu",
}


@dataclass(frozen=True)
class _StateIndex:
    """Resolver index built from datasets/data/entities/state_codes.csv."""

    by_upper_name: dict[str, str]
    by_alias: dict[str, str]
    by_slug: set[str]


def _load_state_index(state_codes_csv: Path) -> _StateIndex:
    by_upper_name: dict[str, str] = {}
    by_alias: dict[str, str] = {}
    by_slug: set[str] = set()
    if not state_codes_csv.exists():
        raise FileNotFoundError(state_codes_csv)
    with state_codes_csv.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            slug = (row.get("slug") or "").strip()
            if not slug:
                continue
            by_slug.add(slug)
            nu = (row.get("lgd_name") or "").strip().upper()
            if nu:
                by_upper_name[nu] = slug
            aliases_raw = (row.get("aliases") or "").strip()
            if aliases_raw:
                for alias in aliases_raw.split("|"):
                    au = alias.strip().upper()
                    if au:
                        by_alias[au] = slug
    return _StateIndex(
        by_upper_name=by_upper_name,
        by_alias=by_alias,
        by_slug=by_slug,
    )


def strip_ut_suffix(publisher_state: str) -> str:
    """Strip the trailing ``(UT)`` qualifier and surrounding whitespace.

    The 2019 press note carries both ``"State (UT)"`` (with space) and
    ``"State(UT)"`` (no space) for the same UT; the latter is a publisher
    typo. Both collapse to the canonical name on strip.

    >>> strip_ut_suffix("Chandigarh (UT)")
    'Chandigarh'
    >>> strip_ut_suffix("Andaman & Nicobar Islands(UT)")
    'Andaman & Nicobar Islands'
    >>> strip_ut_suffix("Tamil Nadu")
    'Tamil Nadu'
    """
    s = publisher_state.strip()
    for suffix in (" (UT)", "(UT)"):
        if s.endswith(suffix):
            return s[: -len(suffix)].strip()
    return s


def resolve_state_slug(
    publisher_state: str,
    *,
    index: _StateIndex,
    remap: dict[str, str] | None = None,
) -> str | None:
    """Resolve a publisher state-name string to a canonical state slug.

    Resolution order:
      1. remap (UPPER, post-strip-UT) - publisher-specific overrides.
      2. state_codes.csv UPPER(lgd_name) - canonical match.
      3. state_codes.csv UPPER(alias) - alias match.

    Returns the slug on hit; ``None`` on miss. Callers should treat None as
    an ingest error (the ECI vocabulary is closed and well-known; a miss
    means the operator must extend ``_PUBLISHER_STATE_REMAP`` or the
    upstream state_codes.csv aliases).
    """
    remap_effective = remap if remap is not None else _PUBLISHER_STATE_REMAP
    stripped = strip_ut_suffix(publisher_state)
    upper = stripped.upper()
    if not upper:
        return None
    hit = remap_effective.get(upper)
    if hit:
        return hit
    hit = index.by_upper_name.get(upper)
    if hit:
        return hit
    hit = index.by_alias.get(upper)
    if hit:
        return hit
    return None


def parse_eci_date(value: str) -> str:
    """Parse the ECI press-note ``DD-MMM-YY`` date to ISO-8601 ``YYYY-MM-DD``.

    The publisher uses a 2-digit year (``19`` for 2019). yen-gov pivots on
    the 2050 boundary: ``00..49`` -> 20YY, ``50..99`` -> 19YY. The 2019 MCC
    press notes are all ``-19``, so this resolves to ``2019-...``. The
    pivot is documented here so future MCC vintages (2024, 2029, ...)
    pick up correctly.

    >>> parse_eci_date("29-Mar-19")
    '2019-03-29'
    >>> parse_eci_date("07-Apr-19")
    '2019-04-07'
    """
    s = value.strip()
    if not s:
        raise ValueError("date cell is empty")
    parsed = dt.datetime.strptime(s, "%d-%b-%y")
    if parsed.year < 1950:
        parsed = parsed.replace(year=parsed.year + 100)
    return parsed.date().isoformat()


def parse_number_or_none(raw: str) -> float | None:
    """Coerce a publisher numeric cell to ``float`` or ``None``.

    Per the file-class notes, the publisher uses blank for 'no action
    reported' (publisher silence, NOT zero-seizure); we preserve that
    distinction and return ``None`` for empty cells. The writer maps
    ``None`` to the empty CSV field on a nullable column.

    >>> parse_number_or_none("0.00")
    0.0
    >>> parse_number_or_none("1.42")
    1.42
    >>> parse_number_or_none("")
    >>> parse_number_or_none("   ")
    """
    s = (raw or "").strip()
    if not s:
        return None
    return float(s)


@dataclass(frozen=True)
class IngestResult:
    """Summary returned to the CLI for operator-visible reporting."""

    output_path: Path
    row_count: int
    unique_state_slugs: int
    unique_dates: int


def ingest(
    *,
    input_csv: Path,
    repo_root: Path,
    election_year: int,
    state_codes_csv: Path | None = None,
) -> IngestResult:
    """Read the publisher ephemeral CSV and emit the canonical per-event CSV.

    Args:
        input_csv: path to the ephemeral publisher CSV
            (``datasets/ephemeral/2019_eci_seizures.csv``).
        repo_root: repo root used to anchor the canonical output path and
            (when not supplied explicitly) the state_codes.csv lookup.
        election_year: parliament election year (4-digit) used in the Hive
            partition (``election=2019``).
        state_codes_csv: optional explicit path to state_codes.csv (tests
            inject a fixture); when ``None``, resolved relative to
            ``repo_root``.

    Returns:
        :class:`IngestResult` carrying the resolved output path and a few
        operator-visible counts. The CLI echoes these on stdout.

    Raises:
        FileNotFoundError: input or state-codes file missing.
        ValueError: any publisher row fails state-slug resolution or
            numeric coercion (the press-note vocabulary is closed; a miss
            means the operator must extend ``_PUBLISHER_STATE_REMAP``).
    """
    if not input_csv.exists():
        raise FileNotFoundError(input_csv)
    sc_path = state_codes_csv if state_codes_csv is not None else (
        repo_root / "datasets" / "data" / "entities" / "state_codes.csv"
    )
    index = _load_state_index(sc_path)
    source_id = derive_source_id(PRODUCER, TITLE, VINTAGE_2019)

    rows_out: list[dict[str, Any]] = []
    with input_csv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for line_no, raw in enumerate(reader, start=2):  # header is line 1
            publisher_state = (raw.get("STATE/UT") or "").strip()
            if not publisher_state:
                raise ValueError(
                    f"line {line_no}: STATE/UT cell is empty"
                )
            slug = resolve_state_slug(publisher_state, index=index)
            if slug is None:
                raise ValueError(
                    f"line {line_no}: cannot resolve state {publisher_state!r} "
                    f"to a canonical slug; extend _PUBLISHER_STATE_REMAP."
                )
            row_out: dict[str, Any] = {
                "state_slug": slug,
                "date": parse_eci_date(raw["Date"]),
                "cash_inr_crore": parse_number_or_none(
                    raw.get("CASH (in Rs. Cr.)", "")
                ),
                "liquor_qty_lakh_litres": parse_number_or_none(
                    raw.get("LIQUOR Qty in Lakh litres", "")
                ),
                "liquor_value_inr_crore": parse_number_or_none(
                    raw.get("LIQUOR value in Rs. Cr.", "")
                ),
                "drugs_qty_kg": parse_number_or_none(
                    raw.get("DRUGS/ NARCOTICS Quantity in Kg", "")
                ),
                "drugs_value_inr_crore": parse_number_or_none(
                    raw.get("DRUGS/ NARCOTICS value in Rs. Cr.", "")
                ),
                "precious_metals_qty_kg": parse_number_or_none(
                    raw.get(
                        "PRECIOUS METALS GOLD, SILVER etc. Qty in Kg",
                        "",
                    )
                ),
                "precious_metals_value_inr_crore": parse_number_or_none(
                    raw.get(
                        "PRECIOUS METALS GOLD, SILVER etc. value in Rs. Cr.",
                        "",
                    )
                ),
                "other_items_seizure_value_inr_crore": parse_number_or_none(
                    raw.get("OTHER ITEMS/ FREEBIES seizure", "")
                ),
                "total_seizure_inr_crore": parse_number_or_none(
                    raw.get("TOTAL seizure (value in Rs. Cr.)", "")
                ),
                "source_id": source_id,
                "processing_level": "minor",
            }
            rows_out.append(row_out)

    # Oracle check: bijection on (state_slug, date). This catches accidental
    # row duplication (e.g. if a future remap collapses two distinct
    # historical UTs into one slug) BEFORE write_csv's PK-sort silently
    # drops the conflict.
    keys = [(r["state_slug"], r["date"]) for r in rows_out]
    if len(set(keys)) != len(keys):
        from collections import Counter
        dupes = [k for k, c in Counter(keys).items() if c > 1]
        raise ValueError(
            f"duplicate (state_slug, date) keys after ingest: {sorted(dupes)[:5]}"
            f" (total dupes: {len(dupes)})"
        )

    output_path = (
        repo_root
        / "datasets"
        / "elections"
        / "parliament"
        / f"election={election_year}"
        / "mcc_seizures.csv"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv(path=output_path, file_class=FILE_CLASS, rows=rows_out)

    unique_slugs = len({r["state_slug"] for r in rows_out})
    unique_dates = len({r["date"] for r in rows_out})
    return IngestResult(
        output_path=output_path,
        row_count=len(rows_out),
        unique_state_slugs=unique_slugs,
        unique_dates=unique_dates,
    )
