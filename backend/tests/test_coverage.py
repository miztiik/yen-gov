"""Tests for the coverage report (data inventory)."""

from __future__ import annotations

import json
from pathlib import Path

from yen_gov.coverage import compute_coverage, render_markdown


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
