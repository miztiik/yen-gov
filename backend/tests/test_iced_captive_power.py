"""Contract tests for the ICED captive-power ingest.

No encrypted fixtures on disk: the synthetic feeds are PLAIN JSON. The real
``load_iced_response(..., decrypt=True)`` only AES-decrypts when the body is a
CryptoJS envelope (it starts with ``"U2FsdGVkX1``); a plain-JSON body is parsed
directly. So a staged plain-JSON ``{"status", "data"}`` envelope exercises the
real decrypt-or-parse path without mocking and without an AES fixture.

The full-ingest test stages the single captive feed under ``tmp_path`` and
asserts the two emitted datapoints CSVs (capacity + generation, each summed
over industries, the all-India aggregate dropped, the combined
"Jammu and Kashmir and Ladakh" label dropped, the national fuel-mix
"sourceWise" rows ignored, null cells skipped) plus the upserted variables /
concepts / source catalogue rows pass the canonical validator (no real-corpus
walk; CLAUDE anti-pattern).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from yen_gov.canonical.adapters.iced_captive_power import (
    SHIPPED_SPECS,
    CaptivePowerShapeError,
    ingest,
    parse_captive_feed,
    spec_by_indicator_id,
)
from yen_gov.canonical.adapters.rbi_handbook import build_state_resolver
from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

# Includes separate jammu-and-kashmir + ladakh entities (the post-2019 split)
# so the test proves the feed's COMBINED "Jammu and Kashmir and Ladakh" label
# still does not resolve and is honestly dropped + reported.
_GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
    "andhra-pradesh,Andhra Pradesh,IN,state,IN-AP|S01|lgd:28,28,28\n"
    "kerala,Kerala,IN,state,IN-KL|S11|lgd:32,32,32\n"
    "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:33,33,33\n"
    "jammu-and-kashmir,Jammu & Kashmir,IN,state,IN-JK|U08|lgd:1|Jammu And Kashmir,1,1\n"
    "ladakh,Ladakh,IN,state,IN-LA|U09|lgd:37,,\n"
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


def _sw(year: str, state: str, industry: str, capacity, generation) -> dict:
    """A `dataFor == "stateWise"` row (the shape the parser reads)."""
    return {
        "year": year,
        "state": state,
        "industry": industry,
        "capacity": capacity,
        "generation": generation,
        "dataFor": "stateWise",
    }


def _so(year: str, industry: str, source: dict, data_of: str) -> dict:
    """A `dataFor == "sourceWise"` national fuel-mix row (must be ignored)."""
    return {
        "industry": industry,
        "year": year,
        "source": source,
        "dataFor": "sourceWise",
        "dataOf": data_of,
    }


# Two industries per (state, year) prove the sum; Kerala carries a null cell in
# each measure (skipped, not zeroed); an "All India" aggregate row (dropped),
# a combined "Jammu and Kashmir and Ladakh" row (unresolved -> dropped), and a
# "sourceWise" national fuel-mix row (ignored).
_CAPTIVE_ROWS = [
    _sw("2005-06", "Andhra Pradesh", "Aluminium", 100, 600),
    _sw("2005-06", "Andhra Pradesh", "Cement", 50, 300),
    _sw("2006-07", "Andhra Pradesh", "Aluminium", 120, 700),
    _sw("2006-07", "Andhra Pradesh", "Cement", 60, 320),
    _sw("2005-06", "Kerala", "Aluminium", None, 40),   # capacity null -> skip
    _sw("2005-06", "Kerala", "Cement", 20, None),       # generation null -> skip
    _sw("2005-06", "All India", "Aluminium", 9999, 99999),  # aggregate -> drop
    _sw("2005-06", "Jammu and Kashmir and Ladakh", "Cement", 7, 8),  # unresolved
    _so("2005-06", "Aluminium", {"coal": 80, "gas": 20}, "capacity"),  # ignored
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
    def test_capacity_sums_industries_per_state_year(self, tmp_path):
        rows, report = parse_captive_feed(
            _feed_bytes(_CAPTIVE_ROWS),
            spec_by_indicator_id("captive-power-capacity-mw"),
            _resolver(tmp_path),
        )
        got = {(r.entity_id, r.time): r.value for r in rows}
        assert got == {
            ("andhra-pradesh", 2005): 150.0,   # 100 + 50
            ("andhra-pradesh", 2006): 180.0,   # 120 + 60
            ("kerala", 2005): 20.0,            # Aluminium null skipped, Cement 20
        }
        assert report.aggregate_labels == ("All India",)
        assert report.unresolved_labels == ("Jammu and Kashmir and Ladakh",)

    def test_generation_sums_industries_per_state_year(self, tmp_path):
        rows, report = parse_captive_feed(
            _feed_bytes(_CAPTIVE_ROWS),
            spec_by_indicator_id("captive-power-generation-gwh"),
            _resolver(tmp_path),
        )
        got = {(r.entity_id, r.time): r.value for r in rows}
        assert got == {
            ("andhra-pradesh", 2005): 900.0,   # 600 + 300
            ("andhra-pradesh", 2006): 1020.0,  # 700 + 320
            ("kerala", 2005): 40.0,            # Aluminium 40, Cement null skipped
        }

    def test_all_india_aggregate_dropped_not_emitted(self, tmp_path):
        rows, report = parse_captive_feed(
            _feed_bytes(_CAPTIVE_ROWS),
            spec_by_indicator_id("captive-power-capacity-mw"),
            _resolver(tmp_path),
        )
        assert all(r.entity_id != "IN" for r in rows)
        # The 9999 aggregate value must NOT appear anywhere.
        assert 9999.0 not in {r.value for r in rows}
        assert report.aggregate_labels == ("All India",)

    def test_combined_jk_ladakh_label_unresolved_and_reported(self, tmp_path):
        rows, report = parse_captive_feed(
            _feed_bytes(_CAPTIVE_ROWS),
            spec_by_indicator_id("captive-power-capacity-mw"),
            _resolver(tmp_path),
        )
        # 7 (the J&K+Ladakh Cement capacity) must not be summed into any state.
        assert 7.0 not in {r.value for r in rows}
        assert report.unresolved_labels == ("Jammu and Kashmir and Ladakh",)

    def test_sourcewise_rows_ignored(self, tmp_path):
        # A feed whose ONLY non-aggregate data is sourceWise has no stateWise
        # observation at all -> shape error (never emit empty).
        with pytest.raises(CaptivePowerShapeError, match="no 'stateWise' rows"):
            parse_captive_feed(
                _feed_bytes(
                    [_so("2005-06", "Aluminium", {"coal": 80, "gas": 20}, "capacity")]
                ),
                spec_by_indicator_id("captive-power-capacity-mw"),
                _resolver(tmp_path),
            )

    def test_time_is_fiscal_year_start(self, tmp_path):
        rows, _ = parse_captive_feed(
            _feed_bytes(_CAPTIVE_ROWS),
            spec_by_indicator_id("captive-power-capacity-mw"),
            _resolver(tmp_path),
        )
        assert {r.time for r in rows} == {2005, 2006}

    def test_all_cells_non_state_raises(self, tmp_path):
        # stateWise rows present, but every one is an aggregate / unresolved
        # label -> no observation -> shape error.
        only_dropped = [
            _sw("2005-06", "All India", "Aluminium", 9999, 99999),
            _sw("2005-06", "Jammu and Kashmir and Ladakh", "Cement", 7, 8),
        ]
        with pytest.raises(CaptivePowerShapeError, match="no observation"):
            parse_captive_feed(
                _feed_bytes(only_dropped),
                spec_by_indicator_id("captive-power-capacity-mw"),
                _resolver(tmp_path),
            )

    def test_garbage_measure_raises(self, tmp_path):
        with pytest.raises(CaptivePowerShapeError, match="not a number"):
            parse_captive_feed(
                _feed_bytes([_sw("2005-06", "Andhra Pradesh", "Cement", "lots", 1)]),
                spec_by_indicator_id("captive-power-capacity-mw"),
                _resolver(tmp_path),
            )

    def test_na_marker_measure_skipped_not_dropped(self, tmp_path):
        rows, report = parse_captive_feed(
            _feed_bytes(
                [
                    _sw("2005-06", "Andhra Pradesh", "Aluminium", 100, 600),
                    _sw("2005-06", "Kerala", "Aluminium", "N.A.", 600),
                ]
            ),
            spec_by_indicator_id("captive-power-capacity-mw"),
            _resolver(tmp_path),
        )
        got = {r.entity_id for r in rows}
        assert got == {"andhra-pradesh"}  # Kerala N.A. capacity carries no value
        assert report.unresolved_labels == ()  # an N.A. cell is not a label drop


# --------------------------------------------------------------------------- #
# Registry hygiene
# --------------------------------------------------------------------------- #


class TestRegistry:
    def test_ids_have_no_double_underscore_or_grain_prefix(self):
        for spec in SHIPPED_SPECS:
            assert "__" not in spec.indicator_id
            assert not spec.indicator_id.startswith(("state-", "district-", "national-"))

    def test_two_measures_present(self):
        ids = {s.indicator_id for s in SHIPPED_SPECS}
        assert ids == {"captive-power-capacity-mw", "captive-power-generation-gwh"}

    def test_normalisation_topic_entity_kinds(self):
        for spec in SHIPPED_SPECS:
            assert spec.normalisation == "absolute"
            assert spec.topic == "energy"
            assert spec.entity_kinds == "state"

    def test_units_and_measures(self):
        cap = spec_by_indicator_id("captive-power-capacity-mw")
        gen = spec_by_indicator_id("captive-power-generation-gwh")
        assert (cap.unit, cap.unit_canonical, cap.measure) == ("MW", "MW", "capacity")
        assert (gen.unit, gen.unit_canonical, gen.measure) == ("GWh", "GWh", "generation")

    def test_both_measures_share_one_source_triple(self):
        cap = spec_by_indicator_id("captive-power-capacity-mw")
        gen = spec_by_indicator_id("captive-power-generation-gwh")
        assert (cap.source_producer, cap.source_title, cap.source_vintage) == (
            gen.source_producer,
            gen.source_title,
            gen.source_vintage,
        )
        assert cap.staging_filename == gen.staging_filename


# --------------------------------------------------------------------------- #
# Full ingest -> emitted corpus validates
# --------------------------------------------------------------------------- #


class TestIngest:
    def _stage(self, tmp_path: Path) -> Path:
        staging = tmp_path / "staging"
        staging.mkdir(parents=True, exist_ok=True)
        (staging / "captive_power_industry.json").write_bytes(_feed_bytes(_CAPTIVE_ROWS))
        return staging

    def test_emits_two_datapoint_files(self, tmp_path):
        _write_geo(tmp_path)
        result = ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))

        assert len(result.indicators) == 2
        for ind in result.indicators:
            assert ind.output_path.exists()
            header = ind.output_path.read_text(encoding="utf-8").splitlines()[0]
            assert header == "entity_id,time,value,source_id"

    def test_capacity_values(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        out = tmp_path / "datasets/data/datapoints/geo/captive-power-capacity-mw.csv"
        got = _read_datapoints(out)
        assert got == {
            ("andhra-pradesh", 2005): 150.0,
            ("andhra-pradesh", 2006): 180.0,
            ("kerala", 2005): 20.0,
        }

    def test_generation_values(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        out = tmp_path / "datasets/data/datapoints/geo/captive-power-generation-gwh.csv"
        got = _read_datapoints(out)
        assert got == {
            ("andhra-pradesh", 2005): 900.0,
            ("andhra-pradesh", 2006): 1020.0,
            ("kerala", 2005): 40.0,
        }

    def test_no_country_or_unresolved_row_emitted(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        for stem in ("captive-power-capacity-mw", "captive-power-generation-gwh"):
            got = _read_datapoints(
                tmp_path / f"datasets/data/datapoints/geo/{stem}.csv"
            )
            assert all(entity not in {"IN", "jammu-and-kashmir", "ladakh"} for entity, _ in got)

    def test_drop_reports(self, tmp_path):
        _write_geo(tmp_path)
        result = ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        for ind in result.indicators:
            assert ind.drop_report.aggregate_labels == ("All India",)
            assert ind.drop_report.unresolved_labels == ("Jammu and Kashmir and Ladakh",)

    def test_source_ids_are_derived_and_shared(self, tmp_path):
        _write_geo(tmp_path)
        result = ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        expected = derive_source_id(
            "NITI Aayog India Climate & Energy Dashboard",
            "Captive Power (industry-wise) State-wise API",
            "2024-25",
        )
        # Both measures share ONE derived source_id.
        assert {ind.source_id for ind in result.indicators} == {expected}
        source_csv = (tmp_path / "datasets/data/entities/source.csv").read_text(
            encoding="utf-8"
        )
        # ... and the citation ledger carries exactly ONE row for the pair.
        assert source_csv.count(expected) == 1

    def test_catalogue_rows_upserted(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        variables = (tmp_path / "datasets/data/variables.csv").read_text(encoding="utf-8")
        concepts = (tmp_path / "datasets/data/concepts.csv").read_text(encoding="utf-8")
        for indicator_id, concept_id in (
            ("captive-power-capacity-mw", "captive-power-capacity"),
            ("captive-power-generation-gwh", "captive-power-generation"),
        ):
            assert indicator_id in variables
            assert concept_id in concepts
        # entity_kinds + topic present on the variables rows.
        assert "state" in variables
        assert "energy" in variables

    def test_emitted_datapoints_pass_validator(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        # FK targets (geo.csv + source.csv) + variables.csv all exist in
        # tmp_path; the validator must accept every emitted file (FK closure +
        # filename == indicator_id).
        for stem in ("captive-power-capacity-mw", "captive-power-generation-gwh"):
            validate_csv(
                path=tmp_path / f"datasets/data/datapoints/geo/{stem}.csv",
                file_class="datasets/data/datapoints/geo/*.csv",
                repo_root=tmp_path,
            )

    def test_idempotent_second_run_is_noop(self, tmp_path):
        _write_geo(tmp_path)
        staging = self._stage(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=staging)
        out = tmp_path / "datasets/data/datapoints/geo/captive-power-capacity-mw.csv"
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
