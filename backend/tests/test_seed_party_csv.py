"""Tests for B2a.8 entities/parties.csv emitter (sub-plan)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.seed.party_csv import FILE_CLASS, emit


def _stage(path: Path, parties: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"parties": parties}), encoding="utf-8")
    return path


def _party(**overrides) -> dict:
    base = {
        "party_id": "parties.IN.AGP",
        "short_name": "AGP",
        "full_name": "Asom Gana Parishad",
        "eci_codes": ["83"],
        "wikipedia_url": "https://en.wikipedia.org/wiki/Asom_Gana_Parishad",
        "brand_colour": {"hex": "#99CCFF"},
        "election_symbol": {
            "asset_path": "party-symbols/elephant-agp.png",
            "symbol_status": "verified",
        },
    }
    base.update(overrides)
    return base


def test_emit_minimal_row(tmp_path):
    src = _stage(tmp_path / "parties.json", [_party()])
    out = tmp_path / "datasets" / "data" / "entities" / "parties.csv"
    emit(parties_json=src, out_path=out)
    lines = out.read_text(encoding="utf-8").splitlines()
    # v1.2 (PR-1 of TODO/20260615-party-page-citizen-fixes-plan.md):
    # the parties.csv file class now declares 21 columns (8 original + 10 v1.1
    # nullable identity-metadata + 3 v1.2 nullable provenance triple
    # source_id/processing_level/processing_note). The seed emitter only
    # populates the original 8; the 13 new cells trail empty per the column
    # contract. Backfill of source_id+processing_level+processing_note for
    # priority parties is the canonical-helper code-path, not the seed emit.
    assert lines[0] == (
        "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia,aliases,"
        "recognition_scope,home_state_codes,founded_year,dissolved_year,"
        "predecessor_party_ids,successor_party_ids,name_history,"
        "claims_to_parent_name,name_native_script,is_sentinel,"
        "source_id,processing_level,processing_note"
    )
    assert len(lines) == 2
    assert (
        lines[1]
        == "parties.IN.AGP,AGP,Asom Gana Parishad,83,#99CCFF,party-symbols/elephant-agp.png,https://en.wikipedia.org/wiki/Asom_Gana_Parishad,,,,,,,,,,,,,,"
    )


def test_emit_nullable_fields_blank_when_absent(tmp_path):
    src = _stage(
        tmp_path / "parties.json",
        [
            {
                "party_id": "parties.IN.X",
                "short_name": "X",
                "full_name": "Party X",
                "eci_codes": [],
            }
        ],
    )
    out = tmp_path / "parties.csv"
    emit(parties_json=src, out_path=out)
    body = out.read_text(encoding="utf-8").splitlines()[1]
    # eci_codes, brand_colour, symbol_asset, wikipedia, aliases all blank, plus
    # the 10 v1.1 nullable identity-metadata columns also blank, plus the 3 v1.2
    # nullable provenance trailing columns (source_id/processing_level/
    # processing_note) also blank for a seed emit that does not populate them.
    # 18 trailing commas (cells 4-21 empty) per the v1.2 column contract.
    assert body == "parties.IN.X,X,Party X,,,,,,,,,,,,,,,,,,"



def test_emit_pipe_joins_multiple_eci_codes(tmp_path):
    src = _stage(
        tmp_path / "parties.json",
        [_party(eci_codes=["83", "545"])],
    )
    out = tmp_path / "parties.csv"
    emit(parties_json=src, out_path=out)
    body = out.read_text(encoding="utf-8")
    assert "83|545" in body


def test_emit_sorts_by_party_id(tmp_path):
    src = _stage(
        tmp_path / "parties.json",
        [
            _party(party_id="parties.IN.ZZZ", short_name="Z", full_name="Z"),
            _party(party_id="parties.IN.AAA", short_name="A", full_name="A"),
        ],
    )
    out = tmp_path / "parties.csv"
    emit(parties_json=src, out_path=out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[1].startswith("parties.IN.AAA,")
    assert lines[2].startswith("parties.IN.ZZZ,")


def test_emit_rejects_duplicate_party_id(tmp_path):
    src = _stage(
        tmp_path / "parties.json",
        [_party(), _party()],
    )
    with pytest.raises(ValueError, match="duplicate party_id"):
        emit(parties_json=src, out_path=tmp_path / "out.csv")


def test_emit_rejects_double_underscore_party_id(tmp_path):
    src = _stage(
        tmp_path / "parties.json",
        [_party(party_id="parties.IN.BAD__ID")],
    )
    with pytest.raises(ValueError, match="must not contain '__'"):
        emit(parties_json=src, out_path=tmp_path / "out.csv")


def test_emit_rejects_missing_short_name(tmp_path):
    bad = _party()
    bad.pop("short_name")
    src = _stage(tmp_path / "parties.json", [bad])
    with pytest.raises(ValueError, match="missing 'short_name'"):
        emit(parties_json=src, out_path=tmp_path / "out.csv")


def test_emit_rejects_missing_full_name(tmp_path):
    bad = _party()
    bad.pop("full_name")
    src = _stage(tmp_path / "parties.json", [bad])
    with pytest.raises(ValueError, match="missing 'full_name'"):
        emit(parties_json=src, out_path=tmp_path / "out.csv")


def test_emit_rejects_missing_party_id(tmp_path):
    bad = _party()
    bad.pop("party_id")
    src = _stage(tmp_path / "parties.json", [bad])
    with pytest.raises(ValueError, match="missing 'party_id'"):
        emit(parties_json=src, out_path=tmp_path / "out.csv")


def test_emit_rejects_non_list_eci_codes(tmp_path):
    src = _stage(tmp_path / "parties.json", [_party(eci_codes="83")])
    with pytest.raises(ValueError, match="eci_codes must be a list"):
        emit(parties_json=src, out_path=tmp_path / "out.csv")


def test_emitted_csv_passes_validator(tmp_path):
    src = _stage(
        tmp_path / "parties.json",
        [
            _party(),
            _party(
                party_id="parties.IN.BJP",
                short_name="BJP",
                full_name="Bharatiya Janata Party",
                eci_codes=[],
                brand_colour=None,
                election_symbol=None,
                wikipedia_url=None,
            ),
        ],
    )
    repo_root = tmp_path
    out = repo_root / "datasets" / "data" / "entities" / "parties.csv"
    emit(parties_json=src, out_path=out)
    validate_csv(path=out, file_class=FILE_CLASS, repo_root=repo_root)
