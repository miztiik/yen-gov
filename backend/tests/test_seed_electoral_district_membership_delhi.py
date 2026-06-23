"""Tests for the geometry-derived Delhi AC->district membership supplement."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from yen_gov.canonical.seed import (
    electoral_district_membership_delhi_geometry as delhi,
)


def _ac_prop(ac_no, ac_name, dist_lgd, *, dist_name="X", st_code="07"):
    return {
        "st_code": st_code,
        "ac_no": ac_no,
        "ac_name": ac_name,
        "Dist_LGD": dist_lgd,
        "dist_name": dist_name,
    }


def test_build_rows_maps_dist_lgd_to_geo_entity():
    props = [_ac_prop(1, "Nerela", 81), _ac_prop(28, "Hari Nagar", 85)]
    geo_index = {"81": "delhi/north", "85": "delhi/west"}
    rows = delhi.build_delhi_membership_rows(
        props, geo_index, source_id="src-x", lgd_snapshot="2026-06-16"
    )
    assert rows == [
        {
            "electoral_id": "IN-AC-2008-delhi-eci1",
            "lgd_district_id": "delhi/north",
            "is_primary": True,
            "lgd_snapshot": "2026-06-16",
            "source_id": "src-x",
        },
        {
            "electoral_id": "IN-AC-2008-delhi-eci28",
            "lgd_district_id": "delhi/west",
            "is_primary": True,
            "lgd_snapshot": "2026-06-16",
            "source_id": "src-x",
        },
    ]


def test_build_rows_raises_on_district_without_geo_entity():
    # The Shahdara case before delhi/shahdara was added to geo.csv: a missing
    # FK target must be LOUD, never silently dropped.
    props = [_ac_prop(62, "Shahdara", 671)]
    with pytest.raises(ValueError, match="Dist_LGD=671"):
        delhi.build_delhi_membership_rows(props, {"81": "delhi/north"})


def test_load_geo_lgd_index_reads_lgd_alias(tmp_path: Path):
    geo = tmp_path / "geo.csv"
    geo.write_text(
        "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
        "delhi/north,North,delhi,district,lgd:81,,\n"
        "delhi/shahdara,Shahdara,delhi,district,lgd:671,,\n"
        "delhi,Delhi,,state,,,\n",
        encoding="utf-8",
    )
    assert delhi.load_geo_lgd_index(geo) == {
        "81": "delhi/north",
        "671": "delhi/shahdara",
    }


def _write_topojson(path: Path, props_list):
    path.write_text(
        json.dumps(
            {
                "type": "Topology",
                "objects": {
                    "ac": {
                        "type": "GeometryCollection",
                        "geometries": [
                            {"type": "Point", "properties": p} for p in props_list
                        ],
                    }
                },
                "arcs": [],
            }
        ),
        encoding="utf-8",
    )


def test_append_replaces_stale_delhi_keeps_other_states_and_is_idempotent(tmp_path: Path):
    mem = tmp_path / "electoral_district_membership.csv"
    mem.write_text(
        "electoral_id,lgd_district_id,is_primary,lgd_snapshot,source_id\n"
        "IN-AC-2008-andhra-pradesh-3166,andhra-pradesh/x,true,2026-06-05,src-lgd\n"
        "IN-AC-2008-delhi-eci99,delhi/north,true,stale,src-old\n",
        encoding="utf-8",
    )
    geo = tmp_path / "geo.csv"
    geo.write_text(
        "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
        "delhi/north,North,delhi,district,lgd:81,,\n"
        "delhi/shahdara,Shahdara,delhi,district,lgd:671,,\n",
        encoding="utf-8",
    )
    topo = tmp_path / "ac.topojson"
    _write_topojson(
        topo,
        [
            _ac_prop(1, "Nerela", 81),
            _ac_prop(62, "Shahdara", 671),
            _ac_prop(5, "Out Of State", 81, st_code="28"),  # non-Delhi -> ignored
        ],
    )

    n = delhi.append_delhi_to_membership(
        membership_csv=mem, geo_csv=geo, ac_topojson=topo, source_id="src-rs"
    )
    assert n == 2  # the st_code=28 feature is excluded

    rows = list(csv.DictReader(mem.open(encoding="utf-8")))
    eids = {r["electoral_id"] for r in rows}
    assert "IN-AC-2008-andhra-pradesh-3166" in eids  # other state preserved
    assert "IN-AC-2008-delhi-eci99" not in eids  # stale Delhi row dropped
    assert {"IN-AC-2008-delhi-eci1", "IN-AC-2008-delhi-eci62"} <= eids  # fresh edges
    shahdara = next(r for r in rows if r["electoral_id"] == "IN-AC-2008-delhi-eci62")
    assert shahdara["lgd_district_id"] == "delhi/shahdara"
    assert shahdara["source_id"] == "src-rs"

    # second run is stable (idempotent)
    n2 = delhi.append_delhi_to_membership(
        membership_csv=mem, geo_csv=geo, ac_topojson=topo, source_id="src-rs"
    )
    assert n2 == 2
    assert len(list(csv.DictReader(mem.open(encoding="utf-8")))) == len(rows)
