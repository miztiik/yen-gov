"""Tests for the Section 10 Detailed Results parser, covering BOTH layouts:

  - 2024+ 15-col layout (e.g. TN-2026): separate "OVER VALID VOTES + NOTA"
    and "OVER TOTAL ELECTORS" % columns plus "TOTAL ELECTORS".
  - 2023 14-col layout (MP / Chh / Miz / Telangana): single "% VOTES POLLED"
    column plus "TOTAL ELECTORS".

Both fixtures are populated by running the pipeline once
(``python -m yen_gov eci-statreport-emit <S> <year>``) which leaves the
raw XLSX under ``.runtime/raw/eci/...``. CI / fresh checkouts skip these.

The point is to LOCK IN the header-name-based column resolution:
re-introducing the old hardcoded indices would silently break MP-2023's
turnout & elector readings (off-by-one) but keep parsing 2024+, which is
exactly the kind of regression a single-layout test would miss.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yen_gov.sources.eci.statistical_report_detailed import parse_detailed_results

ROOT = Path(__file__).resolve().parents[2]

TN_2026_XLSX = (
    ROOT / ".runtime" / "raw" / "eci" / "eci-backend" / "public" / "all_files"
    / "election_report"
    / "General_Election_to_the_Legislative_Assembly_of_Tamil_Nadu_2026_2026"
    / "10-Detailed_Results_1778165153.xlsx"
)
MP_2023_XLSX = (
    ROOT / ".runtime" / "raw" / "eci" / "eci-backend" / "public" / "all_files"
    / "full-statistical-reports" / "mp" / "2023" / "Detailed_Results.xlsx"
)


@pytest.mark.skipif(
    not TN_2026_XLSX.exists(),
    reason="raw TN-2026 Section 10 fixture not downloaded; run "
           "eci-statreport S22 2026 --download --skip-pdf to populate",
)
def test_parses_2024_plus_15_col_layout() -> None:
    """TN-2026 — 15-col layout with separate over-electors %."""
    raw = parse_detailed_results(TN_2026_XLSX.read_bytes())

    # TN has 234 ACs; all should parse.
    assert len(raw.sections) == 234

    # AC #1 (Gummidipoondi) — known winner is S.vijayakumar (TVK).
    s = raw.sections[0]
    assert s.eci_no == 1
    assert s.constituency_name == "GUMMIDIPOONDI"
    # Turnout-over-electors comes from the dedicated 2024+ column.
    assert s.turnout_pct == 91.48
    assert s.total_electors == 254175
    top = s.candidates[0]
    assert top.name == "S.vijayakumar"
    assert top.party_short == "TVK"
    assert top.votes_total == 94320


@pytest.mark.skipif(
    not MP_2023_XLSX.exists(),
    reason="raw MP-2023 Section 10 fixture not downloaded; run "
           "eci-statreport-emit S12 2023 to populate",
)
def test_parses_2023_14_col_layout() -> None:
    """MP-2023 — 14-col layout with single % column doubling as turnout."""
    raw = parse_detailed_results(MP_2023_XLSX.read_bytes())

    # MP has 230 ACs; all should parse.
    assert len(raw.sections) == 230

    # AC #1 (Sheopur) — known winner is INC's Babu Jandel (per ECI).
    s = raw.sections[0]
    assert s.eci_no == 1
    assert s.constituency_name == "Sheopur"
    # Turnout reading must use the SINGLE % column (idx 12), not 2024+'s
    # missing idx 13 — the regression guard for the parser refactor.
    assert s.turnout_pct == 81.83
    # Total electors reading must use idx 13 (2023 layout), not idx 14
    # (which is out-of-range for 14-col rows). Off-by-one would silently
    # drop electors to None for every AC.
    assert s.total_electors == 258978
    top = s.candidates[0]
    assert top.name == "Babu Jandel"
    assert top.party_short == "INC"
    assert top.votes_total == 96844


def test_null_token_treated_as_missing() -> None:
    """Pre-2019 Statistical Reports use literal 'NULL' in vote columns for
    ACs where no poll was held (uncontested winner declared, e.g.
    Northern Angami-II 2018 with Neiphiu Rio unopposed; countermanded
    polls, e.g. Williamnagar 2018 in Meghalaya). The coercers must treat
    'NULL' (and any case variant) the same way they treat '' and '-':
    zero for int/float, None for the percentage-or-none variant.

    Regression guard: this used to raise ``ValueError: could not convert
    string to float: 'NULL'`` and blocked ingest of Meghalaya / Nagaland
    2018 Statistical Reports until a follow-up fix landed.
    """
    from yen_gov.sources.eci.statistical_report_detailed import (
        _to_float,
        _to_float_or_none,
        _to_int,
    )

    for tok in ("NULL", "null", "Null", " NULL ", "null\n"):
        assert _to_int(tok) == 0
        assert _to_float(tok) == 0.0
        assert _to_float_or_none(tok) is None

    # Existing missing-token semantics preserved.
    assert _to_int("") == 0
    assert _to_int("-") == 0
    assert _to_int(None) == 0
    assert _to_float_or_none("-") is None
    assert _to_float_or_none(None) is None

    # Real values still parse.
    assert _to_int("1,234") == 1234
    assert _to_float("81.83%") == 81.83
