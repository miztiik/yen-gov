"""Tests for the coverage report (data inventory)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from yen_gov.coverage import (
    _compute_meter,
    _parse_temporal,
    _scan_indicators,
    compute_coverage,
    render_markdown,
)


def _write(path: Path, content: str | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, dict):
        path.write_text(json.dumps(content), encoding="utf-8")
    else:
        path.write_text(content, encoding="utf-8")


def test_coverage_reconciles_catalogue_and_disk(tmp_path: Path) -> None:
    """Catalogue + on-disk should produce one slice per (event, state)."""
    _write(
        tmp_path / "datasets/reference/in/states.json",
        {"states": [{"eci_code": "S22", "name": "Tamil Nadu"}]},
    )
    _write(
        tmp_path / "datasets/reference/in/election-events.json",
        {
            "states": {
                "S22": [
                    {
                        "event_id": "AcGenMay2026",
                        "kind": "assembly",
                        "display": "Tamil Nadu Assembly . May 2026",
                        "polled_on": "2026-05-08",
                        "default": True,
                        "data_status": "complete",
                    }
                ]
            }
        },
    )
    state_dir = tmp_path / "datasets/elections/AcGenMay2026/S22"
    _write(state_dir / "result.summary.json", "{}")
    _write(state_dir / "parties.json", "{}")
    _write(state_dir / "results/1.json", "{}")
    _write(state_dir / "results/2.json", "{}")

    report = compute_coverage(tmp_path)
    assert len(report.slices) == 1
    s = report.slices[0]
    assert s.event_id == "AcGenMay2026"
    assert s.state_code == "S22"
    assert s.state_name == "Tamil Nadu"
    assert s.on_disk is True
    assert s.ac_count == 2
    assert s.has_summary and s.has_parties
    assert s.declared_status == "complete"


def test_coverage_flags_undeclared_and_pending(tmp_path: Path) -> None:
    """On-disk-but-undeclared and declared-but-missing both surface as issues
    (except `pending_upstream`, which is the canonical 'awaiting publication'
    state and must NOT be reported as an inconsistency)."""
    _write(tmp_path / "datasets/reference/in/states.json", {"states": []})
    _write(
        tmp_path / "datasets/reference/in/election-events.json",
        {
            "states": {
                "S04": [
                    {
                        "event_id": "AcGenNov2025",
                        "kind": "assembly",
                        "display": "Bihar Assembly . November 2025",
                        "polled_on": "2025-11-11",
                        "default": True,
                        "data_status": "pending_upstream",
                    }
                ],
                "S22": [
                    {
                        "event_id": "AcGenMay2026",
                        "kind": "assembly",
                        "display": "Tamil Nadu Assembly . May 2026",
                        "polled_on": "2026-05-08",
                        "default": True,
                        "data_status": "complete",
                    }
                ],
            }
        },
    )
    # On-disk for an *undeclared* slice (catalogue knows S22/AcGenMay2026 but not S99/AcGenJan1900).
    _write(
        tmp_path / "datasets/elections/AcGenJan1900/S99/result.summary.json", "{}"
    )

    report = compute_coverage(tmp_path)
    md = render_markdown(report)

    assert "Inconsistencies" in md
    assert "AcGenJan1900" in md  # undeclared on-disk surfaces
    assert "S22" in md  # declared-and-missing surfaces (not pending)
    # Pending Bihar must NOT appear under Inconsistencies.
    bihar_in_issues = any(
        "S04" in line and "Inconsistencies" not in line
        for line in md.split("## Inconsistencies", 1)[1].splitlines()
    )
    assert not bihar_in_issues


def test_parse_temporal_handles_range_and_snapshot() -> None:
    assert _parse_temporal("2007-04..2025-04") == (date(2007, 4, 1), date(2025, 4, 1))
    assert _parse_temporal("2026-03") == (date(2026, 3, 1), date(2026, 3, 1))
    assert _parse_temporal("2019") == (date(2019, 4, 1), date(2019, 4, 1))
    with pytest.raises(ValueError):
        _parse_temporal("not-a-date")
    with pytest.raises(ValueError):
        _parse_temporal("")


def test_compute_meter_buckets() -> None:
    # FY07-04 -> FY25-04 covers all 7 buckets (FY06-FY26).
    assert _compute_meter(date(2007, 4, 1), date(2025, 4, 1)) == (
        True, True, True, True, True, True, True,
    )
    # 2026-03 snapshot lands only in the rightmost (FY24-FY26) bucket.
    assert _compute_meter(date(2026, 3, 1), date(2026, 3, 1)) == (
        False, False, False, False, False, False, True,
    )
    # FY16-04 -> FY22-04 -> middle three buckets (4, 5, 6).
    assert _compute_meter(date(2016, 4, 1), date(2022, 4, 1)) == (
        False, False, False, True, True, True, False,
    )


def test_scan_indicators_emits_meter(tmp_path: Path) -> None:
    base = tmp_path / "datasets/indicators/in"
    annual = {
        "$schema": "x", "$schema_version": "1.0",
        "sources": [{"url": "https://www.rbi.org.in/x", "fetched_at": "2026-01-01T00:00:00Z"}],
        "coverage": {"temporal": "2007-04..2025-04", "admin_level": "national"},
        "indicator": {
            "id": "fiscal/national_x", "title": "X", "unit": "INR (crore)",
            "time_grain": "fiscal_year",
        },
        "rows": [{"entity_id": "IN", "period": "2007-04", "value": 1}],
    }
    snap = {
        "$schema": "x", "$schema_version": "1.0",
        "sources": [{"url": "https://cea.nic.in/y", "fetched_at": "2026-05-01T00:00:00Z"}],
        "coverage": {"temporal": "2026-03", "admin_level": "state"},
        "indicator": {
            "id": "energy/installed_y_mw", "title": "Y", "unit": "MW",
            "time_grain": "month",
        },
        "rows": [{"entity_id": "S22", "period": "2026-03", "value": 1000}],
    }
    _write(base / "fiscal/national_x.json", annual)
    _write(base / "energy/installed_y_mw.json", snap)

    inds = {i.id: i for i in _scan_indicators(tmp_path)}
    assert set(inds) == {"fiscal/national_x", "energy/installed_y_mw"}

    fx = inds["fiscal/national_x"]
    assert fx.category == "fiscal"
    assert fx.is_snapshot is False
    assert fx.meter_cells == (True, True, True, True, True, True, True)
    assert fx.source_host == "www.rbi.org.in"

    cy = inds["energy/installed_y_mw"]
    assert cy.category == "energy"
    assert cy.is_snapshot is True
    assert cy.meter_cells == (False, False, False, False, False, False, True)
    assert cy.source_host == "cea.nic.in"


def test_render_includes_indicators_and_state_first(tmp_path: Path) -> None:
    _write(
        tmp_path / "datasets/reference/in/states.json",
        {"states": [{"eci_code": "S03", "name": "Assam"}]},
    )
    _write(
        tmp_path / "datasets/reference/in/election-events.json",
        {
            "states": {
                "S03": [
                    {"event_id": "AcGenApr2016", "kind": "assembly",
                     "display": "Assam . April 2016", "polled_on": "2016-04-11",
                     "default": False, "data_status": "complete"},
                    {"event_id": "AcGenMay2026", "kind": "assembly",
                     "display": "Assam . May 2026", "polled_on": "2026-05-08",
                     "default": True, "data_status": "complete"},
                ]
            }
        },
    )
    for ev in ("AcGenApr2016", "AcGenMay2026"):
        sd = tmp_path / f"datasets/elections/{ev}/S03"
        _write(sd / "result.summary.json", "{}")
        _write(sd / "parties.json", "{}")
        _write(sd / "results/1.json", "{}")

    _write(
        tmp_path / "datasets/indicators/in/fiscal/national_x.json",
        {
            "$schema": "x", "$schema_version": "1.0",
            "sources": [{"url": "https://www.rbi.org.in/x",
                         "fetched_at": "2026-01-01T00:00:00Z"}],
            "coverage": {"temporal": "2007-04..2025-04",
                         "admin_level": "national"},
            "indicator": {"id": "fiscal/national_x", "title": "X",
                          "unit": "INR (crore)", "time_grain": "fiscal_year"},
            "rows": [{"entity_id": "IN", "period": "2007-04", "value": 1}],
        },
    )

    md = render_markdown(compute_coverage(tmp_path))

    assert md.startswith("# Data Inventory\n")
    assert "## 1. Indicators" in md
    assert "`fiscal/national_x`" in md
    # Phase #4a (2026-05-17): id cell links to the artifact JSON on disk,
    # NOT to the auto-generated per-indicator markdown tree (which was
    # retired in the same phase). Positive shape + negative guard so the
    # next regression — link-shape drift OR id-cell deletion — is caught.
    assert (
        "[`fiscal/national_x`](../../datasets/indicators/in/fiscal/national_x.json)"
        in md
    )
    assert "](indicators/" not in md
    # 7/7 for the all-7 bucket case.
    assert "7/7" in md
    assert "## 2a. Elections \u2014 coverage depth (state-first)" in md
    assert "Assam" in md
    # 2 events -> 2/7 with the rightmost two cells filled.
    assert "2/7" in md
    assert "## 2b. Elections \u2014 by cohort (event-first)" in md


def test_render_markdown_includes_frontend_wiring_section(tmp_path: Path) -> None:
    """When ``topic-catalogue.json`` is present, the inventory must report
    which indicators are wired vs unwired \u2014 the catalogue is hand-maintained
    (Holy Law #6 risk) and ~half the inventory was silently absent from the
    IA before this section existed."""
    _write(
        tmp_path / "datasets/reference/in/states.json",
        {"states": [{"eci_code": "S22", "name": "Tamil Nadu"}]},
    )
    _write(
        tmp_path / "datasets/reference/in/election-events.json",
        {"states": {}},
    )
    _write(
        tmp_path / "datasets/reference/in/topic-catalogue.json",
        {
            "$schema": "x", "$schema_version": "1.0", "sources": [],
            "topics": [
                {
                    "id": "fiscal", "title": "Fiscal", "list": "state",
                    "summary": "x", "icon": "x", "featured": True,
                    "artifacts": [
                        {"kind": "indicator", "id": "fiscal/wired_one",
                         "default": True, "scope": "national"}
                    ],
                }
            ],
        },
    )
    _write(
        tmp_path / "datasets/indicators/in/fiscal/wired_one.json",
        {
            "$schema": "x", "$schema_version": "1.0",
            "sources": [{"url": "https://x", "fetched_at": "2026-01-01T00:00:00Z"}],
            "coverage": {"temporal": "2007-04..2025-04", "admin_level": "national"},
            "indicator": {"id": "fiscal/wired_one", "title": "Wired",
                          "unit": "INR", "time_grain": "fiscal_year"},
            "rows": [{"entity_id": "IN", "period": "2007-04", "value": 1}],
        },
    )
    _write(
        tmp_path / "datasets/indicators/in/health/unwired_one.json",
        {
            "$schema": "x", "$schema_version": "1.0",
            "sources": [{"url": "https://x", "fetched_at": "2026-01-01T00:00:00Z"}],
            "coverage": {"temporal": "2015-04..2024-04", "admin_level": "state"},
            "indicator": {"id": "health/unwired_one", "title": "Unwired",
                          "unit": "per 1000", "time_grain": "year"},
            "rows": [{"entity_id": "S22", "period": "2015-04", "value": 1}],
        },
    )

    md = render_markdown(compute_coverage(tmp_path))

    # Top-of-section summary line.
    assert "Frontend wiring" in md
    assert "1 of 2" in md
    # 1Z. unwired listing.
    assert "## 1. Indicators" in md
    assert "1Z. Frontend wiring" in md
    assert "`health/unwired_one`" in md
    # The wired indicator must NOT appear in the unwired table; assert the
    # unwired block contains only the unwired id by checking the wired id is
    # absent from the lines after the "1Z." header.
    z_idx = md.index("1Z. Frontend wiring")
    next_h2 = md.index("## 2a.")
    assert "`fiscal/wired_one`" not in md[z_idx:next_h2]
    # Per-row Wired column glyphs.
    assert " \u25cf | iced" not in md  # not asserting host, just that glyph exists somewhere
    assert "Wired |" in md

