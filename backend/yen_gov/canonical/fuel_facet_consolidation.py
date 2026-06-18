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
    "GENERATION_FAMILIES",
    "RETIRED_FAMILIES",
    "ALL_FUEL_FACETED_FAMILIES",
    "OIL_PRODUCT_FAMILIES",
    "consolidate_family_rows",
    "write_faceted_family",
]

_GEO_DIR = "datasets/data/datapoints/geo"

# Each faceting axis writes to its own per-axis sibling file-class
# datasets/data/datapoints/geo_by_<segment>/*.csv (blessed in columns.json).
# The dataclass ``axis`` field is the dimension COLUMN name; this maps it to
# the directory segment (fuel_type -> geo_by_fuel; product -> geo_by_product).
_AXIS_TO_FACET_SEGMENT: dict[str, str] = {
    "fuel_type": "fuel",
    "product": "product",
}

# The aggregate member that carries the publisher's published total (NOT a sum
# of parts). Only families with a parent total file on disk emit it.
ALL_MEMBER = "all"


def _facet_dir(axis: str) -> str:
    """``datasets/data/datapoints/geo_by_<segment>`` for the given axis."""
    return f"datasets/data/datapoints/geo_by_{_AXIS_TO_FACET_SEGMENT[axis]}"


def _facet_file_class(axis: str) -> str:
    """The columns.json file-class glob for the given axis."""
    return f"{_facet_dir(axis)}/*.csv"


@dataclass(frozen=True)
class FuelFamilySpec:
    """One faceted measure to materialise.

    Attributes:
        parent_id: the faceted measure's ``variable_id`` - also the output
            filename stem (``geo_by_<axis>/<parent_id>.csv``). Stays in
            ``variables.csv`` as the single faceted measure row.
        has_all_member: when True, ``geo/<parent_id>.csv`` exists on disk and
            its rows fold in as the ``<axis> = all`` aggregate member.
        children: ordered ``(facet_value, child_variable_id)`` pairs; each
            ``geo/<child_variable_id>.csv`` is read and tagged
            ``<axis> = facet_value``. ``facet_value`` MUST be in the file
            class's enum for ``axis``.
        axis: the dimension COLUMN name written into the faceted file and the
            geo_by_<segment> directory selector. Defaults to ``"fuel_type"``
            (the geo_by_fuel families); ``"product"`` selects geo_by_product.
    """

    parent_id: str
    has_all_member: bool
    children: tuple[tuple[str, str], ...]
    axis: str = "fuel_type"


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

    Each output row is ``{entity_id, time, <axis>, value, source_id}`` with
    the per-row ``source_id`` preserved verbatim from the input (Holy Law #9).
    ``value`` is passed through as a string (empty -> None) and coerced by
    ``write_csv``; the writer's shortest-round-trippable float repr keeps the
    bytes stable.
    """
    rows: list[dict[str, Any]] = []
    if spec.has_all_member:
        for r in _read_geo_rows(root, spec.parent_id):
            rows.append(_facet_row(r, ALL_MEMBER, spec.axis))
    for facet_value, child_id in spec.children:
        for r in _read_geo_rows(root, child_id):
            rows.append(_facet_row(r, facet_value, spec.axis))
    return rows


def _facet_row(
    geo_row: dict[str, str], facet_value: str, axis: str
) -> dict[str, Any]:
    return {
        "entity_id": geo_row["entity_id"],
        "time": geo_row["time"],
        axis: facet_value,
        "value": geo_row["value"] if geo_row["value"] != "" else None,
        "source_id": geo_row["source_id"],
    }


def write_faceted_family(root: Path, spec: FuelFamilySpec) -> Path:
    """Consolidate one family and write ``geo_by_<axis>/<parent_id>.csv``."""
    rows = consolidate_family_rows(root, spec)
    out_path = root / _facet_dir(spec.axis) / f"{spec.parent_id}.csv"
    return write_csv(
        path=out_path, file_class=_facet_file_class(spec.axis), rows=rows
    )


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


# D1 (energy fast-follow): state electricity generation by fuel. Same move as
# the capacity families above -- 5 per-fuel geo/*.csv children + a parent total
# file fold into ONE faceted geo_by_fuel/electricity-generation-gwh.csv. The
# parent electricity-generation-gwh.csv exists on disk (the published state
# total) -> has_all_member=True (the `all` member). Fuel children are the 5
# canonical buckets (no sub-fuel collapse: the per-fuel files are already
# canonical-bucket keyed).
GENERATION_FAMILIES: tuple[FuelFamilySpec, ...] = (
    FuelFamilySpec(
        parent_id="electricity-generation-gwh",
        has_all_member=True,  # geo/electricity-generation-gwh.csv = the state total
        children=(
            ("coal", "electricity-generation-gwh-coal"),
            ("gas", "electricity-generation-gwh-gas"),
            ("hydro", "electricity-generation-gwh-hydro"),
            ("nuclear", "electricity-generation-gwh-nuclear"),
            ("renewable", "electricity-generation-gwh-renewable"),
        ),
    ),
)


# D2 (energy fast-follow): national thermal capacity retired by fuel. The two
# per-fuel files (coal, gas) fold into ONE faceted file. National-only
# (entity_id=IN); no parent total file on disk -> has_all_member=False (no
# `all` member; the contract forbids synthesising a published total).
RETIRED_FAMILIES: tuple[FuelFamilySpec, ...] = (
    FuelFamilySpec(
        parent_id="india-thermal-capacity-retired-mw",
        has_all_member=False,
        children=(
            ("coal", "india-thermal-capacity-retired-mw-coal"),
            ("gas", "india-thermal-capacity-retired-mw-gas"),
        ),
    ),
)


# Every fuel-faceted energy family the consolidate-fuel-facets CLI materialises.
ALL_FUEL_FACETED_FAMILIES: tuple[FuelFamilySpec, ...] = (
    INSTALLED_CAPACITY_FAMILIES + GENERATION_FAMILIES + RETIRED_FAMILIES
)


# Path A (oil-product faceting): per-state petroleum-product consumption by
# product. The 7 per-product geo/*.csv children fold into ONE faceted file
# under the NEW per-axis sibling class geo_by_product/*.csv (axis="product";
# closed enum of the 7 NITI Aayog ICED "Oil Product Consumption State-wise"
# product slugs). State-only grain (no IN/country rows); there is NO parent
# total file on disk -> has_all_member=False (no `all` member; the contract
# forbids synthesising a published total). Same structural move as the
# geo_by_fuel families (PR #1097 / D1 / D2) at a new axis + file-class,
# materialised by the sibling consolidate-product-facets CLI. This is a
# SEPARATE registry from ALL_FUEL_FACETED_FAMILIES (different axis + output
# class), so it is intentionally NOT folded into that fuel-only tuple.
OIL_PRODUCT_FAMILIES: tuple[FuelFamilySpec, ...] = (
    FuelFamilySpec(
        parent_id="oil-product-consumption-kt",
        has_all_member=False,
        children=(
            ("diesel-hsd", "oil-product-consumption-kt-diesel-hsd"),
            ("kerosene", "oil-product-consumption-kt-kerosene"),
            ("lpg", "oil-product-consumption-kt-lpg"),
            ("naphtha", "oil-product-consumption-kt-naphtha"),
            ("others", "oil-product-consumption-kt-others"),
            ("petrol", "oil-product-consumption-kt-petrol"),
            ("petroleum-coke", "oil-product-consumption-kt-petroleum-coke"),
        ),
        axis="product",
    ),
)
