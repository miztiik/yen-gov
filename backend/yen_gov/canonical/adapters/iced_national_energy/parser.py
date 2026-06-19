"""NITI ICED national energy-balance feeds - decrypt, map to closed enums, shape.

NITI Aayog's India Climate & Energy Dashboard (ICED) publishes India's national
energy balance as two AES-encrypted JSON feeds:

* ``sourceWiseEnergySupply`` - Total Primary Energy Supply (TPES) by primary
  source per fiscal year. Shape::

      {"status": "success",
       "data": [{"year": "2005-06", "source": "Coal",
                 "energyValue": 205.6297986...}, ...]}

  Six sources partition TPES: Coal, Gas, Hydro, Nuclear, Oil, Renewables. One
  row per (source, year); 6 x 20 fiscal years = 120 rows. No published total
  row, so this adapter emits no ``all`` member (synthesising a sum-of-parts
  total is forbidden by the geo_by_primary_source contract).

* ``sectorWiseEnergyConsumption`` - Final Energy Consumption by demand sector
  AND delivered fuel per fiscal year. Shape::

      {"status": "success",
       "data": [{"sector": "Industry", "source": "Coal", "year": "2005-06",
                 "energyValue": 90.1...}, ...]}

  Eight sectors x four delivered carriers (Coal / Electricity / Gas / Oil),
  reported as a SPARSE matrix (not every sector consumes every fuel); 360 rows.
  ``source`` here is the delivered carrier (= our ``fuel`` column); electricity
  is a carrier of final consumption, NOT a primary source.

Both feeds are NATIONAL: every row is India (entity_id ``IN``). The ``energyValue``
is in million tonnes of oil equivalent (mtoe), preserved verbatim (no rounding).
``year`` is the fiscal-year string ("2005-06") reduced to its integer START year
(2005), matching the repo time convention.

The source / sector / fuel vocabularies are CLOSED enums: an upstream value not
in the spec's slug map is raised loud (a new member must surface to the operator,
never be silently dropped - a quiet coverage gap would lie to the citizen).

No network: reads operator-staged response bytes only (parent plan section
21.4). Decryption is the shared CryptoJS-OpenSSL path in
``yen_gov.sources.iced_common.crypto`` (a plain-JSON staged fixture parses
without AES via ``load_iced_response(..., decrypt=True)``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from yen_gov.sources.iced_common import load_iced_response

__all__ = [
    "FinalConsumptionRow",
    "FinalEnergySpec",
    "NationalEnergyShapeError",
    "PrimarySupplyRow",
    "PrimaryEnergySpec",
    "parse_sector_wise_consumption",
    "parse_source_wise_supply",
]

# energyValue cell contents that mean "no observation" -> the cell is skipped
# (sparse-safe), NOT a shape error. The live feeds carry no such cells, but the
# guard keeps a future sparse edition from raising.
_NA_MARKERS: frozenset[str] = frozenset(
    {"", "-", "--", "n.a.", "na", "n.a", "na.", "nr", "...", "null", "none"}
)

# Every row of both national feeds is India.
NATIONAL_ENTITY_ID = "IN"


class NationalEnergyShapeError(ValueError):
    """A staged ICED national energy-balance feed no longer matches its spec.

    Raised loud (never emit a wholesale-empty or silently-narrowed file) so an
    upstream new source / sector / fuel member, a renamed key, a changed
    envelope, or an unparseable value surfaces to the operator instead of
    silently dropping part of the national balance.
    """


@dataclass(frozen=True)
class PrimarySupplyRow:
    """One emitted long-format primary-supply observation (year x source -> mtoe)."""

    time: int
    primary_source: str
    value: float


@dataclass(frozen=True)
class FinalConsumptionRow:
    """One emitted long-format final-consumption observation (year x sector x fuel -> mtoe)."""

    time: int
    sector: str
    fuel: str
    value: float


@dataclass(frozen=True)
class PrimaryEnergySpec:
    """The ICED Source-wise Energy Supply feed -> one faceted national indicator.

    ``source_slugs`` is the CLOSED enum: it maps each publisher ``source`` label
    to the canonical ``primary_source`` slug. An upstream label absent from the
    map is a shape change (new primary source) and is raised, never dropped.
    """

    # --- identity / output (the variables.csv + concepts.csv rows) ---
    indicator_id: str
    name: str
    concept_id: str
    concept_noun: str
    concept_description: str
    unit: str
    unit_canonical: str
    normalisation: str
    topic: str
    entity_kinds: str
    update_period_days: int
    derivation: str | None
    # --- provenance (source.csv row; source_id is DERIVED, never set) ---
    source_producer: str
    source_title: str
    source_vintage: str
    source_url: str
    # --- staging + transform ---
    staging_filename: str
    file_class: str
    source_slugs: dict[str, str]


@dataclass(frozen=True)
class FinalEnergySpec:
    """The ICED Sector-wise Energy Consumption feed -> one 2-D faceted indicator.

    ``sector_slugs`` and ``fuel_slugs`` are the two CLOSED enums (demand sector
    and delivered carrier). An upstream label absent from either map is raised.
    """

    # --- identity / output ---
    indicator_id: str
    name: str
    concept_id: str
    concept_noun: str
    concept_description: str
    unit: str
    unit_canonical: str
    normalisation: str
    topic: str
    entity_kinds: str
    update_period_days: int
    derivation: str | None
    # --- provenance ---
    source_producer: str
    source_title: str
    source_vintage: str
    source_url: str
    # --- staging + transform ---
    staging_filename: str
    file_class: str
    sector_slugs: dict[str, str]
    fuel_slugs: dict[str, str]


def parse_source_wise_supply(
    raw_bytes: bytes, spec: PrimaryEnergySpec
) -> list[PrimarySupplyRow]:
    """Decrypt and shape the Source-wise Energy Supply feed.

    Returns the long-format rows (sorted by ``(primary_source, time)`` so the
    canonical writer's PK sort - (entity_id, time, primary_source) - lands a
    deterministic file). Raises :class:`NationalEnergyShapeError` on any shape
    drift (missing key, unknown source member, unparseable year/value, or a
    duplicate (source, year) pair).
    """
    data = _extract_data(load_iced_response(raw_bytes, decrypt=True), spec.indicator_id)
    seen: dict[tuple[int, str], float] = {}
    for index, raw in enumerate(data):
        _require_dict(raw, spec.indicator_id, index)
        slug = _map_member(
            raw.get("source"), spec.source_slugs, spec.indicator_id, "source", index
        )
        time = _fy_start_year(raw.get("year"), spec.indicator_id, index)
        value = _coerce_value(raw.get("energyValue"), spec.indicator_id, index)
        if value is None:
            continue
        key = (time, slug)
        if key in seen:
            raise NationalEnergyShapeError(
                f"{spec.indicator_id}: duplicate (year={time}, source={slug!r}) "
                f"at data[{index}]; the feed should carry one row per "
                f"(source, year). The shape changed - re-check before ingesting."
            )
        seen[key] = value
    rows = [
        PrimarySupplyRow(time=time, primary_source=slug, value=value)
        for (time, slug), value in seen.items()
    ]
    rows.sort(key=lambda r: (r.primary_source, r.time))
    return rows


def parse_sector_wise_consumption(
    raw_bytes: bytes, spec: FinalEnergySpec
) -> list[FinalConsumptionRow]:
    """Decrypt and shape the Sector-wise Energy Consumption feed.

    Returns the long-format rows (sorted by ``(sector, fuel, time)``). Raises
    :class:`NationalEnergyShapeError` on missing key, unknown sector / fuel
    member, unparseable year/value, or a duplicate (sector, fuel, year) triple.
    The matrix is sparse, so an absent (sector, fuel, year) cell is simply an
    absent row.
    """
    data = _extract_data(load_iced_response(raw_bytes, decrypt=True), spec.indicator_id)
    seen: dict[tuple[int, str, str], float] = {}
    for index, raw in enumerate(data):
        _require_dict(raw, spec.indicator_id, index)
        sector = _map_member(
            raw.get("sector"), spec.sector_slugs, spec.indicator_id, "sector", index
        )
        fuel = _map_member(
            raw.get("source"), spec.fuel_slugs, spec.indicator_id, "fuel", index
        )
        time = _fy_start_year(raw.get("year"), spec.indicator_id, index)
        value = _coerce_value(raw.get("energyValue"), spec.indicator_id, index)
        if value is None:
            continue
        key = (time, sector, fuel)
        if key in seen:
            raise NationalEnergyShapeError(
                f"{spec.indicator_id}: duplicate (year={time}, sector={sector!r}, "
                f"fuel={fuel!r}) at data[{index}]; one row per (sector, fuel, "
                f"year) expected. The shape changed - re-check before ingesting."
            )
        seen[key] = value
    rows = [
        FinalConsumptionRow(time=time, sector=sector, fuel=fuel, value=value)
        for (time, sector, fuel), value in seen.items()
    ]
    rows.sort(key=lambda r: (r.sector, r.fuel, r.time))
    return rows


def _extract_data(envelope: Any, indicator_id: str) -> list[Any]:
    """Pull the ``data`` list out of the decrypted envelope, fail-loud."""
    if isinstance(envelope, dict):
        data = envelope.get("data")
    elif isinstance(envelope, list):
        data = envelope
    else:
        data = None
    if not isinstance(data, list):
        raise NationalEnergyShapeError(
            f"{indicator_id}: decrypted response has no 'data' list "
            f"(got {type(envelope).__name__}); the endpoint format changed."
        )
    if not data:
        raise NationalEnergyShapeError(
            f"{indicator_id}: decrypted 'data' list is empty; refusing to emit "
            f"a wholesale-empty national balance."
        )
    return data


def _require_dict(raw: Any, indicator_id: str, index: int) -> None:
    if not isinstance(raw, dict):
        raise NationalEnergyShapeError(
            f"{indicator_id}: data[{index}] is not an object "
            f"({type(raw).__name__}); the feed shape changed."
        )


def _map_member(
    raw_value: Any,
    slug_map: dict[str, str],
    indicator_id: str,
    axis: str,
    index: int,
) -> str:
    """Map a publisher label to its canonical slug via the CLOSED enum map.

    An unmapped label is a shape change (a new enum member upstream) and is
    raised, never silently dropped - the operator must widen the enum (a
    columns.json bump) before the new member can be ingested.
    """
    label = str(raw_value).strip() if raw_value is not None else ""
    if label not in slug_map:
        raise NationalEnergyShapeError(
            f"{indicator_id}: data[{index}] has an unmapped {axis} {raw_value!r}; "
            f"known {axis} members: {sorted(slug_map)}. The publisher added or "
            f"renamed a {axis} - widen the closed enum (columns.json + the spec) "
            f"before ingesting (refusing to drop an unknown member)."
        )
    return slug_map[label]


def _fy_start_year(year: Any, indicator_id: str, index: int) -> int:
    """Reduce a fiscal-year label ("2005-06") to its integer start year (2005)."""
    text = str(year).strip() if year is not None else ""
    if len(text) < 4 or not text[:4].isdigit():
        raise NationalEnergyShapeError(
            f"{indicator_id}: data[{index}] has an unparseable year {year!r}; "
            f"expected a 'YYYY' or 'YYYY-YY' fiscal-year label."
        )
    return int(text[:4])


def _coerce_value(value: Any, indicator_id: str, index: int) -> float | None:
    """Coerce an energyValue cell to an mtoe float, or None for a sparse (N.A.) cell.

    Raises on genuine garbage (a non-numeric, non-N.A. string or a boolean) so
    a feed-shape change surfaces instead of being silently coerced.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise NationalEnergyShapeError(
            f"{indicator_id}: data[{index}] energyValue is a boolean; "
            f"expected a number."
        )
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if text.lower() in _NA_MARKERS:
            return None
        try:
            return float(text)
        except ValueError as err:
            raise NationalEnergyShapeError(
                f"{indicator_id}: data[{index}] energyValue {value!r} is not a "
                f"number ({err})."
            ) from err
    raise NationalEnergyShapeError(
        f"{indicator_id}: data[{index}] energyValue has unexpected type "
        f"{type(value).__name__}."
    )
