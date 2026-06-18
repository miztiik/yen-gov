"""ICED renewable-energy potential feeds - decrypt, filter, resolve, sum.

NITI Aayog's India Climate & Energy Dashboard (ICED) publishes the modelled
state-wise renewable potential as AES-encrypted JSON feeds (one each for
solar, wind, and bio-energy). Every feed is a single assessment-year snapshot
(2025-26) of the shape::

    {"status": "success",
     "data": [{"region": "SR", "state": "Andhra Pradesh",
               "source": "solar", "subSource": "solar @3% wasteland area",
               "sourceType": "renewable", "year": "2025-26",
               "capacity": 38440, "fyear": "2025-26-61"}, ...]}

``capacity`` is the modelled maximum buildable potential in MW. The
``subSource`` column carries scenario variants - solar @3% vs @6.69%
wasteland; wind @120m vs @150m AGL; bio biomass vs cogeneration-bagasse. A
:class:`RenewablePotentialSpec` names which subSource(s) to keep; the
emitter then SUMS the kept rows per (entity, year). So solar and wind keep a
single headline scenario (the alternative scenario is a non-additive
estimate, dropped), while bio keeps both of its physically-additive streams
and sums them.

Entity resolution reuses the shared RBI-Handbook state resolver: the
``state`` column carries full display names ("Andhra Pradesh", "Andaman and
Nicobar Islands") that map to LGD slugs, an all-India "India" row (if a
future edition carries one) maps to the country entity "IN", and any label
that does not resolve - the "Others" aggregate bucket today, or a
power-region / aggregate label tomorrow - is DROPPED and counted, never
silently emitted. The power-region codes (SR/NER/ER/WR/NR) live in the
``region`` column, never in ``state``, so they never reach the resolver.

No network: reads operator-staged response bytes only (parent plan section
21.4). Decryption is the shared CryptoJS-OpenSSL path in
``yen_gov.sources.iced_common.crypto``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from yen_gov.canonical.adapters.rbi_handbook import StateResolver
from yen_gov.sources.iced_common import load_iced_response

__all__ = [
    "PotentialRow",
    "RenewablePotentialShapeError",
    "RenewablePotentialSpec",
    "parse_potential_feed",
]

# Capacity cell contents that mean "no observation" -> the row is skipped
# (sparse-safe), NOT counted as an aggregate drop.
_NA_MARKERS: frozenset[str] = frozenset(
    {"", "-", "--", "n.a.", "na", "n.a", "na.", "nr", "...", "null", "none"}
)


class RenewablePotentialShapeError(ValueError):
    """The staged ICED potential feed no longer matches its spec.

    Raised loud (never emit a wholesale-empty file) so an upstream rename of
    a ``subSource`` scenario, a changed envelope, or an unparseable capacity
    surfaces to the operator instead of silently dropping a state's
    potential - a silent coverage drop would lie to the citizen.
    """


@dataclass(frozen=True)
class PotentialRow:
    """One emitted long-format observation (entity x year -> MW)."""

    entity_id: str
    time: int
    value: float


@dataclass(frozen=True)
class RenewablePotentialSpec:
    """One ICED renewable-potential feed -> one canonical indicator.

    A single spec carries everything three downstream surfaces need: the
    feed transform (parser), the catalogue rows (``variables.csv`` +
    ``concepts.csv``), and the citation triple (``source.csv``). Adding a
    new potential feed means appending one spec in ``registry.py`` - no
    parser edits.
    """

    # --- identity / output (the variables.csv + concepts.csv rows) ---
    indicator_id: str          # flat kebab; = the datapoint filename stem
    name: str                  # citizen-facing label (variables.csv.name)
    concept_id: str            # FK -> concepts.csv
    concept_noun: str          # concepts.csv.noun
    concept_description: str   # concepts.csv.description (one honest caveat)
    unit: str                  # variables.csv.unit (display); "MW"
    unit_canonical: str        # concepts.csv.unit_canonical; "MW"
    normalisation: str         # concepts.csv enum: absolute|per_capita|per_area|share|ratio|index
    topic: str                 # FK -> topics.csv; "energy"
    entity_kinds: str          # concepts.csv.entity_kinds (space-joined)
    update_period_days: int    # publisher refresh cadence
    derivation: str | None     # variables.csv.derivation (None unless summed)

    # --- provenance (source.csv row; source_id is DERIVED, never set) ---
    source_producer: str       # ICED dashboard (the access surface / publisher)
    source_title: str          # names the specific potential feed
    source_vintage: str        # assessment year (e.g. "2025-26")
    source_url: str            # ICED dashboard landing page

    # --- staging + transform ---
    staging_filename: str      # filename the operator saves under the staging dir
    keep_sub_sources: tuple[str, ...]  # subSource scenario(s) to keep + sum


def parse_potential_feed(
    raw_bytes: bytes,
    spec: RenewablePotentialSpec,
    resolver: StateResolver,
) -> tuple[list[PotentialRow], int]:
    """Decrypt, filter by subSource, resolve entities, and sum per (entity, year).

    Args:
        raw_bytes: the operator-staged raw response body (AES envelope).
        spec: the feed spec naming the keep-scenario(s) and the citation.
        resolver: the shared RBI-Handbook display-name -> entity_id resolver.

    Returns:
        A 2-tuple ``(rows, dropped)`` where ``rows`` is the long-format
        observations (sorted by ``(entity_id, time)``) and ``dropped`` is the
        count of rows that passed the subSource filter but whose ``state`` did
        not resolve to a known LGD entity (the "Others" aggregate today; a
        power-region or all-India aggregate in a future feed).

    Raises:
        RenewablePotentialShapeError: the envelope has no ``data`` list, a
            data element is not a dict, an expected keep-scenario subSource is
            absent (upstream rename), or a kept capacity is unparseable.
    """
    envelope = load_iced_response(raw_bytes, decrypt=True)
    data = _extract_data(envelope, spec)
    keep = {s.strip() for s in spec.keep_sub_sources}

    seen_sub_sources: set[str] = set()
    sums: dict[tuple[str, int], float] = {}
    dropped = 0
    for index, raw in enumerate(data):
        if not isinstance(raw, dict):
            raise RenewablePotentialShapeError(
                f"{spec.indicator_id}: data[{index}] is not an object "
                f"({type(raw).__name__}); the feed shape changed."
            )
        sub_raw = raw.get("subSource")
        sub = str(sub_raw).strip() if sub_raw is not None else ""
        seen_sub_sources.add(sub)
        if keep and sub not in keep:
            continue
        value = _coerce_capacity(raw.get("capacity"), spec, index)
        if value is None:
            # Sparse cell (N.A. potential): no observation. Skipped, not an
            # aggregate drop. The drift guard below still protects against a
            # wholesale-empty emit.
            continue
        entity = resolver.resolve(raw.get("state"))
        if entity is None:
            dropped += 1
            continue
        time = _fy_start_year(raw.get("year"), spec, index)
        key = (entity, time)
        sums[key] = sums.get(key, 0.0) + value

    missing = keep - seen_sub_sources
    if missing:
        raise RenewablePotentialShapeError(
            f"{spec.indicator_id}: expected subSource(s) {sorted(missing)} not "
            f"present in the feed; saw {sorted(seen_sub_sources)}. The "
            f"publisher may have renamed a scenario - re-check the feed before "
            f"ingesting (refusing to emit a partial/empty file)."
        )

    rows = [
        PotentialRow(entity_id=entity, time=time, value=value)
        for (entity, time), value in sums.items()
    ]
    rows.sort(key=lambda r: (r.entity_id, r.time))
    return rows, dropped


def _extract_data(envelope: Any, spec: RenewablePotentialSpec) -> list[Any]:
    """Pull the ``data`` list out of the decrypted envelope, fail-loud."""
    if isinstance(envelope, dict):
        data = envelope.get("data")
    elif isinstance(envelope, list):
        data = envelope
    else:
        data = None
    if not isinstance(data, list):
        raise RenewablePotentialShapeError(
            f"{spec.indicator_id}: decrypted response has no 'data' list "
            f"(got {type(envelope).__name__}); the endpoint format changed."
        )
    return data


def _fy_start_year(year: Any, spec: RenewablePotentialSpec, index: int) -> int:
    """Reduce a fiscal-year label ("2025-26") to its integer start year (2025).

    The canonical ``datasets/data/datapoints/geo/*.csv`` ``time`` column is an
    integer year. These feeds are a single-year assessment snapshot whose
    ``year`` is the fiscal-year string "2025-26"; the repo convention
    (``iced_state_wise._period_to_year_int``) takes the first four digits, so
    a fiscal year maps to its START calendar year ("2025-26" -> 2025).
    """
    text = str(year).strip() if year is not None else ""
    if len(text) < 4 or not text[:4].isdigit():
        raise RenewablePotentialShapeError(
            f"{spec.indicator_id}: data[{index}] has an unparseable year "
            f"{year!r}; expected a 'YYYY' or 'YYYY-YY' fiscal-year label."
        )
    return int(text[:4])


def _coerce_capacity(
    capacity: Any, spec: RenewablePotentialSpec, index: int
) -> float | None:
    """Coerce a capacity cell to MW float, or None for a sparse (N.A.) cell.

    Raises on genuine garbage (a non-numeric, non-N.A. string) so a feed-shape
    change surfaces instead of being silently coerced.
    """
    if capacity is None:
        return None
    if isinstance(capacity, bool):
        raise RenewablePotentialShapeError(
            f"{spec.indicator_id}: data[{index}] capacity is a boolean; "
            f"expected a number."
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
            raise RenewablePotentialShapeError(
                f"{spec.indicator_id}: data[{index}] capacity {capacity!r} is "
                f"not a number ({err})."
            ) from err
    raise RenewablePotentialShapeError(
        f"{spec.indicator_id}: data[{index}] capacity has unexpected type "
        f"{type(capacity).__name__}."
    )
