"""ICED transmission-substation list - decrypt, classify by voltage, aggregate.

NITI Aayog's India Climate & Energy Dashboard (ICED) publishes the national
transmission-substation asset inventory as an AES-encrypted JSON feed. Each
element is ONE commissioned substation asset::

    {"name": "Biswanath Chariyali & Agra HVDC terminal (Pole-I)",
     "sector": "Central", "executiveAgency": "PGCIL",
     "voltageRatio": "+-800", "capacity": 1500,
     "monthOfCompletion": "NOV-15", "yearOfCompletion": "2015-16",
     "createdAt": "2026-05-21T18:33:31.554Z", "type": "substation"}

The feed carries NO state field, so the only honest geography is the country
(``entity_id = "IN"``): this is a NATIONAL series. ``createdAt`` is the scrape
wall-clock and is NEVER persisted (CLAUDE.md datetime.now rule - it is
operational telemetry, not provenance).

The emitted measure is the transmission substation capacity COMMISSIONED per
fiscal year, FACETED BY VOLTAGE CLASS. ``capacity`` (MVA) is summed per
``(IN, fiscal-year, voltage_class)`` and written to the per-axis sibling
file-class ``datasets/data/datapoints/geo_by_voltage/*.csv`` (mirrors the
geo_by_fuel / geo_by_product dimension-column pattern).

No network: reads operator-staged response bytes only (parent plan section
21.4). Decryption is the shared CryptoJS-OpenSSL path in
``yen_gov.sources.iced_common.crypto`` - a plain-JSON staged body parses
straight through (the loader only AES-decrypts a CryptoJS envelope).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from yen_gov.sources.iced_common import load_iced_response

__all__ = [
    "ParseStats",
    "SubstationFacetRow",
    "TransmissionSubstationShapeError",
    "TransmissionSubstationSpec",
    "VOLTAGE_CLASSES",
    "classify_voltage_class",
    "parse_substation_feed",
]

# The closed voltage_class enum (the geo_by_voltage facet axis). Declared once
# here so the registry spec, the file-class enum in columns.json, and the
# frontend allowlist descriptor all trace back to the same source of truth.
VOLTAGE_CLASSES: tuple[str, ...] = ("hvdc", "765kv", "400kv", "220kv", "other")

# HVDC pole voltages (kV). India operates +-800 kV (Biswanath-Agra,
# Champa-Kurukshetra, Raigarh-Pugalur), +-500 kV (Rihand-Dadri, Talcher-Kolar)
# and +-320 kV VSC links (e.g. Pugalur-Thrissur). NONE of these has an AC
# transmission equivalent, so a governing voltage at one of these levels is
# unambiguously an HVDC terminal even when the raw string drops the +- marker
# (the feed carries both "+-800" and a bare "800"/"320").
_HVDC_POLE_KV: frozenset[int] = frozenset({320, 500, 800})

# EHV transmission-tier floor (kV). A winding whose highest voltage is below
# this is sub-transmission / distribution, not an EHV transmission asset, so it
# buckets to `other`. Defensive: every asset in the current feed has a >=220 kV
# winding (it IS a transmission-substation list), so nothing trips this today.
_EHV_FLOOR_KV = 200

# Capacity cell contents that mean "no observation" -> the asset is dropped and
# counted (per the brief: drop rows with null capacity).
_NA_MARKERS: frozenset[str] = frozenset(
    {"", "-", "--", "n.a.", "na", "n.a", "na.", "nr", "...", "null", "none"}
)


class TransmissionSubstationShapeError(ValueError):
    """The staged ICED substation feed no longer matches its spec.

    Raised loud (never emit a wholesale-empty file) so a changed envelope, an
    unparseable capacity, or a classifier that produces an out-of-enum voltage
    class surfaces to the operator instead of silently shipping a broken or
    empty series.
    """


@dataclass(frozen=True)
class SubstationFacetRow:
    """One emitted faceted observation (country x year x voltage_class -> MVA)."""

    entity_id: str
    time: int
    voltage_class: str
    value: float


@dataclass(frozen=True)
class ParseStats:
    """Counters reported back to the CLI for an honest ingest receipt."""

    total_assets: int
    dropped_null_capacity: int
    dropped_unparseable_year: int


@dataclass(frozen=True)
class TransmissionSubstationSpec:
    """The ICED transmission-substation feed -> one faceted canonical indicator.

    Carries everything the downstream surfaces need: the citation triple
    (``source.csv``), the catalogue rows (``variables.csv`` + ``concepts.csv``),
    and the transform knobs (the country entity, the facet column, and the
    closed voltage-class enum the classifier is checked against).
    """

    # --- identity / output (variables.csv + concepts.csv rows) ---
    indicator_id: str          # flat kebab; = the faceted datapoint filename stem
    name: str                  # citizen-facing label (variables.csv.name)
    concept_id: str            # FK -> concepts.csv
    concept_noun: str          # concepts.csv.noun
    concept_description: str   # concepts.csv.description (honest caveat)
    unit: str                  # variables.csv.unit (display); "MVA"
    unit_canonical: str        # concepts.csv.unit_canonical; "MVA"
    normalisation: str         # concepts.csv enum: absolute|per_capita|per_area|share|ratio|index
    topic: str                 # FK -> topics.csv; "energy"
    entity_kinds: str          # concepts.csv.entity_kinds (space-joined); "country"
    update_period_days: int    # publisher refresh cadence (days)
    derivation: str | None     # variables.csv.derivation (the sum-by-class note)

    # --- provenance (source.csv row; source_id is DERIVED, never set) ---
    source_producer: str       # ICED dashboard (the access surface / publisher)
    source_title: str          # names the specific substation feed
    source_vintage: str        # dashboard snapshot edition (e.g. "2024-25")
    source_url: str            # ICED dashboard landing page

    # --- staging + transform ---
    staging_filename: str          # filename the operator saves under the staging dir
    entity_id: str                 # the country entity ("IN"); the feed has no state field
    facet_column: str              # the dimension column name ("voltage_class")
    voltage_classes: tuple[str, ...]  # the closed enum the classifier must stay inside


def classify_voltage_class(voltage_ratio: Any) -> str:
    """Map a raw ``voltageRatio`` string to its closed ``voltage_class`` bucket.

    The raw field is the substation's winding ratio in kV written highest-first
    ("765/400", "400/220", "220/132"); HVDC terminals carry a single pole
    voltage, sometimes with a +- marker ("+-800", "800", "320"). The GOVERNING
    voltage is the HIGHEST kV token present, which is robust to the lone
    reversed "33/220" entry and to stray whitespace / newlines / multi-winding
    ratios ("400/220/132"). About 21 of the feed's 2763 rows carry an
    executive-agency name in this field instead of a ratio (a clear upstream
    data-entry slip: "PGCIL", "MSETCL", "TANTRANSCO", ...) or are null - these
    have no parseable voltage and bucket to ``other``.

    Buckets (India's EHV transmission tiers):

        hvdc   +- marker, or a DC pole voltage {320, 500, 800} (no AC at these)
        765kv  765 kV AC (the highest AC transmission voltage in India)
        400kv  400 kV AC
        220kv  220-230 kV AC (the 230 kV southern-grid tier is the same level)
        other  no parseable voltage, or a winding below the 220 kV EHV floor

    HVDC is tested BEFORE the magnitude ladder so a +-320 / +-500 terminal
    (whose pole voltage would otherwise fall in the 220kv / 400kv band) is
    classified by its physics, not its number.
    """
    text = "" if voltage_ratio is None else str(voltage_ratio)
    # "\u00b1" is the +- (plus-minus) sign the feed uses for HVDC poles; the
    # literal ASCII "+-" is accepted too so fixtures need not embed non-ASCII.
    has_dc_marker = ("\u00b1" in text) or ("+-" in text)
    tokens = [int(t) for t in re.findall(r"\d+", text)]
    if not tokens:
        return "other"
    governing = max(tokens)
    if has_dc_marker or governing in _HVDC_POLE_KV:
        return "hvdc"
    if governing >= 765:
        return "765kv"
    if governing >= 400:
        return "400kv"
    if governing >= _EHV_FLOOR_KV:
        return "220kv"
    return "other"


def parse_substation_feed(
    raw_bytes: bytes,
    spec: TransmissionSubstationSpec,
) -> tuple[list[SubstationFacetRow], ParseStats]:
    """Decrypt, classify by voltage, and sum capacity per (IN, year, class).

    Args:
        raw_bytes: the operator-staged raw response body (AES envelope or plain
            JSON).
        spec: the feed spec naming the country entity, the facet column, and the
            closed voltage-class enum.

    Returns:
        A 2-tuple ``(rows, stats)`` where ``rows`` is the faceted observations
        (sorted by ``(entity_id, time, voltage_class)``) and ``stats`` carries
        the total asset count plus the null-capacity / unparseable-year drop
        counts.

    Raises:
        TransmissionSubstationShapeError: the envelope has no ``data`` list, a
            data element is not a dict, a capacity is genuine garbage (non-numeric,
            non-N.A.), every asset dropped (wholesale-empty emit), or the
            classifier produced a value outside the declared closed enum.
    """
    envelope = load_iced_response(raw_bytes, decrypt=True)
    data = _extract_data(envelope, spec)

    sums: dict[tuple[str, int, str], float] = {}
    seen_classes: set[str] = set()
    dropped_capacity = 0
    dropped_year = 0
    for index, raw in enumerate(data):
        if not isinstance(raw, dict):
            raise TransmissionSubstationShapeError(
                f"{spec.indicator_id}: data[{index}] is not an object "
                f"({type(raw).__name__}); the feed shape changed."
            )
        capacity = _coerce_capacity(raw.get("capacity"), spec, index)
        if capacity is None:
            # Null / N.A. capacity: no observation. Dropped and counted.
            dropped_capacity += 1
            continue
        year = _fy_start_year(raw.get("yearOfCompletion"))
        if year is None:
            # Missing / unparseable completion year: dropped and counted (a few
            # assets carry no year). A wholesale drop is caught below.
            dropped_year += 1
            continue
        voltage_class = classify_voltage_class(raw.get("voltageRatio"))
        seen_classes.add(voltage_class)
        key = (spec.entity_id, year, voltage_class)
        sums[key] = sums.get(key, 0.0) + capacity

    if not sums:
        raise TransmissionSubstationShapeError(
            f"{spec.indicator_id}: every one of {len(data)} assets dropped "
            f"(null capacity or unparseable year); refusing to emit an empty "
            f"file - the feed shape likely changed."
        )
    unknown = seen_classes - set(spec.voltage_classes)
    if unknown:
        raise TransmissionSubstationShapeError(
            f"{spec.indicator_id}: voltage classifier produced {sorted(unknown)} "
            f"outside the declared closed enum {list(spec.voltage_classes)}; "
            f"keep the classifier and the columns.json enum in lockstep."
        )

    rows = [
        SubstationFacetRow(entity_id=e, time=t, voltage_class=vc, value=v)
        for (e, t, vc), v in sums.items()
    ]
    rows.sort(key=lambda r: (r.entity_id, r.time, r.voltage_class))
    stats = ParseStats(
        total_assets=len(data),
        dropped_null_capacity=dropped_capacity,
        dropped_unparseable_year=dropped_year,
    )
    return rows, stats


def _extract_data(envelope: Any, spec: TransmissionSubstationSpec) -> list[Any]:
    """Pull the ``data`` list out of the decrypted envelope, fail-loud."""
    if isinstance(envelope, dict):
        data = envelope.get("data")
    elif isinstance(envelope, list):
        data = envelope
    else:
        data = None
    if not isinstance(data, list):
        raise TransmissionSubstationShapeError(
            f"{spec.indicator_id}: decrypted response has no 'data' list "
            f"(got {type(envelope).__name__}); the endpoint format changed."
        )
    return data


def _fy_start_year(year: Any) -> int | None:
    """Reduce a fiscal-year label ("2015-16") to its integer start year (2015).

    Returns ``None`` for a null / unparseable year so the caller can DROP and
    COUNT the asset (the feed carries a few rows with no completion year). The
    repo convention (``iced_state_wise._period_to_year_int``) takes the first
    four digits, so a fiscal year maps to its START calendar year.
    """
    text = "" if year is None else str(year).strip()
    if len(text) < 4 or not text[:4].isdigit():
        return None
    return int(text[:4])


def _coerce_capacity(
    capacity: Any, spec: TransmissionSubstationSpec, index: int
) -> float | None:
    """Coerce a capacity cell (MVA) to float, or None for a null / N.A. cell.

    Raises on genuine garbage (a non-numeric, non-N.A. string, or a bool) so a
    feed-shape change surfaces instead of being silently coerced.
    """
    if capacity is None:
        return None
    if isinstance(capacity, bool):
        raise TransmissionSubstationShapeError(
            f"{spec.indicator_id}: data[{index}] capacity is a boolean; "
            f"expected a number (MVA)."
        )
    if isinstance(capacity, (int, float)):
        return float(capacity)
    if isinstance(capacity, str):
        text = capacity.strip()
        if text.lower() in _NA_MARKERS:
            return None
        try:
            return float(text)
        except ValueError as err:
            raise TransmissionSubstationShapeError(
                f"{spec.indicator_id}: data[{index}] capacity {capacity!r} is "
                f"not a number ({err})."
            ) from err
    raise TransmissionSubstationShapeError(
        f"{spec.indicator_id}: data[{index}] capacity has unexpected type "
        f"{type(capacity).__name__}."
    )
