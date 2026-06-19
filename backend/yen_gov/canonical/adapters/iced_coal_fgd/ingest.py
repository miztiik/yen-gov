"""ICED coal-FGD - ingest orchestrator (parse -> geocode -> aggregate -> emit).

One pipeline turns the staged coal-plant inventory into the single state-grain
``coal-capacity-fgd-share-pct`` series:

    staged encrypted JSON  ->  decrypt + classify (parser)
                           ->  geocode each operating unit to its LGD state
                               (geocode: ray-cast point-in-polygon + bounded
                               coastal snap)
                           ->  per state: share = 100 x scrubbed-operating-MW
                               / total-operating-MW
                           ->  emit datapoints/geo CSV  +  upsert
                               variables / concepts / source catalogue rows

Fail-loud discipline (CLAUDE Holy Law #5, the task's "do not emit a
misleading partial series"): if more than :data:`MAX_UNPLACED_FRACTION` of the
operating fleet cannot be attributed to a state (missed every polygon beyond
the snap tolerance, or had no coordinates), the run RAISES rather than emit a
biased series. Coastal plants that snap to the nearest boundary and unplaced
plants are both reported on the result so the operator sees exactly what was
attributed.

No network: reads operator-staged response bytes only (parent plan section
21.4). Each run is idempotent (the canonical writer skip-writes byte-identical
output).
"""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_columns import load_columns
from yen_gov.canonical.csv_writer import write_csv

from .geocode import StateGeocoder
from .parser import CoalUnit, ParseReport, parse_coal_units
from .registry import ASSESSMENT_YEAR, SHIPPED_SPEC, CoalFgdSpec

__all__ = [
    "ingest",
    "CoalFgdIngestResult",
    "GeocodeReport",
    "CoalFgdGeocodeError",
    "MAX_UNPLACED_FRACTION",
    "SHARE_VALUE_DECIMALS",
]

# If more than this fraction of operating units cannot be attributed to a
# state, the per-state share series is no longer trustworthy -> STOP. On the
# real feed this is 0 (every operating unit is contained or snaps to a coastal
# boundary); the guard protects against a future bad re-stage.
MAX_UNPLACED_FRACTION = 0.05

# Citizen-readable percentage precision.
SHARE_VALUE_DECIMALS = 2

_DATAPOINTS_FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
_DATAPOINTS_REL_DIR = "datasets/data/datapoints/geo"
_VARIABLES_REL = "datasets/data/variables.csv"
_CONCEPTS_REL = "datasets/data/concepts.csv"
_SOURCE_REL = "datasets/data/entities/source.csv"


class CoalFgdGeocodeError(ValueError):
    """Too much of the operating fleet could not be geocoded to a state.

    Raised when the unattributed fraction exceeds :data:`MAX_UNPLACED_FRACTION`
    - refusing to emit a per-state share series that silently omits a large,
    geographically-biased slice of the fleet.
    """


@dataclass(frozen=True)
class GeocodeReport:
    """What the geocoder attributed - the honesty receipt for the run."""

    operational_units: int
    placed_contained: int
    placed_snapped: int
    snapped_units: tuple[CoalUnit, ...]
    unplaced_units: tuple[CoalUnit, ...]
    missing_coords_units: tuple[CoalUnit, ...]
    missing_capacity_units: tuple[CoalUnit, ...]
    states_emitted: int
    states_with_fgd: int
    national_share_pct: float

    @property
    def unattributed(self) -> int:
        return len(self.unplaced_units) + len(self.missing_coords_units)

    @property
    def unattributed_fraction(self) -> float:
        if self.operational_units == 0:
            return 0.0
        return self.unattributed / self.operational_units


@dataclass(frozen=True)
class CoalFgdIngestResult:
    """Aggregate outcome of one ``ingest`` run."""

    indicator_id: str
    output_path: Path
    row_count: int
    source_id: str
    parse_report: ParseReport
    geocode_report: GeocodeReport


