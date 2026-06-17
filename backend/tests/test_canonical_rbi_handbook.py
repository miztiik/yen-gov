"""Contract tests for the reusable RBI Handbook of Statistics ingest.

No fixture files on disk: in-memory openpyxl workbooks mirror the two
real Handbook layouts -

  - single-value: ``State`` header + calendar-year columns + one value
    per (state, year) cell (Birth/Death rate, TFR, IMR);
  - banded: a period row of multi-year windows over Male/Female/Total
    sub-columns, kept to the Total band (Life Expectancy).

The full-ingest test stages a workbook under ``tmp_path`` and asserts the
emitted datapoints CSV plus the upserted variables/concepts/source
catalogue rows pass the canonical validator (no real-corpus walk; CLAUDE
anti-pattern).
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest
from openpyxl import Workbook

from yen_gov.canonical.adapters.rbi_handbook import (
    COUNTRY_ENTITY_ID,
    SHIPPED_SPECS,
    HbsTableSpec,
    RbiHbsShapeError,
    build_state_resolver,
    ingest,
    normalise_label,
    parse_hbs_workbook,
    spec_by_indicator_id,
)
from yen_gov.canonical.adapters.rbi_handbook.parser import (
    TIME_CALENDAR_YEAR,
)
from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

_GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
    "andhra-pradesh,Andhra Pradesh,IN,state,IN-AP|S01|lgd:28,28,28\n"
    "kerala,Kerala,IN,state,IN-KL|S11|lgd:32,32,32\n"
    "odisha,Odisha,IN,state,IN-OD|S18|lgd:21,21,21\n"
    "jammu-and-kashmir,Jammu & Kashmir,IN,state,IN-JK|U08|lgd:1,1,1\n"
    "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:33,33,33\n"
)


def _write_geo(repo_root: Path) -> Path:
    geo = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    geo.parent.mkdir(parents=True, exist_ok=True)
    geo.write_text(_GEO_CSV, encoding="utf-8")
    return geo


def _wb_bytes(rows: list[list[object]], *, title: str = "Sheet1") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = title
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _resolver(tmp_path: Path):
    return build_state_resolver(_write_geo(tmp_path))


# A single-value calendar-year table (TFR-shaped).
_TFR_ROWS: list[list[object]] = [
    ["Table 6: State-Wise Total Fertility Rate", None, None, None],
    ["State", 2016, 2017, 2018],
    ["1. Andhra Pradesh", 1.7, 1.6, 1.6],
    ["2. Kerala", 1.8, 1.7, 1.7],
    ["Orissa", 2.1, 2.0, 1.9],
    ["Jammu & Kashmir", 2.0, "N.A.", 1.5],
    ["All India", 2.3, 2.2, 2.0],
    ["Source: SRS Statistical Report 2024", None, None, None],
]

# A banded window table with Male/Female/Total sub-columns (Life-Exp-shaped).
_LIFE_ROWS: list[list[object]] = [
    ["Table 10: State-Wise Life Expectancy", None, None, None, None, None, None],
    ["State", "2014-18", None, None, "2018-22", None, None],
    [None, "Male", "Female", "Total", "Male", "Female", "Total"],
    ["1. Andhra Pradesh", 67.0, 71.0, 69.0, 68.3, 72.7, 70.3],
    ["Kerala", 72.0, 77.0, 74.5, 71.7, 78.0, 74.8],
    ["All India", 67.0, 70.0, 68.5, 68.2, 71.9, 70.0],
]


# --------------------------------------------------------------------------- #
# normalise_label
# --------------------------------------------------------------------------- #


class TestNormaliseLabel:
    def test_strips_ordinal_and_ampersand(self):
        assert normalise_label("1. Jammu & Kashmir") == "jammu and kashmir"

    def test_lowercases_and_collapses(self):
        assert normalise_label("  Tamil   Nadu ") == "tamil nadu"

    def test_none_is_empty(self):
        assert normalise_label(None) == ""


# --------------------------------------------------------------------------- #
# Resolver
# --------------------------------------------------------------------------- #


class TestResolver:
    def test_canonical_name(self, tmp_path):
        assert _resolver(tmp_path).resolve("Andhra Pradesh") == "andhra-pradesh"

    def test_alias_token(self, tmp_path):
        # S01 / IN-AP aliases in geo.csv resolve to the slug.
        assert _resolver(tmp_path).resolve("S01") == "andhra-pradesh"

    def test_rbi_dialect_orissa(self, tmp_path):
        assert _resolver(tmp_path).resolve("Orissa") == "odisha"

    def test_ampersand_spelling(self, tmp_path):
        assert _resolver(tmp_path).resolve("Jammu & Kashmir") == "jammu-and-kashmir"

    def test_all_india_to_country(self, tmp_path):
        assert _resolver(tmp_path).resolve("All India") == COUNTRY_ENTITY_ID

    def test_unmatched_is_none(self, tmp_path):
        assert _resolver(tmp_path).resolve("Atlantis") is None


# --------------------------------------------------------------------------- #
# Parser - single value
# --------------------------------------------------------------------------- #


def _test_tfr_spec() -> HbsTableSpec:
    return HbsTableSpec(
        indicator_id="test-tfr",
        name="TFR",
        concept_id="total-fertility-rate",
        concept_noun="TFR",
        concept_description="x",
        unit="children per woman",
        unit_canonical="children per woman",
        normalisation="ratio",
        topic="health",
        entity_kinds="country state",
        update_period_days=365,
        source_producer="ORGI",
        source_title="SRS",
        source_vintage="2024-25",
        source_url="https://example.gov.in",
        staging_filename="tfr.xlsx",
        time_kind=TIME_CALENDAR_YEAR,
        skip_labels=("Source",),
    )


class TestParseSingleValue:
    def test_melts_state_year_matrix(self, tmp_path):
        rows = parse_hbs_workbook(
            _wb_bytes(_TFR_ROWS), _test_tfr_spec(), _resolver(tmp_path)
        )
        got = {(r.entity_id, r.time): r.value for r in rows}
        assert got[("andhra-pradesh", 2016)] == 1.7
        assert got[("andhra-pradesh", 2018)] == 1.6
        assert got[("kerala", 2017)] == 1.7
        # Orissa dialect -> odisha slug.
        assert got[("odisha", 2016)] == 2.1
        # All-India row kept as the country entity.
        assert got[("IN", 2018)] == 2.0

    def test_na_cells_dropped(self, tmp_path):
        rows = parse_hbs_workbook(
            _wb_bytes(_TFR_ROWS), _test_tfr_spec(), _resolver(tmp_path)
        )
        jk = {r.time for r in rows if r.entity_id == "jammu-and-kashmir"}
        # 2017 was "N.A." -> dropped; 2016 + 2018 survive.
        assert jk == {2016, 2018}

    def test_source_footnote_row_skipped(self, tmp_path):
        rows = parse_hbs_workbook(
            _wb_bytes(_TFR_ROWS), _test_tfr_spec(), _resolver(tmp_path)
        )
        assert all(r.entity_id != "" for r in rows)
        # Sorted by (entity_id, time).
        keys = [(r.entity_id, r.time) for r in rows]
        assert keys == sorted(keys)

    def test_unmatched_state_raises(self, tmp_path):
        rows = [
            ["State", 2016, 2017],
            ["Andhra Pradesh", 1.7, 1.6],
            ["Atlantis", 9.9, 9.8],
        ]
        with pytest.raises(RbiHbsShapeError, match="unmatched"):
            parse_hbs_workbook(_wb_bytes(rows), _test_tfr_spec(), _resolver(tmp_path))

    def test_unparseable_value_raises(self, tmp_path):
        rows = [
            ["State", 2016],
            ["Andhra Pradesh", "garbage"],
        ]
        with pytest.raises(RbiHbsShapeError, match="unparseable"):
            parse_hbs_workbook(_wb_bytes(rows), _test_tfr_spec(), _resolver(tmp_path))

    def test_missing_header_raises(self, tmp_path):
        rows = [["County", 2016], ["Andhra Pradesh", 1.7]]
        with pytest.raises(RbiHbsShapeError, match="could not locate"):
            parse_hbs_workbook(_wb_bytes(rows), _test_tfr_spec(), _resolver(tmp_path))


# --------------------------------------------------------------------------- #
# Parser - banded (Male / Female / Total)
# --------------------------------------------------------------------------- #


class TestParseBanded:
    def test_keeps_only_total_band_at_window_end_year(self, tmp_path):
        spec = spec_by_indicator_id("life-expectancy-at-birth-years")
        rows = parse_hbs_workbook(_wb_bytes(_LIFE_ROWS), spec, _resolver(tmp_path))
        got = {(r.entity_id, r.time): r.value for r in rows}
        # Window "2014-18" -> time 2018; "2018-22" -> 2022. Only Total kept.
        assert got[("andhra-pradesh", 2018)] == 69.0
        assert got[("andhra-pradesh", 2022)] == 70.3
        assert got[("kerala", 2018)] == 74.5
        assert got[("IN", 2022)] == 70.0
        # Male/Female values must NOT appear.
        assert 68.3 not in got.values()  # AP male 2018-22
        assert 72.7 not in got.values()  # AP female 2018-22

    def test_two_windows_per_state(self, tmp_path):
        spec = spec_by_indicator_id("life-expectancy-at-birth-years")
        rows = parse_hbs_workbook(_wb_bytes(_LIFE_ROWS), spec, _resolver(tmp_path))
        ap_times = sorted(r.time for r in rows if r.entity_id == "andhra-pradesh")
        assert ap_times == [2018, 2022]


# --------------------------------------------------------------------------- #
# Registry hygiene
# --------------------------------------------------------------------------- #


class TestRegistry:
    def test_ids_have_no_double_underscore_or_grain_prefix(self):
        for spec in SHIPPED_SPECS:
            assert "__" not in spec.indicator_id
            assert not spec.indicator_id.startswith(("state-", "district-", "national-"))

    def test_normalisation_in_enum(self):
        allowed = {"absolute", "per_capita", "per_area", "share", "ratio", "index"}
        for spec in SHIPPED_SPECS:
            assert spec.normalisation in allowed

    def test_topics_are_known(self):
        for spec in SHIPPED_SPECS:
            assert spec.topic in {"health", "demography"}

    def test_fertility_and_life_expectancy_present(self):
        ids = {s.indicator_id for s in SHIPPED_SPECS}
        assert "total-fertility-rate" in ids
        assert "life-expectancy-at-birth-years" in ids

    def test_producer_is_source_of_origin_not_rbi(self):
        # Holy Law #9 + Hans/Max verdict: producer = SRS/ORGI, not RBI.
        for spec in SHIPPED_SPECS:
            assert "Registrar General" in spec.source_producer
            assert "RBI" not in spec.source_producer


# --------------------------------------------------------------------------- #
# Full ingest -> emitted corpus validates
# --------------------------------------------------------------------------- #


class TestIngest:
    def _stage(self, tmp_path: Path, spec: HbsTableSpec, rows: list[list[object]]) -> Path:
        staging = tmp_path / "staging"
        staging.mkdir(parents=True, exist_ok=True)
        (staging / spec.staging_filename).write_bytes(_wb_bytes(rows))
        return staging

    def test_emits_datapoints_and_catalogue(self, tmp_path):
        _write_geo(tmp_path)
        spec = spec_by_indicator_id("total-fertility-rate")
        staging = self._stage(tmp_path, spec, _TFR_ROWS)

        result = ingest(repo_root=tmp_path, staging_dir=staging, specs=[spec])

        assert len(result.tables) == 1
        table = result.tables[0]
        assert table.indicator_id == "total-fertility-rate"
        assert table.time_min == 2016
        assert table.time_max == 2018
        # 4 states (AP/Kerala/Odisha) full + JK partial + IN.
        assert table.entity_count == 5

        out = tmp_path / "datasets/data/datapoints/geo/total-fertility-rate.csv"
        assert out.exists()
        header = out.read_text(encoding="utf-8").splitlines()[0]
        assert header == "entity_id,time,value,source_id"

    def test_source_id_is_derived(self, tmp_path):
        _write_geo(tmp_path)
        spec = spec_by_indicator_id("total-fertility-rate")
        staging = self._stage(tmp_path, spec, _TFR_ROWS)
        ingest(repo_root=tmp_path, staging_dir=staging, specs=[spec])

        expected = derive_source_id(
            spec.source_producer, spec.source_title, spec.source_vintage
        )
        source_csv = tmp_path / "datasets/data/entities/source.csv"
        assert expected in source_csv.read_text(encoding="utf-8")

    def test_catalogue_rows_upserted(self, tmp_path):
        _write_geo(tmp_path)
        spec = spec_by_indicator_id("total-fertility-rate")
        staging = self._stage(tmp_path, spec, _TFR_ROWS)
        ingest(repo_root=tmp_path, staging_dir=staging, specs=[spec])

        variables = (tmp_path / "datasets/data/variables.csv").read_text(encoding="utf-8")
        concepts = (tmp_path / "datasets/data/concepts.csv").read_text(encoding="utf-8")
        assert "total-fertility-rate" in variables
        assert "total-fertility-rate" in concepts
        # update_period_days + entity_kinds present on the variables row.
        assert "country state" in variables

    def test_emitted_datapoints_pass_validator(self, tmp_path):
        _write_geo(tmp_path)
        spec = spec_by_indicator_id("total-fertility-rate")
        staging = self._stage(tmp_path, spec, _TFR_ROWS)
        ingest(repo_root=tmp_path, staging_dir=staging, specs=[spec])

        out = tmp_path / "datasets/data/datapoints/geo/total-fertility-rate.csv"
        # FK targets (geo.csv + source.csv) + variables.csv all exist in
        # tmp_path; the validator must accept the emitted file.
        validate_csv(
            path=out,
            file_class="datasets/data/datapoints/geo/*.csv",
            repo_root=tmp_path,
        )

    def test_idempotent_second_run_is_noop(self, tmp_path):
        _write_geo(tmp_path)
        spec = spec_by_indicator_id("total-fertility-rate")
        staging = self._stage(tmp_path, spec, _TFR_ROWS)
        ingest(repo_root=tmp_path, staging_dir=staging, specs=[spec])

        out = tmp_path / "datasets/data/datapoints/geo/total-fertility-rate.csv"
        first_bytes = out.read_bytes()
        first_mtime = out.stat().st_mtime_ns

        ingest(repo_root=tmp_path, staging_dir=staging, specs=[spec])
        # Skip-write-if-equal: bytes identical, mtime untouched.
        assert out.read_bytes() == first_bytes
        assert out.stat().st_mtime_ns == first_mtime

    def test_missing_staged_workbook_raises(self, tmp_path):
        _write_geo(tmp_path)
        spec = spec_by_indicator_id("total-fertility-rate")
        empty = tmp_path / "staging"
        empty.mkdir()
        with pytest.raises(FileNotFoundError, match="staged workbook not found"):
            ingest(repo_root=tmp_path, staging_dir=empty, specs=[spec])
