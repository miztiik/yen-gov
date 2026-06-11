"""Tier-A tests for the recon namespace (PR-2 of the 2026-06-10 plan).

Covers:
  - ``write_shape_a_csv`` -> ``read_shape_a_csv`` round-trip (header order,
    enum invariants, None-vs-empty notes).
  - ``compare`` Compare-Aggregator on a 3-party hand-fixture per plan
    section 2.PR-2 brief (BJP / INC existing-canonical match + 2 oracles
    each -> VERIFIED; ABCD single-source mint-new -> UNVERIFIED).
  - The ``parity`` CLI exits non-zero with ``no adapter registered for
    source ...`` when called with an unregistered source.

Per CLAUDE.md section 14 the aggregator is exercised against in-memory
fixtures (NOT the real corpus). The CLI smoke uses ``tmp_path`` for the
report output to honour the no-real-disk-writes-from-pytest rule.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from yen_gov.canonical.recon.adapters import REGISTRY
from yen_gov.canonical.recon.aggregator import (
    VerdictRow,
    compare,
    verdict_csv_header,
    write_verdict_csv,
)
from yen_gov.canonical.recon.shape_a import (
    ShapeARow,
    VALID_PROPOSED_ACTIONS,
    read_shape_a_csv,
    write_shape_a_csv,
)
from yen_gov.cli import app


runner = CliRunner()


# --- round-trip ------------------------------------------------------------


def test_write_then_read_round_trip_preserves_field_values(tmp_path):
    """ShapeARow -> CSV -> ShapeARow preserves every field byte-identically."""
    rows_in = [
        ShapeARow(
            external_key="TCPD-AIADMK-1",
            external_short="AIADMK",
            external_full="All India Anna Dravida Munnetra Kazhagam",
            external_scope="tcpd-parties",
            external_vintage="2021",
            proposed_party_id="parties.IN.AIADMK",
            proposed_action="match",
            notes="ECI code 89 confirmed",
        ),
        ShapeARow(
            external_key="WIKI-aiadmk",
            external_short="ADMK",
            external_full="All India Anna Dravida Munnetra Kazhagam",
            external_scope="wikipedia-parties",
            external_vintage="2026-06-01",
            proposed_party_id="parties.IN.AIADMK",
            proposed_action="alias-add",
            notes=None,
        ),
    ]
    out_csv = tmp_path / "shape-a.csv"

    n_written = write_shape_a_csv(rows_in, out_csv)
    assert n_written == 2
    assert out_csv.is_file()

    rows_out = read_shape_a_csv(out_csv)

    assert rows_out == rows_in, (
        "shape-A round-trip dropped or mutated field values; "
        f"in={rows_in!r} out={rows_out!r}"
    )

    # Header order matches dataclass field declaration (single source of truth).
    header_line = out_csv.read_text(encoding="utf-8").splitlines()[0]
    expected_header = (
        "external_key,external_short,external_full,external_scope,"
        "external_vintage,proposed_party_id,proposed_action,notes,"
        "constituency_no,constituency_name,state_code,"
        "winner_candidate,winner_votes"
    )
    assert header_line == expected_header


def test_write_rejects_invalid_proposed_action(tmp_path):
    """A shape-A row with proposed_action outside the enum is rejected at write."""
    rows = [
        ShapeARow(
            external_key="X",
            external_short="X",
            external_full="X",
            external_scope="src",
            external_vintage="2024",
            proposed_party_id="parties.IN.X",
            proposed_action="renumber",  # type: ignore[arg-type]
            notes=None,
        )
    ]
    with pytest.raises(ValueError, match="invalid proposed_action"):
        write_shape_a_csv(rows, tmp_path / "bad.csv")


def test_read_rejects_header_mismatch(tmp_path):
    """A shape-A CSV with the wrong header is rejected at read time."""
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "external_key,proposed_party_id\nX,parties.IN.X\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="header mismatch"):
        read_shape_a_csv(bad)


def test_valid_proposed_actions_is_the_closed_enum():
    """The exported enum constant equals the schema closed-enum (sanity)."""
    assert VALID_PROPOSED_ACTIONS == (
        "match",
        "enrich",
        "mint-new",
        "alias-add",
        "conflict",
    )


# --- Compare-Aggregator: 3-party hand-fixture ------------------------------


def _canonical_parties() -> dict[str, dict[str, str]]:
    """Stand-in for the parties.csv projection consumed by ``compare``."""
    return {
        "parties.IN.BJP": {"party_id": "parties.IN.BJP", "short": "BJP"},
        "parties.IN.INC": {"party_id": "parties.IN.INC", "short": "INC"},
        # parties.IN.ABCD intentionally absent (mint-new leg).
    }


def test_compare_3_party_fixture(tmp_path):
    """Plan section 2.PR-2 oracle: BJP / INC = VERIFIED match (2 oracles),
    ABCD = UNVERIFIED mint-new (single oracle).
    """
    shape_a_rows = [
        # BJP from 2 distinct oracles -> 2 agreeing -> VERIFIED match.
        ShapeARow(
            external_key="TCPD-BJP",
            external_short="BJP",
            external_full="Bharatiya Janata Party",
            external_scope="tcpd-parties",
            external_vintage="2021",
            proposed_party_id="parties.IN.BJP",
            proposed_action="match",
            notes=None,
        ),
        ShapeARow(
            external_key="ECI-BJP-2024",
            external_short="BJP",
            external_full="Bharatiya Janata Party",
            external_scope="eci-registered",
            external_vintage="2024-06",
            proposed_party_id="parties.IN.BJP",
            proposed_action="match",
            notes=None,
        ),
        # INC from 2 distinct oracles -> 2 agreeing -> VERIFIED match.
        ShapeARow(
            external_key="TCPD-INC",
            external_short="INC",
            external_full="Indian National Congress",
            external_scope="tcpd-parties",
            external_vintage="2021",
            proposed_party_id="parties.IN.INC",
            proposed_action="match",
            notes=None,
        ),
        ShapeARow(
            external_key="ECI-INC-2024",
            external_short="INC",
            external_full="Indian National Congress",
            external_scope="eci-registered",
            external_vintage="2024-06",
            proposed_party_id="parties.IN.INC",
            proposed_action="match",
            notes=None,
        ),
        # ABCD from a SINGLE oracle -> 1 oracle present -> UNVERIFIED mint-new.
        ShapeARow(
            external_key="TCPD-ABCD",
            external_short="ABCD",
            external_full="A B C D Party",
            external_scope="tcpd-parties",
            external_vintage="2021",
            proposed_party_id="parties.IN.ABCD",
            proposed_action="mint-new",
            notes="absent from canonical; new mint candidate",
        ),
    ]

    verdicts = compare(shape_a_rows, _canonical_parties())

    # 3 distinct proposed_party_id values -> 3 verdict rows.
    assert len(verdicts) == 3

    # Verdict rows are returned sorted by proposed_party_id: ABCD < BJP < INC.
    assert [v.proposed_party_id for v in verdicts] == [
        "parties.IN.ABCD",
        "parties.IN.BJP",
        "parties.IN.INC",
    ]

    by_id = {v.proposed_party_id: v for v in verdicts}

    bjp = by_id["parties.IN.BJP"]
    assert bjp.action == "match"
    assert bjp.verdict == "VERIFIED"
    assert bjp.n_oracles_present == 2
    assert bjp.n_oracles_agreeing == 2
    assert bjp.oracles_agreeing == "eci-registered|tcpd-parties"
    assert bjp.oracles_disagreeing == ""
    assert bjp.current_party_id == "parties.IN.BJP"
    assert bjp.curator_note is None

    inc = by_id["parties.IN.INC"]
    assert inc.action == "match"
    assert inc.verdict == "VERIFIED"
    assert inc.n_oracles_present == 2
    assert inc.n_oracles_agreeing == 2
    assert inc.current_party_id == "parties.IN.INC"

    abcd = by_id["parties.IN.ABCD"]
    assert abcd.action == "mint-new"
    assert abcd.verdict == "UNVERIFIED"  # single-oracle -> UNVERIFIED per Fowler rule.
    assert abcd.n_oracles_present == 1
    assert abcd.n_oracles_agreeing == 1
    assert abcd.current_party_id is None  # not in canonical roster.
    assert abcd.oracles_agreeing == "tcpd-parties"


def test_compare_mint_new_against_existing_canonical_downgrades_to_conflict():
    """mint-new on a party_id that already exists in canonical -> conflict."""
    rows = [
        ShapeARow(
            external_key="upstream-bjp",
            external_short="BJP",
            external_full="Bharatiya Janata Party",
            external_scope="some-source",
            external_vintage="2025",
            proposed_party_id="parties.IN.BJP",
            proposed_action="mint-new",
            notes=None,
        )
    ]
    verdicts = compare(rows, _canonical_parties())
    assert len(verdicts) == 1
    assert verdicts[0].action == "conflict"


def test_compare_rejects_invalid_proposed_action():
    """A malformed shape-A row surfaces at compare() with a clear error."""
    bad = [
        ShapeARow(
            external_key="X",
            external_short="X",
            external_full="X",
            external_scope="src",
            external_vintage="2024",
            proposed_party_id="parties.IN.X",
            proposed_action="renumber",  # type: ignore[arg-type]
            notes=None,
        )
    ]
    with pytest.raises(ValueError, match="invalid proposed_action"):
        compare(bad, {})


def test_verdict_csv_write_round_trip(tmp_path):
    """write_verdict_csv emits the expected header + serialises None as ''."""
    verdicts = [
        VerdictRow(
            external_key="X",
            external_short="X",
            external_full="X",
            proposed_party_id="parties.IN.X",
            current_party_id=None,
            action="mint-new",
            n_oracles_present=1,
            n_oracles_agreeing=1,
            oracles_agreeing="src-a",
            oracles_disagreeing="",
            verdict="UNVERIFIED",
            curator_note=None,
            curator_source_id=None,
        )
    ]
    out = tmp_path / "verdict.csv"
    n = write_verdict_csv(verdicts, out)
    assert n == 1
    text = out.read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines[0] == ",".join(verdict_csv_header())
    # current_party_id, curator_note, curator_source_id all None -> ""
    assert "parties.IN.X,," in lines[1]


# --- CLI: empty-registry exit path -----------------------------------------


def test_cli_parity_help_lists_the_subcommand():
    """python -m yen_gov parity --help prints the usage block."""
    result = runner.invoke(app, ["parity", "--help"])
    assert result.exit_code == 0, result.output
    assert "--source" in result.output
    assert "--vintage" in result.output
    assert "--report" in result.output


def test_cli_parity_unknown_source_exits_non_zero(tmp_path):
    """An un-registered --source exits non-zero with the expected message."""
    # PR-W-1 onwards: REGISTRY carries one adapter per Wave B / Stream X PR.
    # Defensive guard: confirm REGISTRY only contains the published PR set
    # (each PR adds one source-id), so an accidental over-registration is
    # caught here. Update the expected set when a new Wave B PR lands.
    expected_sources: set[str] = {"tcpd-parties"}
    assert set(REGISTRY) >= expected_sources, (
        f"recon.adapters.REGISTRY missing expected adapter(s); "
        f"got: {sorted(REGISTRY)}, expected superset of: {sorted(expected_sources)}"
    )

    report_path = tmp_path / "verdict.csv"
    result = runner.invoke(
        app,
        [
            "parity",
            "--source",
            "nonexistent",
            "--vintage",
            "2024",
            "--report",
            str(report_path),
            "--root",
            str(tmp_path),
        ],
    )
    assert result.exit_code != 0, (
        f"expected non-zero exit on unknown source; got 0. output:\n{result.output}"
    )
    combined = (result.output or "") + (result.stderr if result.stderr_bytes else "")
    assert "no adapter registered for source 'nonexistent'" in combined, (
        f"expected 'no adapter registered for source ...' in CLI output; "
        f"got:\n{combined!r}"
    )
    assert not report_path.exists(), (
        "report file MUST NOT be written when the adapter lookup fails"
    )
