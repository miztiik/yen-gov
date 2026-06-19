"""Contract tests for the ICED ICE-vs-EV (VAHAN) EV-share ingest.

No encrypted fixtures on disk: the synthetic feed is PLAIN JSON. The real
``load_iced_response(..., decrypt=True)`` only AES-decrypts when the body is a
CryptoJS envelope (it starts with ``"U2FsdGVkX1``); a plain-JSON body is parsed
directly. So a staged plain-JSON ``{"status", "data": {"iceEvData": [...],
"populationData": [...]}}`` envelope exercises the real decrypt-or-parse path
without mocking and without an AES fixture.

The full-ingest test stages the feed under ``tmp_path`` and asserts the emitted
datapoints CSV (the per-(state, year) EV share, with the populationData block
ignored, the unresolved "Others" label dropped, and the zero-total cell
dropped) plus the upserted variables / concepts / source catalogue rows pass
the canonical validator (no real-corpus walk; CLAUDE anti-pattern).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from yen_gov.canonical.adapters.iced_ev_share import (
    SHIPPED_SPECS,
    EvShareShapeError,
    ingest,
    parse_ev_share_feed,
    spec_by_indicator_id,
)
from yen_gov.canonical.adapters.rbi_handbook import build_state_resolver
from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv

_INDICATOR_ID = "ev-share-of-registrations-pct"

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

_GEO_CSV = (
    "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
    "IN,India,,country,IN|IND|356,,\n"
    "andhra-pradesh,Andhra Pradesh,IN,state,IN-AP|S01|lgd:28,28,28\n"
    "kerala,Kerala,IN,state,IN-KL|S11|lgd:32,32,32\n"
    "tamil-nadu,Tamil Nadu,IN,state,IN-TN|S22|lgd:33,33,33\n"
)


def _write_geo(repo_root: Path) -> Path:
    geo = repo_root / "datasets" / "data" / "entities" / "geo.csv"
    geo.parent.mkdir(parents=True, exist_ok=True)
    geo.write_text(_GEO_CSV, encoding="utf-8")
    return geo


def _resolver(tmp_path: Path):
    return build_state_resolver(_write_geo(tmp_path))


def _ev_row(state, vehicle, fuel, value, *, year, broad="2 Wheeler") -> dict:
    return {
        "state": state,
        "vehicleCategory": vehicle,
        "broadCategory": broad,
        "year": year,
        "fuelCategory": fuel,
        "value": value,
    }


# Synthetic iceEvData: 3 resolvable states + an unresolved "Others" aggregate,
# 2+ years, electric + non-electric fuelCategory across 2+ vehicleCategory.
_ICE_EV_ROWS = [
    # Andhra Pradesh 2022-23: EV 100 / total 500 = 20.0 %
    _ev_row("Andhra Pradesh", "TWO WHEELER(NT)", "Electric Vehicle", 100, year="2022-23"),
    _ev_row("Andhra Pradesh", "TWO WHEELER(NT)", "Petrol & Others", 300, year="2022-23"),
    _ev_row("Andhra Pradesh", "LIGHT MOTOR VEHICLE", "Electric Vehicle", 0, year="2022-23", broad="LMV"),
    _ev_row("Andhra Pradesh", "LIGHT MOTOR VEHICLE", "Diesel & Others", 100, year="2022-23", broad="LMV"),
    # Andhra Pradesh 2023-24: EV (150+50) / total 400 = 50.0 %
    _ev_row("Andhra Pradesh", "TWO WHEELER(NT)", "Electric Vehicle", 150, year="2023-24"),
    _ev_row("Andhra Pradesh", "TWO WHEELER(NT)", "Petrol & Others", 150, year="2023-24"),
    _ev_row("Andhra Pradesh", "THREE WHEELER(T)", "Electric Vehicle", 50, year="2023-24", broad="3 Wheeler"),
    _ev_row("Andhra Pradesh", "THREE WHEELER(T)", "CNG", 50, year="2023-24", broad="3 Wheeler"),
    # Andhra Pradesh 2024-25: explicit zero total -> dropped (zero-total cell)
    _ev_row("Andhra Pradesh", "TWO WHEELER(NT)", "Electric Vehicle", 0, year="2024-25"),
    _ev_row("Andhra Pradesh", "TWO WHEELER(NT)", "Petrol & Others", 0, year="2024-25"),
    # Kerala 2022-23: EV 30 / total 100 = 30.0 %
    _ev_row("Kerala", "TWO WHEELER(NT)", "Electric Vehicle", 30, year="2022-23"),
    _ev_row("Kerala", "TWO WHEELER(NT)", "Petrol & Others", 70, year="2022-23"),
    # Kerala 2023-24: EV 25 / total 100 = 25.0 %
    _ev_row("Kerala", "LIGHT MOTOR VEHICLE", "Electric Vehicle", 25, year="2023-24", broad="LMV"),
    _ev_row("Kerala", "LIGHT MOTOR VEHICLE", "Diesel & Others", 75, year="2023-24", broad="LMV"),
    # Kerala 2024-25: all N.A. -> skipped, key never created (no row at all)
    _ev_row("Kerala", "TWO WHEELER(NT)", "Electric Vehicle", "N.A.", year="2024-25"),
    _ev_row("Kerala", "TWO WHEELER(NT)", "Petrol & Others", "N.A.", year="2024-25"),
    # Tamil Nadu 2023-24: EV 1 / total 3 = 33.333333 % (rounding case)
    _ev_row("Tamil Nadu", "TWO WHEELER(NT)", "Electric Vehicle", 1, year="2023-24"),
    _ev_row("Tamil Nadu", "TWO WHEELER(NT)", "Petrol & Others", 2, year="2023-24"),
    # "Others" aggregate across 2 years -> unresolved, counted ONCE (distinct label)
    _ev_row("Others", "TWO WHEELER(NT)", "Electric Vehicle", 5, year="2022-23"),
    _ev_row("Others", "TWO WHEELER(NT)", "Petrol & Others", 95, year="2022-23"),
    _ev_row("Others", "TWO WHEELER(NT)", "Electric Vehicle", 9, year="2023-24"),
    _ev_row("Others", "TWO WHEELER(NT)", "Petrol & Others", 91, year="2023-24"),
]

# populationData: large magnitudes that would visibly corrupt any output if the
# parser accidentally summed them. The parser must DROP this block entirely.
_POPULATION_ROWS = [
    {"state": "Andhra Pradesh", "year": "2022-23", "value": 99999999},
    {"state": "Kerala", "year": "2023-24", "value": 88888888},
    {"state": "Tamil Nadu", "year": "2023-24", "value": 77777777},
]

# Hand-computed expected EV shares (entity_id, fy-start year) -> percent.
_EXPECTED_SHARES = {
    ("andhra-pradesh", 2022): 20.0,
    ("andhra-pradesh", 2023): 50.0,
    ("kerala", 2022): 30.0,
    ("kerala", 2023): 25.0,
    ("tamil-nadu", 2023): 33.333333,
}


def _feed_bytes(ice_ev: list[dict], population=None, *, status: str = "success") -> bytes:
    """Serialise a synthetic decrypted ICED EV/VAHAN envelope to plain JSON."""
    return json.dumps(
        {
            "status": status,
            "data": {
                "iceEvData": ice_ev,
                "populationData": population if population is not None else [],
            },
        }
    ).encode("utf-8")


def _read_datapoints(path: Path) -> dict[tuple[str, int], float]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {
            (r["entity_id"], int(r["time"])): float(r["value"])
            for r in csv.DictReader(fh)
        }


# --------------------------------------------------------------------------- #
# Parser - accumulate / ratio / drop
# --------------------------------------------------------------------------- #


class TestParse:
    def test_share_values_and_unresolved_drop(self, tmp_path):
        rows, dropped = parse_ev_share_feed(
            _feed_bytes(_ICE_EV_ROWS, _POPULATION_ROWS),
            spec_by_indicator_id(_INDICATOR_ID),
            _resolver(tmp_path),
        )
        got = {(r.entity_id, r.time): r.value for r in rows}
        assert got[("andhra-pradesh", 2022)] == 20.0
        assert got[("andhra-pradesh", 2023)] == 50.0
        assert got[("kerala", 2022)] == 30.0
        assert got[("kerala", 2023)] == 25.0
        # The unresolved "Others" aggregate is counted ONCE (distinct label),
        # not once per row/year.
        assert dropped == 1

    def test_population_data_is_ignored(self, tmp_path):
        rows, _ = parse_ev_share_feed(
            _feed_bytes(_ICE_EV_ROWS, _POPULATION_ROWS),
            spec_by_indicator_id(_INDICATOR_ID),
            _resolver(tmp_path),
        )
        # No share exceeds 100; the 8-digit population magnitudes never leak in.
        assert all(0.0 <= r.value <= 100.0 for r in rows)
        assert {(r.entity_id, r.time): r.value for r in rows} == _EXPECTED_SHARES

    def test_zero_total_cell_dropped(self, tmp_path):
        rows, _ = parse_ev_share_feed(
            _feed_bytes(_ICE_EV_ROWS),
            spec_by_indicator_id(_INDICATOR_ID),
            _resolver(tmp_path),
        )
        got = {(r.entity_id, r.time) for r in rows}
        # AP 2024-25 has an explicit 0 total -> no defined share -> dropped.
        assert ("andhra-pradesh", 2024) not in got

    def test_na_cell_never_keyed(self, tmp_path):
        rows, _ = parse_ev_share_feed(
            _feed_bytes(_ICE_EV_ROWS),
            spec_by_indicator_id(_INDICATOR_ID),
            _resolver(tmp_path),
        )
        got = {(r.entity_id, r.time) for r in rows}
        # Kerala 2024-25 is all N.A. -> skipped, key never created.
        assert ("kerala", 2024) not in got

    def test_rounding_of_non_terminating_share(self, tmp_path):
        rows, _ = parse_ev_share_feed(
            _feed_bytes(_ICE_EV_ROWS),
            spec_by_indicator_id(_INDICATOR_ID),
            _resolver(tmp_path),
        )
        got = {(r.entity_id, r.time): r.value for r in rows}
        # 1/3 -> 33.3333...% rounded to 6 dp.
        assert got[("tamil-nadu", 2023)] == pytest.approx(33.333333, abs=1e-9)

    def test_time_is_fiscal_year_start(self, tmp_path):
        rows, _ = parse_ev_share_feed(
            _feed_bytes(_ICE_EV_ROWS),
            spec_by_indicator_id(_INDICATOR_ID),
            _resolver(tmp_path),
        )
        assert {r.time for r in rows} == {2022, 2023}

    def test_missing_electric_bucket_raises(self, tmp_path):
        # A feed whose electric bucket was renamed upstream must fail loud,
        # never emit an all-zero EV share.
        no_ev = [
            _ev_row("Andhra Pradesh", "TWO WHEELER(NT)", "Petrol & Others", 300, year="2023-24"),
            _ev_row("Kerala", "LIGHT MOTOR VEHICLE", "Diesel & Others", 100, year="2023-24"),
        ]
        with pytest.raises(EvShareShapeError, match="electric"):
            parse_ev_share_feed(
                _feed_bytes(no_ev),
                spec_by_indicator_id(_INDICATOR_ID),
                _resolver(tmp_path),
            )

    def test_garbage_value_raises(self, tmp_path):
        with pytest.raises(EvShareShapeError, match="not a number"):
            parse_ev_share_feed(
                _feed_bytes(
                    [_ev_row("Andhra Pradesh", "TWO WHEELER(NT)", "Electric Vehicle", "lots", year="2023-24")]
                ),
                spec_by_indicator_id(_INDICATOR_ID),
                _resolver(tmp_path),
            )

    def test_old_list_shaped_data_raises(self, tmp_path):
        # The renewable feeds carry data as a LIST; this feed must carry a DICT
        # with iceEvData. A list-shaped data must fail loud.
        body = json.dumps({"status": "success", "data": [{"x": 1}]}).encode("utf-8")
        with pytest.raises(EvShareShapeError, match="iceEvData"):
            parse_ev_share_feed(
                body, spec_by_indicator_id(_INDICATOR_ID), _resolver(tmp_path)
            )


# --------------------------------------------------------------------------- #
# Registry hygiene
# --------------------------------------------------------------------------- #


class TestRegistry:
    def test_id_has_no_double_underscore_or_grain_prefix(self):
        for spec in SHIPPED_SPECS:
            assert "__" not in spec.indicator_id
            assert not spec.indicator_id.startswith(("state-", "district-", "national-"))

    def test_normalisation_unit_topic(self):
        spec = spec_by_indicator_id(_INDICATOR_ID)
        assert spec.normalisation == "share"
        assert spec.unit == "%"
        assert spec.unit_canonical == "%"
        assert spec.topic == "energy"
        assert spec.entity_kinds == "state"

    def test_one_feed_present(self):
        assert {s.indicator_id for s in SHIPPED_SPECS} == {_INDICATOR_ID}

    def test_electric_bucket(self):
        assert spec_by_indicator_id(_INDICATOR_ID).electric_fuel_categories == (
            "Electric Vehicle",
        )


# --------------------------------------------------------------------------- #
# Full ingest -> emitted corpus validates
# --------------------------------------------------------------------------- #


class TestIngest:
    def _stage(self, tmp_path: Path) -> Path:
        staging = tmp_path / "staging"
        staging.mkdir(parents=True, exist_ok=True)
        (staging / "ice_ev_vahan.json").write_bytes(
            _feed_bytes(_ICE_EV_ROWS, _POPULATION_ROWS)
        )
        return staging

    def test_emits_one_datapoint_file(self, tmp_path):
        _write_geo(tmp_path)
        result = ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))

        assert len(result.feeds) == 1
        feed = result.feeds[0]
        assert feed.indicator_id == _INDICATOR_ID
        assert feed.output_path.exists()
        header = feed.output_path.read_text(encoding="utf-8").splitlines()[0]
        assert header == "entity_id,time,value,source_id"
        assert feed.row_count == 5
        assert feed.entity_count == 3
        assert (feed.time_min, feed.time_max) == (2022, 2023)

    def test_share_values(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        out = tmp_path / f"datasets/data/datapoints/geo/{_INDICATOR_ID}.csv"
        got = _read_datapoints(out)
        assert got[("andhra-pradesh", 2022)] == 20.0
        assert got[("andhra-pradesh", 2023)] == 50.0
        assert got[("kerala", 2022)] == 30.0
        assert got[("kerala", 2023)] == 25.0
        assert got[("tamil-nadu", 2023)] == pytest.approx(33.333333, abs=1e-9)

    def test_population_block_not_in_output(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        out = tmp_path / f"datasets/data/datapoints/geo/{_INDICATOR_ID}.csv"
        got = _read_datapoints(out)
        assert got == _EXPECTED_SHARES  # exact set; no population magnitudes

    def test_dropped_count_reported(self, tmp_path):
        _write_geo(tmp_path)
        result = ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        assert result.feeds[0].dropped_unresolved == 1

    def test_source_id_is_derived(self, tmp_path):
        _write_geo(tmp_path)
        result = ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        feed = result.feeds[0]
        spec = spec_by_indicator_id(_INDICATOR_ID)
        expected = derive_source_id(
            spec.source_producer, spec.source_title, spec.source_vintage
        )
        # D2 (ingest plan Row 10/11): the producer is the MoRTH issuing
        # authority (a passthrough) and the ICED access surface moves into the
        # title; the corrected source_id is what is now on disk.
        assert expected == derive_source_id(
            "Ministry of Road Transport and Highways",
            "ICE vs EV (VAHAN) State-wise API"
            " [republished via NITI Aayog India Climate & Energy Dashboard]",
            "2024-25",
        )
        assert feed.source_id == expected
        source_csv = (tmp_path / "datasets/data/entities/source.csv").read_text(
            encoding="utf-8"
        )
        assert expected in source_csv

    def test_catalogue_rows_upserted(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        variables = (tmp_path / "datasets/data/variables.csv").read_text(encoding="utf-8")
        concepts = (tmp_path / "datasets/data/concepts.csv").read_text(encoding="utf-8")
        assert _INDICATOR_ID in variables
        assert "ev-registration-share" in concepts
        assert "energy" in variables  # topic
        # entity_kinds is state-grain on both catalogue rows.
        assert "state" in variables
        assert "share" in concepts  # normalisation

    def test_emitted_datapoints_pass_validator(self, tmp_path):
        _write_geo(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=self._stage(tmp_path))
        # FK targets (geo.csv + source.csv) + variables.csv all exist in
        # tmp_path; the validator must accept the emitted file (FK closure +
        # filename == indicator_id).
        validate_csv(
            path=tmp_path / f"datasets/data/datapoints/geo/{_INDICATOR_ID}.csv",
            file_class="datasets/data/datapoints/geo/*.csv",
            repo_root=tmp_path,
        )

    def test_idempotent_second_run_is_noop(self, tmp_path):
        _write_geo(tmp_path)
        staging = self._stage(tmp_path)
        ingest(repo_root=tmp_path, staging_dir=staging)
        out = tmp_path / f"datasets/data/datapoints/geo/{_INDICATOR_ID}.csv"
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
