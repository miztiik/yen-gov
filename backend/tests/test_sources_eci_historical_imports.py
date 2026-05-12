"""Anchor tests for the historical (2016-2023) hand-imported assembly elections.

These elections were ingested via ``python -m yen_gov eci-statreport-emit-local``
from XLSX files hand-downloaded into ``datasets/raw_ephemeral_datasets/`` (the
files are deleted on successful emit). All artifacts carry ``sources: []``
per ADR-0002 (hand-authored signal).

Rather than retesting the parser against raw bytes (which we no longer have on
disk), this module pins KNOWN-TRUTH winner / total / candidate-field values
from the emitted JSON. Anchors are chosen across all three Section 10 layouts:

  Layout A (2019+): STATE/UT NAME + TURN OUT/TURNOUT sentinel + 14-15 cols.
                    Fixture: Delhi-2020, Bihar-2020.
  Layout B (2016-2017): No STATE col, no TURN OUT sentinel; AC boundary via
                        Constituency No. change. Fixture: Assam-2016, Goa-2017.
  Layout C (2018): No header row at all; ``Constituency <n> . <name>`` marker.
                   Fixture: Karnataka-2018.

The anchors verify the layout-specific code paths emit identical
schema-conformant artifacts. Any future parser change that drops gender/
age/category or breaks vote totals will fire one of these.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ELECTIONS = ROOT / "datasets" / "elections"


def _load(event: str, state: str, eci_no: int) -> dict:
    return json.loads(
        (ELECTIONS / event / state / "results" / f"{eci_no}.json").read_text(
            encoding="utf-8"
        )
    )


# -----------------------------------------------------------------------------
# Layout B — Assam 2016 (no STATE col, no TURN OUT sentinel)
# -----------------------------------------------------------------------------
def test_layout_b_assam_2016_ac1_ratabari() -> None:
    d = _load("AcGenApr2016", "S03", 1)
    assert d["constituency_name"] == "Ratabari"
    assert d["sources"] == []  # hand-authored signal
    assert d["winner"]["name"] == "KRIPANATH MALLAH"
    assert d["winner"]["party_short"] == "BJP"
    assert d["winner"]["votes"] == 53975
    # Layout B has Candidate Sex/Age/Category columns; values must propagate.
    top = d["candidates"][0]
    assert top["gender"] == "M"
    assert top["age"] == 40
    assert top["category"] == "SC"


def test_layout_b_goa_2017_ac1_mandrem() -> None:
    d = _load("AcGenFeb2017", "S05", 1)
    assert d["constituency_name"] == "Mandrem"
    assert d["winner"]["name"] == "DAYANAND RAGHUNATH SOPTE"
    assert d["winner"]["party_short"] == "INC"
    assert d["winner"]["votes"] == 16490


# -----------------------------------------------------------------------------
# Layout C — Karnataka 2018 (no header; "Constituency N . Name" marker rows)
# -----------------------------------------------------------------------------
def test_layout_c_karnataka_2018_ac1_nippani() -> None:
    d = _load("AcGenMay2018", "S10", 1)
    assert d["constituency_name"] == "Nippani"
    assert d["sources"] == []
    assert d["totals"]["electors"] == 212456
    top = d["candidates"][0]
    assert top["name"] == "JOLLE SHASHIKALA ANNASAHEB"
    assert top["party_short"] == "BJP"
    assert top["votes"] == 87006
    # Layout C carries gender/age/category positionally; verify they flow through.
    assert top["gender"] == "F"
    assert top["age"] == 49
    assert top["category"] == "GEN"


# -----------------------------------------------------------------------------
# Layout A historical (TURNOUT/TURN OUT spacing tolerance) — Delhi 2020
# -----------------------------------------------------------------------------
def test_layout_a_delhi_2020_ac1_narela() -> None:
    d = _load("AcGenFeb2020", "U05", 1)
    # NCT of Delhi state token preserved on disk via --state inference.
    assert d["state"] == "U05"
    assert d["constituency_name"] == "NARELA"
    assert d["winner"]["name"] == "SHARAD KUMAR"
    assert d["winner"]["party_short"] == "AAAP"
    assert d["winner"]["votes"] == 86262


def test_historical_events_all_have_summary() -> None:
    """Every historical event registered in events.py must have a result.summary.json."""
    expected = [
        ("AcGenApr2016", "S03"), ("AcGenMay2016", "S11"),
        ("AcGenFeb2017", "S05"), ("AcGenNov2017", "S08"),
        ("AcGenMay2018", "S10"),
        ("AcGenApr2019", "S01"), ("AcGenOct2019", "S07"),
        ("AcGenDec2019", "S27"),
        ("AcGenFeb2020", "U05"), ("AcGenNov2020", "S04"),
        ("AcGenApr2021", "S03"), ("AcGenApr2021", "S11"),
        ("AcGenFeb2022", "S05"), ("AcGenNov2022", "S08"),
        ("AcGenMay2023", "S10"),
    ]
    for event, state in expected:
        p = ELECTIONS / event / state / "result.summary.json"
        assert p.exists(), f"missing {p.relative_to(ROOT).as_posix()}"
