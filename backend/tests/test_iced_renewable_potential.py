"""Contract tests for the ICED renewable-energy potential ingest.

No encrypted fixtures on disk: the synthetic feeds are PLAIN JSON. The real
``load_iced_response(..., decrypt=True)`` only AES-decrypts when the body is
a CryptoJS envelope (it starts with ``"U2FsdGVkX1``); a plain-JSON body is
parsed directly. So a staged plain-JSON ``{"status", "data"}`` envelope
exercises the real decrypt-or-parse path without mocking and without an AES
fixture (the documented "plain feed requested with decrypt=True" behaviour).

The full-ingest test stages the three feeds under ``tmp_path`` and asserts
the emitted datapoints CSVs (solar keeps @3% only, wind keeps @150m only, bio
sums both streams, the "Others" aggregate is dropped) plus the upserted
variables / concepts / source catalogue rows pass the canonical validator (no
real-corpus walk; CLAUDE anti-pattern).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from yen_gov.canonical.adapters.iced_renewable_potential import (
    SHIPPED_SPECS,
    RenewablePotentialShapeError,
    ingest,
    parse_potential_feed,
    spec_by_indicator_id,
)
from yen_gov.canonical.adapters.rbi_handbook import build_state_resolver
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
    "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:33,33,33\n"
    "andaman-and-nicobar,Andaman and Nicobar Islands,IN,state,IN-AN|U01|lgd:35,35,35\n"
)


def _write_geo(repo_root: Path) -> Path:
    geo = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    geo.parent.mkdir(parents=True, exist_ok=True)
    geo.write_text(_GEO_CSV, encoding="utf-8")
    return geo


def _resolver(tmp_path: Path):
    return build_state_resolver(_write_geo(tmp_path))


def _feed_bytes(rows: list[dict], *, status: str = "success") -> bytes:
    """Serialise a synthetic decrypted ICED envelope to plain-JSON bytes."""
    return json.dumps({"status": status, "data": rows}).encode("utf-8")


def _row(state: str, sub: str, capacity, *, region: str = "SR", year: str = "2025-26") -> dict:
    return {
        "region": region,
        "state": state,
        "source": "renewable",
        "subSource": sub,
        "sourceType": "renewable",
        "year": year,
        "capacity": capacity,
        "fyear": "2025-26-61",
    }


# Solar: two scenarios per state (keep @3% only); an "Others" aggregate row.
_SOLAR_ROWS = [
    _row("Andhra Pradesh", "solar @3% wasteland area", 38440),
    _row("Andhra Pradesh", "solar @6.69% wasteland", 85700),
    _row("Kerala", "solar @3% wasteland area", 6110),
    _row("Kerala", "solar @6.69% wasteland", 13600),
    _row("Others", "solar @3% wasteland area", 790, region="IN"),
]

# Wind: two hub heights per state (keep @150m only); no "Others" row.
_WIND_ROWS = [
    _row("Andhra Pradesh", "wind @120m agl", 74906),
    _row("Andhra Pradesh", "wind @150m agl", 123330),
    _row("Tamil Nadu", "wind @120m agl", 33800),
    _row("Tamil Nadu", "wind @150m agl", 68000),
]

# Bio: two additive streams per state (sum both); an "Others" aggregate row.
_BIO_ROWS = [
    _row("Andhra Pradesh", "biomass", 1999),
    _row("Andhra Pradesh", "cogeneration-bagasse", 300),
    _row("Andaman and Nicobar Islands", "biomass", 18, region="ER"),
    _row("Others", "cogeneration-bagasse", 284, region="IN"),
]


def _read_datapoints(path: Path) -> dict[tuple[str, int], float]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {
            (r["entity_id"], int(r["time"])): float(r["value"])
            for r in csv.DictReader(fh)
        }


# --------------------------------------------------------------------------- #
# Parser - filter / sum / drop
# --------------------------------------------------------------------------- #


class TestParse:
    def test_solar_keeps_only_3pct_scenario(self, tmp_path):
        rows, dropped = parse_potential_feed(
            _feed_bytes(_SOLAR_ROWS),
            spec_by_indicator_id("solar-potential-mw"),
            _resolver(tmp_path),
        )
        got = {(r.entity_id, r.time): r.value for r in rows}
        assert got == {("andhra-pradesh", 2025): 38440.0, ("kerala", 2025): 6110.0}
        # @6.69% scenario values must NOT appear.
        assert 85700.0 not in got.values()
        assert 13600.0 not in got.values()
        # The "Others" aggregate row (region=IN) is dropped and counted.
        assert dropped == 1

    def test_wind_keeps_only_150m_scenario(self, tmp_path):
        rows, dropped = parse_potential_feed(
            _feed_bytes(_WIND_ROWS),
            spec_by_indicator_id("wind-potential-mw"),
            _resolver(tmp_path),
        )
        got = {(r.entity_id, r.time): r.value for r in rows}
        assert got == {
            ("andhra-pradesh", 2025): 123330.0,
            ("tamil-nadu", 2025): 68000.0,
        }
        assert 74906.0 not in got.values()  # @120m must be dropped
        assert dropped == 0  # no aggregate rows in this feed

    def test_bio_sums_both_streams(self, tmp_path):
        rows, dropped = parse_potential_feed(
            _feed_bytes(_BIO_ROWS),
            spec_by_indicator_id("bio-energy-potential-mw"),
            _resolver(tmp_path),
        )
        got = {(r.entity_id, r.time): r.value for r in rows}
        # AP = biomass 1999 + cogeneration-bagasse 300 = 2299.
        assert got[("andhra-pradesh", 2025)] == 2299.0
        assert got[("andaman-and-nicobar", 2025)] == 18.0
        # "Others" cogeneration-bagasse aggregate dropped + counted.
        assert dropped == 1

    def test_time_is_fiscal_year_start(self, tmp_path):
        rows, _ = parse_potential_feed(
            _feed_bytes(_SOLAR_ROWS),
            spec_by_indicator_id("solar-potential-mw"),
            _resolver(tmp_path),
        )
        assert {r.time for r in rows} == {2025}

    def test_missing_subsource_raises(self, tmp_path):
        # A feed whose headline scenario was renamed upstream must fail loud,
        # never emit a partial/empty file.
        renamed = [_row("Andhra Pradesh", "solar @3.0% wasteland area", 38440)]
        with pytest.raises(RenewablePotentialShapeError, match="not present"):
            parse_potential_feed(
                _feed_bytes(renamed),
                spec_by_indicator_id("solar-potential-mw"),
                _resolver(tmp_path),
            )

    def test_sparse_capacity_skipped_not_dropped(self, tmp_path):
        rows, dropped = parse_potential_feed(
            _feed_bytes(
                [
                    _row("Andhra Pradesh", "solar @3% wasteland area", 38440),
                    _row("Kerala", "solar @3% wasteland area", "N.A."),
                ]
            ),
            spec_by_indicator_id("solar-potential-mw"),
            _resolver(tmp_path),
        )
        got = {r.entity_id for r in rows}
        assert got == {"andhra-pradesh"}  # Kerala N.A. cell carries no value
        assert dropped == 0  # an N.A. cell is not an aggregate drop

    def test_garbage_capacity_raises(self, tmp_path):
        with pytest.raises(RenewablePotentialShapeError, match="not a number"):
            parse_potential_feed(
                _feed_bytes([_row("Andhra Pradesh", "solar @3% wasteland area", "lots")]),
                spec_by_indicator_id("solar-potential-mw"),
                _resolver(tmp_path),
            )


# --------------------------------------------------------------------------- #
# Registry hygiene
# --------------------------------------------------------------------------- #


class TestRegistry:
    def test_ids_have_no_double_underscore_or_grain_prefix(self):
        for spec in SHIPPED_SPECS:
            assert "__" not in spec.indicator_id
            assert not spec.indicator_id.startswith(("state-", "district-", "national-"))

    def test_normalisation_and_unit(self):
        for spec in SHIPPED_SPECS:
            assert spec.normalisation == "absolute"
            assert spec.unit == "MW"
            assert spec.unit_canonical == "MW"
            assert spec.topic == "energy"

    def test_three_feeds_present(self):
        ids = {s.indicator_id for s in SHIPPED_SPECS}
        assert ids == {
            "solar-potential-mw",
            "wind-potential-mw",
            "bio-energy-potential-mw",
        }

    def test_bio_keeps_both_streams_others_keep_one(self):
        assert spec_by_indicator_id("bio-energy-potential-mw").keep_sub_sources == (
            "biomass",
            "cogeneration-bagasse",
        )
        assert spec_by_indicator_id("solar-potential-mw").keep_sub_sources == (
            "solar @3% wasteland area",
        )
        assert spec_by_indicator_id("wind-potential-mw").keep_sub_sources == (
            "wind @150m agl",
        )


# --------------------------------------------------------------------------- #
# Full ingest -> emitted corpus validates
# --------------------------------------------------------------------------- #


class TestIngest:
    def _stage(self, tmp_path: Path) -> Path:
        staging = tmp_path / "staging"
        staging.mkdir(parents=True, exist_ok=True)
        (staging / "solar_potential_by_state.json").write_bytes(_feed_bytes(_SOLAR_ROWS))
        (staging / "wind_potential_by_state.json").write_bytes(_feed_bytes(_WIND_ROWS))
        (staging / "bio_energy_potential_by_state.json").write_bytes(_feed_bytes(_BIO_ROWS))
        return staging

    def test_emits_three_datapoint_files(self, tmp_path):
        _write_geo(tmp_path)
        result = ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))

        assert len(result.feeds) == 3
        for feed in result.feeds:
            assert feed.output_path.exists()
            header = feed.output_path.read_text(encoding="utf-8").splitlines()[0]
            assert header == "entity_id,time,value,source_id"

    def test_solar_values_and_drop_count(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        out = tmp_path / "datasets/data/datapoints/geo/solar-potential-mw.csv"
        got = _read_datapoints(out)
        assert got == {("andhra-pradesh", 2025): 38440.0, ("kerala", 2025): 6110.0}

    def test_bio_summed_values(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        out = tmp_path / "datasets/data/datapoints/geo/bio-energy-potential-mw.csv"
        got = _read_datapoints(out)
        assert got[("andhra-pradesh", 2025)] == 2299.0
        assert got[("andaman-and-nicobar", 2025)] == 18.0

    def test_dropped_counts_reported(self, tmp_path):
        _write_geo(tmp_path)
        result = ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        by_id = {f.indicator_id: f for f in result.feeds}
        assert by_id["solar-potential-mw"].dropped_unresolved == 1
        assert by_id["wind-potential-mw"].dropped_unresolved == 0
        assert by_id["bio-energy-potential-mw"].dropped_unresolved == 1

    def test_no_india_row_emitted(self, tmp_path):
        # These feeds carry no all-India ("India"/"All India") row, only an
        # "Others" aggregate which is dropped; the result is purely state-grain.
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        for stem in ("solar-potential-mw", "wind-potential-mw", "bio-energy-potential-mw"):
            got = _read_datapoints(
                tmp_path / f"datasets/data/datapoints/geo/{stem}.csv"
            )
            assert all(entity != "IN" for entity, _ in got)

    def test_source_ids_are_derived(self, tmp_path):
        _write_geo(tmp_path)
        result = ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        source_csv = (tmp_path / "datasets/data/entities/source.csv").read_text(
            encoding="utf-8"
        )
        for feed in result.feeds:
            spec = spec_by_indicator_id(feed.indicator_id)
            expected = derive_source_id(
                spec.source_producer, spec.source_title, spec.source_vintage
            )
            assert feed.source_id == expected
            assert expected in source_csv

    def test_catalogue_rows_upserted(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        variables = (tmp_path / "datasets/data/variables.csv").read_text(encoding="utf-8")
        concepts = (tmp_path / "datasets/data/concepts.csv").read_text(encoding="utf-8")
        for indicator_id, concept_id in (
            ("solar-potential-mw", "solar-energy-potential"),
            ("wind-potential-mw", "wind-energy-potential"),
            ("bio-energy-potential-mw", "bio-energy-potential"),
        ):
            assert indicator_id in variables
            assert concept_id in concepts
        # entity_kinds + topic present on the variables rows.
        assert "country state" in variables
        assert "energy" in variables

    def test_emitted_datapoints_pass_validator(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        # FK targets (geo.csv + source.csv) + variables.csv all exist in
        # tmp_path; the validator must accept every emitted file (FK closure).
        for stem in ("solar-potential-mw", "wind-potential-mw", "bio-energy-potential-mw"):
            validate_csv(
                path=tmp_path / f"datasets/data/datapoints/geo/{stem}.csv",
                file_class="datasets/data/datapoints/geo/*.csv",
                repo_root=tmp_path,
            )

    def test_idempotent_second_run_is_noop(self, tmp_path):
        _write_geo(tmp_path)
        staging = self._stage(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=staging)
        out = tmp_path / "datasets/data/datapoints/geo/solar-potential-mw.csv"
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