def ingest(
    *,
    repo_root: Path,
    staging_dir: Path,
    spec: CoalFgdSpec = SHIPPED_SPEC,
    geocoder: StateGeocoder | None = None,
) -> CoalFgdIngestResult:
    """Ingest the staged ICED coal-FGD feed into the canonical store.

    Args:
        repo_root: repo root; anchors the datapoint output dir, the catalogue
            CSVs, and (unless ``geocoder`` is supplied) the boundary corpus.
        staging_dir: directory the operator dropped the ICED JSON response
            into (``spec.staging_filename``). Never a committed contract
            surface (operator input).
        spec: the feed spec (defaults to :data:`SHIPPED_SPEC`).
        geocoder: an explicit geocoder (tests inject a synthetic-boundary one);
            defaults to :meth:`StateGeocoder.from_repo`.

    Returns:
        :class:`CoalFgdIngestResult` with the emitted file + the parse/geocode
        honesty receipts.

    Raises:
        FileNotFoundError: the staged feed (or a boundary/entity file) is
            missing.
        CoalFgdShapeError: the feed no longer matches its expected shape.
        CoalFgdGeocodeError: too much of the fleet could not be geocoded.
    """
    feed_path = staging_dir / spec.staging_filename
    if not feed_path.exists():
        raise FileNotFoundError(
            f"{spec.indicator_id}: staged feed not found at {feed_path}. "
            f"Stage the ICED response there (no network ingest)."
        )

    units, parse_report = parse_coal_units(feed_path.read_bytes())
    if geocoder is None:
        geocoder = StateGeocoder.from_repo(repo_root)

    per_state_den: dict[str, float] = defaultdict(float)
    per_state_num: dict[str, float] = defaultdict(float)
    placed_contained = 0
    placed_snapped = 0
    snapped: list[CoalUnit] = []
    unplaced: list[CoalUnit] = []

    operational = [u for u in units if u.operational]
    for unit in operational:
        if unit.lat is None or unit.lng is None:
            continue  # reported via parse_report.operational_missing_coords
        match = geocoder.locate(unit.lng, unit.lat)
        if match is None:
            unplaced.append(unit)
            continue
        if match.mode == "snapped":
            placed_snapped += 1
            snapped.append(unit)
        else:
            placed_contained += 1
        if unit.capacity_mw is None:
            continue  # reported via parse_report.operational_missing_capacity
        per_state_den[match.entity_id] += unit.capacity_mw
        if unit.has_fgd:
            per_state_num[match.entity_id] += unit.capacity_mw

    total_den = sum(per_state_den.values())
    total_num = sum(per_state_num.values())
    national_share = (
        round(100.0 * total_num / total_den, SHARE_VALUE_DECIMALS)
        if total_den
        else 0.0
    )
    geocode_report = GeocodeReport(
        operational_units=len(operational),
        placed_contained=placed_contained,
        placed_snapped=placed_snapped,
        snapped_units=tuple(snapped),
        unplaced_units=tuple(unplaced),
        missing_coords_units=parse_report.operational_missing_coords,
        missing_capacity_units=parse_report.operational_missing_capacity,
        states_emitted=len(per_state_den),
        states_with_fgd=sum(1 for v in per_state_num.values() if v > 0),
        national_share_pct=national_share,
    )

    # Fail-loud: refuse a geographically-biased partial series.
    if geocode_report.unattributed_fraction > MAX_UNPLACED_FRACTION:
        raise CoalFgdGeocodeError(
            f"{spec.indicator_id}: {geocode_report.unattributed} of "
            f"{len(operational)} operating coal units "
            f"({geocode_report.unattributed_fraction:.1%}) could not be "
            f"geocoded to a state (exceeds the "
            f"{MAX_UNPLACED_FRACTION:.0%} limit). Refusing to emit a "
            f"misleading partial series. Unplaced examples: "
            f"{[u.plant_name for u in unplaced[:5]]}; missing-coords examples: "
            f"{[u.plant_name for u in geocode_report.missing_coords_units[:5]]}."
        )

    contract = load_columns()
    source_id = derive_source_id(
        spec.source_producer, spec.source_title, spec.source_vintage
    )
    datapoint_rows = [
        {
            "entity_id": slug,
            "time": ASSESSMENT_YEAR,
            "value": round(
                100.0 * per_state_num.get(slug, 0.0) / per_state_den[slug],
                SHARE_VALUE_DECIMALS,
            ),
            "source_id": source_id,
        }
        for slug in sorted(per_state_den)
    ]
    out_path = write_csv(
        path=repo_root / _DATAPOINTS_REL_DIR / f"{spec.indicator_id}.csv",
        file_class=_DATAPOINTS_FILE_CLASS,
        rows=datapoint_rows,
        contract=contract,
    )

    _upsert_rows(
        repo_root,
        _VARIABLES_REL,
        [
            {
                "indicator_id": spec.indicator_id,
                "name": spec.name,
                "concept_id": spec.concept_id,
                "unit": spec.unit,
                "derivation": spec.derivation,
                "topic": spec.topic,
                "source_id": source_id,
                "update_period_days": spec.update_period_days,
                "time_min": ASSESSMENT_YEAR,
                "time_max": ASSESSMENT_YEAR,
                "entity_kinds": spec.entity_kinds,
            }
        ],
        contract=contract,
    )
    _upsert_rows(
        repo_root,
        _CONCEPTS_REL,
        [
            {
                "concept_id": spec.concept_id,
                "noun": spec.concept_noun,
                "unit_canonical": spec.unit_canonical,
                "normalisation": spec.normalisation,
                "entity_kinds": spec.entity_kinds,
                "description": spec.concept_description,
            }
        ],
        contract=contract,
    )
    _upsert_rows(
        repo_root,
        _SOURCE_REL,
        [
            {
                "source_id": source_id,
                "producer": spec.source_producer,
                "title": spec.source_title,
                "vintage": spec.source_vintage,
                "url": spec.source_url,
            }
        ],
        contract=contract,
    )

    return CoalFgdIngestResult(
        indicator_id=spec.indicator_id,
        output_path=out_path,
        row_count=len(datapoint_rows),
        source_id=source_id,
        parse_report=parse_report,
        geocode_report=geocode_report,
    )


