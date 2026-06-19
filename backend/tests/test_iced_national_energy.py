"""Contract tests for the ICED national energy-balance ingest.

No encrypted fixtures on disk: the synthetic feeds are PLAIN JSON. The real
``load_iced_response(..., decrypt=True)`` only AES-decrypts a CryptoJS envelope
(a body starting ``"U2FsdGVkX1``); a plain-JSON body is parsed directly. So a
staged plain-JSON ``{"status", "data"}`` envelope exercises the real
decrypt-or-parse path without mocking and without an AES fixture.

The ingest tests stage each national feed under ``tmp_path`` and assert the
emitted FACETED datapoints CSVs (geo_by_primary_source for primary supply;
the 2-D geo_by_sector_fuel for final consumption) plus the upserted catalogue
rows pass the canonical validator (FK closure; no real-corpus walk - CLAUDE
anti-pattern). The two source rows reproduce the on-disk citation ledger
(``src-1d5665f61d9f`` / ``src-c8210dc4af23``, the D2-corrected NITI Aayog ICED
rows) exactly, proving idempotency.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from yen_gov.canonical.adapters.iced_national_energy import (
    FINAL_ENERGY_SPEC,
    PRIMARY_ENERGY_SPEC,
    NationalEnergyShapeError,
    ingest_final,
    ingest_primary,
    parse_sector_wise_consumption,
    parse_source_wise_supply,
)
from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv

# The two citation-ledger rows already on disk (CLAUDE.md section 12). The
# ingest MUST reproduce these exactly from the (producer, title, vintage)
# triple - a new id would orphan the FK and break idempotency.
_PRIMARY_SOURCE_ID = "src-1d5665f61d9f"
_FINAL_SOURCE_ID = "src-c8210dc4af23"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

_GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
)


def _write_geo(repo_root: Path) -> Path:
    geo = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    geo.parent.mkdir(parents=True, exist_ok=True)
    geo.write_text(_GEO_CSV, encoding="utf-8")
    return geo


def _feed_bytes(rows: list[dict], *, status: str = "success") -> bytes:
    """Serialise a synthetic decrypted ICED envelope to plain-JSON bytes."""
    return json.dumps({"status": status, "data": rows}).encode("utf-8")


# Primary: the full 6-source enum across two fiscal years (12 rows). Values are
# illustrative mtoe figures; the FY label reduces to its start year.
_PRIMARY_ROWS = [
    {"year": "2005-06", "source": "Coal", "energyValue": 205.6297986},
    {"year": "2005-06", "source": "Oil", "energyValue": 121.946095},
    {"year": "2005-06", "source": "Gas", "energyValue": 30.5},
    {"year": "2005-06", "source": "Hydro", "energyValue": 8.0},
    {"year": "2005-06", "source": "Nuclear", "energyValue": 4.0},
    {"year": "2005-06", "source": "Renewables", "energyValue": 0.590218},
    {"year": "2006-07", "source": "Coal", "energyValue": 215.0},
    {"year": "2006-07", "source": "Oil", "energyValue": 125.0},
    {"year": "2006-07", "source": "Gas", "energyValue": 31.0},
    {"year": "2006-07", "source": "Hydro", "energyValue": 8.5},
    {"year": "2006-07", "source": "Nuclear", "energyValue": 4.2},
    {"year": "2006-07", "source": "Renewables", "energyValue": 0.7},
]

# Final: a SPARSE sector x fuel matrix (Agriculture has no Coal; not every
# sector has every fuel) across two years - proving sparse handling.
_FINAL_ROWS = [
    {"sector": "Agriculture", "source": "Gas", "year": "2005-06", "energyValue": 0.139673},
    {"sector": "Agriculture", "source": "Oil", "year": "2005-06", "energyValue": 7.289505},
    {"sector": "Agriculture", "source": "Electricity", "year": "2005-06", "energyValue": 7.765112},
    {"sector": "Industry", "source": "Coal", "year": "2005-06", "energyValue": 90.1},
    {"sector": "Industry", "source": "Electricity", "year": "2005-06", "energyValue": 40.0},
    {"sector": "Transport", "source": "Oil", "year": "2005-06", "energyValue": 50.0},
    {"sector": "Industry", "source": "Coal", "year": "2006-07", "energyValue": 95.0},
    {"sector": "Non-Energy", "source": "Oil", "year": "2006-07", "energyValue": 12.0},
]


def _read_primary(path: Path) -> dict[tuple[str, int, str], float]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {
            (r["entity_id"], int(r["time"]), r["primary_source"]): float(r["value"])
            for r in csv.DictReader(fh)
        }


def _read_final(path: Path) -> dict[tuple[str, int, str, str], float]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {
            (r["entity_id"], int(r["time"]), r["sector"], r["fuel"]): float(r["value"])
            for r in csv.DictReader(fh)
        }


def _stage(tmp_path: Path) -> Path:
    staging = tmp_path / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    (staging / PRIMARY_ENERGY_SPEC.staging_filename).write_bytes(_feed_bytes(_PRIMARY_ROWS))
    (staging / FINAL_ENERGY_SPEC.staging_filename).write_bytes(_feed_bytes(_FINAL_ROWS))
    return staging


_PRIMARY_OUT = "datasets/data/datapoints/geo_by_primary_source/primary-energy-supply-mtoe.csv"
_FINAL_OUT = "datasets/data/datapoints/geo_by_sector_fuel/final-energy-consumption-mtoe.csv"


# --------------------------------------------------------------------------- #
# Parser - primary supply
# --------------------------------------------------------------------------- #


class TestParsePrimary:
    def test_maps_all_six_sources_to_slugs(self):
        rows = parse_source_wise_supply(_feed_bytes(_PRIMARY_ROWS), PRIMARY_ENERGY_SPEC)
        assert {r.primary_source for r in rows} == {
            "coal", "gas", "hydro", "nuclear", "oil", "renewable"
        }
        # Renewables -> renewable (matches the geo_by_fuel slug convention).
        coal_2005 = next(
            r for r in rows if r.primary_source == "coal" and r.time == 2005
        )
        assert coal_2005.value == 205.6297986

    def test_time_is_fiscal_year_start(self):
        rows = parse_source_wise_supply(_feed_bytes(_PRIMARY_ROWS), PRIMARY_ENERGY_SPEC)
        assert {r.time for r in rows} == {2005, 2006}

    def test_unknown_source_raises(self):
        bad = [{"year": "2005-06", "source": "Geothermal", "energyValue": 1.0}]
        with pytest.raises(NationalEnergyShapeError, match="unmapped source"):
            parse_source_wise_supply(_feed_bytes(bad), PRIMARY_ENERGY_SPEC)

    def test_garbage_value_raises(self):
        bad = [{"year": "2005-06", "source": "Coal", "energyValue": "lots"}]
        with pytest.raises(NationalEnergyShapeError, match="not a number"):
            parse_source_wise_supply(_feed_bytes(bad), PRIMARY_ENERGY_SPEC)

    def test_duplicate_source_year_raises(self):
        dup = [
            {"year": "2005-06", "source": "Coal", "energyValue": 1.0},
            {"year": "2005-06", "source": "Coal", "energyValue": 2.0},
        ]
        with pytest.raises(NationalEnergyShapeError, match="duplicate"):
            parse_source_wise_supply(_feed_bytes(dup), PRIMARY_ENERGY_SPEC)

    def test_empty_data_raises(self):
        with pytest.raises(NationalEnergyShapeError, match="empty"):
            parse_source_wise_supply(_feed_bytes([]), PRIMARY_ENERGY_SPEC)


# --------------------------------------------------------------------------- #
# Parser - final consumption (2-D)
# --------------------------------------------------------------------------- #


class TestParseFinal:
    def test_maps_sector_and_fuel(self):
        rows = parse_sector_wise_consumption(_feed_bytes(_FINAL_ROWS), FINAL_ENERGY_SPEC)
        got = {(r.time, r.sector, r.fuel): r.value for r in rows}
        assert got[(2005, "agriculture", "gas")] == 0.139673
        assert got[(2005, "industry", "coal")] == 90.1
        # Electricity is a delivered carrier (mapped into the fuel enum).
        assert got[(2005, "agriculture", "electricity")] == 7.765112

    def test_sparse_matrix_emits_only_present_cells(self):
        # Agriculture x Coal is absent upstream -> no row is synthesised.
        rows = parse_sector_wise_consumption(_feed_bytes(_FINAL_ROWS), FINAL_ENERGY_SPEC)
        keys = {(r.sector, r.fuel) for r in rows}
        assert ("agriculture", "coal") not in keys
        assert ("industry", "coal") in keys

    def test_unknown_sector_raises(self):
        bad = [{"sector": "Mining", "source": "Coal", "year": "2005-06", "energyValue": 1.0}]
        with pytest.raises(NationalEnergyShapeError, match="unmapped sector"):
            parse_sector_wise_consumption(_feed_bytes(bad), FINAL_ENERGY_SPEC)

    def test_unknown_fuel_raises(self):
        bad = [{"sector": "Industry", "source": "Biomass", "year": "2005-06", "energyValue": 1.0}]
        with pytest.raises(NationalEnergyShapeError, match="unmapped fuel"):
            parse_sector_wise_consumption(_feed_bytes(bad), FINAL_ENERGY_SPEC)

    def test_duplicate_sector_fuel_year_raises(self):
        dup = [
            {"sector": "Industry", "source": "Coal", "year": "2005-06", "energyValue": 1.0},
            {"sector": "Industry", "source": "Coal", "year": "2005-06", "energyValue": 2.0},
        ]
        with pytest.raises(NationalEnergyShapeError, match="duplicate"):
            parse_sector_wise_consumption(_feed_bytes(dup), FINAL_ENERGY_SPEC)


# --------------------------------------------------------------------------- #
# Registry hygiene + source_id reproduction
# --------------------------------------------------------------------------- #


class TestRegistry:
    def test_ids_have_no_double_underscore_or_grain_prefix(self):
        for spec in (PRIMARY_ENERGY_SPEC, FINAL_ENERGY_SPEC):
            assert "__" not in spec.indicator_id
            assert not spec.indicator_id.startswith(("state-", "district-", "national-", "country-"))

    def test_unit_normalisation_topic_entity_kinds(self):
        for spec in (PRIMARY_ENERGY_SPEC, FINAL_ENERGY_SPEC):
            assert spec.unit == "mtoe"
            assert spec.unit_canonical == "mtoe"
            assert spec.normalisation == "absolute"
            assert spec.topic == "energy"
            assert spec.entity_kinds == "country"
            assert spec.update_period_days == 365

    def test_file_classes(self):
        assert PRIMARY_ENERGY_SPEC.file_class == "datasets/data/datapoints/geo_by_primary_source/*.csv"
        assert FINAL_ENERGY_SPEC.file_class == "datasets/data/datapoints/geo_by_sector_fuel/*.csv"

    def test_source_ids_reproduce_on_disk_ledger(self):
        assert (
            derive_source_id(
                PRIMARY_ENERGY_SPEC.source_producer,
                PRIMARY_ENERGY_SPEC.source_title,
                PRIMARY_ENERGY_SPEC.source_vintage,
            )
            == _PRIMARY_SOURCE_ID
        )
        assert (
            derive_source_id(
                FINAL_ENERGY_SPEC.source_producer,
                FINAL_ENERGY_SPEC.source_title,
                FINAL_ENERGY_SPEC.source_vintage,
            )
            == _FINAL_SOURCE_ID
        )


# --------------------------------------------------------------------------- #
# Full ingest - primary supply (single-axis faceted)
# --------------------------------------------------------------------------- #


class TestIngestPrimary:
    def test_emits_faceted_file_with_header(self, tmp_path):
        _write_geo(tmp_path)
        result = ingest_primary(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        assert result.output_path.exists()
        header = result.output_path.read_text(encoding="utf-8").splitlines()[0]
        assert header == "entity_id,time,primary_source,value,source_id"
        assert result.row_count == 12

    def test_values_and_entity_in(self, tmp_path):
        _write_geo(tmp_path)
        ingest_primary(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        got = _read_primary(tmp_path / _PRIMARY_OUT)
        assert got[("IN", 2005, "coal")] == 205.6297986
        assert got[("IN", 2005, "renewable")] == 0.590218
        assert all(entity == "IN" for entity, _, _ in got)

    def test_source_id_reproduced_and_in_ledger(self, tmp_path):
        _write_geo(tmp_path)
        result = ingest_primary(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        assert result.source_id == _PRIMARY_SOURCE_ID
        source_csv = (tmp_path / "datasets/data/entities/source.csv").read_text(encoding="utf-8")
        assert _PRIMARY_SOURCE_ID in source_csv

    def test_catalogue_rows_upserted(self, tmp_path):
        _write_geo(tmp_path)
        ingest_primary(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        variables = (tmp_path / "datasets/data/variables.csv").read_text(encoding="utf-8")
        concepts = (tmp_path / "datasets/data/concepts.csv").read_text(encoding="utf-8")
        assert "primary-energy-supply-mtoe" in variables
        assert "primary-energy-supply" in concepts
        assert "mtoe" in variables
        assert "country" in variables

    def test_datapoints_pass_validator(self, tmp_path):
        _write_geo(tmp_path)
        ingest_primary(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        validate_csv(
            path=tmp_path / _PRIMARY_OUT,
            file_class=PRIMARY_ENERGY_SPEC.file_class,
            repo_root=tmp_path,
        )

    def test_idempotent_second_run_is_noop(self, tmp_path):
        _write_geo(tmp_path)
        staging = _stage(tmp_path)
        ingest_primary(repo_root=tmp_path, staging_dir=staging)
        out = tmp_path / _PRIMARY_OUT
        first_bytes = out.read_bytes()
        first_mtime = out.stat().st_mtime_ns
        ingest_primary(repo_root=tmp_path, staging_dir=staging)
        assert out.read_bytes() == first_bytes
        assert out.stat().st_mtime_ns == first_mtime

    def test_missing_staged_feed_raises(self, tmp_path):
        _write_geo(tmp_path)
        empty = tmp_path / "empty"
        empty.mkdir()
        with pytest.raises(FileNotFoundError, match="staged feed not found"):
            ingest_primary(repo_root=tmp_path, staging_dir=empty)


# --------------------------------------------------------------------------- #
# Full ingest - final consumption (2-D faceted)
# --------------------------------------------------------------------------- #


class TestIngestFinal:
    def test_emits_two_axis_file_with_header(self, tmp_path):
        _write_geo(tmp_path)
        result = ingest_final(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        assert result.output_path.exists()
        header = result.output_path.read_text(encoding="utf-8").splitlines()[0]
        assert header == "entity_id,time,sector,fuel,value,source_id"
        assert result.row_count == len(_FINAL_ROWS)

    def test_values_and_entity_in(self, tmp_path):
        _write_geo(tmp_path)
        ingest_final(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        got = _read_final(tmp_path / _FINAL_OUT)
        assert got[("IN", 2005, "industry", "coal")] == 90.1
        assert got[("IN", 2005, "transport", "oil")] == 50.0
        assert all(entity == "IN" for entity, _, _, _ in got)

    def test_source_id_reproduced_and_in_ledger(self, tmp_path):
        _write_geo(tmp_path)
        result = ingest_final(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        assert result.source_id == _FINAL_SOURCE_ID
        source_csv = (tmp_path / "datasets/data/entities/source.csv").read_text(encoding="utf-8")
        assert _FINAL_SOURCE_ID in source_csv

    def test_catalogue_rows_upserted(self, tmp_path):
        _write_geo(tmp_path)
        ingest_final(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        variables = (tmp_path / "datasets/data/variables.csv").read_text(encoding="utf-8")
        concepts = (tmp_path / "datasets/data/concepts.csv").read_text(encoding="utf-8")
        assert "final-energy-consumption-mtoe" in variables
        assert "final-energy-consumption" in concepts

    def test_two_dimensional_class_validates(self, tmp_path):
        # The task's explicit gate: the new 2-D geo_by_sector_fuel class must
        # validate (composite PK entity_id,time,sector,fuel; FK closure).
        _write_geo(tmp_path)
        ingest_final(repo_root=tmp_path, staging_dir=_stage(tmp_path))
        validate_csv(
            path=tmp_path / _FINAL_OUT,
            file_class=FINAL_ENERGY_SPEC.file_class,
            repo_root=tmp_path,
        )

    def test_idempotent_second_run_is_noop(self, tmp_path):
        _write_geo(tmp_path)
        staging = _stage(tmp_path)
        ingest_final(repo_root=tmp_path, staging_dir=staging)
        out = tmp_path / _FINAL_OUT
        first_bytes = out.read_bytes()
        ingest_final(repo_root=tmp_path, staging_dir=staging)
        assert out.read_bytes() == first_bytes
