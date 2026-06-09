"""G11 contract: parties.csv ``symbol_asset`` column lifted from parties.json.

Plan row 28 (TODO/20260603-data-and-charting-platform-reset-plan.md section 4 EL3):
lift the curator-verified election_symbol.asset_path from
``datasets/taxonomy/parties.json`` into the ``symbol_asset`` column of
``datasets/data/entities/parties.csv`` so the citizen UI can render the
ECI glyph alongside the PartyPill (plan section 25.3).

Four invariants, no mocks (real on-disk corpus per CLAUDE.md Holy Law #7):

1. Every parties.json party with ``election_symbol.symbol_status ==
   "verified"`` has a non-empty ``symbol_asset`` cell on its parties.csv
   row (writer correctness post-G11).
2. Every non-empty ``symbol_asset`` value points at a file that exists
   under ``frontend/public/`` (no broken refs reach the static bundle).
3. Every non-empty ``symbol_asset`` value is byte-equal to the
   ``election_symbol.asset_path`` for the same ``party_id`` in
   parties.json (no silent drift).
4. ``emit()`` is deterministic: running twice over the same input
   produces byte-identical bytes (tmp_path fixture; the real CSV is not
   touched by this test).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from yen_gov.canonical.seed.party_csv import emit


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PARTIES_JSON = _REPO_ROOT / "datasets" / "taxonomy" / "parties.json"
_PARTIES_CSV = _REPO_ROOT / "datasets" / "data" / "entities" / "parties.csv"
_PUBLIC_DIR = _REPO_ROOT / "frontend" / "public"


def _load_json_verified_assets() -> dict[str, str]:
    payload = json.loads(_PARTIES_JSON.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for party in payload["parties"]:
        block = party.get("election_symbol")
        if not isinstance(block, dict):
            continue
        if block.get("symbol_status") != "verified":
            continue
        asset = block.get("asset_path")
        if not asset:
            continue
        out[party["party_id"]] = str(asset)
    return out


def _load_csv_symbol_assets() -> dict[str, str]:
    with _PARTIES_CSV.open(encoding="utf-8", newline="") as fh:
        return {
            row["party_id"]: row["symbol_asset"]
            for row in csv.DictReader(fh)
            if row["symbol_asset"]
        }


@pytest.fixture(scope="module")
def json_verified() -> dict[str, str]:
    return _load_json_verified_assets()


@pytest.fixture(scope="module")
def csv_populated() -> dict[str, str]:
    return _load_csv_symbol_assets()


def test_every_verified_party_in_csv_has_symbol_asset(
    json_verified: dict[str, str], csv_populated: dict[str, str]
) -> None:
    missing = sorted(set(json_verified) - set(csv_populated))
    assert missing == [], (
        "parties.json parties with symbol_status=verified that are MISSING "
        f"a populated symbol_asset cell in parties.csv: {missing}"
    )


def test_every_populated_symbol_asset_file_exists(
    csv_populated: dict[str, str],
) -> None:
    broken = [
        (pid, asset)
        for pid, asset in csv_populated.items()
        if not (_PUBLIC_DIR / asset).exists()
    ]
    assert broken == [], (
        "parties.csv rows whose symbol_asset path does NOT resolve to a "
        f"file under frontend/public/: {broken}"
    )


def test_csv_symbol_asset_matches_json_byte_equal(
    json_verified: dict[str, str], csv_populated: dict[str, str]
) -> None:
    drift = [
        (pid, csv_populated[pid], json_verified.get(pid))
        for pid in csv_populated
        if pid in json_verified and csv_populated[pid] != json_verified[pid]
    ]
    assert drift == [], (
        "parties.csv symbol_asset values that drift from parties.json "
        f"election_symbol.asset_path for the same party_id: {drift}"
    )


def test_emit_is_deterministic(tmp_path: Path) -> None:
    src = tmp_path / "parties.json"
    src.write_text(
        json.dumps(
            {
                "parties": [
                    {
                        "party_id": "parties.IN.AGP",
                        "short_name": "AGP",
                        "full_name": "Asom Gana Parishad",
                        "eci_codes": ["83"],
                        "election_symbol": {
                            "asset_path": "party-symbols/elephant-agp.png",
                            "symbol_status": "verified",
                        },
                    },
                    {
                        "party_id": "parties.IN.UNV",
                        "short_name": "UNV",
                        "full_name": "Unverified Party",
                        "eci_codes": [],
                        "election_symbol": {
                            "asset_path": "party-symbols/should-not-appear.png",
                            "symbol_status": "placeholder",
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    out_a = tmp_path / "a.csv"
    out_b = tmp_path / "b.csv"
    emit(parties_json=src, out_path=out_a)
    emit(parties_json=src, out_path=out_b)

    bytes_a = out_a.read_bytes()
    bytes_b = out_b.read_bytes()
    assert bytes_a == bytes_b, "emit() output differs across two runs"

    # And confirm the verified filter holds end-to-end on the deterministic
    # fixture: AGP populated, UNV blank.
    rows = list(csv.DictReader(out_a.read_text(encoding="utf-8").splitlines()))
    by_id = {r["party_id"]: r["symbol_asset"] for r in rows}
    assert by_id["parties.IN.AGP"] == "party-symbols/elephant-agp.png"
    assert by_id["parties.IN.UNV"] == ""
