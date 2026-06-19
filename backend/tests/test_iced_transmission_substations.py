"""Contract tests for the ICED transmission-substation faceted ingest.

No encrypted fixtures on disk: the synthetic feed is PLAIN JSON. The real
``load_iced_response(..., decrypt=True)`` only AES-decrypts a CryptoJS envelope
(it starts with ``"U2FsdGVkX1``); a plain-JSON body is parsed directly. So a
staged plain-JSON ``{"status", "data"}`` envelope exercises the real
decrypt-or-parse path without mocking and without an AES fixture.

The feed has no state field, so this is a NATIONAL series (entity_id "IN")
faceted by voltage_class. The full-ingest test stages the feed under
``tmp_path`` and asserts the emitted faceted geo_by_voltage CSV (the sum of
capacity per (IN, fiscal-year, voltage_class), the voltage-class mapping, the
dropped-row counts) plus the upserted catalogue rows pass the canonical
validator under the new geo_by_voltage file-class (no real-corpus walk;
CLAUDE anti-pattern).
"""
from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from yen_gov.canonical.adapters.iced_transmission_substations import (
    SHIPPED_SPEC,
    VOLTAGE_CLASSES,
    TransmissionSubstationShapeError,
    classify_voltage_class,
    ingest,
    parse_substation_feed,
)
from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

# Only the country entity is needed (the feed is national-only); FK closure of
# the emitted geo_by_voltage rows is against entities/geo.csv.entity_id == "IN".
_GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
    "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:33,33,33\n"
)


def _write_geo(repo_root: Path) -> Path:
    geo = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    geo.parent.mkdir(parents=True, exist_ok=True)
    geo.write_text(_GEO_CSV, encoding="utf-8")
    return geo


def _feed_bytes(rows: list[dict], *, status: str = "success") -> bytes:
    """Serialise a synthetic decrypted ICED envelope to plain-JSON bytes."""
    return json.dumps({"status": status, "data": rows}).encode("utf-8")


def _asset(voltage_ratio, capacity, year, *, name: str = "Some Substation") -> dict:
    return {
        "name": name,
        "sector": "Central",
        "executiveAgency": "PGCIL",
        "monthOfCompletion": "NOV-15",
        "yearOfCompletion": year,
        # createdAt is the scrape wall-clock; the parser MUST ignore it.
        "createdAt": "2026-05-21T18:33:31.554Z",
        "voltageRatio": voltage_ratio,
        "capacity": capacity,
        "type": "substation",
    }


# >=2 voltage classes + >=2 years, plus the two drop cases and the edge classes
# (HVDC +- marker, bare DC pole, agency-name -> other, reversed 33/220).
_ASSETS = [
    # FY 2015-16 -> 2015
    _asset("765/400", 1500, "2015-16"),                 # 765kv
    _asset("765", 500, "2015-16"),                       # 765kv (sums -> 2000)
    _asset("400/220", 315, "2015-16"),                   # 400kv
    _asset("220/132", 100, "2015-16"),                   # 220kv
    _asset("33/220", 50, "2015-16"),                     # 220kv reversed (sums -> 150)
    _asset("\u00b1800", 1000, "2015-16"),                # hvdc (+- marker)
    _asset("320", 200, "2015-16"),                       # hvdc (DC pole; sums -> 1200)
    _asset("PGCIL", 25, "2015-16"),                      # other (agency-name slip)
    # FY 2016-17 -> 2016
    _asset("400/220/132", 630, "2016-17"),               # 400kv
    _asset("230/110", 60, "2016-17"),                    # 220kv (230 tier)
    _asset("+-800", 1500, "2016-17"),                    # hvdc (ASCII marker)
    # dropped: null capacity
    _asset("400/220", None, "2017-18"),
    # dropped: unparseable year
    _asset("220/132", 80, None),
]

_EXPECTED = {
    ("IN", 2015, "765kv"): 2000.0,
    ("IN", 2015, "400kv"): 315.0,
    ("IN", 2015, "220kv"): 150.0,
    ("IN", 2015, "hvdc"): 1200.0,
    ("IN", 2015, "other"): 25.0,
    ("IN", 2016, "400kv"): 630.0,
    ("IN", 2016, "220kv"): 60.0,
    ("IN", 2016, "hvdc"): 1500.0,
}

_OUT_REL = (
    "datasets/data/datapoints/geo_by_voltage/"
    "substation-capacity-commissioned-mva.csv"
)


def _read_faceted(path: Path) -> dict[tuple[str, int, str], float]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {
            (r["entity_id"], int(r["time"]), r["voltage_class"]): float(r["value"])
            for r in csv.DictReader(fh)
        }


