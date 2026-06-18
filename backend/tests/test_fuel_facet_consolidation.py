"""Unit tests for fuel-facet consolidation (geo-facet plan, C3).

The consolidation reads per-fuel geo/*.csv single-value files and writes one
faceted geo_by_fuel/*.csv with a fuel_type dimension column. tmp_path
fixtures only - never walks the real on-disk corpus (CLAUDE.md anti-pattern).
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from yen_gov.canonical.fuel_facet_consolidation import (
    ALL_FUEL_FACETED_FAMILIES,
    GENERATION_FAMILIES,
    INSTALLED_CAPACITY_FAMILIES,
    OIL_PRODUCT_FAMILIES,
    RETIRED_FAMILIES,
    FuelFamilySpec,
    consolidate_family_rows,
    write_faceted_family,
)


def _write_geo(path: Path, rows: list[tuple[str, str, str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = ["entity_id,time,value,source_id"]
    for r in rows:
        body.append(",".join(r))
    path.write_text("\n".join(body) + "\n", encoding="utf-8")


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    text = path.read_text(encoding="utf-8")
    rows = list(csv.reader(io.StringIO(text, newline="")))
    return rows[0], rows[1:]


def _geo(root: Path) -> Path:
    return root / "datasets" / "data" / "datapoints" / "geo"


def test_consolidate_with_all_member(tmp_path):
    geo = _geo(tmp_path)
    _write_geo(geo / "cap-mw.csv", [("IN-S01", "2020", "1500", "src-a")])
    _write_geo(geo / "cap-mw-coal.csv", [("IN-S01", "2020", "1000", "src-a")])
    _write_geo(geo / "cap-mw-renewable.csv", [("IN-S01", "2020", "500", "src-a")])
    spec = FuelFamilySpec(
        parent_id="cap-mw",
        has_all_member=True,
        children=(
            ("coal", "cap-mw-coal"),
            ("renewable", "cap-mw-renewable"),
        ),
    )
    rows = consolidate_family_rows(tmp_path, spec)
    # 1 parent (all) + 2 fuel rows.
    assert len(rows) == 3
    by_fuel = {r["fuel_type"]: r for r in rows}
    assert set(by_fuel) == {"all", "coal", "renewable"}
    assert by_fuel["all"]["value"] == "1500"
    assert by_fuel["coal"]["source_id"] == "src-a"


def test_consolidate_without_all_member(tmp_path):
    geo = _geo(tmp_path)
    _write_geo(geo / "snap-mw-coal.csv", [("IN-S01", "2026", "100", "src-b")])
    _write_geo(geo / "snap-mw-gas.csv", [("IN-S01", "2026", "50", "src-b")])
    spec = FuelFamilySpec(
        parent_id="snap-mw",
        has_all_member=False,
        children=(("coal", "snap-mw-coal"), ("gas", "snap-mw-gas")),
    )
    rows = consolidate_family_rows(tmp_path, spec)
    assert len(rows) == 2
    assert {r["fuel_type"] for r in rows} == {"coal", "gas"}
    assert all(r["fuel_type"] != "all" for r in rows)


def test_write_faceted_family_emits_sorted_composite_pk(tmp_path):
    geo = _geo(tmp_path)
    # Deliberately unsorted across files; the writer sorts by PK
    # (entity_id, time, fuel_type) so 'all' precedes 'coal'.
    _write_geo(geo / "cap-mw.csv", [
        ("IN-S22", "2020", "800", "src-a"),
        ("IN-S01", "2020", "1500", "src-a"),
    ])
    _write_geo(geo / "cap-mw-coal.csv", [
        ("IN-S01", "2020", "1000", "src-a"),
        ("IN-S22", "2020", "600", "src-a"),
    ])
    spec = FuelFamilySpec(
        parent_id="cap-mw",
        has_all_member=True,
        children=(("coal", "cap-mw-coal"),),
    )
    out = write_faceted_family(tmp_path, spec)
    assert out == (
        tmp_path / "datasets" / "data" / "datapoints" / "geo_by_fuel" / "cap-mw.csv"
    )
    header, data = _read_csv(out)
    assert header == ["entity_id", "time", "fuel_type", "value", "source_id"]
    # Sorted (entity_id, time, fuel_type): S01/all, S01/coal, S22/all, S22/coal.
    assert [(r[0], r[2]) for r in data] == [
        ("IN-S01", "all"),
        ("IN-S01", "coal"),
        ("IN-S22", "all"),
        ("IN-S22", "coal"),
    ]


def test_null_value_round_trips_as_empty(tmp_path):
    geo = _geo(tmp_path)
    _write_geo(geo / "snap-mw-coal.csv", [("IN-S01", "2026", "", "src-b")])
    spec = FuelFamilySpec(
        parent_id="snap-mw",
        has_all_member=False,
        children=(("coal", "snap-mw-coal"),),
    )
    out = write_faceted_family(tmp_path, spec)
    _header, data = _read_csv(out)
    assert data == [["IN-S01", "2026", "coal", "", "src-b"]]


def test_generation_family_is_registered_with_all_member():
    # D1: state electricity generation by fuel, parent total -> `all`.
    assert len(GENERATION_FAMILIES) == 1
    gen = GENERATION_FAMILIES[0]
    assert gen.parent_id == "electricity-generation-gwh"
    assert gen.has_all_member is True  # parent geo file = the published total
    assert [fuel for fuel, _ in gen.children] == [
        "coal", "gas", "hydro", "nuclear", "renewable",
    ]
    # Generation is one of the families the combined registry materialises.
    assert set(GENERATION_FAMILIES) <= set(ALL_FUEL_FACETED_FAMILIES)
    assert set(INSTALLED_CAPACITY_FAMILIES) <= set(ALL_FUEL_FACETED_FAMILIES)


def test_generation_consolidation_folds_parent_into_all(tmp_path):
    geo = _geo(tmp_path)
    _write_geo(geo / "electricity-generation-gwh.csv", [("andhra-pradesh", "2020", "1500", "src-g")])
    _write_geo(geo / "electricity-generation-gwh-coal.csv", [("andhra-pradesh", "2020", "1000", "src-g")])
    _write_geo(geo / "electricity-generation-gwh-renewable.csv", [("andhra-pradesh", "2020", "500", "src-g")])
    spec = FuelFamilySpec(
        parent_id="electricity-generation-gwh",
        has_all_member=True,
        children=(("coal", "electricity-generation-gwh-coal"), ("renewable", "electricity-generation-gwh-renewable")),
    )
    rows = consolidate_family_rows(tmp_path, spec)
    by_fuel = {r["fuel_type"]: r["value"] for r in rows}
    assert by_fuel == {"all": "1500", "coal": "1000", "renewable": "500"}


def test_retired_family_is_registered_without_all_member():
    # D2: national thermal capacity retired by fuel; no parent total -> no `all`.
    assert len(RETIRED_FAMILIES) == 1
    ret = RETIRED_FAMILIES[0]
    assert ret.parent_id == "india-thermal-capacity-retired-mw"
    assert ret.has_all_member is False
    assert [fuel for fuel, _ in ret.children] == ["coal", "gas"]
    # The combined registry the CLI iterates is capacity + generation + retired.
    assert set(ALL_FUEL_FACETED_FAMILIES) == set(
        INSTALLED_CAPACITY_FAMILIES + GENERATION_FAMILIES + RETIRED_FAMILIES
    )


def test_retired_consolidation_has_no_all_member(tmp_path):
    geo = _geo(tmp_path)
    _write_geo(geo / "india-thermal-capacity-retired-mw-coal.csv", [("IN", "2020", "800", "src-r")])
    _write_geo(geo / "india-thermal-capacity-retired-mw-gas.csv", [("IN", "2020", "120", "src-r")])
    rows = consolidate_family_rows(tmp_path, RETIRED_FAMILIES[0])
    by_fuel = {r["fuel_type"]: r["value"] for r in rows}
    assert by_fuel == {"coal": "800", "gas": "120"}
    assert "all" not in by_fuel


def test_fuel_family_spec_defaults_axis_to_fuel_type():
    # Byte-identical guarantee for geo_by_fuel: the axis generalisation leaves
    # every existing fuel spec on axis="fuel_type" (so the output dir, file
    # class and dimension column are all unchanged).
    assert (
        FuelFamilySpec(parent_id="x", has_all_member=False, children=()).axis
        == "fuel_type"
    )
    for fam in ALL_FUEL_FACETED_FAMILIES:
        assert fam.axis == "fuel_type"


def test_oil_product_family_is_registered_with_product_axis():
    # Path A: per-state oil-product consumption faceted by `product`; no parent
    # total file on disk -> no `all` member; NEW geo_by_product axis.
    assert len(OIL_PRODUCT_FAMILIES) == 1
    oil = OIL_PRODUCT_FAMILIES[0]
    assert oil.parent_id == "oil-product-consumption-kt"
    assert oil.axis == "product"
    assert oil.has_all_member is False
    assert [p for p, _ in oil.children] == [
        "diesel-hsd",
        "kerosene",
        "lpg",
        "naphtha",
        "others",
        "petrol",
        "petroleum-coke",
    ]
    # Oil products are a SEPARATE registry from the fuel families (different
    # axis + file-class); they are NOT in the fuel-only registry the
    # consolidate-fuel-facets CLI iterates.
    assert not (set(OIL_PRODUCT_FAMILIES) & set(ALL_FUEL_FACETED_FAMILIES))


def test_product_consolidation_writes_geo_by_product_with_product_column(tmp_path):
    geo = _geo(tmp_path)
    _write_geo(
        geo / "oil-product-consumption-kt-diesel-hsd.csv",
        [("andhra-pradesh", "2020", "1000", "src-o")],
    )
    _write_geo(
        geo / "oil-product-consumption-kt-lpg.csv",
        [("andhra-pradesh", "2020", "500", "src-o")],
    )
    spec = FuelFamilySpec(
        parent_id="oil-product-consumption-kt",
        has_all_member=False,
        children=(
            ("diesel-hsd", "oil-product-consumption-kt-diesel-hsd"),
            ("lpg", "oil-product-consumption-kt-lpg"),
        ),
        axis="product",
    )
    out = write_faceted_family(tmp_path, spec)
    # Writes to the geo_by_product sibling dir, NOT geo_by_fuel.
    assert out == (
        tmp_path
        / "datasets"
        / "data"
        / "datapoints"
        / "geo_by_product"
        / "oil-product-consumption-kt.csv"
    )
    header, data = _read_csv(out)
    assert header == ["entity_id", "time", "product", "value", "source_id"]
    # Sorted (entity_id, time, product): diesel-hsd precedes lpg; no `all` row.
    assert [(r[0], r[2], r[3]) for r in data] == [
        ("andhra-pradesh", "diesel-hsd", "1000"),
        ("andhra-pradesh", "lpg", "500"),
    ]
    assert all(r[2] != "all" for r in data)


def test_product_null_value_round_trips_as_empty(tmp_path):
    geo = _geo(tmp_path)
    _write_geo(
        geo / "oil-product-consumption-kt-naphtha.csv",
        [("goa", "2024", "", "src-o")],
    )
    spec = FuelFamilySpec(
        parent_id="oil-product-consumption-kt",
        has_all_member=False,
        children=(("naphtha", "oil-product-consumption-kt-naphtha"),),
        axis="product",
    )
    out = write_faceted_family(tmp_path, spec)
    _header, data = _read_csv(out)
    assert data == [["goa", "2024", "naphtha", "", "src-o"]]
