"""Row P0b: geometric AC->PC crosswalk wiring tests.

Two surfaces, both with tiny tmp_path fixtures only (no mocks, no real-corpus
walk; Holy Law #7):

1. ``electoral_csv_from_snapshot.emit`` crosswalk fallback - LGD-first,
   crosswalk-second, NULL-last - for a future LGD-snapshot regen.
2. ``apply_ac_pc_backfill.apply_backfill`` surgical applier that fills the
   committed electoral.csv ``parent`` column without touching any other byte.
"""

from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.seed import electoral_csv_from_snapshot as electoral
from yen_gov.canonical.seed.apply_ac_pc_backfill import apply_backfill


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return path


def _read(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return {r["entity_id"]: r for r in csv.DictReader(fh)}


# --------------------------------------------------------------------------- #
# 1. writer crosswalk fallback (electoral_csv_from_snapshot.emit)             #
# --------------------------------------------------------------------------- #

def _state_codes(tmp_path: Path) -> Path:
    return _write(
        tmp_path / "state_codes.csv",
        "lgd_state_id,lgd_name,iso_3166_2,census_2001_code,census_2011_code,kind,slug,aliases\n"
        "28,Andhra Pradesh,IN-AP,28,28,state,andhra-pradesh,\n",
    )


def _snapshot(tmp_path: Path) -> Path:
    return _write(
        tmp_path / "constituencies.csv",
        "lgd_state_code,kind,lgd_code,eci_code,name,parent_pc_lgd_code\n"
        "28,pc,411,9,Amalapuram,\n"
        "28,pc,412,10,OtherPC,\n"
        "28,ac,3166,163,Amalapuram,411\n"  # LGD-resolved -> PC 411
        "28,ac,3167,165,Gannavaram,\n"  # NULL via LGD; present in crosswalk
        "28,ac,3168,166,Kakinada,\n",  # NULL via LGD; absent from crosswalk
    )


def _writer_crosswalk(tmp_path: Path) -> Path:
    return _write(
        tmp_path / "ac_pc_geometric_backfill.csv",
        "ac_entity_id,parent_pc_entity_id\n"
        "IN-AC-2008-andhra-pradesh-3167,IN-PC-2008-andhra-pradesh-411\n"  # fills NULL AC
        "IN-AC-2008-andhra-pradesh-3166,IN-PC-2008-andhra-pradesh-412\n",  # LGD wins -> ignored
    )


def test_writer_crosswalk_fallback_lgd_first(tmp_path):
    out = tmp_path / "electoral.csv"
    electoral.emit(
        constituencies_csv=_snapshot(tmp_path),
        state_codes_csv=_state_codes(tmp_path),
        out_path=out,
        crosswalk_csv=_writer_crosswalk(tmp_path),
    )
    by_id = _read(out)
    # LGD-resolved AC keeps its LGD parent even though the crosswalk names another PC.
    assert by_id["IN-AC-2008-andhra-pradesh-3166"]["parent"] == "IN-PC-2008-andhra-pradesh-411"
    # NULL-via-LGD AC present in the crosswalk gets the crosswalk parent.
    assert by_id["IN-AC-2008-andhra-pradesh-3167"]["parent"] == "IN-PC-2008-andhra-pradesh-411"
    # NULL-via-LGD AC absent from the crosswalk stays NULL.
    assert by_id["IN-AC-2008-andhra-pradesh-3168"]["parent"] == ""


def test_writer_without_crosswalk_leaves_null(tmp_path):
    out = tmp_path / "electoral.csv"  # no crosswalk file next to out_path
    electoral.emit(
        constituencies_csv=_snapshot(tmp_path),
        state_codes_csv=_state_codes(tmp_path),
        out_path=out,
    )
    by_id = _read(out)
    assert by_id["IN-AC-2008-andhra-pradesh-3167"]["parent"] == ""
    assert by_id["IN-AC-2008-andhra-pradesh-3168"]["parent"] == ""


# --------------------------------------------------------------------------- #
# 2. surgical applier (apply_ac_pc_backfill.apply_backfill)                    #
# --------------------------------------------------------------------------- #

_ELECTORAL_HEADER = (
    "entity_id,name,entity_kind,delim_year,state,parent,eci_no,aliases,reservation"
)
_ELECTORAL_BODY = [
    "IN-PC-2008-andhra-pradesh-411,Amalapuram,pc,2008,andhra-pradesh,andhra-pradesh,9,,",
    "IN-PC-2008-andhra-pradesh-412,OtherPC,pc,2008,andhra-pradesh,andhra-pradesh,10,,",
    # LGD-linked AC (parent already set):
    "IN-AC-2008-andhra-pradesh-3166,Amalapuram,ac,2008,andhra-pradesh,IN-PC-2008-andhra-pradesh-411,163,,",
    # gap AC, empty parent, present in crosswalk:
    "IN-AC-2008-andhra-pradesh-eci999,Gannavaram,ac,2008,andhra-pradesh,,165,,",
    # gap AC, comma-quoted name, present in crosswalk (quoting-preservation canary):
    'IN-AC-2008-andhra-pradesh-eci1001,"Foo, Bar",ac,2008,andhra-pradesh,,167,,',
    # gap AC, empty parent, absent from crosswalk -> stays NULL:
    "IN-AC-2008-andhra-pradesh-eci1000,Kakinada,ac,2008,andhra-pradesh,,166,,",
]


def _applier_electoral(tmp_path: Path) -> Path:
    return _write(
        tmp_path / "electoral.csv",
        _ELECTORAL_HEADER + "\n" + "\n".join(_ELECTORAL_BODY) + "\n",
    )


def _applier_crosswalk(tmp_path: Path) -> Path:
    return _write(
        tmp_path / "ac_pc_geometric_backfill.csv",
        "ac_entity_id,parent_pc_entity_id,parent_pc_eci_no,match_method,overlap_frac,source_id\n"
        "IN-AC-2008-andhra-pradesh-eci999,IN-PC-2008-andhra-pradesh-411,9,geometric_overlap,0.95,src-test\n"
        "IN-AC-2008-andhra-pradesh-eci1001,IN-PC-2008-andhra-pradesh-412,10,geometric_overlap,0.9,src-test\n"
        "IN-AC-2008-andhra-pradesh-3166,IN-PC-2008-andhra-pradesh-412,10,geometric_overlap,0.88,src-test\n"  # LGD wins
        "IN-AC-2008-andhra-pradesh-eci2000,IN-PC-2008-andhra-pradesh-411,9,geometric_overlap,0.91,src-test\n",  # not in electoral
    )


def test_applier_fills_only_parent_for_listed_acs(tmp_path):
    elec = _applier_electoral(tmp_path)
    before = elec.read_text(encoding="utf-8")

    result = apply_backfill(electoral_csv=elec, crosswalk_csv=_applier_crosswalk(tmp_path))

    assert result.filled == 2  # eci999 + eci1001
    assert result.already_linked == 1  # 3166 (LGD wins; crosswalk ignored)
    assert result.missing == ("IN-AC-2008-andhra-pradesh-eci2000",)
    assert result.crosswalk_rows == 4

    by_id = _read(elec)
    assert by_id["IN-AC-2008-andhra-pradesh-eci999"]["parent"] == "IN-PC-2008-andhra-pradesh-411"
    assert by_id["IN-AC-2008-andhra-pradesh-eci1001"]["parent"] == "IN-PC-2008-andhra-pradesh-412"
    # LGD-linked AC is UNCHANGED (NOT the crosswalk's 412):
    assert by_id["IN-AC-2008-andhra-pradesh-3166"]["parent"] == "IN-PC-2008-andhra-pradesh-411"
    # gap AC absent from the crosswalk stays NULL:
    assert by_id["IN-AC-2008-andhra-pradesh-eci1000"]["parent"] == ""

    # byte-level: exactly the two filled lines differ, and only in the parent cell.
    old_lines = before.split("\n")
    new_lines = elec.read_text(encoding="utf-8").split("\n")
    assert len(old_lines) == len(new_lines)  # no add / remove / reorder
    changed = [(o, n) for o, n in zip(old_lines, new_lines) if o != n]
    assert len(changed) == 2
    for old_line, new_line in changed:
        of = next(csv.reader([old_line]))
        nf = next(csv.reader([new_line]))
        assert of[0] == nf[0]  # entity_id unchanged
        assert of[5] == "" and nf[5] != ""  # parent: empty -> set
        of[5] = nf[5]
        assert of == nf  # every other field byte-identical
    # comma-quoted name preserved byte-for-byte through the re-serialise:
    assert any('"Foo, Bar"' in new_line for _, new_line in changed)


def test_applier_is_idempotent(tmp_path):
    elec = _applier_electoral(tmp_path)
    xwalk = _applier_crosswalk(tmp_path)
    apply_backfill(electoral_csv=elec, crosswalk_csv=xwalk)
    after_first = elec.read_text(encoding="utf-8")

    second = apply_backfill(electoral_csv=elec, crosswalk_csv=xwalk)
    assert second.filled == 0
    assert second.already_linked == 3  # eci999 + eci1001 + 3166 now all linked
    assert elec.read_text(encoding="utf-8") == after_first  # no churn on re-run