def _stage(tmp_path: Path, rows: list[dict] | None = None) -> Path:
    staging = tmp_path / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / SHIPPED_SPEC.staging_filename).write_bytes(
        _feed_bytes(_ASSETS if rows is None else rows)
    )
    return staging


# --------------------------------------------------------------------------- #
# classify_voltage_class - the voltageRatio -> bucket mapping
# --------------------------------------------------------------------------- #


class TestClassify:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("765/400", "765kv"),
            ("765", "765kv"),
            ("765/400/220", "765kv"),
            ("400/220", "400kv"),
            ("400", "400kv"),
            ("400/220/132", "400kv"),
            ("400/230-110", "400kv"),
            ("220/132", "220kv"),
            ("220/66", "220kv"),
            ("230/110", "220kv"),       # 230 kV southern tier == 220 level
            ("33/220", "220kv"),        # reversed entry: highest token governs
            ("220  /132", "220kv"),     # stray whitespace
            ("400/220/\n33", "400kv"),  # embedded newline
            ("\u00b1800", "hvdc"),      # +- (plus-minus) marker
            ("+-800", "hvdc"),          # ASCII +- marker
            ("800", "hvdc"),            # bare DC pole voltage
            ("320", "hvdc"),            # +-320 kV VSC pole
            ("PGCIL", "other"),         # agency name mis-populated upstream
            ("TANTRANSCO", "other"),
            ("", "other"),
            (None, "other"),
        ],
    )
    def test_mapping(self, raw, expected):
        assert classify_voltage_class(raw) == expected

    def test_governing_voltage_is_the_highest_token(self):
        # A multi-winding ratio is classified by its highest voltage, never the
        # leading or trailing one.
        assert classify_voltage_class("33/220") == "220kv"
        assert classify_voltage_class("765/400/220") == "765kv"

    def test_every_output_is_in_the_closed_enum(self):
        for raw in ("765/400", "400", "220/132", "+-800", "320", "PGCIL", None):
            assert classify_voltage_class(raw) in VOLTAGE_CLASSES


# --------------------------------------------------------------------------- #
# parse_substation_feed - aggregate / drop / fail-loud
# --------------------------------------------------------------------------- #


class TestParse:
    def test_aggregation_sums_capacity_per_entity_year_class(self):
        rows, stats = parse_substation_feed(_feed_bytes(_ASSETS), SHIPPED_SPEC)
        got = {(r.entity_id, r.time, r.voltage_class): r.value for r in rows}
        assert got == _EXPECTED

    def test_only_country_entity_emitted(self):
        rows, _ = parse_substation_feed(_feed_bytes(_ASSETS), SHIPPED_SPEC)
        assert {r.entity_id for r in rows} == {"IN"}

    def test_rows_sorted_by_entity_year_class(self):
        rows, _ = parse_substation_feed(_feed_bytes(_ASSETS), SHIPPED_SPEC)
        keys = [(r.entity_id, r.time, r.voltage_class) for r in rows]
        assert keys == sorted(keys)

    def test_drop_counts(self):
        _, stats = parse_substation_feed(_feed_bytes(_ASSETS), SHIPPED_SPEC)
        assert stats.total_assets == len(_ASSETS)
        assert stats.dropped_null_capacity == 1
        assert stats.dropped_unparseable_year == 1

    def test_null_capacity_checked_before_year(self):
        # A row that is BOTH null-capacity and null-year counts only as a
        # null-capacity drop (capacity is checked first).
        rows, stats = parse_substation_feed(
            _feed_bytes([_asset("400/220", None, None)] + _ASSETS),
            SHIPPED_SPEC,
        )
        assert stats.dropped_null_capacity == 2
        assert stats.dropped_unparseable_year == 1

    def test_all_dropped_raises(self):
        with pytest.raises(TransmissionSubstationShapeError, match="every one of"):
            parse_substation_feed(
                _feed_bytes([_asset("400/220", None, "2015-16")]),
                SHIPPED_SPEC,
            )

    def test_missing_data_list_raises(self):
        with pytest.raises(TransmissionSubstationShapeError, match="no 'data' list"):
            parse_substation_feed(json.dumps({"status": "ok"}).encode(), SHIPPED_SPEC)

    def test_non_dict_element_raises(self):
        with pytest.raises(TransmissionSubstationShapeError, match="not an object"):
            parse_substation_feed(_feed_bytes(["nope"]), SHIPPED_SPEC)

    def test_garbage_capacity_raises(self):
        with pytest.raises(TransmissionSubstationShapeError, match="not a number"):
            parse_substation_feed(
                _feed_bytes([_asset("400/220", "lots", "2015-16")]),
                SHIPPED_SPEC,
            )

    def test_class_outside_declared_enum_raises(self):
        # A spec whose closed enum omits a class the classifier can produce
        # fails loud (keeps classifier + columns.json enum in lockstep).
        narrow = replace(SHIPPED_SPEC, voltage_classes=("765kv",))
        with pytest.raises(TransmissionSubstationShapeError, match="closed enum"):
            parse_substation_feed(_feed_bytes(_ASSETS), narrow)


