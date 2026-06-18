"""Contract tests for the ICED coal-plant FGD ingest.

No encrypted fixtures on disk: the synthetic feeds are PLAIN JSON. The real
``load_iced_response(..., decrypt=True)`` only AES-decrypts a CryptoJS
envelope (a body starting ``"U2FsdGVkX1``); a plain-JSON body parses straight
through, so a synthetic ``{"status", "data"}`` envelope exercises the real
decrypt-or-parse path without mocking.

The boundary corpus is NEVER loaded here (CLAUDE anti-pattern: no real-corpus
walk in pytest). The geocoder is built from a tiny synthetic 2-state square
fixture - Alpha = lng[0,10] x lat[0,10], Beta = lng[20,30] x lat[0,10], with a
wide gap so an out-of-bounds point is unambiguously unplaced.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from yen_gov.canonical.adapters.iced_coal_fgd import (
    CoalFgdGeocodeError,
    CoalFgdShapeError,
    GeocoderError,
    StateGeocoder,
    ingest,
    parse_coal_units,
)
from yen_gov.canonical.adapters.iced_coal_fgd.registry import (
    ASSESSMENT_YEAR,
    SHIPPED_SPEC,
)
from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv


# --------------------------------------------------------------------------- #
# Synthetic boundary + feed fixtures (NOT the real corpus)
# --------------------------------------------------------------------------- #
_GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
    "alpha,Alpha,IN,state,IN-AL|S91|lgd:101,,\n"
    "beta,Beta,IN,state,IN-BE|S92|lgd:102,,\n"
)


def _square(lng0: float, lat0: float, lng1: float, lat1: float) -> list:
    """A single closed exterior ring for an axis-aligned square."""
    return [
        [
            [lng0, lat0],
            [lng1, lat0],
            [lng1, lat1],
            [lng0, lat1],
            [lng0, lat0],
        ]
    ]


_STATES_FEATURES = [
    {
        "type": "Feature",
        "properties": {"State_LGD": 101, "STNAME": "ALPHA"},
        "geometry": {"type": "Polygon", "coordinates": _square(0, 0, 10, 10)},
    },
    {
        "type": "Feature",
        "properties": {"State_LGD": 102, "STNAME": "BETA"},
        "geometry": {"type": "Polygon", "coordinates": _square(20, 0, 30, 10)},
    },
]


def _write_boundaries(repo_root: Path) -> Path:
    """Write the synthetic geo.csv + states GeoJSON under a repo root."""
    geo = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    geo.parent.mkdir(parents=True, exist_ok=True)
    geo.write_text(_GEO_CSV, encoding="utf-8")
    gj = repo_root / "datasets" / "boundaries" / "in" / "states" / "all.geojson"
    gj.parent.mkdir(parents=True, exist_ok=True)
    gj.write_text(
        json.dumps({"type": "FeatureCollection", "features": _STATES_FEATURES}),
        encoding="utf-8",
    )
    return repo_root


def _geocoder(repo_root: Path) -> StateGeocoder:
    _write_boundaries(repo_root)
    return StateGeocoder.from_repo(repo_root)


def _unit(
    plant: str,
    lng,
    lat,
    capacity,
    fgd_group: str,
    *,
    commissioning_group: str = "operational",
    source: str = "coal",
    unit_name: str | None = None,
) -> dict:
    return {
        "plantName": plant,
        "unitName": unit_name or f"{plant} Unit 1",
        "source": source,
        "capacity": capacity,
        "commissioningStatus": commissioning_group,
        "commissioningGroup": commissioning_group,
        "fgdStatus": fgd_group,
        "fgdGroup": fgd_group,
        "lat": lat,
        "lng": lng,
    }


def _feed_bytes(units: list[dict], *, status: str = "success") -> bytes:
    return json.dumps({"status": status, "data": units}).encode("utf-8")


def _read_datapoints(path: Path) -> dict[str, float]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {r["entity_id"]: float(r["value"]) for r in csv.DictReader(fh)}


# --------------------------------------------------------------------------- #
# Geocoder - point-in-polygon, coastal snap, unplaced, hole, MultiPolygon
# --------------------------------------------------------------------------- #
class TestGeocoder:
    def test_contained_point(self, tmp_path):
        gc = _geocoder(tmp_path)
        a = gc.locate(5.0, 5.0)
        b = gc.locate(25.0, 5.0)
        assert a is not None and a.entity_id == "alpha" and a.mode == "contained"
        assert b is not None and b.entity_id == "beta" and b.mode == "contained"

    def test_coastal_point_snaps_within_tolerance(self, tmp_path):
        # 0.05 deg east of Alpha's edge (lng 10) - inside the 0.1 deg snap band.
        gc = _geocoder(tmp_path)
        m = gc.locate(10.05, 5.0)
        assert m is not None and m.entity_id == "alpha" and m.mode == "snapped"

    def test_out_of_bounds_point_is_unplaced(self, tmp_path):
        gc = _geocoder(tmp_path)
        assert gc.locate(50.0, 50.0) is None  # far from every state
        assert gc.locate(15.0, 5.0) is None  # in the gap between Alpha and Beta

    def test_point_in_hole_is_not_contained(self, tmp_path):
        geo = tmp_path / "geo.csv"
        geo.write_text(_GEO_CSV, encoding="utf-8")
        # Beta as a square with a square hole in the middle.
        exterior = _square(20, 0, 40, 20)[0]
        hole = _square(28, 8, 32, 12)[0]
        gj = tmp_path / "states.geojson"
        gj.write_text(
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {"State_LGD": 102, "STNAME": "BETA"},
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [exterior, hole],
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        gc = StateGeocoder.from_files(geo, gj)
        # In the body but outside the hole -> contained.
        assert gc.locate(22.0, 5.0).entity_id == "beta"
        # Dead centre of the hole -> not contained, and > 0.1 deg from any
        # boundary -> unplaced (never snapped into a hole it sits deep inside).
        assert gc.locate(30.0, 10.0) is None

    def test_multipolygon_second_part_contained(self, tmp_path):
        geo = tmp_path / "geo.csv"
        geo.write_text(_GEO_CSV, encoding="utf-8")
        gj = tmp_path / "states.geojson"
        gj.write_text(
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {"State_LGD": 101, "STNAME": "ALPHA"},
                            "geometry": {
                                "type": "MultiPolygon",
                                "coordinates": [
                                    _square(0, 0, 10, 10),
                                    _square(0, 20, 10, 30),
                                ],
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        gc = StateGeocoder.from_files(geo, gj)
        assert gc.locate(5.0, 5.0).entity_id == "alpha"  # first part
        assert gc.locate(5.0, 25.0).entity_id == "alpha"  # second part

    def test_unmapped_state_lgd_raises(self, tmp_path):
        geo = tmp_path / "geo.csv"
        geo.write_text(_GEO_CSV, encoding="utf-8")  # only lgd 101 + 102
        gj = tmp_path / "states.geojson"
        gj.write_text(
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {"State_LGD": 999, "STNAME": "GHOST"},
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": _square(0, 0, 10, 10),
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        with pytest.raises(GeocoderError, match="maps to no 'state' row"):
            StateGeocoder.from_files(geo, gj)


# --------------------------------------------------------------------------- #
# Parser - classification, coercion, vocabulary-drift fail-loud
# --------------------------------------------------------------------------- #
class TestParser:
    def test_fgd_classification_only_installed_counts(self):
        feed = _feed_bytes(
            [
                _unit("P1", 5, 5, 100, "FGD installed"),
                _unit("P2", 5, 5, 100, "None"),
                _unit("P3", 5, 5, 100, "Bid Awarded"),
                _unit("P4", 5, 5, 100, "Ciculating Fluidized Bed Combustion (CFBC) Boilers"),
                _unit("P5", 5, 5, 100, "Claims to be SO2 compliant"),
            ]
        )
        units, _ = parse_coal_units(feed)
        has_fgd = {u.plant_name: u.has_fgd for u in units}
        assert has_fgd == {
            "P1": True,   # installed
            "P2": False,  # none
            "P3": False,  # bidding
            "P4": False,  # CFBC is a different SO2 tech, not flue-gas FGD
            "P5": False,  # unverified claim
        }

    def test_operational_classification(self):
        feed = _feed_bytes(
            [
                _unit("Op", 5, 5, 100, "FGD installed", commissioning_group="operational"),
                _unit("Ret", 5, 5, 100, "FGD installed", commissioning_group="retired"),
                _unit("Pipe", 5, 5, 100, "FGD installed", commissioning_group="pipeline"),
            ]
        )
        units, report = parse_coal_units(feed)
        operating = {u.plant_name: u.operational for u in units}
        assert operating == {"Op": True, "Ret": False, "Pipe": False}
        assert report.operational_units == 1

    def test_na_coordinates_become_none(self):
        feed = _feed_bytes(
            [
                _unit("Good", 5, 5, 100, "FGD installed"),
                _unit("NoCoord", "N.A.", "N.A.", 100, "None"),
            ]
        )
        units, _ = parse_coal_units(feed)
        by = {u.plant_name: u for u in units}
        assert by["Good"].lat == 5.0 and by["Good"].lng == 5.0
        assert by["NoCoord"].lat is None and by["NoCoord"].lng is None

    def test_non_coal_rows_skipped_and_counted(self):
        feed = _feed_bytes(
            [
                _unit("Coal", 5, 5, 100, "FGD installed"),
                _unit("CoalOp", 6, 6, 100, "None"),
                _unit("Gas", 5, 5, 100, "None", source="gas"),
            ]
        )
        units, report = parse_coal_units(feed)
        assert {u.plant_name for u in units} == {"Coal", "CoalOp"}
        assert report.non_coal_skipped == 1
        assert report.coal_units == 2

    def test_missing_fgd_installed_bucket_raises(self):
        # Publisher renamed the FGD-installed bucket -> refuse an all-zero series.
        feed = _feed_bytes(
            [
                _unit("P1", 5, 5, 100, "None"),
                _unit("P2", 6, 6, 100, "Bid Awarded"),
            ]
        )
        with pytest.raises(CoalFgdShapeError, match="FGD-installed"):
            parse_coal_units(feed)

    def test_missing_operational_bucket_raises(self):
        feed = _feed_bytes(
            [
                _unit("P1", 5, 5, 100, "FGD installed", commissioning_group="retired"),
                _unit("P2", 6, 6, 100, "None", commissioning_group="pipeline"),
            ]
        )
        with pytest.raises(CoalFgdShapeError, match="operational"):
            parse_coal_units(feed)

    def test_no_data_list_raises(self):
        with pytest.raises(CoalFgdShapeError, match="no 'data' list"):
            parse_coal_units(json.dumps({"status": "success"}).encode("utf-8"))


# --------------------------------------------------------------------------- #
# Ingest - per-state share, operating filter, snap, FK closure, source_id
# --------------------------------------------------------------------------- #
class TestIngest:
    def _share_feed(self) -> list[dict]:
        return [
            # Alpha: 1000 FGD + 1000 none -> 50%.
            _unit("Alpha-FGD", 5, 5, 1000, "FGD installed"),
            _unit("Alpha-None", 6, 6, 1000, "None"),
            # Beta: 1500 FGD + 500 none -> 75%.
            _unit("Beta-FGD", 25, 5, 1500, "FGD installed"),
            _unit("Beta-None", 26, 6, 500, "Bid Awarded"),
            # A RETIRED Alpha unit with FGD - must be excluded from the share
            # (if counted, Alpha would jump to (1000+9000)/(2000+9000)=90.9%).
            _unit("Alpha-Retired", 5, 5, 9000, "FGD installed", commissioning_group="retired"),
        ]

    def _stage(self, repo_root: Path, units: list[dict]) -> Path:
        staging = repo_root / "staging"
        staging.mkdir(parents=True, exist_ok=True)
        (staging / SHIPPED_SPEC.staging_filename).write_bytes(_feed_bytes(units))
        return staging

    def test_per_state_share_with_operating_filter(self, tmp_path):
        _write_boundaries(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path, self._share_feed()))
        got = _read_datapoints(
            tmp_path / "datasets/data/datapoints/geo/coal-capacity-fgd-share-pct.csv"
        )
        assert got == {"alpha": 50.0, "beta": 75.0}

    def test_time_is_assessment_year(self, tmp_path):
        _write_boundaries(tmp_path)
        result = ingest(
            repo_root=tmp_path, staging_dir=self._stage(tmp_path, self._share_feed())
        )
        out = tmp_path / "datasets/data/datapoints/geo/coal-capacity-fgd-share-pct.csv"
        with out.open(encoding="utf-8", newline="") as fh:
            times = {int(r["time"]) for r in csv.DictReader(fh)}
        assert times == {ASSESSMENT_YEAR} == {2026}
        assert result.geocode_report.states_with_fgd == 2

    def test_coastal_unit_is_snapped_and_counted(self, tmp_path):
        _write_boundaries(tmp_path)
        feed = [
            _unit("Inland", 5, 5, 1000, "FGD installed"),
            # 0.05 deg east of Alpha's edge -> snapped into Alpha.
            _unit("Coastal", 10.05, 5, 1000, "FGD installed"),
        ]
        result = ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path, feed))
        gr = result.geocode_report
        assert gr.placed_contained == 1
        assert gr.placed_snapped == 1
        assert [u.plant_name for u in gr.snapped_units] == ["Coastal"]
        got = _read_datapoints(
            tmp_path / "datasets/data/datapoints/geo/coal-capacity-fgd-share-pct.csv"
        )
        assert got == {"alpha": 100.0}  # both FGD, both attributed to Alpha

    def test_source_id_is_reproduced(self, tmp_path):
        _write_boundaries(tmp_path)
        result = ingest(
            repo_root=tmp_path, staging_dir=self._stage(tmp_path, self._share_feed())
        )
        expected = derive_source_id(
            SHIPPED_SPEC.source_producer,
            SHIPPED_SPEC.source_title,
            SHIPPED_SPEC.source_vintage,
        )
        assert result.source_id == expected
        source_csv = (tmp_path / "datasets/data/entities/source.csv").read_text(
            encoding="utf-8"
        )
        assert expected in source_csv

    def test_catalogue_rows_upserted(self, tmp_path):
        _write_boundaries(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path, self._share_feed()))
        variables = (tmp_path / "datasets/data/variables.csv").read_text(encoding="utf-8")
        concepts = (tmp_path / "datasets/data/concepts.csv").read_text(encoding="utf-8")
        assert "coal-capacity-fgd-share-pct" in variables
        assert "coal-fgd-compliance-share" in concepts
        # concept normalisation + entity grain.
        assert "share" in concepts
        assert "state" in variables

    def test_emitted_datapoints_pass_validator(self, tmp_path):
        # FK closure: entity_id -> geo.csv (staged) + source_id -> source.csv
        # (upserted by ingest), and filename == indicator_id in variables.csv.
        _write_boundaries(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path, self._share_feed()))
        validate_csv(
            path=tmp_path
            / "datasets/data/datapoints/geo/coal-capacity-fgd-share-pct.csv",
            file_class="datasets/data/datapoints/geo/*.csv",
            repo_root=tmp_path,
        )

    def test_idempotent_reingest(self, tmp_path):
        _write_boundaries(tmp_path)
        staging = self._stage(tmp_path, self._share_feed())
        ingest(repo_root=tmp_path, staging_dir=staging)
        out = tmp_path / "datasets/data/datapoints/geo/coal-capacity-fgd-share-pct.csv"
        first = out.read_bytes()
        ingest(repo_root=tmp_path, staging_dir=staging)
        assert out.read_bytes() == first  # byte-identical re-run


# --------------------------------------------------------------------------- #
# Fail-loud: too much of the fleet unplaced -> refuse a misleading series
# --------------------------------------------------------------------------- #
class TestFailLoud:
    def test_excess_unplaced_raises_and_names_plant(self, tmp_path):
        _write_boundaries(tmp_path)
        feed = [
            _unit("Inland", 5, 5, 1000, "FGD installed"),
            # Far out to sea -> unplaced. 1 of 2 operating units (50%) > the
            # 5% limit, so the ingest must refuse and name the unplaced plant.
            _unit("Offshore Rig", 50, 50, 1000, "None"),
        ]
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / SHIPPED_SPEC.staging_filename).write_bytes(_feed_bytes(feed))
        with pytest.raises(CoalFgdGeocodeError, match="Offshore Rig"):
            ingest(repo_root=tmp_path, staging_dir=staging)
