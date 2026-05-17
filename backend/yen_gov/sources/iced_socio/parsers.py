"""Pure parsers + indicator catalogue for the ICED socio-economic adapter.

Five indicators ingested from five ICED API endpoints (one each, no
multi-endpoint composition). Per Hans (Governance) triage 2026-05-14:

    1. economy/state_per_capita_nsdp_constant_2011_12_inr  (priority 1)
    2. human_development/state_hdi                          (priority 2)
    3. economy/state_per_capita_consumption_inr             (priority 3)
    4. demography/state_population_by_sex_count             (priority 5)
    5. environment/india_ghg_emissions_mtco2e_by_sector     (priority 6)

(Hans's priority-4 indicator â€” per-capita income at current prices â€” is
already shipped as ``economy/state_per_capita_nsdp_current_inr.json``
from the state-wise-deep-dive ingest. We do not re-emit it here.)

The five parsers are pure: they take one decrypted ICED response (the
full ``{status, data}`` envelope) and return ``list[dict]`` of canonical
indicator rows ready for ``write_artifact``. No I/O. No fetching. The
orchestrator at ``ingest.py`` does the network and persistence.

ICED-specific quirks every parser handles:

* ICED writes years as ``"YYYY-YY"`` (fiscal-year label) for state-level
  series and as bare ``YYYY`` (calendar year) for international/national
  series. We normalise per ``time_grain`` (fiscal_year â†’ ``YYYY-04``,
  year â†’ ``YYYY``).
* Several state names ICED uses are not in our master list (``"Daman
  and Diu"`` pre-2020 merger, ``"World"`` for India-vs-world rows,
  ``"All States"``). Unmapped names drop silently with a counter so the
  artifact still ships with the entities that do map.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from yen_gov.sources.iced_common import ENTITY_MAP, ICEDShapeError, coerce_numeric, parser_kit


# ---------------------------------------------------------------------------
# 1. Per-capita NSDP â€” both current and constant prices live in the same feed
# ---------------------------------------------------------------------------



@dataclass(frozen=True)
class PerCapitaIncomeSplit:
    """Two parallel row sets carved from one /per-capita-income response."""

    current: list[dict[str, Any]]
    constant: list[dict[str, Any]]
    skipped_unmapped: int


def parse_per_capita_income(decrypted: Any) -> PerCapitaIncomeSplit:
    """Split ICED ``per-capita-income`` into current-price and constant-price sets.

    Endpoint: ``/economy-demography/key-economic-indicators/per-capita-income``.
    Row shape: ``{state, year, priceType: "current"|"constant", price}``.
    Years arrive as fiscal-year labels (``"2004-05"`` â€¦). Returns row
    dicts ready for ``write_artifact`` â€” entity_id is the ECI state code,
    time is ``YYYY-04``, value is INR per person per year.
    """
    rows = parser_kit.unwrap_data(decrypted)
    if not isinstance(rows, list):
        raise ICEDShapeError(
            f"per-capita-income: expected list under 'data', got {type(rows).__name__}"
        )

    current: list[dict[str, Any]] = []
    constant: list[dict[str, Any]] = []
    skipped = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        state_name = r.get("state")
        entity_id = ENTITY_MAP.get(state_name) if state_name else None
        if entity_id is None:
            skipped += 1
            continue
        time = parser_kit.fy_to_period(r.get("year"), time_grain="fiscal_year")
        if time is None:
            continue
        value = coerce_numeric(r.get("price"))
        if value is None:
            continue
        bucket = (r.get("priceType") or "").strip().lower()
        if bucket == "current":
            current.append(parser_kit.row(entity_id=entity_id, time=time, value=value))
        elif bucket == "constant":
            constant.append(parser_kit.row(entity_id=entity_id, time=time, value=value))
        # silently ignore unknown priceType buckets

    return PerCapitaIncomeSplit(
        current=parser_kit.dedup_sort(current),
        constant=parser_kit.dedup_sort(constant),
        skipped_unmapped=skipped,
    )


# ---------------------------------------------------------------------------
# 2. HDI map
# ---------------------------------------------------------------------------


def parse_hdi_map(decrypted: Any) -> tuple[list[dict[str, Any]], int]:
    """Parse ICED ``hdi-map`` into HDI rows.

    Endpoint: ``/economy-demography/key-economic-indicators/hdi-map``.
    Row shape: ``{state, year, value, type, _id}``. Years arrive as
    ``"2011-12"``-style FY labels. Values are unitless 0â€“1 HDI scores.
    Returns ``(rows, skipped_unmapped_count)``.
    """
    raw = parser_kit.unwrap_data(decrypted)
    if not isinstance(raw, list):
        raise ICEDShapeError(
            f"hdi-map: expected list under 'data', got {type(raw).__name__}"
        )

    out: list[dict[str, Any]] = []
    skipped = 0
    for r in raw:
        if not isinstance(r, dict):
            continue
        entity_id = ENTITY_MAP.get(r.get("state")) if r.get("state") else None
        if entity_id is None:
            skipped += 1
            continue
        time = parser_kit.fy_to_period(r.get("year"), time_grain="fiscal_year")
        if time is None:
            continue
        value = coerce_numeric(r.get("value"))
        if value is None:
            continue
        out.append(parser_kit.row(entity_id=entity_id, time=time, value=value))
    return parser_kit.dedup_sort(out), skipped


# ---------------------------------------------------------------------------
# 3. Per-capita consumption
# ---------------------------------------------------------------------------


def parse_per_capita_consumption(decrypted: Any) -> tuple[list[dict[str, Any]], int]:
    """Parse ICED ``per-capita-consumption`` (state-only segment) into rows.

    Endpoint: ``/economy-demography/key-economic-indicators/per-capita-consumption``.
    Response top-level is ``{state: [...], indiaWorld: [...]}``. We only
    keep ``state`` rows (stateÃ—FY, INR/person), NOT the ``indiaWorld``
    series (those mix India-vs-World comparisons that need their own
    indicator and a country entity_kind we don't ship here yet).

    Each state row: ``{year: "2017-18", state, perCapitaConsumption}``.
    Years arrive as FY labels.
    """
    raw = parser_kit.unwrap_data(decrypted)
    if not isinstance(raw, dict):
        raise ICEDShapeError(
            f"per-capita-consumption: expected dict under 'data', got {type(raw).__name__}"
        )
    state_rows = raw.get("state")
    if not isinstance(state_rows, list):
        raise ICEDShapeError("per-capita-consumption: 'data.state' is not a list")

    out: list[dict[str, Any]] = []
    skipped = 0
    for r in state_rows:
        if not isinstance(r, dict):
            continue
        entity_id = ENTITY_MAP.get(r.get("state")) if r.get("state") else None
        if entity_id is None:
            skipped += 1
            continue
        time = parser_kit.fy_to_period(r.get("year"), time_grain="fiscal_year")
        if time is None:
            continue
        value = coerce_numeric(r.get("perCapitaConsumption"))
        if value is None:
            continue
        out.append(parser_kit.row(entity_id=entity_id, time=time, value=value))
    return parser_kit.dedup_sort(out), skipped


# ---------------------------------------------------------------------------
# 4. Demography (population by sex)
# ---------------------------------------------------------------------------


def parse_demography_by_sex(decrypted: Any) -> tuple[list[dict[str, Any]], int]:
    """Parse ICED ``demographyActual`` into populationÃ—sex rows.

    Endpoint: ``/economy-demography/demography/demographyActual``.
    Row shape: ``{state, category: "Male"|"Female"|..., year (int),
    type: "actual"|"projected", population, fyear}``.

    We faceted by ``Male`` / ``Female`` only â€” other ``category`` values
    (e.g. totals) drop silently. ``vintage`` carries ``"actual"`` for
    Census rows or ``"projected"`` for inter-/post-censal estimates so
    the chart can mark the projection era visually distinct.

    ``time`` uses calendar-year grain (the API ships int years like
    ``1961`` for these) so the chart can plot the Census points cleanly.
    """
    raw = parser_kit.unwrap_data(decrypted)
    if not isinstance(raw, list):
        raise ICEDShapeError(
            f"demographyActual: expected list under 'data', got {type(raw).__name__}"
        )

    keep_categories = {"Male", "Female"}
    out: list[dict[str, Any]] = []
    skipped = 0
    for r in raw:
        if not isinstance(r, dict):
            continue
        category = r.get("category")
        if category not in keep_categories:
            continue
        entity_id = ENTITY_MAP.get(r.get("state")) if r.get("state") else None
        if entity_id is None:
            skipped += 1
            continue
        time = parser_kit.fy_to_period(r.get("year"), time_grain="year")
        if time is None:
            continue
        value = coerce_numeric(r.get("population"))
        if value is None:
            continue
        vintage_raw = (r.get("type") or "").strip().lower()
        vintage = vintage_raw if vintage_raw in {"actual", "projected"} else None
        out.append(
            parser_kit.row(
                entity_id=entity_id, time=time, value=value,
                facet=category, vintage=vintage,
            )
        )
    return parser_kit.dedup_sort(out), skipped


# ---------------------------------------------------------------------------
# 5. Economy-wide GHG emissions by sector (national)
# ---------------------------------------------------------------------------


def parse_ghg_economy_wide(decrypted: Any) -> list[dict[str, Any]]:
    """Parse ICED ``economy-wide-emission`` into national GHG rows by sector.

    Endpoint: ``/climate-environment/ghg-emissions/economy-wide-emission``.
    Row shape: ``{_id: {year, sector}, value}`` where ``value`` is in
    ``Gg CO2-equivalent`` per ICED footnotes (1 Gg = 1 kt; we emit kt
    here so the unit is human-friendly â€” ``Mt`` is also fine if value
    suggests it; the unit is declared on the indicator block).

    All rows carry ``entity_id="IN"`` (India total). Faceted by sector.
    """
    raw = parser_kit.unwrap_data(decrypted)
    if not isinstance(raw, list):
        raise ICEDShapeError(
            f"economy-wide-emission: expected list under 'data', got {type(raw).__name__}"
        )

    out: list[dict[str, Any]] = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        ident = r.get("_id")
        if not isinstance(ident, dict):
            continue
        time = parser_kit.fy_to_period(ident.get("year"), time_grain="year")
        if time is None:
            continue
        sector = ident.get("sector")
        if not sector:
            continue
        value = coerce_numeric(r.get("value"))
        if value is None:
            continue
        out.append(parser_kit.row(entity_id="IN", time=time, value=value, facet=str(sector)))
    return parser_kit.dedup_sort(out)
