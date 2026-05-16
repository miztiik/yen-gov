"""Integration tests for the RBI Statement 27 health-share indicator.

Validates the full ingest pipeline (parser → orchestrator → artifact)
against the byte-faithful workbook snapshot captured by
``tools/rbi_statement_27_recon.py``. Per Holy Law #7 the fixture is the
real RBI bytes — no mocking of the upstream layout.

The fixture also pins our contract against the upstream: if RBI ships
a Statement-27 layout shift (sheet renamed, header row moved, new
fiscal-year column ordering, footnote rows misinterpreted as state
rows), one of these assertions will fail with a clear diagnostic
before the change ever reaches the artifact on disk.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.sources.rbi_xlsx.parsers import (
    IndicatorSpec,
    parse_workbook,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "rbi_statement_27"
    / "27_ST23012026_HealthExpenditureShare.xlsx"
)


HEALTH_SPEC = IndicatorSpec(
    indicator_id="health/state_health_expenditure_pct_total_expenditure",
    sheet_match="ST_27",
    header_label_match="state/ut",
    period_kind="fy_span",
)


@pytest.fixture(scope="module")
def workbook_bytes() -> bytes:
    assert FIXTURE.exists(), (
        f"Missing fixture {FIXTURE}; re-run tools/rbi_statement_27_recon.py"
    )
    return FIXTURE.read_bytes()


def test_fixture_parses_with_expected_shape(workbook_bytes: bytes) -> None:
    parsed = parse_workbook(workbook_bytes, HEALTH_SPEC)

    assert parsed.sheet_name == "ST_27"
    # Statement 27 ships 18 fiscal years: 2008-09 through 2025-26.
    assert parsed.period_columns == 18
    # 31 states × 18 fiscal years = 558 rows. Aggregate rows
    # ("All States and UTs", "...(Per cent of GDP)") and footnote rows
    # ("*: ...", "Note: ...", "Source: ...") MUST be excluded.
    assert len(parsed.rows) == 558
    # No upstream label should fall through unmatched — every "31. X"
    # row currently maps to an ECI code.
    assert parsed.unmatched_states == []


def test_fixture_emits_full_period_grid(workbook_bytes: bytes) -> None:
    parsed = parse_workbook(workbook_bytes, HEALTH_SPEC)

    # Each state should land on exactly the 18 fiscal years and the
    # period strings should be the RBI -> ISO-month convention.
    by_state: dict[str, set[str]] = {}
    for row in parsed.rows:
        by_state.setdefault(row.entity_id, set()).add(row.time)

    expected_periods = {
        f"{2008 + i}-04" for i in range(18)
    }
    for entity_id, periods in by_state.items():
        assert periods == expected_periods, (
            f"{entity_id} period grid drifted: missing="
            f"{sorted(expected_periods - periods)}, extra="
            f"{sorted(periods - expected_periods)}"
        )


def test_fixture_marks_last_two_periods_as_re_then_be(
    workbook_bytes: bytes,
) -> None:
    parsed = parse_workbook(workbook_bytes, HEALTH_SPEC)

    facets_by_time: dict[str, set[str | None]] = {}
    for row in parsed.rows:
        facets_by_time.setdefault(row.time, set()).add(row.facet)

    # The final two periods are RE / BE in the RBI source.
    assert facets_by_time["2024-04"] == {"RE"}
    assert facets_by_time["2025-04"] == {"BE"}
    # Every earlier period is Accounts (no facet qualifier).
    for year in range(2008, 2024):
        period = f"{year}-04"
        assert facets_by_time[period] == {None}, (
            f"period {period} unexpectedly carries facet "
            f"{facets_by_time[period]}"
        )


def test_fixture_telangana_pre_2014_is_null(workbook_bytes: bytes) -> None:
    """Telangana was carved out of Andhra Pradesh in June 2014 — RBI
    publishes '–' for every pre-2014-15 cell. The parser must surface
    those as None rather than skipping the row or coercing to 0."""
    parsed = parse_workbook(workbook_bytes, HEALTH_SPEC)

    telangana_rows = sorted(
        ((r.time, r.value) for r in parsed.rows if r.entity_id == "S29"),
    )
    pre_formation = {t: v for t, v in telangana_rows if t < "2014-04"}
    assert pre_formation, "Telangana fixture rows missing"
    assert all(v is None for v in pre_formation.values()), (
        f"Telangana pre-2014 values not null: {pre_formation}"
    )
    # First non-null Telangana observation is 2014-15.
    first_value = next(v for t, v in telangana_rows if v is not None)
    assert first_value == 4.1


def test_fixture_includes_delhi_and_puducherry(workbook_bytes: bytes) -> None:
    """NCT Delhi ("30. NCT Delhi") and Puducherry ("31. Puducherry") sit
    at the end of the state list. The RBI footnote notes Delhi/Puducherry
    coverage starts 2017-18 — but the workbook publishes earlier
    figures anyway (since these are budget submissions, not survey
    data). Make sure the labels map to the right ECI codes."""
    parsed = parse_workbook(workbook_bytes, HEALTH_SPEC)

    by_state = {r.entity_id for r in parsed.rows}
    assert "U05" in by_state, "NCT Delhi (U05) missing"
    assert "U07" in by_state, "Puducherry (U07) missing"


def test_artifact_on_disk_matches_contract() -> None:
    """The emitted artifact must validate against indicator.schema.json
    and carry the v1.5 Hans-governance fields the meta entry sets."""
    repo_root = Path(__file__).resolve().parents[2]
    artifact_path = (
        repo_root
        / "datasets"
        / "indicators"
        / "in"
        / "health"
        / "state_health_expenditure_pct_total_expenditure.json"
    )
    assert artifact_path.exists(), (
        f"Artifact missing — run `python -m yen_gov ingest-health-rbi-statement-27 "
        f"--root .` to regenerate."
    )

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    indicator = payload["indicator"]

    assert indicator["id"] == "health/state_health_expenditure_pct_total_expenditure"
    assert indicator["direction"] == "higher_is_better"
    assert indicator["comparability"] == "comparable_across_states_and_time"
    assert indicator["unit"] == "% of state total expenditure"
    assert indicator["chart_type"] == "choropleth"
    assert indicator["attribution_geography"] == "where_administered"
    assert indicator["implementing_authority"] == "state"

    # v1.5 Hans-governance fields are populated.
    assert isinstance(indicator["denominator"], dict)
    assert indicator["denominator"]["what"].startswith("State / UT government's")
    assert indicator["denominator"]["price_basis"] == "current"

    tiers = indicator["revision_tier_by_period"]
    assert [t["from"] for t in tiers] == ["2008-04", "2024-04", "2025-04"]
    assert [t["tier"] for t in tiers] == ["Accounts", "RE", "BE"]

    excludes = indicator["excludes"]
    assert len(excludes) >= 3
    assert any("Water Supply" in e for e in excludes)
    assert any("Telangana" in e for e in excludes)

    # Provenance: two sources (workbook URL + RBI authority page).
    sources = payload["sources"]
    assert len(sources) == 2
    assert any("27_ST23012026" in s["url"] for s in sources)