# --------------------------------------------------------------------------- #
# Registry hygiene
# --------------------------------------------------------------------------- #


class TestRegistry:
    def test_id_has_no_double_underscore_or_grain_prefix(self):
        assert "__" not in SHIPPED_SPEC.indicator_id
        assert not SHIPPED_SPEC.indicator_id.startswith(
            ("state-", "district-", "national-")
        )

    def test_unit_topic_normalisation_entity_kinds(self):
        assert SHIPPED_SPEC.unit == "MVA"
        assert SHIPPED_SPEC.unit_canonical == "MVA"
        assert SHIPPED_SPEC.normalisation == "absolute"
        assert SHIPPED_SPEC.topic == "energy"
        assert SHIPPED_SPEC.entity_kinds == "country"

    def test_national_only(self):
        assert SHIPPED_SPEC.entity_id == "IN"
        assert SHIPPED_SPEC.facet_column == "voltage_class"

    def test_voltage_classes_enum(self):
        assert SHIPPED_SPEC.voltage_classes == ("hvdc", "765kv", "400kv", "220kv", "other")


# --------------------------------------------------------------------------- #
# Full ingest -> emitted corpus validates under the geo_by_voltage file-class
# --------------------------------------------------------------------------- #


class TestIngest:
    def test_emits_faceted_file_with_expected_header(self, tmp_path):
        _write_geo(tmp_path)
        result = ingest(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        assert result.output_path.exists()
        header = result.output_path.read_text(encoding="utf-8").splitlines()[0]
        assert header == "entity_id,time,voltage_class,value,source_id"

    def test_faceted_values_match_expected(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        got = _read_faceted(tmp_path / _OUT_REL)
        assert got == _EXPECTED

    def test_row_count_and_drop_counts_reported(self, tmp_path):
        _write_geo(tmp_path)
        result = ingest(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        assert result.row_count == len(_EXPECTED)
        assert result.time_min == 2015
        assert result.time_max == 2016
        assert result.total_assets == len(_ASSETS)
        assert result.dropped_null_capacity == 1
        assert result.dropped_unparseable_year == 1
        assert dict(result.class_row_counts) == {
            "hvdc": 2,
            "765kv": 1,
            "400kv": 2,
            "220kv": 2,
            "other": 1,
        }

    def test_source_id_is_derived(self, tmp_path):
        _write_geo(tmp_path)
        result = ingest(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        # D2 (ingest plan Row 10/11): KEPT under the org-led label NITI Aayog
        # ICED (the derived substation rollup names no single upstream).
        expected = derive_source_id(
            "NITI Aayog ICED",
            "Transmission Substation List API",
            "2024-25",
        )
        assert result.source_id == expected
        source_csv = (tmp_path / "datasets/data/entities/source.csv").read_text(
            encoding="utf-8"
        )
        assert expected in source_csv

    def test_catalogue_rows_upserted(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        variables = (tmp_path / "datasets/data/variables.csv").read_text(encoding="utf-8")
        concepts = (tmp_path / "datasets/data/concepts.csv").read_text(encoding="utf-8")
        assert "substation-capacity-commissioned-mva" in variables
        assert "substation-capacity-commissioned" in concepts
        # country-grain + energy topic on the variables row.
        assert "country" in variables
        assert "energy" in variables

    def test_emitted_faceted_file_passes_validator(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        # FK targets (geo.csv staged + source.csv upserted) + variables.csv all
        # exist in tmp_path; the validator must accept the faceted file under
        # the new geo_by_voltage file-class (entity_id + source_id FK closure,
        # voltage_class closed-enum membership, filename == indicator_id).
        validate_csv(
            path=tmp_path / _OUT_REL,
            file_class="datasets/data/datapoints/geo_by_voltage/*.csv",
            repo_root=tmp_path,
        )

    def test_idempotent_second_run_is_noop(self, tmp_path):
        _write_geo(tmp_path)
        staging = _stage(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=staging)
        out = tmp_path / _OUT_REL
        first_bytes = out.read_bytes()
        first_mtime = out.stat().st_mtime_ns

        ingest(repo_root=tmp_path, staging_dir=staging)
        assert out.read_bytes() == first_bytes
        assert out.stat().st_mtime_ns == first_mtime

    def test_missing_staged_feed_raises(self, tmp_path):
        _write_geo(tmp_path)
        empty = tmp_path / "staging"
        empty.mkdir()
        with pytest.raises(FileNotFoundError, match="staged feed not found"):
            ingest(repo_root=tmp_path, staging_dir=empty)
