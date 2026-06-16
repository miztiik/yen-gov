"""Fuel-facet consolidation - collapse per-fuel geo datapoint files into one.

One-shot structural migration for the section-21.6 dimension-column branch
(TODO/20260616-geo-facet-dimension-column-plan.md). Reads the legacy
per-fuel single-value files under ``datasets/data/datapoints/geo/`` (one
``variable_id`` per fuel, the over-fragmentation workaround) and writes ONE
faceted file per measure under ``datasets/data/datapoints/geo_by_fuel/`` with
a ``fuel_type`` dimension column joining the composite PK
``(entity_id, time, fuel_type)``.

The published total (the parent measure file, where one exists on disk) folds
in as the ``fuel_type = all`` member - the published aggregate, NOT a
render-time sum of the parts. Families with no parent file on disk (CEA
snapshot, all-India snapshot) collapse to their fuel members with no ``all``
row.

This is the structural producer because the upstream ICED adapters that
emitted the per-fuel files were retired in X1b (2026-06-07); the on-disk
per-fuel CSVs are the source of truth. Re-runnable from any checkout that
still carries the per-fuel inputs (they are deleted in the final commit of
the same PR); the migration is recorded in ``datasets/migration-ledger.csv``.

Reused by the energy fast-follow (generation, demand-supply, ...) by adding a
``FuelFamilySpec`` to ``INSTALLED_CAPACITY_FAMILIES`` / a sibling registry.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_writer import write_csv

__all__ = [
    "FuelFamilySpec",
    "INSTALLED_CAPACITY_FAMILIES",
    "consolidate_family_rows",
    "write_faceted_family",
]

_GEO_DIR = "datasets/data/datapoints/geo"
_GEO_BY_FUEL_FC = "datasets/data/datapoints/geo_by_fuel/*.csv"
_GEO_BY_FUEL_DIR = "datasets/data/datapoints/geo_by_fuel"

# The fuel member that carries the publisher's aggregate (NOT a sum of parts).
ALL_MEMBER = "all"


@dataclass(frozen=True)
class FuelFamilySpec:
    """One faceted measure to materialise.

    Attributes:
        parent_id: the faceted measure's ``variable_id`` - also the output
            filename stem (``geo_by_fuel/<parent_id>.csv``). Stays in
            ``variables.csv`` as the single faceted measure row.
        has_all_member: when True, ``geo/<parent_id>.csv`` exists on disk and
            its rows fold in as the ``fuel_type = all`` aggregate member.
        children: ordered ``(fuel_value, child_variable_id)`` pairs; each
            ``geo/<child_variable_id>.csv`` is read and tagged
            ``fuel_type = fuel_value``. ``fuel_value`` MUST be in the
            ``geo_by_fuel`` enum (coal, gas, hydro, nuclear, renewable).
    """

    parent_id: str
    has_all_member: bool
    children: tuple[tuple[str, str], ...]


def _read_geo_rows(root: Path, variable_id: str) -> list[dict[str, str]]:
    """Read ``geo/<variable_id>.csv`` as raw string rows (header-checked)."""
    path = root / _GEO_DIR / f"{variable_id}.csv"
    text = path.read_text(encoding="utf-8")
    reader = csv.reader(io.StringIO(text, newline=""))
    rows = list(reader)
    header = rows[0] if rows else []
    expected = ["entity_id", "time", "value", "source_id"]
    if header != expected:
        raise ValueError(
            f"{path.as_posix()}: header {header} != geo file-class {expected}"
        )
    out: list[dict[str, str]] = []
    for raw in rows[1:]:
        out.append(dict(zip(expected, raw, strict=True)))
    return out


def consolidate_family_rows(root: Path, spec: FuelFamilySpec) -> list[dict[str, Any]]:
    """Build the faceted row list for one family (unsorted; write_csv sorts).

    Each output row is ``{entity_id, time, fuel_type, value, source_id}`` with
    the per-row ``source_id`` preserved verbatim from the input (Holy Law #9).
    ``value`` is passed through as a string (empty -> None) and coerced by
    ``write_csv``; the writer's shortest-round-trippable float repr keeps the
    bytes stable.
    """
    rows: list[dict[str, Any]] = []
    if spec.has_all_member:
        for r in _read_geo_rows(root, spec.parent_id):
            rows.append(_facet_row(r, ALL_MEMBER))
    for fuel_value, child_id in spec.children:
        for r in _read_geo_rows(root, child_id):
            rows.append(_facet_row(r, fuel_value))
    return rows


def _facet_row(geo_row: dict[str, str], fuel_value: str) -> dict[str, Any]:
    return {
        "entity_id": geo_row["entity_id"],
        "time": geo_row["time"],
        "fuel_type": fuel_value,
        "value": geo_row["value"] if geo_row["value"] != "" else None,
        "source_id": geo_row["source_id"],
    }


def write_faceted_family(root: Path, spec: FuelFamilySpec) -> Path:
    """Consolidate one family and write ``geo_by_fuel/<parent_id>.csv``."""
    rows = consolidate_family_rows(root, spec)
    out_path = root / _GEO_BY_FUEL_DIR / f"{spec.parent_id}.csv"
    return write_csv(path=out_path, file_class=_GEO_BY_FUEL_FC, rows=rows)


# The 3 fuel-faceted installed-capacity families in scope for the geo-facet PR.
# allocated-mw is excluded: it is single-value (no fuel children on disk),
# so it fails the four-gate facet test and stays an unfaceted geo/*.csv file.
INSTALLED_CAPACITY_FAMILIES: tuple[FuelFamilySpec, ...] = (
    FuelFamilySpec(
        parent_id="installed-capacity-geographical-mw",
        has_all_member=True,  # geo/installed-capacity-geographical-mw.csv = the state total
        children=(
            ("coal", "installed-capacity-geographical-mw-coal"),
            ("gas", "installed-capacity-geographical-mw-gas"),
            ("hydro", "installed-capacity-geographical-mw-hydro"),
            ("nuclear", "installed-capacity-geographical-mw-nuclear"),
            ("renewable", "installed-capacity-geographical-mw-renewable"),
        ),
    ),
    FuelFamilySpec(
        parent_id="installed-capacity-snapshot-mw",
        has_all_member=False,  # no parent file on disk (catalogue row only)
        children=(
            ("coal", "installed-capacity-snapshot-mw-coal"),
            ("gas", "installed-capacity-snapshot-mw-gas"),
            ("hydro", "installed-capacity-snapshot-mw-hydro"),
            ("nuclear", "installed-capacity-snapshot-mw-nuclear"),
            ("renewable", "installed-capacity-snapshot-mw-renewable"),
        ),
    ),
    FuelFamilySpec(
        parent_id="installed-capacity-mw",
        has_all_member=False,  # no parent file on disk (catalogue row only)
        children=(
            ("coal", "installed-capacity-mw-coal"),
            ("gas", "installed-capacity-mw-gas"),
            ("hydro", "installed-capacity-mw-hydro"),
            ("nuclear", "installed-capacity-mw-nuclear"),
            ("renewable", "installed-capacity-mw-renewable"),
        ),
    ),
)


def consolidate_all(root: Path, specs: Iterable[FuelFamilySpec]) -> list[Path]:
    """Materialise every family; return the written paths."""
    return [write_faceted_family(root, spec) for spec in specs]
