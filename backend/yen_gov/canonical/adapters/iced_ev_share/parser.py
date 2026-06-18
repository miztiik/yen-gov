"""ICED ICE-vs-EV (VAHAN) registrations feed -> state EV-share indicator.

NITI Aayog's India Climate & Energy Dashboard (ICED) republishes the Ministry
of Road Transport & Highways VAHAN registration counts, split by state x
vehicle-category x fuel-category x fiscal-year. The decrypted envelope is::

    {"status": "success",
     "data": {"iceEvData": [{"state": "Andhra Pradesh",
                             "vehicleCategory": "TWO WHEELER(NT)",
                             "broadCategory": "2 Wheeler",
                             "year": "2023-24",
                             "fuelCategory": "Electric Vehicle",
                             "value": 12345}, ...],
              "populationData": [...]}}

This parser uses ONLY ``data["iceEvData"]`` and DROPS ``populationData``
entirely (yen-gov already carries state population at
``datasets/data/datapoints/geo/state-population-lakhs.csv``; a second
population source is forbidden by Holy Law #6 / the data-spine).

> **Share, not absolute (Hans).** The emitted indicator is the EV SHARE of new
> registrations - ``100 * sum(value where fuelCategory is electric) /
> sum(value over ALL fuelCategory)`` per (state, year), summed across every
> vehicleCategory. An absolute EV count just tracks market size (Maharashtra
> always "wins"); the share is the transition signal that is comparable across
> states. ``value`` is a count of newly-registered vehicles, so the
> denominator is total new registrations and the ratio is dimensionless (%).

``fuelCategory`` carries five buckets in the staged feed - ``CNG``,
``Diesel & Others``, ``Electric Vehicle``, ``Others``, ``Petrol & Others``.
``Electric Vehicle`` is the only clearly-electric bucket; every other bucket
(including the residual ``Others``) is non-electric and stays in the
denominator only. The spec names the electric bucket(s) explicitly so a
publisher rename surfaces as a fail-loud drift error rather than a silent 0%.

Entity resolution reuses the shared RBI-Handbook state resolver: the ``state``
column carries full display names ("Andhra Pradesh", "Andaman and Nicobar
Islands") that map to LGD slugs. A label that does not resolve is DROPPED and
its distinct label counted, never silently emitted. A (state, year) cell whose
total registrations are 0/empty is dropped (no share is defined).

No network: reads operator-staged response bytes only (parent plan section
21.4). Decryption is the shared CryptoJS-OpenSSL path in
``yen_gov.sources.iced_common`` via :func:`load_iced_response`; a plain-JSON
body (test fixtures) is parsed directly without AES.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from yen_gov.canonical.adapters.rbi_handbook import StateResolver
from yen_gov.sources.iced_common import load_iced_response

__all__ = [
    "EvShareRow",
    "EvShareShapeError",
    "EvShareSpec",
    "parse_ev_share_feed",
]

# Number of decimal places the percentage share is rounded to. A share is a
# derived ratio; rounding keeps the emitted CSV deterministic (stable bytes ->
# idempotent re-ingest) and citizen-clean while preserving small early-year
# values (6 dp -> 0.000001 % resolution).
_SHARE_DECIMALS = 6

# Value cell contents that mean "no registrations" -> the cell contributes 0
# to both numerator and denominator (skipped), NOT a fail-loud error.
_NA_MARKERS: frozenset[str] = frozenset(
    {"", "-", "--", "n.a.", "na", "n.a", "na.", "nr", "...", "null", "none"}
)


class EvShareShapeError(ValueError):
    """The staged ICED ICE-vs-EV feed no longer matches its spec.

    Raised loud (never emit a wholesale-empty or all-zero file) so an upstream
    envelope change, a renamed electric ``fuelCategory`` bucket, or an
    unparseable count surfaces to the operator instead of silently emitting a
    0% EV share for every state - a silent miscalculation would lie to the
    citizen.
    """


@dataclass(frozen=True)
class EvShareRow:
    """One emitted long-format observation (entity x year -> EV share %)."""

    entity_id: str
    time: int
    value: float


@dataclass(frozen=True)
class EvShareSpec:
    """The ICE-vs-EV (VAHAN) feed -> the canonical EV-share indicator.

    Carries everything three downstream surfaces need: the feed transform
    (parser), the catalogue rows (``variables.csv`` + ``concepts.csv``), and
    the citation triple (``source.csv``). ``source_id`` is DERIVED from the
    (producer, title, vintage) triple, never set here.
    """

    # --- identity / output (the variables.csv + concepts.csv rows) ---
    indicator_id: str          # flat kebab; = the datapoint filename stem
    name: str                  # citizen-facing label (variables.csv.name)
    concept_id: str            # FK -> concepts.csv
    concept_noun: str          # concepts.csv.noun
    concept_description: str    # concepts.csv.description (citizen honesty cue)
    unit: str                  # variables.csv.unit (display); "%"
    unit_canonical: str        # concepts.csv.unit_canonical; "%"
    normalisation: str         # concepts.csv enum; "share"
    topic: str                 # FK -> topics.csv; "energy"
    entity_kinds: str          # concepts.csv.entity_kinds (space-joined)
    update_period_days: int    # publisher refresh cadence (days)
    derivation: str            # variables.csv.derivation (the ratio formula)

    # --- provenance (source.csv row; source_id is DERIVED, never set) ---
    source_producer: str       # ICED dashboard (the access surface / publisher)
    source_title: str          # names the specific VAHAN feed
    source_vintage: str        # publisher edition tag (e.g. "2024-25")
    source_url: str            # ICED dashboard landing page

    # --- staging + transform ---
    staging_filename: str      # filename the operator saves under the staging dir
    electric_fuel_categories: tuple[str, ...] = field(
        default=("Electric Vehicle",)
    )  # fuelCategory value(s) counted as the EV (numerator) bucket


def parse_ev_share_feed(
    raw_bytes: bytes,
    spec: EvShareSpec,
    resolver: StateResolver,
) -> tuple[list[EvShareRow], int]:
    """Decrypt, accumulate EV + total registrations, and emit the per-cell share.

    For every (resolved state, fiscal-year-start) the share is
    ``round(100 * sum(electric value) / sum(all-fuel value), 6)`` summed across
    every ``vehicleCategory``. ``populationData`` is ignored entirely.

    Args:
        raw_bytes: the operator-staged raw response body (AES envelope or, for
            test fixtures, plain JSON).
        spec: the feed spec naming the electric ``fuelCategory`` bucket(s) and
            the citation.
        resolver: the shared RBI-Handbook display-name -> entity_id resolver.

    Returns:
        A 2-tuple ``(rows, dropped_unresolved)`` where ``rows`` is the
        long-format observations (sorted by ``(entity_id, time)``) and
        ``dropped_unresolved`` is the count of DISTINCT ``state`` labels that
        did not resolve to a known LGD entity (counted once per label, not once
        per row, so a single unmapped state is reported as 1).

    Raises:
        EvShareShapeError: the envelope has no ``data["iceEvData"]`` list, a
            data element is not a dict, the electric ``fuelCategory`` bucket is
            absent from the whole feed (upstream rename), a value is genuine
            garbage, or a year is unparseable.
    """
    rows = _extract_ice_ev_rows(envelope=load_iced_response(raw_bytes, decrypt=True), spec=spec)
    electric_keys = {_norm(label) for label in spec.electric_fuel_categories}

    resolved_cache: dict[str, str | None] = {}
    unresolved_labels: set[str] = set()
    total_by: dict[tuple[str, int], float] = {}
    ev_by: dict[tuple[str, int], float] = {}
    saw_electric = False

    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise EvShareShapeError(
                f"{spec.indicator_id}: iceEvData[{index}] is not an object "
                f"({type(raw).__name__}); the feed shape changed."
            )
        is_electric = _norm(raw.get("fuelCategory")) in electric_keys
        if is_electric:
            saw_electric = True
        value = _coerce_count(raw.get("value"), spec, index)
        if value is None:
            # NA / empty cell: no registrations. Contributes 0 to both sums.
            continue
        label = raw.get("state")
        label_key = _norm(label)
        if label_key not in resolved_cache:
            resolved_cache[label_key] = resolver.resolve(label)
        entity = resolved_cache[label_key]
        if entity is None:
            unresolved_labels.add(label_key)
            continue
        year = _fy_start_year(raw.get("year"), spec, index)
        key = (entity, year)
        total_by[key] = total_by.get(key, 0.0) + value
        if is_electric:
            ev_by[key] = ev_by.get(key, 0.0) + value

    if not saw_electric:
        raise EvShareShapeError(
            f"{spec.indicator_id}: none of the electric fuelCategory bucket(s) "
            f"{sorted(spec.electric_fuel_categories)} appear in the feed; the "
            f"publisher may have renamed the electric bucket. Refusing to emit "
            f"an all-zero EV share."
        )

    out: list[EvShareRow] = []
    for (entity, year), total in total_by.items():
        if total <= 0:
            # A (state, year) cell with zero total registrations has no defined
            # share - dropped (sparse-safe).
            continue
        ev = ev_by.get((entity, year), 0.0)
        share = round(100.0 * ev / total, _SHARE_DECIMALS)
        out.append(EvShareRow(entity_id=entity, time=year, value=share))

    out.sort(key=lambda r: (r.entity_id, r.time))
    return out, len(unresolved_labels)


def _extract_ice_ev_rows(*, envelope: Any, spec: EvShareSpec) -> list[Any]:
    """Pull ``data["iceEvData"]`` out of the decrypted envelope, fail-loud.

    ``populationData`` is intentionally never read.
    """
    data = envelope.get("data") if isinstance(envelope, dict) else None
    if not isinstance(data, dict):
        raise EvShareShapeError(
            f"{spec.indicator_id}: decrypted response 'data' is not an object "
            f"(got {type(data).__name__}); expected a dict carrying "
            f"'iceEvData'. The endpoint format changed."
        )
    ice_ev = data.get("iceEvData")
    if not isinstance(ice_ev, list):
        raise EvShareShapeError(
            f"{spec.indicator_id}: data['iceEvData'] is not a list "
            f"(got {type(ice_ev).__name__}); the endpoint format changed."
        )
    return ice_ev


def _norm(label: Any) -> str:
    """Collapse a label to a comparison key (strip + casefold)."""
    return str(label).strip().casefold() if label is not None else ""


def _fy_start_year(year: Any, spec: EvShareSpec, index: int) -> int:
    """Reduce a fiscal-year label ("2023-24") to its integer start year (2023).

    The canonical ``datasets/data/datapoints/geo/*.csv`` ``time`` column is an
    integer year; the repo convention takes the first four digits, so a fiscal
    year maps to its START calendar year ("2023-24" -> 2023).
    """
    text = str(year).strip() if year is not None else ""
    if len(text) < 4 or not text[:4].isdigit():
        raise EvShareShapeError(
            f"{spec.indicator_id}: iceEvData[{index}] has an unparseable year "
            f"{year!r}; expected a 'YYYY' or 'YYYY-YY' fiscal-year label."
        )
    return int(text[:4])


def _coerce_count(value: Any, spec: EvShareSpec, index: int) -> float | None:
    """Coerce a registration-count cell to a float, or None for an NA cell.

    Raises on genuine garbage (a non-numeric, non-NA string) so a feed-shape
    change surfaces instead of being silently coerced.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise EvShareShapeError(
            f"{spec.indicator_id}: iceEvData[{index}] value is a boolean; "
            f"expected a number."
        )
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if text.lower() in _NA_MARKERS:
            return None
        try:
            return float(text.replace(",", ""))
        except ValueError as err:
            raise EvShareShapeError(
                f"{spec.indicator_id}: iceEvData[{index}] value {value!r} is "
                f"not a number ({err})."
            ) from err
    raise EvShareShapeError(
        f"{spec.indicator_id}: iceEvData[{index}] value has unexpected type "
        f"{type(value).__name__}."
    )
