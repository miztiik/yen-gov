"""Tests for the SQLite emitter (docs/architecture/backend/emit-sqlite.md).

Uses an in-memory fixture (tests/_emit_fixtures.py) so the tests exercise the
emitter against a representative shape without depending on the real corpus.
Per CLAUDE.md §10: pytest tests CODE, not DATA — walking
`datasets/elections/AcGenMay2026/S22/` from a pytest test crosses that line.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from yen_gov.emit.sqlite import (
    USER_VERSION,
    emit_state_sqlite,
    emit_state_sqlite_from_data,
)

from tests import _emit_fixtures


def _write_disk_slice(state_dir: Path) -> None:
    """Materialise the in-memory fixture as parties.json + results/<n>.json
    so the disk-wrapper `emit_state_sqlite(state_dir=...)` has files to read."""
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "parties.json").write_text(
        json.dumps(_emit_fixtures.parties_doc(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    results_dir = state_dir / "results"
    results_dir.mkdir(exist_ok=True)
    for cr in _emit_fixtures.constituencies():
        (results_dir / f"{cr['eci_no']}.json").write_text(
            json.dumps(cr, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def test_emit_creates_sqlite_with_user_version(tmp_path: Path) -> None:
    out = emit_state_sqlite_from_data(
        parties_doc=_emit_fixtures.parties_doc(),
        constituencies=_emit_fixtures.constituencies(),
        output_path=tmp_path / "results.sqlite",
    )
    assert out.exists()
    conn = sqlite3.connect(out)
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        assert version == USER_VERSION
    finally:
        conn.close()


def test_emit_party_totals_view_seats_match_winners(tmp_path: Path) -> None:
    """The party_totals view's seats_won column should agree with the
    candidate is_winner flags. Fixture: DMK=2 wins, AIADMK=1 win, INC=0."""
    out = emit_state_sqlite_from_data(
        parties_doc=_emit_fixtures.parties_doc(),
        constituencies=_emit_fixtures.constituencies(),
        output_path=tmp_path / "results.sqlite",
    )
    conn = sqlite3.connect(out)
    try:
        actual = {
            short: seats for short, seats, _votes in
            conn.execute("SELECT party_short, seats_won, votes FROM party_totals WHERE seats_won > 0")
        }
    finally:
        conn.close()
    assert actual == {"DMK": 2, "AIADMK": 1}


def test_emit_is_byte_deterministic(tmp_path: Path) -> None:
    """Same inputs → byte-identical .sqlite outputs (docs/architecture/backend/emit-sqlite.md)."""
    a = emit_state_sqlite_from_data(
        parties_doc=_emit_fixtures.parties_doc(),
        constituencies=_emit_fixtures.constituencies(),
        output_path=tmp_path / "a.sqlite",
    )
    b = emit_state_sqlite_from_data(
        parties_doc=_emit_fixtures.parties_doc(),
        constituencies=_emit_fixtures.constituencies(),
        output_path=tmp_path / "b.sqlite",
    )
    assert a.read_bytes() == b.read_bytes()


def test_emit_includes_nota_rows(tmp_path: Path) -> None:
    out = emit_state_sqlite_from_data(
        parties_doc=_emit_fixtures.parties_doc(),
        constituencies=_emit_fixtures.constituencies(),
        output_path=tmp_path / "results.sqlite",
    )
    conn = sqlite3.connect(out)
    try:
        nota_count = conn.execute(
            "SELECT COUNT(*) FROM candidates WHERE is_nota = 1"
        ).fetchone()[0]
        constituency_count = conn.execute(
            "SELECT COUNT(*) FROM constituencies"
        ).fetchone()[0]
        # Every AC in the fixture has a NOTA row.
        assert nota_count == constituency_count
        # NOTA rows are excluded from party_totals.
        nota_in_view = conn.execute(
            "SELECT COUNT(*) FROM party_totals WHERE party_short = 'NOTA'"
        ).fetchone()[0]
        assert nota_in_view == 0
    finally:
        conn.close()


def test_emit_winner_count_equals_constituency_count(tmp_path: Path) -> None:
    out = emit_state_sqlite_from_data(
        parties_doc=_emit_fixtures.parties_doc(),
        constituencies=_emit_fixtures.constituencies(),
        output_path=tmp_path / "results.sqlite",
    )
    conn = sqlite3.connect(out)
    try:
        winners = conn.execute("SELECT COUNT(*) FROM candidates WHERE is_winner = 1").fetchone()[0]
        constituencies = conn.execute("SELECT COUNT(*) FROM constituencies").fetchone()[0]
        assert winners == constituencies
    finally:
        conn.close()


def test_disk_wrapper_matches_in_memory(tmp_path: Path) -> None:
    """Byte-identity proof: the disk-read wrapper produces the same .sqlite
    bytes as the in-memory primary API for the same data. This guards the
    PR-O.3a refactor: the wrapper must be a pure pass-through, not a
    semantic detour."""
    state_dir = tmp_path / "state"
    _write_disk_slice(state_dir)

    via_disk = emit_state_sqlite(
        state_dir=state_dir, output_path=tmp_path / "via_disk.sqlite",
    )
    via_memory = emit_state_sqlite_from_data(
        parties_doc=_emit_fixtures.parties_doc(),
        constituencies=_emit_fixtures.constituencies(),
        output_path=tmp_path / "via_memory.sqlite",
    )
    assert via_disk.read_bytes() == via_memory.read_bytes()
