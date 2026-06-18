"""Indicator metadata + canonical CSV emission for the ICED v0 fuel family.

The legacy network-fetch + folded-indicator-JSON path (``ingest_iced_fuel``)
was retired in B4-pt2.1 per parent plan section 21.4 ("network-fetch code is
deleted; ingest reads local TCPD / source CSV"). What remains is the
indicator metadata + the B1.4.3 canonical CSV emission exercised by
``backend/tests/test_iced_fuel_csv_repoint.py``.

Three indicators were emitted by the retired path:

- ``energy/state_coal_consumption_mt``         (state coal consumption, Mt)
- ``energy/state_oil_product_consumption_kt``  (state oil-product, kt; faceted)
- ``energy/state_power_purchase_share_pct``    (state procurement mix, %)
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yen_gov.canonical.adapters.eci.state_slug import eci_to_lgd_slug
from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv
from yen_gov.sources.iced_common import load_iced_response
from yen_gov.sources.iced_fuel.parsers import (
    parse_coal_consumption_state,
    parse_ppa_share,
)

# B1.4.3 - canonical CSV citation triples + variable_id prefixes per indicator.
# All three iced_fuel indicators are NITI Aayog ICED v0 endpoints (same
# producer string used across the family per
# `canonical/adapters/energy/_shared.py`); vintage = operator snapshot FY per
# ADR-0042. derive_source_id() hashes the triple at write time; the row in
# `datasets/data/entities/source.csv` is populated by B2a (sub-plan
# section "Pre-flight"). variable_ids honour parent plan section 21.6 / 21.12
# (no `__`) and ADR-0044 (no grain prefix - the legacy `state_` prefix on
# the meadow indicator id is dropped here). Per-facet split because
# csv_writer does not yet accept facet columns (sub-plan section B1.4.1..9
# point 7). concept_id binding for all three indicators is DEFERRED to B2a;
# recorded as a per-PR DEFER marker in the PR body.
_CSV_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_CSV_OUT_REL_DIR = "datasets/data/datapoints/geo"
_CSV_SOURCE_PRODUCER = "NITI Aayog India Climate & Energy Dashboard"
_CSV_SOURCE_VINTAGE = "2024-25"

_CSV_SOURCE_TITLE_COAL = (
    "State coal consumption (domestic, by grade) API"
)
_CSV_VARIABLE_PREFIX_COAL = "coal-consumption-mt"

_CSV_SOURCE_TITLE_OIL = (
    "State oil-product consumption (by product) API"
)
_CSV_VARIABLE_PREFIX_OIL = "oil-product-consumption-kt"

_CSV_SOURCE_TITLE_PPA = (
    "State power-purchase quantum and cost (procurement mix) API"
)
_CSV_VARIABLE_PREFIX_PPA = "power-purchase-share-pct"

LICENSE_ICED = {
    "id": "GoI-OpenData",
    "name": "Government of India Open Data License",
    "url": "https://www.data.gov.in/government-open-data-license-india",
    "redistributable": True,
}


@dataclass(frozen=True)
class IndicatorEmitResult:
    indicator_id: str
    artifact_path: Path
    row_count: int
    time_min: str
    time_max: str
    skipped_unmapped: int = 0


# ---------------------------------------------------------------------------
# Indicator metadata
# ---------------------------------------------------------------------------


def _indicator_coal_consumption() -> dict[str, Any]:
    return {
        "id": "energy/state_coal_consumption_mt",
        "title": "State coal consumption (Mt, FY06–FY25)",
        "description": (
            "Per-state domestic coal consumption in million tonnes per "
            "fiscal year, summed across all coal grades produced or "
            "imported within the state (raw coal + washed coal + "
            "middlings + lignite). Coal is by far India's largest "
            "primary-energy source: states with high coal consumption "
            "are typically those that host large thermal generation "
            "fleets (Maharashtra, UP, MP, Chhattisgarh) or heavy "
            "industry (steel, cement)."
        ),
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "raw",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "Mt",
        "icon": "package",
        "attribution_geography": "where_consumed",
        "comparability": "comparable_with_normalisation",
        "implementing_authority": "joint",
        "methodology_vintage": (
            "NITI Aayog ICED ``/energy/fuel-sources/coal/"
            "consumption-domestic-state`` (Coal Controller's Office / "
            "Ministry of Coal upstream). Aggregated by SUM of the 4 "
            "component grades (raw, washed, middlings, lignite); the "
            "precomputed ``TOTAL COAL`` rows are dropped to avoid "
            "double-counting (they exist for only the most-recent FYs)."
        ),
        "chart_type": "ranked",
        "notes": (
            "Coal consumption is a *consumption* statistic — the state "
            "where coal is burned, not the state where it is mined. For "
            "the production side, see installed-capacity-by-source "
            "(coal facet) and the generation-by-source artifact."
        ),
    }


def _indicator_oil_consumption() -> dict[str, Any]:
    return {
        "id": "energy/state_oil_product_consumption_kt",
        "title": "State oil-product consumption (kt, by product)",
        "description": (
            "Per-state consumption of refined petroleum products in "
            "kilotonnes (kt) per fiscal year, faceted by product: "
            "diesel-HSD, petrol, LPG, kerosene, naphtha, petroleum-coke, "
            "others. Diesel is the largest product nationally, driven by "
            "transport (heavy vehicles, agricultural pumps); LPG is the "
            "household cooking fuel after the PMUY scheme; petroleum "
            "coke is a refinery by-product used as cheap industrial fuel "
            "(cement, glass) and is regulated heavily for air-quality "
            "reasons in some states."
        ),
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "raw",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "kt",
        "icon": "fuel",
        "attribution_geography": "where_consumed",
        "comparability": "comparable_with_normalisation",
        "implementing_authority": "centre",
        "methodology_vintage": (
            "NITI Aayog ICED ``/energy/fuel-sources/oil/"
            "consumptionStateProductTrend`` (PPAC / Ministry of Petroleum "
            "& Natural Gas upstream). Per-state per-product per-FY, "
            "FY11–FY25. The ``OTHERS`` state bucket and the national "
            "aggregate row (region == ``IN``) are dropped."
        ),
        "chart_type": "ranked",
        "notes": (
            "Like coal, oil is a *consumption* statistic — the state "
            "where the product is sold/consumed. Diesel and petrol "
            "consumption track economic activity closely; LPG tracks "
            "household-coverage policy more than wealth."
        ),
    }


def _indicator_ppa_share() -> dict[str, Any]:
    return {
        "id": "energy/state_power_purchase_share_pct",
        "title": "State power-purchase mix by source (%, by source)",
        "description": (
            "Share of total electricity purchased by a state's distribution "
            "utilities, broken down by generation source (coal, hydro, "
            "solar, wind, nuclear, gas, small-hydro, bio-power, "
            "trading-and-others). Values sum to ~100% per (state, fiscal "
            "year). This is the *procurement* mix (where a state's "
            "DISCOMs buy from), not the *generation* mix (what a state's "
            "plants produce) — many states import most of their power."
        ),
        "entity_kind": "state",
        "time_grain": "fiscal_year",
        "value_kind": "share",
        "direction": "neutral",
        "scale_hint": "linear",
        "unit": "percent",
        "icon": "shopping-cart",
        "attribution_geography": "where_consumed",
        "comparability": "comparable_across_states",
        "implementing_authority": "state",
        "methodology_vintage": (
            "NITI Aayog ICED ``/statelevel-power-purchase-quantum-and-cost`` "
            "(PFC / Ministry of Power upstream). Per-state per-source per-FY, "
            "FY16–FY25. The ``totalCost`` upstream field is not emitted "
            "(many nulls in early years and unit unclear)."
        ),
        "chart_type": "ranked",
        "notes": (
            "Compare state procurement mix vs state generation mix "
            "(``state_electricity_generation_by_source_gwh``) to see "
            "the *trade pattern*: states that produce more renewable "
            "than they procure (export RE), states that procure more "
            "coal than they produce (import thermal), etc."
        ),
    }


# ---------------------------------------------------------------------------
# Emit helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Canonical CSV emission helpers (B1.4.3)
# ---------------------------------------------------------------------------


def _slug_segment(text: str) -> str:
    """Kebab-case a facet segment for use inside a `variable_id`.

    Plan section 21.6 / 21.12 ban `__`; ADR-0044 bans grain prefixes. We
    lower-case, replace any non-alphanumeric run with a single `-`, and
    strip leading/trailing `-`. Mirrors the helper in
    ``backend/yen_gov/sources/iced_ghg/ingest.py`` (B1.4.1, PR #635) and
    ``iced_macro/ingest.py`` (B1.4.2, PR #636).
    """
    out: list[str] = []
    prev_dash = True
    for ch in text.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    return "".join(out).strip("-")


def _period_to_year_int(period: str) -> int:
    """Reduce an iced_common ``YYYY-MM`` period to its fiscal-year start year.

    The iced_fuel parsers emit ``fy_to_period`` output (``YYYY-04``). The
    canonical CSV column class ``datasets/data/datapoints/geo/*.csv``
    declares ``time`` as integer. FY 2024-25 -> ``2024``. Raises
    ``ValueError`` on malformed input rather than silently truncating.
    """
    if not (isinstance(period, str) and len(period) >= 4 and period[:4].isdigit()):
        raise ValueError(f"unexpected time format {period!r}; expected 'YYYY-MM'")
    return int(period[:4])


def build_csv_variables(
    parsed_rows: list[dict[str, Any]],
    *,
    source_id: str,
    variable_prefix: str,
) -> dict[str, list[dict[str, Any]]]:
    """Split parser output into per-facet CSV row lists keyed by ``variable_id``.

    Rows may or may not carry a ``facet`` column (coal has none; oil + ppa
    do). When ``facet`` is absent the indicator collapses to a single
    ``variable_id == variable_prefix``; when present we split into one
    ``variable_id`` per facet value: ``<variable_prefix>-<facet-slug>``.
    Each output row carries the canonical 4 columns declared on file
    class ``datasets/data/datapoints/geo/*.csv``: ``entity_id``, ``time``,
    ``value``, ``source_id``.
    """
    by_variable: dict[str, list[dict[str, Any]]] = {}
    for row in parsed_rows:
        facet = row.get("facet")
        if facet is None:
            variable_id = variable_prefix
        else:
            variable_id = f"{variable_prefix}-{_slug_segment(str(facet))}"
        by_variable.setdefault(variable_id, []).append({
            "entity_id": row["entity_id"],
            "time": _period_to_year_int(row["time"]),
            "value": row["value"],
            "source_id": source_id,
        })
    return by_variable


def emit_csv_variables(
    *, repo_root: Path, by_variable: dict[str, list[dict[str, Any]]]
) -> tuple[Path, ...]:
    """Write each ``variable_id`` to ``datasets/data/datapoints/geo/<id>.csv``."""
    written: list[Path] = []
    out_dir = repo_root / _CSV_OUT_REL_DIR
    for variable_id, rows in sorted(by_variable.items()):
        path = write_csv(
            path=out_dir / f"{variable_id}.csv",
            file_class=_CSV_FILE_CLASS,
            rows=rows,
        )
        written.append(path)
    return tuple(written)


def _emit_csv_for(
    *,
    repo_root: Path,
    parsed_rows: list[dict[str, Any]],
    title: str,
    variable_prefix: str,
) -> tuple[Path, ...]:
    """Canonical CSV emission ALONGSIDE the legacy meadow/indicator JSON.

    B1.4.3 - both stores coexist (parent plan section 23.1); reader flip
    is X1a. ``source_id`` derived via ADR-0042 from
    (producer, title, vintage); one ``variable_id`` per facet (csv_writer
    facet-column support deferred).
    """
    source_id = derive_source_id(_CSV_SOURCE_PRODUCER, title, _CSV_SOURCE_VINTAGE)
    by_variable = build_csv_variables(
        parsed_rows, source_id=source_id, variable_prefix=variable_prefix
    )
    return emit_csv_variables(repo_root=repo_root, by_variable=by_variable)


# ---------------------------------------------------------------------------
# Coal-consumption re-ingest (Tier-B: orphan -> LIVE re-ingest)
# ---------------------------------------------------------------------------
#
# ICED domestic coal-consumption-by-state feed: per-(state, FY) coal
# consumption (Mt), aggregated across grades by the parser. The canonical
# single-value series carries one Mt value per (state, calendar year). This
# graduates `coal-consumption-mt` from orphan (the energy-adapter lift code
# was deleted in X1b-pt2) to LIVE re-ingest: stage the response, run the CLI,
# add new years.
#
# The (producer, title, vintage) triple below REPRODUCES the on-disk
# source_id src-c222a8e2cd61 (idempotent re-emit). Recovered verbatim from
# the retired energy adapter's SOURCE_IDS dict
# (8ea74f243^:backend/yen_gov/canonical/adapters/energy/_shared.py, key
# `iced_consumption_coal`). NB: this title differs from the
# `_CSV_SOURCE_TITLE_COAL` constant above -- the on-disk file was written by
# the energy-adapter path, NOT the iced_fuel `_emit_csv_for` path, so the
# idempotent triple is the adapter's, not iced_fuel's legacy constant. The
# variable_id reuses `_CSV_VARIABLE_PREFIX_COAL` (== "coal-consumption-mt").
_COAL_REINGEST_TITLE = (
    "Coal Consumption (Domestic) State-wise API (per-state fiscal-year "
    "coal consumption, by grade)"
)
_COAL_REINGEST_VINTAGE = "2024-25"


@dataclass(frozen=True)
class CoalConsumptionIngestResult:
    """Receipt for the single-value coal-consumption CSV emit."""

    variable_id: str
    artifact_path: Path
    row_count: int
    skipped_unmapped: int


def _to_slug(eci_st_code: str) -> str:
    """ECI st_code -> LGD slug, with the country rollup passed through.

    Mirrors ``iced_power.ingest._to_slug``. The coal parser emits ECI
    st_codes (``S13``); ``entities/geo.csv`` keys on LGD slugs
    (``maharashtra``), so the entity output is re-pointed through the
    translation. ``IN`` (national rollup) passes through unchanged even
    though the coal feed is state-only -- kept for parity with the family.
    """
    if eci_st_code == "IN":
        return "IN"
    return eci_to_lgd_slug(eci_st_code)


def build_coal_consumption_rows(
    parsed_rows: list[dict[str, Any]],
    *,
    source_id: str,
) -> dict[str, list[dict[str, Any]]]:
    """Build the single-value coal-consumption geo rows, ECI st_code -> LGD slug.

    Each parser row ``{entity_id(ECI), time("YYYY-04"), value}`` keeps its
    single-value shape (no facet -- the coal parser sums the grade dimension
    away) but its ECI st_code resolves to the LGD slug (``IN`` country
    passthrough) and its fiscal-year period reduces to the integer start year.
    Returns a one-key ``by_variable`` map keyed on ``coal-consumption-mt``,
    ready for ``emit_csv_variables``.
    """
    rows = [
        {
            "entity_id": _to_slug(str(r["entity_id"])),
            "time": _period_to_year_int(str(r["time"])),
            "value": r["value"],
            "source_id": source_id,
        }
        for r in parsed_rows
    ]
    return {_CSV_VARIABLE_PREFIX_COAL: rows}


def ingest_coal_consumption(
    *, repo_root: Path, raw_json_path: Path, decrypt: bool = True
) -> CoalConsumptionIngestResult:
    """Read a staged coal-consumption JSON, emit the slug-keyed coal CSV.

    Operator-staged local file (no network). The
    ``/energy/fuel-sources/coal/consumption-domestic-state`` feed is
    AES-encrypted on the wire, so the staged blob is the CryptoJS envelope;
    ``decrypt=True`` (default) makes ``load_iced_response`` decrypt it before
    parsing (an already-plain file still loads). Emits the single-value file
    ``datasets/data/datapoints/geo/coal-consumption-mt.csv`` with LGD-slug
    ``entity_id`` rows. The (producer, title, vintage) triple reproduces the
    on-disk ``source_id`` so a re-emit is idempotent with the committed file.
    """
    decoded = load_iced_response(raw_json_path.read_bytes(), decrypt=decrypt)
    parsed_rows, skipped = parse_coal_consumption_state(decoded)
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _COAL_REINGEST_TITLE, _COAL_REINGEST_VINTAGE
    )
    by_variable = build_coal_consumption_rows(parsed_rows, source_id=source_id)
    written = emit_csv_variables(repo_root=repo_root, by_variable=by_variable)
    return CoalConsumptionIngestResult(
        variable_id=_CSV_VARIABLE_PREFIX_COAL,
        artifact_path=written[0],
        row_count=len(by_variable[_CSV_VARIABLE_PREFIX_COAL]),
        skipped_unmapped=skipped,
    )


# ---------------------------------------------------------------------------
# Power-purchase-share re-ingest (Tier-B: orphan -> LIVE re-ingest)
# ---------------------------------------------------------------------------
#
# ICED state-level power-purchase feed: per-(state, FY, source) share (%) of
# electricity procured by a state's DISCOMs, faceted by 12 generation sources
# (biomass, coal, diesel, gas, hybrid-bundled, hydro, nuclear,
# renewable-other, small-hydro, solar, trading-other, wind). This is a
# PERCENTAGE / non-fuel-axis family that does NOT fit the geo_by_fuel
# file-class, so it stays in its existing per-facet
# `datasets/data/datapoints/geo/power-purchase-share-pct-<source>.csv` shape
# (Path B: emit the current shape, NO new file-class). This graduates the
# orphan family to LIVE re-ingest: the energy-adapter lift code that wrote
# these files was deleted in X1b-pt2.
#
# The (producer, title, vintage) triple below REPRODUCES the on-disk
# source_id src-1401f8087b0d (idempotent re-emit). Recovered verbatim from
# the FK target row in `datasets/data/entities/source.csv`. NB: this title
# differs from the `_CSV_SOURCE_TITLE_PPA` constant above -- the on-disk
# files were written by the energy-adapter path, NOT the iced_fuel
# `_emit_csv_for` path, so the idempotent triple is the adapter's, not
# iced_fuel's legacy constant. The variable_id reuses
# `_CSV_VARIABLE_PREFIX_PPA` (== "power-purchase-share-pct").
_PPA_REINGEST_TITLE = (
    "State Power Purchase Quantum and Cost API (state-wise procurement-mix "
    "share by source, fiscal-year, 12 source buckets)"
)
_PPA_REINGEST_VINTAGE = "2024-25"


@dataclass(frozen=True)
class PowerPurchaseShareIngestResult:
    """Receipt for the per-source power-purchase-share CSV emit."""

    variable_ids: tuple[str, ...]
    artifact_paths: tuple[Path, ...]
    row_count: int
    skipped_unmapped: int


def build_power_purchase_share_variables(
    parsed_rows: list[dict[str, Any]],
    *,
    source_id: str,
) -> dict[str, list[dict[str, Any]]]:
    """Build the per-source power-purchase-share geo rows, ECI st_code -> LGD slug.

    Each parser row ``{entity_id(ECI), time("YYYY-04"), value, facet(source)}``
    keeps its faceted shape but its ECI st_code resolves to the LGD slug
    (``IN`` country passthrough). ``time`` is left as the ``YYYY-04`` period
    because ``build_csv_variables`` reduces it to the integer fiscal-year
    start internally. Returns a ``by_variable`` map with one key per source
    facet (``power-purchase-share-pct-<source-slug>``), ready for
    ``emit_csv_variables``.
    """
    translated = [
        {
            "entity_id": _to_slug(str(r["entity_id"])),
            "time": r["time"],
            "value": r["value"],
            "facet": r["facet"],
        }
        for r in parsed_rows
    ]
    return build_csv_variables(
        translated, source_id=source_id, variable_prefix=_CSV_VARIABLE_PREFIX_PPA
    )


def ingest_power_purchase_share(
    *, repo_root: Path, raw_json_path: Path, decrypt: bool = True
) -> PowerPurchaseShareIngestResult:
    """Read a staged power-purchase JSON, emit the per-source share CSVs.

    Operator-staged local file (no network). The
    ``/statelevel-power-purchase-quantum-and-cost`` feed is AES-encrypted on
    the wire, so the staged blob is the CryptoJS envelope; ``decrypt=True``
    (default) makes ``load_iced_response`` decrypt it before parsing (an
    already-plain file still loads). Emits one
    ``datasets/data/datapoints/geo/power-purchase-share-pct-<source>.csv`` per
    source facet with LGD-slug ``entity_id`` rows. The
    (producer, title, vintage) triple reproduces the on-disk ``source_id`` so
    a re-emit is idempotent with the committed files.
    """
    decoded = load_iced_response(raw_json_path.read_bytes(), decrypt=decrypt)
    parsed_rows, skipped = parse_ppa_share(decoded)
    source_id = derive_source_id(
        _CSV_SOURCE_PRODUCER, _PPA_REINGEST_TITLE, _PPA_REINGEST_VINTAGE
    )
    by_variable = build_power_purchase_share_variables(
        parsed_rows, source_id=source_id
    )
    written = emit_csv_variables(repo_root=repo_root, by_variable=by_variable)
    return PowerPurchaseShareIngestResult(
        variable_ids=tuple(sorted(by_variable)),
        artifact_paths=written,
        row_count=sum(len(rows) for rows in by_variable.values()),
        skipped_unmapped=skipped,
    )
