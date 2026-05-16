"""Pure-parser tests for the ICED aqi-map-markers (state-year PM2.5).

Tests run against the captured 2026-05-15 markers fixture (8,453 station-
year rows). No network, no decryption, no I/O — feed dict in, list of
:class:`StateYearMean` out.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

from yen_gov.sources.iced_air_quality.markers_parsers import (
    COVID_GAP_YEAR,
    NO2_FIELD,
    PM10_FIELD,
    PM25_FIELD,
    SO2_FIELD,
    aggregate_state_year_mean,
    emit_indicator_rows,
)
from yen_gov.sources.iced_common import ICEDShapeError

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "iced_air_quality"
    / "aq_aqi_map_markers_2026-05-15.json"
)


@pytest.fixture(scope="module")
def markers() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Outer envelope
# ---------------------------------------------------------------------------

def test_outer_envelope_shape(markers: dict) -> None:
    """Snapshot has the expected {data: [...]} envelope and ~8.5k rows."""
    assert isinstance(markers, dict)
    assert "data" in markers
    assert isinstance(markers["data"], list)
    assert 8000 <= len(markers["data"]) <= 9000


def test_envelope_validation_rejects_bad_input() -> None:
    with pytest.raises(ICEDShapeError):
        aggregate_state_year_mean({"oops": []}, pollutant=PM25_FIELD)
    with pytest.raises(ICEDShapeError):
        aggregate_state_year_mean({"data": "not a list"}, pollutant=PM25_FIELD)
    with pytest.raises(ICEDShapeError):
        aggregate_state_year_mean([], pollutant=PM25_FIELD)


# ---------------------------------------------------------------------------
# Pollutant argument
# ---------------------------------------------------------------------------

def test_unknown_pollutant_raises(markers: dict) -> None:
    with pytest.raises(ValueError):
        aggregate_state_year_mean(markers, pollutant="ozone")


@pytest.mark.parametrize("pollutant", [PM25_FIELD, NO2_FIELD, SO2_FIELD, PM10_FIELD])
def test_all_four_pollutants_aggregate(markers: dict, pollutant: str) -> None:
    """All four NAMP pollutants survive aggregation — proves the parser is
    pollutant-agnostic and the future NO2/SO2/PM10 indicators are
    one-line derivations."""
    rows = aggregate_state_year_mean(markers, pollutant=pollutant)
    assert rows, f"{pollutant} produced zero rows"
    # All values are positive floats (pollutant means are physical).
    assert all(r.mean_value > 0 for r in rows), pollutant
    # All survive at least one station.
    assert all(r.n_stations >= 1 for r in rows), pollutant


# ---------------------------------------------------------------------------
# PM2.5 specifics
# ---------------------------------------------------------------------------

def test_pm25_year_range(markers: dict) -> None:
    """PM2.5 measurements only exist 2014+, and 2020 is empty (COVID gap)."""
    rows = aggregate_state_year_mean(markers, pollutant=PM25_FIELD)
    years = sorted({r.year for r in rows})
    assert min(years) >= 2014, f"PM2.5 should not appear before 2014, got {min(years)}"
    assert COVID_GAP_YEAR not in years, (
        "2020 should be absent from PM2.5 aggregation (no station data in snapshot)"
    )
    # Sanity: span at least 2014..2023.
    assert max(years) >= 2023


def test_pm25_one_row_per_state_year(markers: dict) -> None:
    """Aggregation contract: at most one (state, year) row per pollutant."""
    rows = aggregate_state_year_mean(markers, pollutant=PM25_FIELD)
    keys = [(r.entity_id, r.year) for r in rows]
    assert len(keys) == len(set(keys)), "duplicate (state, year) rows"


def test_pm25_nulls_dropped_not_zeroed(markers: dict) -> None:
    """A station-year with null pm25 must NOT contribute a 0 to the mean.

    Re-roll the aggregation by hand, dropping null tokens, and assert
    parser output matches. If the parser accidentally coerced null → 0,
    the parser mean would be lower than the hand mean.
    """
    from yen_gov.sources.iced_common import ENTITY_MAP
    null_tokens = {None, "N.A.", "N.A", "NA", "n.a.", "na", "-", "", "..", "...", "*"}
    bucket: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in markers["data"]:
        v = row.get(PM25_FIELD)
        if v in null_tokens or isinstance(v, bool):
            continue
        try:
            v = float(v) if not isinstance(v, (int, float)) else float(v)
        except (TypeError, ValueError):
            continue
        state_name = row["state"]
        if state_name not in ENTITY_MAP:
            continue
        bucket[(ENTITY_MAP[state_name], row["year"])].append(v)

    # Hand-rolled (entity_id, year) -> mean.
    hand = {
        key: round(sum(vals) / len(vals), 2)
        for key, vals in bucket.items()
    }

    rows = aggregate_state_year_mean(markers, pollutant=PM25_FIELD)
    parser = {(r.entity_id, r.year): r.mean_value for r in rows}
    assert parser == hand, (
        f"parser disagrees with hand-rolled mean — sample diff: "
        f"{ {k: (parser.get(k), hand.get(k)) for k in list(parser)[:3]} }"
    )


def test_pm25_lakshadweep_absent(markers: dict) -> None:
    """Lakshadweep has no PM2.5 monitor in the snapshot — must NOT appear
    as a row (distinct from appearing with mean=0)."""
    rows = aggregate_state_year_mean(markers, pollutant=PM25_FIELD)
    assert "U04" not in {r.entity_id for r in rows}


def test_pm25_tamil_nadu_2023_in_plausible_range(markers: dict) -> None:
    """TN 2023 PM2.5 should land in the 25-50 µg/m³ range — a sanity
    check against silent unit / aggregation errors."""
    rows = aggregate_state_year_mean(markers, pollutant=PM25_FIELD)
    tn_2023 = [r for r in rows if r.entity_id == "S22" and r.year == 2023]
    assert len(tn_2023) == 1
    v = tn_2023[0].mean_value
    assert 25 <= v <= 50, f"TN 2023 PM2.5 = {v}, outside plausible 25-50 range"
    assert tn_2023[0].n_stations >= 10


def test_pm25_sorted_by_entity_year(markers: dict) -> None:
    rows = aggregate_state_year_mean(markers, pollutant=PM25_FIELD)
    keys = [(r.entity_id, r.year) for r in rows]
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# Loud-fail on unknown state spellings
# ---------------------------------------------------------------------------

def test_unknown_state_spelling_raises() -> None:
    """ENTITY_MAP miss must raise ICEDShapeError — silent drop would
    let CPCB rename a state spelling and our coverage would shrink
    invisibly."""
    bad = {
        "data": [
            {"state": "Tamil Nadu", "year": 2023, "pm25": 30,
             "location": "x", "city": "x"},
            {"state": "MadeUpStateLand", "year": 2023, "pm25": 30,
             "location": "y", "city": "y"},
        ]
    }
    with pytest.raises(ICEDShapeError, match="ENTITY_MAP"):
        aggregate_state_year_mean(bad, pollutant=PM25_FIELD)


# ---------------------------------------------------------------------------
# Schema-row emission
# ---------------------------------------------------------------------------

def test_emit_indicator_rows_shape(markers: dict) -> None:
    parsed = aggregate_state_year_mean(markers, pollutant=PM25_FIELD)
    rows = emit_indicator_rows(parsed)
    assert len(rows) == len(parsed)
    sample = rows[0]
    assert set(sample) == {"entity_id", "time", "value"}
    # `time` is YYYY string for time_grain=year.
    assert sample["time"].isdigit() and len(sample["time"]) == 4
    assert isinstance(sample["value"], float)
    assert sample["entity_id"].startswith("S") or sample["entity_id"].startswith("U")


# ---------------------------------------------------------------------------
# NO2 specifics — sibling of PM2.5 from the same NAMP feed.
# Series begins 2010 (vs PM2.5 which begins 2014); 2020 IS present for
# NO2 (unlike PM2.5 where 2020 is empty), so no series_break is declared.
# ---------------------------------------------------------------------------

def test_no2_year_range(markers: dict) -> None:
    """NO2 measurements exist from 2010 onward, and 2020 IS present
    (unlike PM2.5 which is empty in 2020)."""
    rows = aggregate_state_year_mean(markers, pollutant=NO2_FIELD)
    years = sorted({r.year for r in rows})
    assert min(years) >= 2010, f"NO2 should not appear before 2010, got {min(years)}"
    assert 2020 in years, (
        "NO2 2020 should be present in this snapshot — only PM2.5 is "
        "missing 2020. If this assertion ever fails, declare a 2020 "
        "series_break in the NO2 artifact and update this test."
    )
    assert max(years) >= 2023


def test_no2_one_row_per_state_year(markers: dict) -> None:
    """Aggregation contract: at most one (state, year) row per pollutant."""
    rows = aggregate_state_year_mean(markers, pollutant=NO2_FIELD)
    keys = [(r.entity_id, r.year) for r in rows]
    assert len(keys) == len(set(keys)), "duplicate (state, year) rows for NO2"


def test_no2_delhi_2019_in_plausible_range(markers: dict) -> None:
    """Delhi 2019 NO2 should land in 50–90 µg/m³ — Delhi is the
    canonical Indian high-NO2 metro (dense diesel traffic + thermal
    plants). A reading outside this band signals a parser regression."""
    rows = aggregate_state_year_mean(markers, pollutant=NO2_FIELD)
    delhi_2019 = [r for r in rows if r.entity_id == "U05" and r.year == 2019]
    assert len(delhi_2019) == 1
    v = delhi_2019[0].mean_value
    assert 50 <= v <= 90, f"Delhi 2019 NO2 = {v}, outside plausible 50-90 range"


def test_ingest_no2_emits_artifact(tmp_path, markers: dict) -> None:
    """End-to-end: building the NO2 payload from the captured fixture
    produces a dict that validates against indicator.schema.json v1.5
    when stamped via write_artifact."""
    from datetime import datetime, timezone
    from yen_gov.core.io import Source, write_artifact
    from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
    from yen_gov.sources.iced_air_quality.markers_ingest import (
        CPCB_NAMP_URL,
        MARKERS_API_URL,
        NO2_INDICATOR_ID,
        NO2_SERIES_START_YEAR,
        _build_no2_payload,
    )

    parsed = [
        r for r in aggregate_state_year_mean(markers, pollutant=NO2_FIELD)
        if r.year >= NO2_SERIES_START_YEAR
    ]
    payload = _build_no2_payload(parsed=parsed)
    assert payload["indicator"]["id"] == NO2_INDICATOR_ID
    assert payload["indicator"]["comparability"] == "directional_only"
    assert payload["indicator"]["renderer_rules"] == [
        "no_rank_table",
        "no_growth_across_break",
    ]
    assert payload["indicator"]["excludes"], "NO2 excludes[] must not be empty"
    assert "series_breaks" not in payload["indicator"], (
        "NO2 has 2020 data in this snapshot — series_breaks should not "
        "be declared for NO2"
    )

    out = tmp_path / "state_no2_annual_mean_ug_m3.json"
    fetched_at = datetime(2026, 5, 15, 14, 44, 39, tzinfo=timezone.utc)
    write_artifact(
        path=out,
        schema_id=schema_id("indicator.schema.json"),
        schema_version=schema_version("indicator.schema.json"),
        payload=payload,
        sources=[
            Source(url=MARKERS_API_URL, fetched_at=fetched_at),
            Source(url=CPCB_NAMP_URL, fetched_at=fetched_at),
        ],
        schema_for_validation=schema_doc("indicator.schema.json"),
    )
    body = json.loads(out.read_text(encoding="utf-8"))
    assert body["$schema_version"] == schema_version("indicator.schema.json")
    assert len(body["sources"]) == 2
    assert body["rows"], "NO2 artifact rows[] must not be empty"


# ---------------------------------------------------------------------------
# SO2 specifics — sibling of PM2.5/NO2 from the same NAMP feed.
# Series begins 2010; 2020 IS present. SO2 magnitudes in India are
# generally low (single-digit µg/m³) — the honest signal is anomaly
# (near un-retrofitted thermal plants and refineries), not ranking.
# ---------------------------------------------------------------------------

def test_so2_year_range(markers: dict) -> None:
    """SO2 measurements exist from 2010 onward, and 2020 IS present."""
    rows = aggregate_state_year_mean(markers, pollutant=SO2_FIELD)
    years = sorted({r.year for r in rows})
    assert min(years) >= 2010, f"SO2 should not appear before 2010, got {min(years)}"
    assert 2020 in years, (
        "SO2 2020 should be present in this snapshot. If this ever "
        "fails, declare a 2020 series_break in the SO2 artifact and "
        "update this test."
    )
    assert max(years) >= 2023


def test_so2_one_row_per_state_year(markers: dict) -> None:
    """Aggregation contract: at most one (state, year) row per pollutant."""
    rows = aggregate_state_year_mean(markers, pollutant=SO2_FIELD)
    keys = [(r.entity_id, r.year) for r in rows]
    assert len(keys) == len(set(keys)), "duplicate (state, year) rows for SO2"


def test_so2_delhi_2019_in_plausible_range(markers: dict) -> None:
    """Delhi 2019 SO2 should land in 1–15 µg/m³. Indian metropolitan
    SO2 is typically low single digits (low-sulphur domestic coal;
    most metros off furnace oil). A reading outside this band signals
    a parser regression."""
    rows = aggregate_state_year_mean(markers, pollutant=SO2_FIELD)
    delhi_2019 = [r for r in rows if r.entity_id == "U05" and r.year == 2019]
    assert len(delhi_2019) == 1
    v = delhi_2019[0].mean_value
    assert 1 <= v <= 15, f"Delhi 2019 SO2 = {v}, outside plausible 1-15 range"


def test_ingest_so2_emits_artifact(tmp_path, markers: dict) -> None:
    """End-to-end: building the SO2 payload from the captured fixture
    produces a dict that validates against indicator.schema.json v1.5
    when stamped via write_artifact."""
    from datetime import datetime, timezone
    from yen_gov.core.io import Source, write_artifact
    from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
    from yen_gov.sources.iced_air_quality.markers_ingest import (
        CPCB_NAMP_URL,
        MARKERS_API_URL,
        SO2_INDICATOR_ID,
        SO2_SERIES_START_YEAR,
        _build_so2_payload,
    )

    parsed = [
        r for r in aggregate_state_year_mean(markers, pollutant=SO2_FIELD)
        if r.year >= SO2_SERIES_START_YEAR
    ]
    payload = _build_so2_payload(parsed=parsed)
    assert payload["indicator"]["id"] == SO2_INDICATOR_ID
    assert payload["indicator"]["comparability"] == "directional_only"
    assert payload["indicator"]["renderer_rules"] == [
        "no_rank_table",
        "no_growth_across_break",
    ]
    assert payload["indicator"]["excludes"], "SO2 excludes[] must not be empty"
    assert "series_breaks" not in payload["indicator"], (
        "SO2 has 2020 data in this snapshot — series_breaks should not "
        "be declared for SO2"
    )

    out = tmp_path / "state_so2_annual_mean_ug_m3.json"
    fetched_at = datetime(2026, 5, 15, 14, 44, 39, tzinfo=timezone.utc)
    write_artifact(
        path=out,
        schema_id=schema_id("indicator.schema.json"),
        schema_version=schema_version("indicator.schema.json"),
        payload=payload,
        sources=[
            Source(url=MARKERS_API_URL, fetched_at=fetched_at),
            Source(url=CPCB_NAMP_URL, fetched_at=fetched_at),
        ],
        schema_for_validation=schema_doc("indicator.schema.json"),
    )
    body = json.loads(out.read_text(encoding="utf-8"))
    assert body["$schema_version"] == schema_version("indicator.schema.json")
    assert len(body["sources"]) == 2
    assert body["rows"], "SO2 artifact rows[] must not be empty"


# ---------------------------------------------------------------------------
# PM10 specifics — coarse particulate fraction from the same NAMP feed.
# Series begins 2010; 2020 IS present. PM10 includes the PM2.5 fraction
# by definition; the extra mass is dominated in India by road dust,
# construction, and crop-residue burning.
# ---------------------------------------------------------------------------

def test_pm10_year_range(markers: dict) -> None:
    """PM10 measurements exist from 2010 onward, and 2020 IS present."""
    rows = aggregate_state_year_mean(markers, pollutant=PM10_FIELD)
    years = sorted({r.year for r in rows})
    assert min(years) >= 2010, f"PM10 should not appear before 2010, got {min(years)}"
    assert 2020 in years, (
        "PM10 2020 should be present in this snapshot. If this ever "
        "fails, declare a 2020 series_break in the PM10 artifact and "
        "update this test."
    )
    assert max(years) >= 2023


def test_pm10_one_row_per_state_year(markers: dict) -> None:
    """Aggregation contract: at most one (state, year) row per pollutant."""
    rows = aggregate_state_year_mean(markers, pollutant=PM10_FIELD)
    keys = [(r.entity_id, r.year) for r in rows]
    assert len(keys) == len(set(keys)), "duplicate (state, year) rows for PM10"


def test_pm10_delhi_2019_in_plausible_range(markers: dict) -> None:
    """Delhi 2019 PM10 should land in 150–250 µg/m³. Delhi is the
    canonical Indian high-PM10 metro (heavy road dust + construction
    + winter crop-residue smoke). A reading outside this band signals
    a parser regression."""
    rows = aggregate_state_year_mean(markers, pollutant=PM10_FIELD)
    delhi_2019 = [r for r in rows if r.entity_id == "U05" and r.year == 2019]
    assert len(delhi_2019) == 1
    v = delhi_2019[0].mean_value
    assert 150 <= v <= 250, f"Delhi 2019 PM10 = {v}, outside plausible 150-250 range"


def test_ingest_pm10_emits_artifact(tmp_path, markers: dict) -> None:
    """End-to-end: building the PM10 payload from the captured fixture
    produces a dict that validates against indicator.schema.json v1.5
    when stamped via write_artifact."""
    from datetime import datetime, timezone
    from yen_gov.core.io import Source, write_artifact
    from yen_gov.core.schema_registry import schema_doc, schema_id, schema_version
    from yen_gov.sources.iced_air_quality.markers_ingest import (
        CPCB_NAMP_URL,
        MARKERS_API_URL,
        PM10_INDICATOR_ID,
        PM10_SERIES_START_YEAR,
        _build_pm10_payload,
    )

    parsed = [
        r for r in aggregate_state_year_mean(markers, pollutant=PM10_FIELD)
        if r.year >= PM10_SERIES_START_YEAR
    ]
    payload = _build_pm10_payload(parsed=parsed)
    assert payload["indicator"]["id"] == PM10_INDICATOR_ID
    assert payload["indicator"]["comparability"] == "directional_only"
    assert payload["indicator"]["renderer_rules"] == [
        "no_rank_table",
        "no_growth_across_break",
    ]
    assert payload["indicator"]["excludes"], "PM10 excludes[] must not be empty"
    assert "series_breaks" not in payload["indicator"], (
        "PM10 has 2020 data in this snapshot — series_breaks should "
        "not be declared for PM10"
    )

    out = tmp_path / "state_pm10_annual_mean_ug_m3.json"
    fetched_at = datetime(2026, 5, 15, 14, 44, 39, tzinfo=timezone.utc)
    write_artifact(
        path=out,
        schema_id=schema_id("indicator.schema.json"),
        schema_version=schema_version("indicator.schema.json"),
        payload=payload,
        sources=[
            Source(url=MARKERS_API_URL, fetched_at=fetched_at),
            Source(url=CPCB_NAMP_URL, fetched_at=fetched_at),
        ],
        schema_for_validation=schema_doc("indicator.schema.json"),
    )
    body = json.loads(out.read_text(encoding="utf-8"))
    assert body["$schema_version"] == schema_version("indicator.schema.json")
    assert len(body["sources"]) == 2
    assert body["rows"], "PM10 artifact rows[] must not be empty"
