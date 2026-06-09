"""Tests for the coverage report (data inventory)."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from yen_gov.coverage import (
    _compute_meter,
    _parse_temporal,
    _scan_indicators,
    _walk_assembly_csv,
    _walk_parliament_csv,
    compute_coverage,
    render_markdown,
)


def _write(path: Path, content: str | dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, dict):
        path.write_text(json.dumps(content), encoding="utf-8")
    else:
        path.write_text(content, encoding="utf-8")


def _seed_geo_csv(root: Path, rows: list[tuple[str, str, str]]) -> None:
    """Write a minimal ``datasets/data/entities/geo.csv`` with the columns the
    walker's ``_slug_to_state_code`` helper consumes.

    Each row is ``(entity_id, eci_code, name)`` (e.g. ``("tamil-nadu", "S22",
    "Tamil Nadu")``). The ECI code is encoded into the pipe-delimited
    ``aliases`` column to mirror the production geo.csv shape; ``entity_kind``
    is hard-coded to ``state`` since the canonical store flattens both states
    and UTs under that single value.
    """
    path = root / "datasets/data/entities/geo.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([
            "entity_id", "name", "parent", "entity_kind",
            "aliases", "census_2001_code", "census_2011_code",
        ])
        for entity_id, eci_code, name in rows:
            w.writerow([entity_id, name, "IN", "state", eci_code, "", ""])


_CANDIDACY_COLS = (
    "entity_id", "state", "election_year", "constituency_no",
    "constituency_name", "candidate_name", "party_id", "party_short_raw",
    "votes", "vote_share_pct", "position", "result", "sex", "age",
    "education", "profession", "candidate_type", "source_id",
)
_SUMMARY_COLS = (
    "entity_id", "state", "election_year", "constituency_name",
    "electors", "votes_polled", "turnout_pct",
    "winner_candidate", "winner_party_id", "winner_party_short_raw",
    "winner_votes", "winner_share_pct",
    "runnerup_candidate", "runnerup_party_id", "runnerup_party_short_raw",
    "runnerup_votes", "margin_votes", "margin_pct", "source_id",
)


def _seed_assembly_csv(
    root: Path,
    *,
    state_slug: str,
    election_year: int,
    n_acs: int,
    source_id: str = "src-test",
) -> Path:
    """Write a minimal ``assembly/state=<slug>/election=<year>/{summary,candidacies}.csv``
    pair that the G14 CSV walker can read.

    Each AC gets a single summary row + 2 candidacy rows (winner + runner-up);
    the CSV shape mirrors the on-disk emitter's column contract so the same
    fixture can be reused by the G15 ``summary == recompute(candidacies)``
    parity test if needed.
    """
    base = root / "datasets/elections/assembly" / f"state={state_slug}" / f"election={election_year}"
    base.mkdir(parents=True, exist_ok=True)
    summary_path = base / "summary.csv"
    cand_path = base / "candidacies.csv"
    summary_rows: list[dict[str, object]] = []
    candidacy_rows: list[dict[str, object]] = []
    for n in range(1, n_acs + 1):
        entity_id = f"IN-AC-2008-{state_slug}-{n}"
        winner = {
            "entity_id": entity_id, "state": state_slug,
            "election_year": election_year, "constituency_no": n,
            "constituency_name": f"AC{n}", "candidate_name": f"W{n}",
            "party_id": "parties.IN.A", "party_short_raw": "A",
            "votes": 1000, "vote_share_pct": 60.0,
            "position": 1, "result": "won",
            "sex": "M", "age": 50, "education": "Graduate",
            "profession": "", "candidate_type": "challenger",
            "source_id": source_id,
        }
        runner = {**winner, "candidate_name": f"R{n}",
                  "party_id": "parties.IN.B", "party_short_raw": "B",
                  "votes": 500, "vote_share_pct": 30.0,
                  "position": 2, "result": "lost"}
        candidacy_rows.append(winner)
        candidacy_rows.append(runner)
        summary_rows.append({
            "entity_id": entity_id, "state": state_slug,
            "election_year": election_year, "constituency_name": f"AC{n}",
            "electors": 2000, "votes_polled": 1500, "turnout_pct": 75.0,
            "winner_candidate": f"W{n}", "winner_party_id": "parties.IN.A",
            "winner_party_short_raw": "A", "winner_votes": 1000,
            "winner_share_pct": 60.0,
            "runnerup_candidate": f"R{n}",
            "runnerup_party_id": "parties.IN.B",
            "runnerup_party_short_raw": "B", "runnerup_votes": 500,
            "margin_votes": 500, "margin_pct": 30.0,
            "source_id": source_id,
        })
    with summary_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(_SUMMARY_COLS))
        w.writeheader()
        for row in summary_rows:
            w.writerow(row)
    with cand_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(_CANDIDACY_COLS))
        w.writeheader()
        for row in candidacy_rows:
            w.writerow(row)
    return base


def _seed_parliament_csv(
    root: Path,
    *,
    election_year: int,
    per_state: dict[str, int],
    source_id: str = "src-test",
) -> Path:
    """Write a minimal ``parliament/election=<year>/{summary,candidacies}.csv``
    pair fanning out across ``per_state`` slugs.

    ``per_state`` maps ``state_slug -> n_pcs``; the parliament CSV is a SINGLE
    national file (no ``state=*/`` partition); the walker fans out per state
    by reading the ``state`` column. Each PC gets 1 summary row + 2 candidacy
    rows just like ``_seed_assembly_csv`` for symmetry.
    """
    base = root / "datasets/elections/parliament" / f"election={election_year}"
    base.mkdir(parents=True, exist_ok=True)
    summary_path = base / "summary.csv"
    cand_path = base / "candidacies.csv"
    summary_rows: list[dict[str, object]] = []
    candidacy_rows: list[dict[str, object]] = []
    pc_no = 0
    for state_slug, n_pcs in per_state.items():
        for _ in range(n_pcs):
            pc_no += 1
            entity_id = f"IN-PC-2008-{state_slug}-{pc_no}"
            winner = {
                "entity_id": entity_id, "state": state_slug,
                "election_year": election_year, "constituency_no": pc_no,
                "constituency_name": f"PC{pc_no}", "candidate_name": f"W{pc_no}",
                "party_id": "parties.IN.A", "party_short_raw": "A",
                "votes": 100000, "vote_share_pct": 55.0,
                "position": 1, "result": "won",
                "sex": "M", "age": 55, "education": "Graduate",
                "profession": "", "candidate_type": "challenger",
                "source_id": source_id,
            }
            runner = {**winner, "candidate_name": f"R{pc_no}",
                      "party_id": "parties.IN.B", "party_short_raw": "B",
                      "votes": 80000, "vote_share_pct": 40.0,
                      "position": 2, "result": "lost"}
            candidacy_rows.append(winner)
            candidacy_rows.append(runner)
            summary_rows.append({
                "entity_id": entity_id, "state": state_slug,
                "election_year": election_year,
                "constituency_name": f"PC{pc_no}",
                "electors": 200000, "votes_polled": 180000, "turnout_pct": 90.0,
                "winner_candidate": f"W{pc_no}",
                "winner_party_id": "parties.IN.A",
                "winner_party_short_raw": "A",
                "winner_votes": 100000, "winner_share_pct": 55.0,
                "runnerup_candidate": f"R{pc_no}",
                "runnerup_party_id": "parties.IN.B",
                "runnerup_party_short_raw": "B",
                "runnerup_votes": 80000,
                "margin_votes": 20000, "margin_pct": 15.0,
                "source_id": source_id,
            })
    with summary_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(_SUMMARY_COLS))
        w.writeheader()
        for row in summary_rows:
            w.writerow(row)
    with cand_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(_CANDIDACY_COLS))
        w.writeheader()
        for row in candidacy_rows:
            w.writerow(row)
    return base


def _seed_election_csv(
    root: Path,
    slices: dict[tuple[str, str], dict[str, object]],
) -> None:
    """Drop-in replacement for the legacy ``_seed_election_parquet`` helper.

    Emits the on-disk CSV shape the G14 walker reads. Each ``slices`` entry
    maps ``(event_id, state_code)`` to a dict with:

    - ``ac_count``    : ``int``  - number of (AC or PC) summary rows to emit.
    - ``has_summary`` : ``bool`` - unused (kept for back-compat with the old
      signature; the walker treats every directory with ``summary.csv`` as
      ``has_summary=True``).
    - ``has_parties`` : ``bool`` - same (always ``False`` in the new CSV
      tree; no separate ``parties.csv`` is emitted).
    - ``body``        : ``str``  - ``"AC"`` (default) or ``"PC"``.
    - ``state_slug``  : ``str``  - the on-disk slug, e.g. ``"tamil-nadu"``.
      Required because the walker partition discriminator is slug, not ECI
      code; tests must supply the same string the production emitter writes.
    - ``election_year``: ``int`` - the election year encoded in the
      partition path; for ``event_id``-keyed slices this also drives the
      catalogue back-resolution if a paired ``election_events.json`` entry
      is present in the fixture.
    """
    for (_event_id, _state_code), spec in slices.items():
        body = spec.get("body", "AC")
        state_slug = spec.get("state_slug")
        year = spec.get("election_year")
        ac_count = int(spec.get("ac_count", 0))  # type: ignore[arg-type]
        if state_slug is None or year is None:
            raise ValueError(
                "_seed_election_csv requires both 'state_slug' and "
                "'election_year' in every spec dict"
            )
        if body == "AC":
            _seed_assembly_csv(
                root,
                state_slug=str(state_slug),
                election_year=int(year),
                n_acs=ac_count,
            )
        else:
            _seed_parliament_csv(
                root,
                election_year=int(year),
                per_state={str(state_slug): ac_count},
            )


def test_coverage_reconciles_catalogue_and_disk(tmp_path: Path) -> None:
    """Catalogue + on-disk should produce one slice per (event, state)."""
    _write(
        tmp_path / "datasets/taxonomy/entities.json",
        {
            "entities": [
                {
                    "entity_code": "S22",
                    "entity_type": "state",
                    "display_name": "Tamil Nadu",
                    "entity_valid_to": None,
                }
            ]
        },
    )
    _write(
        tmp_path / "datasets/taxonomy/election_events.json",
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
    # G14: coverage now walks the on-disk CSV tree at
    # ``datasets/elections/{assembly,parliament}/`` directly (the canonical
    # Parquet store retired 2026-06-07 via X1a-fu2). The slug-to-ECI map is
    # built from ``datasets/data/entities/geo.csv``.
    _seed_geo_csv(tmp_path, [("tamil-nadu", "S22", "Tamil Nadu")])
    _seed_election_csv(
        tmp_path,
        {
            ("AcGenMay2026", "S22"): {
                "ac_count": 2,
                "has_summary": True,
                "has_parties": False,
                "body": "AC",
                "state_slug": "tamil-nadu",
                "election_year": 2026,
            }
        },
    )

    report = compute_coverage(tmp_path)
    assert len(report.slices) == 1
    s = report.slices[0]
    assert s.event_id == "AcGenMay2026"
    assert s.state_code == "S22"
    assert s.state_name == "Tamil Nadu"
    assert s.on_disk is True
    assert s.ac_count == 2
    assert s.has_summary
    # has_parties is always False under the new CSV tree (no parties.csv
    # is emitted; party rollups happen at frontend render time from
    # candidacies). The contract field is preserved for back-compat.
    assert s.has_parties is False
    assert s.body == "AC"
    assert s.declared_status == "complete"


def test_coverage_flags_undeclared_and_pending(tmp_path: Path) -> None:
    """On-disk-but-undeclared and declared-but-missing both surface as issues
    (except `pending_upstream`, which is the canonical 'awaiting publication'
    state and must NOT be reported as an inconsistency)."""
    _write(tmp_path / "datasets/taxonomy/entities.json", {"entities": []})
    _write(
        tmp_path / "datasets/taxonomy/election_events.json",
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
    # G14: an on-disk slice the catalogue does NOT declare. The walker
    # synthesises ``Ac<year>`` as the fallback event_id when no catalogue
    # event matches (state_code, year, body). For this test, slug
    # "wonderland" maps to ECI code "S99" via the geo.csv seed; year 1900
    # is not in the catalogue -> walker emits ("Ac1900", "S99") -> appears
    # in the "On-disk artifacts but no entry in the catalogue" lane of
    # the Inconsistencies section.
    _seed_geo_csv(tmp_path, [("wonderland", "S99", "Wonderland")])
    _seed_election_csv(
        tmp_path,
        {
            ("Ac1900", "S99"): {
                "ac_count": 1,
                "has_summary": True,
                "has_parties": False,
                "body": "AC",
                "state_slug": "wonderland",
                "election_year": 1900,
            }
        },
    )

    report = compute_coverage(tmp_path)
    md = render_markdown(report)

    assert "Inconsistencies" in md
    assert "Ac1900" in md  # undeclared on-disk surfaces
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
        tmp_path / "datasets/taxonomy/entities.json",
        {
            "entities": [
                {
                    "entity_code": "S03",
                    "entity_type": "state",
                    "display_name": "Assam",
                    "entity_valid_to": None,
                }
            ]
        },
    )
    _write(
        tmp_path / "datasets/taxonomy/election_events.json",
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
    # G14: seed CSV slices for both Assam events. Walker derives event_id
    # via catalogue back-resolution (S03, 2016) -> AcGenApr2016 and
    # (S03, 2026) -> AcGenMay2026.
    _seed_geo_csv(tmp_path, [("assam", "S03", "Assam")])
    _seed_election_csv(
        tmp_path,
        {
            ("AcGenApr2016", "S03"): {
                "ac_count": 1,
                "has_summary": True,
                "has_parties": False,
                "body": "AC",
                "state_slug": "assam",
                "election_year": 2016,
            },
            ("AcGenMay2026", "S03"): {
                "ac_count": 1,
                "has_summary": True,
                "has_parties": False,
                "body": "AC",
                "state_slug": "assam",
                "election_year": 2026,
            },
        },
    )

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
    # G14: section 2a is the state-first Assembly (AC) meter.
    assert "## 2a. Elections \u2014 Assembly (AC) coverage depth (state-first)" in md
    assert "Assam" in md
    # 2 events -> 2/7 with the rightmost two cells filled.
    assert "2/7" in md
    # G14: cohort table moved to 2c (was 2b before the AC/PC split).
    assert "## 2c. Elections \u2014 cohort (AC + PC, event-first)" in md


def test_render_markdown_includes_frontend_wiring_section(tmp_path: Path) -> None:
    """When ``topics.json`` is present, the inventory must report
    which indicators are wired vs unwired — the catalogue is hand-maintained
    (Holy Law #6 risk) and ~half the inventory was silently absent from the
    IA before this section existed."""
    _write(
        tmp_path / "datasets/taxonomy/entities.json",
        {
            "entities": [
                {
                    "entity_code": "S22",
                    "entity_type": "state",
                    "display_name": "Tamil Nadu",
                    "entity_valid_to": None,
                }
            ]
        },
    )
    _write(
        tmp_path / "datasets/taxonomy/election_events.json",
        {"states": {}},
    )
    _write(
        tmp_path / "datasets/taxonomy/topics.json",
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


# ---------------------------------------------------------------------------
# G14 (plan section 23.4 EL7): CSV walker discriminates AC vs PC.
# ---------------------------------------------------------------------------


def _seed_minimal_catalogue(tmp_path: Path) -> None:
    """Seed the bare minimum catalogue + entities files the walker needs."""
    _write(tmp_path / "datasets/taxonomy/entities.json", {"entities": []})
    _write(
        tmp_path / "datasets/taxonomy/election_events.json",
        {"states": {}},
    )


def test_walker_returns_ac_and_pc_rows(tmp_path: Path) -> None:
    """The two CSV walkers MUST yield both AC and PC slices when both trees
    are present on disk. This is the central G14 invariant: an aggregator
    silently blind to a whole election class is a latent reporting bug
    (plan section 23.4 EL7)."""
    _seed_minimal_catalogue(tmp_path)
    _seed_geo_csv(
        tmp_path,
        [
            ("tamil-nadu", "S22", "Tamil Nadu"),
            ("kerala", "S11", "Kerala"),
        ],
    )
    _seed_assembly_csv(
        tmp_path, state_slug="tamil-nadu", election_year=2021, n_acs=3
    )
    _seed_parliament_csv(
        tmp_path,
        election_year=2019,
        per_state={"tamil-nadu": 2, "kerala": 1},
    )

    from yen_gov.coverage import _polled_year_to_event

    catalogue: dict[str, object] = {"states": {}}
    slug_to_code = {"tamil-nadu": "S22", "kerala": "S11"}
    ac_map = _polled_year_to_event(catalogue, "AC")
    pc_map = _polled_year_to_event(catalogue, "PC")

    ac_rows = list(
        _walk_assembly_csv(
            tmp_path / "datasets/elections", ac_map, slug_to_code
        )
    )
    pc_rows = list(
        _walk_parliament_csv(
            tmp_path / "datasets/elections", pc_map, slug_to_code
        )
    )
    # Walker tuple layout: (ac_count, has_summary, has_parties, body).
    assert len(ac_rows) == 1
    assert ac_rows[0][0] == ("Ac2021", "S22")
    assert ac_rows[0][1] == (3, True, False, "AC")
    assert len(pc_rows) == 2
    pc_keys = {row[0] for row in pc_rows}
    assert pc_keys == {("Pc2019", "S11"), ("Pc2019", "S22")}
    for _, tup in pc_rows:
        assert tup[3] == "PC"
        assert tup[1] is True
        assert tup[2] is False


def test_render_markdown_contains_section_2b_pc_header(tmp_path: Path) -> None:
    """The PC section header MUST appear when at least one PC slice is on
    disk. A future PR that drops PC support should fail this test loudly."""
    _seed_minimal_catalogue(tmp_path)
    _seed_geo_csv(tmp_path, [("tamil-nadu", "S22", "Tamil Nadu")])
    _seed_parliament_csv(
        tmp_path, election_year=2019, per_state={"tamil-nadu": 2}
    )

    md = render_markdown(compute_coverage(tmp_path))
    assert "## 2b. Elections \u2014 Parliament (PC) coverage by cycle" in md
    assert "Parliament" in md


def test_render_markdown_contains_body_column_in_2c(tmp_path: Path) -> None:
    """Section 2c (combined AC+PC cohort) MUST carry a Body column so AC
    and PC slices can be told apart at a glance, and BOTH ``AC`` and ``PC``
    cells MUST appear in the rendered Markdown when both bodies are on disk.
    """
    _seed_minimal_catalogue(tmp_path)
    _seed_geo_csv(tmp_path, [("tamil-nadu", "S22", "Tamil Nadu")])
    _seed_assembly_csv(
        tmp_path, state_slug="tamil-nadu", election_year=2021, n_acs=1
    )
    _seed_parliament_csv(
        tmp_path, election_year=2019, per_state={"tamil-nadu": 1}
    )

    md = render_markdown(compute_coverage(tmp_path))
    assert "## 2c. Elections \u2014 cohort (AC + PC, event-first)" in md
    # 2c header row carries Body column.
    assert "| State | Code | Body | Rows |" in md
    # Both body kinds appear as cell values in the 2c table. The pipe-
    # framed cell text is deterministic; the regex would be overkill.
    c2_start = md.index("## 2c. Elections")
    c2_block = md[c2_start:]
    assert "| AC |" in c2_block
    assert "| PC |" in c2_block


def test_summary_counts_ac_and_pc_separately(tmp_path: Path) -> None:
    """The top-of-report Summary list MUST split AC and PC counts onto
    separate bullet lines so a reader can see at a glance how many slices
    of each body are on disk. A single combined count would silently mask
    a 'PC went to zero' regression."""
    _seed_minimal_catalogue(tmp_path)
    _seed_geo_csv(
        tmp_path,
        [
            ("tamil-nadu", "S22", "Tamil Nadu"),
            ("kerala", "S11", "Kerala"),
        ],
    )
    _seed_assembly_csv(
        tmp_path, state_slug="tamil-nadu", election_year=2021, n_acs=2
    )
    _seed_parliament_csv(
        tmp_path,
        election_year=2019,
        per_state={"tamil-nadu": 1, "kerala": 1},
    )

    md = render_markdown(compute_coverage(tmp_path))
    # Find the Summary section block; both AC and PC bullets must exist.
    sum_start = md.index("## Summary")
    sum_block = md[sum_start:].split("##", 2)[1]  # everything up to next h2
    assert "- Assembly (AC):" in sum_block
    assert "- Parliament (PC):" in sum_block
    # Counts are correct: 1 AC slice + 2 PC slices.
    assert "Assembly (AC): 1 slice" in sum_block
    assert "Parliament (PC): 2 slice" in sum_block


def test_ac_only_walk_back_compat(tmp_path: Path) -> None:
    """When only the assembly tree exists on disk, the walker MUST behave
    exactly as the AC-only history of this report did: every emitted slice
    carries ``body='AC'`` (the dataclass default), no PC rows appear, and
    the rendered Markdown still has section 2a (state-first AC meter).
    Section 2b (PC) MUST surface the 'No on-disk Parliament slices yet'
    fallback rather than disappearing entirely."""
    _seed_minimal_catalogue(tmp_path)
    _seed_geo_csv(tmp_path, [("tamil-nadu", "S22", "Tamil Nadu")])
    _seed_assembly_csv(
        tmp_path, state_slug="tamil-nadu", election_year=2021, n_acs=2
    )

    report = compute_coverage(tmp_path)
    on_disk = [s for s in report.slices if s.on_disk]
    assert len(on_disk) == 1
    assert on_disk[0].body == "AC"
    assert on_disk[0].state_code == "S22"
    assert on_disk[0].ac_count == 2
    # No PC slices materialised when the parliament tree is absent.
    assert not any(s.body == "PC" for s in report.slices if s.on_disk)

    md = render_markdown(report)
    assert "## 2a. Elections \u2014 Assembly (AC) coverage depth (state-first)" in md
    # 2b is still rendered (so PC doesn't silently disappear); it surfaces
    # the empty-state placeholder.
    assert "## 2b. Elections \u2014 Parliament (PC) coverage by cycle" in md
    assert "_No on-disk Parliament slices yet._" in md

