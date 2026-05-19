"""Tests for the CSV bundle emitter (docs/architecture/backend/emit-csv.md).

Uses an in-memory fixture (tests/_emit_fixtures.py) so the tests exercise the
emitter against a representative shape without depending on the real corpus.
Per CLAUDE.md §10: pytest tests CODE, not DATA — walking
`datasets/elections/AcGenMay2026/S22/` from a pytest test crosses that line.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from yen_gov.emit.csv_bundle import (
    LAYOUT_VERSION,
    _COLUMNS,
    emit_state_csv,
    emit_state_csv_from_data,
)

from tests import _emit_fixtures


def _read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _write_disk_slice(state_dir: Path) -> None:
    """Materialise the in-memory fixture as results/<n>.json so the
    disk-wrapper `emit_state_csv(state_dir=...)` has files to read."""
    results_dir = state_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    for cr in _emit_fixtures.constituencies():
        (results_dir / f"{cr['eci_no']}.json").write_text(
            json.dumps(cr, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def test_layout_version_is_documented() -> None:
    assert LAYOUT_VERSION == 1


def test_emit_creates_csv_with_expected_columns(tmp_path: Path) -> None:
    out = emit_state_csv_from_data(
        constituencies=_emit_fixtures.constituencies(),
        output_path=tmp_path / "results.csv",
    )
    assert out.exists()
    with out.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
    assert header == _COLUMNS


def test_emit_uses_unix_line_endings(tmp_path: Path) -> None:
    """Determinism: `\\n` only, never `\\r\\n`. Platform-native line endings
    would break byte-identical regeneration on Windows vs Linux CI."""
    out = emit_state_csv_from_data(
        constituencies=_emit_fixtures.constituencies(),
        output_path=tmp_path / "results.csv",
    )
    raw = out.read_bytes()
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")


def test_emit_is_byte_deterministic(tmp_path: Path) -> None:
    a = emit_state_csv_from_data(
        constituencies=_emit_fixtures.constituencies(),
        output_path=tmp_path / "a.csv",
    )
    b = emit_state_csv_from_data(
        constituencies=_emit_fixtures.constituencies(),
        output_path=tmp_path / "b.csv",
    )
    assert a.read_bytes() == b.read_bytes()


def test_emit_includes_one_winner_per_constituency(tmp_path: Path) -> None:
    out = emit_state_csv_from_data(
        constituencies=_emit_fixtures.constituencies(),
        output_path=tmp_path / "results.csv",
    )
    rows = _read_rows(out)
    winners_per_ac: dict[str, int] = {}
    constituencies: set[str] = set()
    for r in rows:
        constituencies.add(r["ac_eci_no"])
        if r["is_winner"] == "1":
            winners_per_ac[r["ac_eci_no"]] = winners_per_ac.get(r["ac_eci_no"], 0) + 1
    assert constituencies, "no constituencies emitted"
    assert set(winners_per_ac) == constituencies
    assert all(count == 1 for count in winners_per_ac.values())


def test_emit_includes_nota_row_per_constituency(tmp_path: Path) -> None:
    """Every AC in the fixture has a NOTA row; the CSV must reflect that."""
    out = emit_state_csv_from_data(
        constituencies=_emit_fixtures.constituencies(),
        output_path=tmp_path / "results.csv",
    )
    rows = _read_rows(out)
    constituencies: set[str] = set()
    nota_acs: set[str] = set()
    for r in rows:
        constituencies.add(r["ac_eci_no"])
        if r["is_nota"] == "1":
            assert r["candidate_name"] == "NOTA"
            assert r["party_short"] == "NOTA"
            assert r["is_winner"] == "0"
            nota_acs.add(r["ac_eci_no"])
    assert nota_acs == constituencies


def test_emit_rows_sorted_by_ac_then_rank(tmp_path: Path) -> None:
    out = emit_state_csv_from_data(
        constituencies=_emit_fixtures.constituencies(),
        output_path=tmp_path / "results.csv",
    )
    rows = _read_rows(out)
    keys = [(int(r["ac_eci_no"]), int(r["rank"])) for r in rows]
    assert keys == sorted(keys)


def test_emit_long_format_matches_in_memory_winners(tmp_path: Path) -> None:
    """Winner column in the CSV must equal the winner from each ConstituencyResult dict."""
    cs = _emit_fixtures.constituencies()
    out = emit_state_csv_from_data(
        constituencies=cs,
        output_path=tmp_path / "results.csv",
    )
    rows = _read_rows(out)
    csv_winner_by_ac: dict[int, str] = {}
    for r in rows:
        if r["is_winner"] == "1":
            csv_winner_by_ac[int(r["ac_eci_no"])] = r["candidate_name"]

    for cr in cs:
        eci_no = cr["eci_no"]
        expected = cr["winner"]["name"]
        assert csv_winner_by_ac.get(eci_no) == expected, (
            f"winner mismatch for AC {eci_no}: csv={csv_winner_by_ac.get(eci_no)!r}, in-memory={expected!r}"
        )


def test_emit_raises_when_results_missing(tmp_path: Path) -> None:
    empty_state = tmp_path / "empty_state"
    (empty_state / "results").mkdir(parents=True)
    with pytest.raises(ValueError, match="no per-AC results"):
        emit_state_csv(state_dir=empty_state, output_path=tmp_path / "out.csv")


def test_emit_from_data_raises_on_empty_list(tmp_path: Path) -> None:
    """The in-memory API must fail loudly if called with no data — silent
    success would emit an orphan CSV with just the header."""
    with pytest.raises(ValueError, match="constituencies list is empty"):
        emit_state_csv_from_data(constituencies=[], output_path=tmp_path / "out.csv")


def test_disk_wrapper_matches_in_memory(tmp_path: Path) -> None:
    """Byte-identity proof: the disk-read wrapper produces the same .csv
    bytes as the in-memory primary API for the same data. Guards the
    PR-O.3a refactor — the wrapper must be a pure pass-through."""
    state_dir = tmp_path / "state"
    _write_disk_slice(state_dir)

    via_disk = emit_state_csv(
        state_dir=state_dir, output_path=tmp_path / "via_disk.csv",
    )
    via_memory = emit_state_csv_from_data(
        constituencies=_emit_fixtures.constituencies(),
        output_path=tmp_path / "via_memory.csv",
    )
    assert via_disk.read_bytes() == via_memory.read_bytes()