def _upsert_rows(
    repo_root: Path,
    rel_path: str,
    new_rows: list[dict[str, Any]],
    *,
    contract: Any,
) -> Path:
    """Merge ``new_rows`` into the catalogue CSV at ``rel_path`` by PK.

    A self-contained copy of the rbi_handbook / iced_renewable_potential
    catalogue-merge helper - keeping it local makes this adapter purely
    additive (no cross-adapter private import). Generic PK merge: existing
    rows are preserved verbatim; a re-ingest of the same edition is a no-op.
    """
    path = repo_root / rel_path
    file_class = rel_path
    fc = contract.for_glob(file_class)
    names = [c.name for c in fc.columns]
    pk_names = [c.name for c in fc.pk_columns]

    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            for raw in csv.DictReader(fh):
                row = {
                    name: (raw.get(name) if (raw.get(name) or "") != "" else None)
                    for name in names
                }
                merged[tuple(_pk_value(row[k]) for k in pk_names)] = row
    for row in new_rows:
        key = tuple(_pk_value(row.get(k)) for k in pk_names)
        merged[key] = {name: row.get(name) for name in names}

    return write_csv(
        path=path,
        file_class=file_class,
        rows=list(merged.values()),
        contract=contract,
    )


def _pk_value(value: Any) -> Any:
    """Normalise a PK value for keying (stringify so int/str match)."""
    return str(value) if value is not None else None
