"""Tests for the CSV bundle emitter (docs/architecture/backend/emit-csv.md).

Uses the committed TN slice as a fixture so the test exercises real shape
without re-fetching from ECI.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from yen_gov.emit.csv_bundle import LAYOUT_VERSION, _COLUMNS, emit_state_csv

REPO_ROOT = Path(__file__).resolve().parents[2]
TN_DIR = REPO_ROOT / "datasets" / "elections" / "AcGenMay2026" / "S22"


pytestmark = pytest.mark.skipif(
    not (TN_DIR / "results").exists(),
    reason="TN AcGenMay2026/S22 dataset not present; run `yen-gov run` first",
)


def _read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_layout_version_is_documented() -> None:
    assert LAYOUT_VERSION == 1


def test_emit_creates_csv_with_expected_columns(tmp_path: Path) -> None:
    out = emit_state_csv(state_dir=TN_DIR, output_path=tmp_path / "results.csv")
    assert out.exists()
    with out.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
    assert header == _COLUMNS


def test_emit_uses_unix_line_endings(tmp_path: Path) -> None:
    """Determinism: `\\n` only, never `\\r\\n`. Platform-native line endings
    would break byte-identical regeneration on Windows vs Linux CI."""
    out = emit_state_csv(state_dir=TN_DIR, output_path=tmp_path / "results.csv")
    raw = out.read_bytes()
    assert b"\r\n" not in raw
    assert raw.endswith(b"\n")


def test_emit_is_byte_deterministic(tmp_path: Path) -> None:
    a = emit_state_csv(state_dir=TN_DIR, output_path=tmp_path / "a.csv")
    b = emit_state_csv(state_dir=TN_DIR, output_path=tmp_path / "b.csv")
    assert a.read_bytes() == b.read_bytes()


def test_emit_includes_one_winner_per_constituency(tmp_path: Path) -> None:
    out = emit_state_csv(state_dir=TN_DIR, output_path=tmp_path / "results.csv")
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
    """Every AC has a NOTA row in the source JSON; the CSV must reflect that."""
    out = emit_state_csv(state_dir=TN_DIR, output_path=tmp_path / "results.csv")
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
    out = emit_state_csv(state_dir=TN_DIR, output_path=tmp_path / "results.csv")
    rows = _read_rows(out)
    keys = [(int(r["ac_eci_no"]), int(r["rank"])) for r in rows]
    assert keys == sorted(keys)


def test_emit_long_format_matches_json_winners(tmp_path: Path) -> None:
    """Winner from the CSV must equal winner from each per-AC JSON."""
    out = emit_state_csv(state_dir=TN_DIR, output_path=tmp_path / "results.csv")
    rows = _read_rows(out)
    csv_winner_by_ac: dict[int, str] = {}
    for r in rows:
        if r["is_winner"] == "1":
            csv_winner_by_ac[int(r["ac_eci_no"])] = r["candidate_name"]

    for json_path in (TN_DIR / "results").glob("*.json"):
        doc = json.loads(json_path.read_text(encoding="utf-8"))
        eci_no = doc["eci_no"]
        expected = doc["winner"]["name"]
        assert csv_winner_by_ac.get(eci_no) == expected, (
            f"winner mismatch for AC {eci_no}: csv={csv_winner_by_ac.get(eci_no)!r}, json={expected!r}"
        )


def test_emit_raises_when_results_missing(tmp_path: Path) -> None:
    empty_state = tmp_path / "empty_state"
    (empty_state / "results").mkdir(parents=True)
    with pytest.raises(ValueError, match="no per-AC results"):
        emit_state_csv(state_dir=empty_state, output_path=tmp_path / "out.csv")
