"""ICED captive-power (industry-wise) feed - decrypt, filter, resolve, sum.

NITI Aayog's India Climate & Energy Dashboard (ICED) republishes the Central
Electricity Authority's captive-power returns as a single AES-encrypted JSON
feed. "Captive" power is electricity that an industry builds and runs behind
the meter for its own use, NOT grid supply. The feed mixes two row shapes,
tagged by ``dataFor``::

    {"status": "success",
     "data": [
       # dataFor == "stateWise": one row per (year, state, industry) carrying
       # both measures - this is the only shape we read.
       {"year": "2005-06", "state": "Andhra Pradesh", "industry": "Cement",
        "capacity": 50.0, "generation": 300.0, "dataFor": "stateWise"},
       # dataFor == "sourceWise": one row per (year, industry) whose `source`
       # is a NATIONAL fuel-mix dict with NO state - ignored (it carries no
       # state grain and re-counting it would double-count the same MW).
       {"industry": "Cement", "year": "2005-06",
        "source": {"coal": 1008, "diesel": 1036, "gas": 938, ...},
        "dataFor": "sourceWise", "dataOf": "capacity"}, ...]}

This parser drops the 22-industry dimension (Hans: no fragmentation) and emits
ONE state total per measure: it sums the chosen ``measure`` column
("capacity" -> MW, "generation" -> GWh) over every industry for each
(state, year).

Entity resolution reuses the shared RBI-Handbook state resolver: the
``state`` column carries full display names ("Andhra Pradesh", "Tamil Nadu")
that map to LGD slugs. Two label classes are dropped and reported rather than
emitted, because this is a STATE-grain series:

  * the publisher's "All India" aggregate row (it resolves to the country
    entity "IN", and equals the sum of the state rows, so keeping it would
    add a non-state row and invite double-counting); and
  * any label that does not resolve to a single LGD entity - today the
    combined "Jammu and Kashmir and Ladakh" total, which the source still
    reports as one label even though those territories split into two
    separate entities in 2019, so it cannot be honestly attributed to either.

A null/None measure cell is a sparse "no observation" and is skipped (it does
not zero-out the state's total); a (state, year) whose every industry cell is
null contributes no row at all.

No network: reads operator-staged response bytes only (parent plan section
21.4). Decryption is the shared CryptoJS-OpenSSL path in
``yen_gov.canonical.adapters.iced_common.crypto``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from yen_gov.canonical.adapters.rbi_handbook import StateResolver
from yen_gov.canonical.adapters.iced_common import load_iced_response

__all__ = [
    "CaptiveDropReport",
    "CaptivePowerShapeError",
    "CaptivePowerSpec",
    "CaptiveRow",
    "parse_captive_feed",
]

# The country entity id (ISO 3166 alpha-2). The feed's "All India" aggregate
# label resolves to this; for a state-grain series it is dropped, not emitted.
_COUNTRY_ENTITY_ID = "IN"

# State-label spellings that denote the all-India aggregate. Compared
# case-folded. Caught explicitly (before the resolver) so the drop is recorded
# as an intentional aggregate drop rather than a coverage gap.
_AGGREGATE_LABELS: frozenset[str] = frozenset({"all india", "india", "all-india"})

# Measure-cell contents that mean "no observation" -> the cell is skipped
# (sparse-safe), NOT coerced to zero.
_NA_MARKERS: frozenset[str] = frozenset(
    {"", "-", "--", "n.a.", "na", "n.a", "na.", "nr", "...", "null", "none"}
)


class CaptivePowerShapeError(ValueError):
    """The staged ICED captive-power feed no longer matches its spec.

    Raised loud (never emit a wholesale-empty file) so an upstream change -
    a missing ``data`` list, the disappearance of the ``stateWise`` rows, a
    renamed measure column, or an unparseable value - surfaces to the operator
    instead of silently dropping every state's captive total.
    """


@dataclass(frozen=True)
class CaptiveRow:
    """One emitted long-format observation (entity x year -> MW or GWh)."""

    entity_id: str
    time: int
    value: float


@dataclass(frozen=True)
class CaptiveDropReport:
    """Distinct non-state ``state`` labels skipped during aggregation.

    Both buckets are reported (never silently swallowed) so the operator can
    see exactly what the state-grain emit excluded.
    """

    aggregate_labels: tuple[str, ...]   # all-India / national aggregate labels
    unresolved_labels: tuple[str, ...]  # labels with no single LGD entity

    @property
    def total_labels(self) -> int:
        return len(self.aggregate_labels) + len(self.unresolved_labels)


@dataclass(frozen=True)
class CaptivePowerSpec:
    """One ICED captive-power measure -> one canonical indicator.

    A single spec carries everything three downstream surfaces need: the feed
    transform (parser), the catalogue rows (``variables.csv`` +
    ``concepts.csv``), and the citation triple (``source.csv``). Both shipped
    measures (capacity, generation) read the SAME staged feed and share the
    SAME source triple; they differ only in ``measure`` (which column to sum)
    and their identity / unit.
    """

    # --- identity / output (the variables.csv + concepts.csv rows) ---
    indicator_id: str          # flat kebab; = the datapoint filename stem
    name: str                  # citizen-facing label (variables.csv.name)
    concept_id: str            # FK -> concepts.csv
    concept_noun: str          # concepts.csv.noun
    concept_description: str   # concepts.csv.description (honest caveats)
    unit: str                  # variables.csv.unit (display); "MW" / "GWh"
    unit_canonical: str        # concepts.csv.unit_canonical
    normalisation: str         # concepts.csv enum: absolute|per_capita|per_area|share|ratio|index
    topic: str                 # FK -> topics.csv; "energy"
    entity_kinds: str          # concepts.csv.entity_kinds (space-joined); "state"
    update_period_days: int    # publisher refresh cadence
    derivation: str | None     # variables.csv.derivation (the sum-over-industries note)

    # --- provenance (source.csv row; source_id is DERIVED, never set) ---
    source_producer: str       # ICED dashboard (the access surface / publisher)
    source_title: str          # names the captive-power feed
    source_vintage: str        # access edition (e.g. "2024-25")
    source_url: str            # ICED dashboard landing page

    # --- staging + transform ---
    staging_filename: str      # filename the operator saves under the staging dir
    measure: str               # which feed column to sum: "capacity" | "generation"


def parse_captive_feed(
    raw_bytes: bytes,
    spec: CaptivePowerSpec,
    resolver: StateResolver,
) -> tuple[list[CaptiveRow], CaptiveDropReport]:
    """Decrypt, keep stateWise rows, resolve entities, sum the measure per (entity, year).

    Args:
        raw_bytes: the operator-staged raw response body (AES envelope, or
            plain JSON in tests).
        spec: the measure spec naming the column to sum and the citation.
        resolver: the shared RBI-Handbook display-name -> entity_id resolver.

    Returns:
        A 2-tuple ``(rows, report)`` where ``rows`` is the long-format
        observations (sorted by ``(entity_id, time)``) and ``report`` names the
        distinct aggregate / unresolved ``state`` labels that were dropped.

    Raises:
        CaptivePowerShapeError: the envelope has no ``data`` list, a data
            element is not a dict, no ``stateWise`` row is present (the shape
            we depend on vanished), the chosen measure is unparseable, or the
            whole feed yielded no observation (refusing to emit empty).
    """
    envelope = load_iced_response(raw_bytes, decrypt=True)
    data = _extract_data(envelope, spec)

    sums: dict[tuple[str, int], float] = {}
    aggregate: set[str] = set()
    unresolved: set[str] = set()
    saw_state_wise = False

    for index, raw in enumerate(data):
        if not isinstance(raw, dict):
            raise CaptivePowerShapeError(
                f"{spec.indicator_id}: data[{index}] is not an object "
                f"({type(raw).__name__}); the feed shape changed."
            )
        if raw.get("dataFor") != "stateWise":
            # sourceWise (national fuel-mix) rows carry no state and would
            # double-count the same MW - ignored by design.
            continue
        saw_state_wise = True

        label_raw = raw.get("state")
        label = str(label_raw).strip() if label_raw is not None else ""
        if label.casefold() in _AGGREGATE_LABELS:
            aggregate.add(label)
            continue
        entity = resolver.resolve(label_raw)
        if entity == _COUNTRY_ENTITY_ID:
            aggregate.add(label)
            continue
        if entity is None:
            unresolved.add(label)
            continue

        value = _coerce_measure(raw.get(spec.measure), spec, index)
        if value is None:
            # Sparse cell (this industry reported no captive total this year):
            # no observation. Skipped, not summed as zero.
            continue
        time = _fy_start_year(raw.get("year"), spec, index)
        key = (entity, time)
        sums[key] = sums.get(key, 0.0) + value

    if not saw_state_wise:
        raise CaptivePowerShapeError(
            f"{spec.indicator_id}: no 'stateWise' rows in the feed; the "
            f"endpoint shape changed (refusing to emit an empty file)."
        )
    if not sums:
        raise CaptivePowerShapeError(
            f"{spec.indicator_id}: every stateWise '{spec.measure}' cell was "
            f"empty or non-state; the feed yielded no observation (refusing to "
            f"emit an empty file)."
        )

    rows = [
        CaptiveRow(entity_id=entity, time=time, value=value)
        for (entity, time), value in sums.items()
    ]
    rows.sort(key=lambda r: (r.entity_id, r.time))
    report = CaptiveDropReport(
        aggregate_labels=tuple(sorted(aggregate)),
        unresolved_labels=tuple(sorted(unresolved)),
    )
    return rows, report


def _extract_data(envelope: Any, spec: CaptivePowerSpec) -> list[Any]:
    """Pull the ``data`` list out of the decrypted envelope, fail-loud."""
    if isinstance(envelope, dict):
        data = envelope.get("data")
    elif isinstance(envelope, list):
        data = envelope
    else:
        data = None
    if not isinstance(data, list):
        raise CaptivePowerShapeError(
            f"{spec.indicator_id}: decrypted response has no 'data' list "
            f"(got {type(envelope).__name__}); the endpoint format changed."
        )
    return data


def _fy_start_year(year: Any, spec: CaptivePowerSpec, index: int) -> int:
    """Reduce a fiscal-year label ("2005-06") to its integer start year (2005).

    The canonical ``datasets/data/datapoints/geo/*.csv`` ``time`` column is an
    integer year. The feed's ``year`` is a fiscal-year string; the repo
    convention (``iced_state_wise._period_to_year_int``) takes the first four
    digits, so a fiscal year maps to its START calendar year ("2005-06" ->
    2005).
    """
    text = str(year).strip() if year is not None else ""
    if len(text) < 4 or not text[:4].isdigit():
        raise CaptivePowerShapeError(
            f"{spec.indicator_id}: data[{index}] has an unparseable year "
            f"{year!r}; expected a 'YYYY' or 'YYYY-YY' fiscal-year label."
        )
    return int(text[:4])


def _coerce_measure(
    value: Any, spec: CaptivePowerSpec, index: int
) -> float | None:
    """Coerce a measure cell to a float, or None for a sparse (N.A.) cell.

    Raises on genuine garbage (a non-numeric, non-N.A. string) so a feed-shape
    change surfaces instead of being silently coerced.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise CaptivePowerShapeError(
            f"{spec.indicator_id}: data[{index}] {spec.measure} is a boolean; "
            f"expected a number."
        )
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if text.casefold() in _NA_MARKERS:
            return None
        try:
            return float(text)
        except ValueError as err:
            raise CaptivePowerShapeError(
                f"{spec.indicator_id}: data[{index}] {spec.measure} {value!r} "
                f"is not a number ({err})."
            ) from err
    raise CaptivePowerShapeError(
        f"{spec.indicator_id}: data[{index}] {spec.measure} has unexpected "
        f"type {type(value).__name__}."
    )
