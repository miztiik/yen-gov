"""Tests for the SQLite emitter (docs/architecture/backend/emit-sqlite.md).

Uses the committed TN slice as a fixture so the test exercises real shape
without re-fetching from ECI.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from yen_gov.emit.sqlite import USER_VERSION, emit_state_sqlite

REPO_ROOT = Path(__file__).resolve().parents[2]
TN_DIR = REPO_ROOT / "datasets" / "elections" / "AcGenMay2026" / "S22"


pytestmark = pytest.mark.skipif(
    not (TN_DIR / "parties.json").exists(),
    reason="TN AcGenMay2026/S22 dataset not present; run `yen-gov run` first",
)


def test_emit_creates_sqlite_with_user_version(tmp_path: Path) -> None:
    out = emit_state_sqlite(state_dir=TN_DIR, output_path=tmp_path / "results.sqlite")
    assert out.exists()
    conn = sqlite3.connect(out)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == USER_VERSION
    finally:
        conn.close()


def test_emit_party_totals_view_matches_summary(tmp_path: Path) -> None:
    """The view's seats-by-party should agree with result.summary.json."""
    import json
    summary = json.loads((TN_DIR / "result.summary.json").read_text(encoding="utf-8"))
    expected = {
        row["party_short"]: row["seats_won"]
        for row in summary["party_totals"]
        if row["seats_won"] > 0
    }

    out = emit_state_sqlite(state_dir=TN_DIR, output_path=tmp_path / "results.sqlite")
    conn = sqlite3.connect(out)
    try:
        actual = {
            short: seats for short, seats, _votes in
            conn.execute("SELECT party_short, seats_won, votes FROM party_totals WHERE seats_won > 0")
        }
    finally:
        conn.close()
    assert actual == expected


def test_emit_is_byte_deterministic(tmp_path: Path) -> None:
    """Same JSON inputs → byte-identical .sqlite outputs (docs/architecture/backend/emit-sqlite.md)."""
    a = emit_state_sqlite(state_dir=TN_DIR, output_path=tmp_path / "a.sqlite")
    b = emit_state_sqlite(state_dir=TN_DIR, output_path=tmp_path / "b.sqlite")
    assert a.read_bytes() == b.read_bytes()


def test_emit_includes_nota_rows(tmp_path: Path) -> None:
    out = emit_state_sqlite(state_dir=TN_DIR, output_path=tmp_path / "results.sqlite")
    conn = sqlite3.connect(out)
    try:
        nota_count = conn.execute(
            "SELECT COUNT(*) FROM candidates WHERE is_nota = 1"
        ).fetchone()[0]
        # Every AC has a NOTA row in the source JSON.
        constituency_count = conn.execute(
            "SELECT COUNT(*) FROM constituencies"
        ).fetchone()[0]
        assert nota_count == constituency_count
        # NOTA rows are excluded from party_totals.
        nota_in_view = conn.execute(
            "SELECT COUNT(*) FROM party_totals WHERE party_short = 'NOTA'"
        ).fetchone()[0]
        assert nota_in_view == 0
    finally:
        conn.close()


def test_emit_winner_count_equals_constituency_count(tmp_path: Path) -> None:
    out = emit_state_sqlite(state_dir=TN_DIR, output_path=tmp_path / "results.sqlite")
    conn = sqlite3.connect(out)
    try:
        winners = conn.execute("SELECT COUNT(*) FROM candidates WHERE is_winner = 1").fetchone()[0]
        constituencies = conn.execute("SELECT COUNT(*) FROM constituencies").fetchone()[0]
        assert winners == constituencies
    finally:
        conn.close()
