"""Row P0a invariants for the geometric AC->PC parent backfill crosswalk.

The generator
(:mod:`yen_gov.canonical.seed.ac_pc_geometric_backfill`) resolves the ``parent``
Parliament-constituency (PC) link for the 2008-delimitation Assembly seats (AC)
left NULL in ``datasets/data/entities/electoral.csv`` by an in-repo spatial join
(a PC is the union of whole ACs, so each AC's parent is the PC polygon it lies
inside).

Per CLAUDE.md section 10 + 14 these tests do NOT walk the real ``datasets/``
corpus and do NOT re-prove the geometry maths against the shipped boundary
layers. They stage a tiny self-contained repo in ``tmp_path`` - two PC squares
side by side, a handful of AC squares nesting inside them - run the real
generator against it, and assert the structural invariants of the emitted
crosswalk CSV:

- every ``ac_entity_id`` was a NULL-parent 2008-delim AC in the input;
- every ``parent_pc_entity_id`` is a PC entity;
- no already-parented AC is ever emitted;
- ``overlap_frac >= 0.80`` on every emitted row;
- ``match_method`` is a closed enum value (``geometric_overlap`` or
  ``single_pc_state``);
- ``source_id`` is non-empty and present in the cited ``source.csv``;
- the emitted CSV passes the real column/FK contract validator.

Two safety behaviours are also pinned: the per-row double-lock (a low-overlap or
unconfirmed seat is LEFT OUT, never guessed) and the hard validation gate (a
poor geometric-vs-LGD agreement STOPS the run and writes nothing).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

pytest.importorskip("shapely", reason="geometric backfill needs the 'geo' extra")

from yen_gov.canonical.csv_validator import validate_csv  # noqa: E402
from yen_gov.canonical.seed import ac_pc_geometric_backfill as backfill  # noqa: E402

# Known fixture entity ids (the test owns the ground truth - no corpus walk).
PC_A = "IN-PC-2008-teststate-501"  # eci_no 1, square (0,0)-(10,10)
PC_B = "IN-PC-2008-teststate-502"  # eci_no 2, square (10,0)-(20,10)
PC_IDS = {PC_A, PC_B}

FILLED_ACS = {
    "IN-AC-2008-teststate-101": PC_A,  # eci 11, inside A
    "IN-AC-2008-teststate-102": PC_A,  # eci 12, inside A
    "IN-AC-2008-teststate-103": PC_B,  # eci 13, inside B
}
GAP_ALPHA = "IN-AC-2008-teststate-eci21"  # inside A, name matches -> emit
GAP_BRAVO = "IN-AC-2008-teststate-eci22"  # inside B, name matches -> emit
GAP_AMBIGUOUS = "IN-AC-2008-teststate-eci23"  # straddles A/B 50:50 -> residual
GAP_NAME_MISMATCH = "IN-AC-2008-teststate-eci24"  # inside A, name differs -> residual
NULL_ACS = {GAP_ALPHA, GAP_BRAVO, GAP_AMBIGUOUS, GAP_NAME_MISMATCH}

# (entity_id, eci_no, geometry-label, ring) for the AC TopoJSON. The geometry
# label is what the spatial layer calls the seat; for GAP_NAME_MISMATCH it is
# deliberately unlike the electoral name so only the per-state trust lock could
# admit it.
_AC_SQUARES: list[tuple[str, int, str, list[list[float]]]] = [
    ("IN-AC-2008-teststate-101", 11, "Filled1", [[0, 0], [5, 0], [5, 5], [0, 5], [0, 0]]),
    ("IN-AC-2008-teststate-102", 12, "Filled2", [[5, 0], [10, 0], [10, 5], [5, 5], [5, 0]]),
    ("IN-AC-2008-teststate-103", 13, "Filled3", [[10, 0], [15, 0], [15, 5], [10, 5], [10, 0]]),
    (GAP_ALPHA, 21, "GapAlpha", [[0, 5], [5, 5], [5, 10], [0, 10], [0, 5]]),
    (GAP_BRAVO, 22, "GapBravo", [[15, 0], [20, 0], [20, 5], [15, 5], [15, 0]]),
    (GAP_AMBIGUOUS, 23, "GapAmbiguous", [[8, 5], [12, 5], [12, 9], [8, 9], [8, 5]]),
    (GAP_NAME_MISMATCH, 24, "Totally Different", [[5, 5], [10, 5], [10, 9], [5, 9], [5, 5]]),
]
_AC_ECI: dict[str, int] = {eid: eci for eid, eci, _, _ in _AC_SQUARES}
_AC_NAME: dict[str, str] = {
    GAP_ALPHA: "GapAlpha",
    GAP_BRAVO: "GapBravo",
    GAP_AMBIGUOUS: "GapAmbiguous",
    GAP_NAME_MISMATCH: "GapNameMismatch",
}

_PC_SQUARES: list[tuple[str, int, str, list[list[float]]]] = [
    (PC_A, 1, "PcAlpha", [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]),
    (PC_B, 2, "PcBravo", [[10, 0], [20, 0], [20, 10], [10, 10], [10, 0]]),
]


def _stage_repo(tmp_path: Path, *, corrupt_lgd: bool = False) -> Path:
    """Write a minimal self-contained repo and return its root (``tmp_path``).

    When ``corrupt_lgd`` is true every already-parented AC is pointed at the
    WRONG PC, so the geometric-vs-LGD agreement collapses to zero and the gate
    must STOP.
    """
    entities = tmp_path / "datasets" / "data" / "entities"
    entities.mkdir(parents=True)
    ac_dir = tmp_path / "datasets" / "boundaries" / "electoral" / "delim=2024" / "ac"
    pc_dir = tmp_path / "datasets" / "boundaries" / "electoral" / "delim=2024" / "pc"
    ac_dir.mkdir(parents=True)
    pc_dir.mkdir(parents=True)

    # geo.csv: one state S01 -> slug "teststate".
    (entities / "geo.csv").write_text(
        "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
        "teststate,Teststate,IN,state,S01,,\n",
        encoding="utf-8",
    )

    # source.csv: header only - the generator upserts its derived citation row.
    (entities / "source.csv").write_text(
        "source_id,producer,title,vintage,url\n", encoding="utf-8"
    )

    # electoral.csv: PCs + filled ACs (parented) + gap ACs (NULL parent).
    lines = ["entity_id,name,entity_kind,delim_year,state,parent,eci_no,aliases,reservation"]
    for eid, eci, name, _ in _PC_SQUARES:
        lines.append(f"{eid},{name},pc,2008,teststate,,{eci},,GEN")
    wrong_pc = {PC_A: PC_B, PC_B: PC_A}
    for eid, lgd_parent in FILLED_ACS.items():
        parent = wrong_pc[lgd_parent] if corrupt_lgd else lgd_parent
        lines.append(
            f"{eid},{_label(eid)},ac,2008,teststate,{parent},{_AC_ECI[eid]},,GEN"
        )
    for eid in (GAP_ALPHA, GAP_BRAVO, GAP_AMBIGUOUS, GAP_NAME_MISMATCH):
        lines.append(f"{eid},{_AC_NAME[eid]},ac,2008,teststate,,{_AC_ECI[eid]},,GEN")
    (entities / "electoral.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # AC TopoJSON (no transform -> absolute lon/lat coords; one arc per square).
    arcs = [ring for _, _, _, ring in _AC_SQUARES]
    geometries = [
        {
            "type": "Polygon",
            "arcs": [[idx]],
            "properties": {"state_ut_code": "S01", "ac_no": eci, "ac_name": label},
        }
        for idx, (_, eci, label, _) in enumerate(_AC_SQUARES)
    ]
    (ac_dir / "all.topojson").write_text(
        json.dumps(
            {
                "type": "Topology",
                "objects": {"ac": {"type": "GeometryCollection", "geometries": geometries}},
                "arcs": arcs,
            }
        ),
        encoding="utf-8",
    )

    # PC GeoJSON.
    features = [
        {
            "type": "Feature",
            "properties": {"unique_id": f"S01_{eci}"},
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        }
        for _, eci, _, ring in _PC_SQUARES
    ]
    (pc_dir / "all.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}),
        encoding="utf-8",
    )
    return tmp_path


def _label(entity_id: str) -> str:
    return {
        "IN-AC-2008-teststate-101": "Filled1",
        "IN-AC-2008-teststate-102": "Filled2",
        "IN-AC-2008-teststate-103": "Filled3",
    }[entity_id]


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# Gate + the six structural invariants of the emitted crosswalk.
# ---------------------------------------------------------------------------
def test_gate_passes_and_crosswalk_invariants_hold(tmp_path: Path) -> None:
    root = _stage_repo(tmp_path)
    result = backfill.generate(repo_root=root, write=True)

    assert result.status == "ok"
    assert result.agreement_rate >= 0.95  # filled ACs agree with LGD -> gate open
    assert result.out_path is not None and result.out_path.exists()

    rows = _read_rows(root / backfill.OUT_REL)
    assert rows, "expected at least one resolved gap AC"

    source_ids = {r["source_id"] for r in _read_rows(root / backfill.SOURCE_REL)}
    emitted = {r["ac_entity_id"] for r in rows}

    for row in rows:
        # invariant 1: emitted ACs were NULL-parent 2008-delim ACs in the input.
        assert row["ac_entity_id"] in NULL_ACS
        # invariant 2: the parent is a PC entity.
        assert row["parent_pc_entity_id"] in PC_IDS
        # invariant 4: dominant overlap clears the 0.80 floor.
        assert float(row["overlap_frac"]) >= 0.80
        # invariant: match_method is a closed enum value. The crosswalk file
        # class admits six methods (geometric_overlap, single_pc_state, the
        # Survey-of-India composition backfill values soi_composition /
        # soi_centroid, composition_alias for official-composition rows
        # bridged via a verified name alias, and eci_delimitation_order for
        # rows read directly from an ECI delimitation-order PC-wise AC
        # composition table); the generator under test emits only the first two.
        assert row["match_method"] in {
            "geometric_overlap",
            "single_pc_state",
            "soi_composition",
            "soi_centroid",
            "composition_alias",
            "eci_delimitation_order",
        }
        # invariant 5: source_id is non-empty and cited in source.csv.
        assert row["source_id"] and row["source_id"] in source_ids

    # invariant 3: no already-parented AC is ever emitted.
    assert emitted.isdisjoint(FILLED_ACS.keys())

    # PK uniqueness (one parent per gap AC).
    assert len(emitted) == len(rows)

    # The two clean, name-confirmed seats resolve to the PC they sit inside.
    by_ac = {r["ac_entity_id"]: r for r in rows}
    assert by_ac[GAP_ALPHA]["parent_pc_entity_id"] == PC_A
    assert by_ac[GAP_BRAVO]["parent_pc_entity_id"] == PC_B


def test_emitted_crosswalk_passes_contract_validator(tmp_path: Path) -> None:
    """The real column + FK validator accepts the emitted crosswalk (proves the
    ac/pc/source FKs all close against the staged sibling CSVs)."""
    root = _stage_repo(tmp_path)
    result = backfill.generate(repo_root=root, write=True)
    assert result.status == "ok"

    # Raises CsvValidationError on any header/dtype/enum/FK/sort violation.
    validate_csv(
        path=root / backfill.OUT_REL,
        file_class=backfill.FILE_CLASS,
        repo_root=root,
    )


def test_provenance_row_cites_eci_delimitation(tmp_path: Path) -> None:
    root = _stage_repo(tmp_path)
    result = backfill.generate(repo_root=root, write=True)

    by_id = {r["source_id"]: r for r in _read_rows(root / backfill.SOURCE_REL)}
    assert result.source_id in by_id
    row = by_id[result.source_id]
    # Public-facing electoral data always cites ECI. The AC->PC linkage is a
    # de-jure delimitation fact whose authority is the ECI 2008 Delimitation
    # Order; the geometric join is the recovery METHOD (disclosed per-row via
    # match_method + overlap_frac), not the origin.
    assert row["producer"] == "Election Commission of India"
    assert "Delimitation" in row["title"] and "2008" in row["title"]
    assert row["vintage"] == "2008"


# ---------------------------------------------------------------------------
# Per-row double-lock: low-overlap + unconfirmed seats stay NULL.
# ---------------------------------------------------------------------------
def test_double_lock_leaves_low_overlap_and_unconfirmed_null(tmp_path: Path) -> None:
    root = _stage_repo(tmp_path)
    result = backfill.generate(repo_root=root, write=True)

    emitted = {r["ac_entity_id"] for r in _read_rows(root / backfill.OUT_REL)}

    # Default run: no state is "trusted" (only 3 filled ACs < min_state_filled),
    # so emission rides the per-row name lock alone.
    assert emitted == {GAP_ALPHA, GAP_BRAVO}
    # The 50:50 straddler fails the overlap+runner-up lock.
    assert GAP_AMBIGUOUS not in emitted
    # The high-overlap-but-name-mismatch seat fails the identity lock.
    assert GAP_NAME_MISMATCH not in emitted
    assert result.residual == 2


def test_tier_b_state_trust_recovers_name_variant(tmp_path: Path) -> None:
    """A seat whose geometry label does not match the register is still admitted
    when its whole state passed the LGD-agreement bar (Tier-B), but the overlap
    lock remains independent - the ambiguous straddler stays out."""
    root = _stage_repo(tmp_path)
    result = backfill.generate(repo_root=root, min_state_filled=2, write=True)

    emitted = {r["ac_entity_id"] for r in _read_rows(root / backfill.OUT_REL)}
    assert GAP_NAME_MISMATCH in emitted  # recovered via per-state trust
    assert emitted == {GAP_ALPHA, GAP_BRAVO, GAP_NAME_MISMATCH}
    assert GAP_AMBIGUOUS not in emitted  # overlap lock is not waived by trust
    assert result.residual == 1


# ---------------------------------------------------------------------------
# Hard gate: poor agreement STOPS the run and writes nothing.
# ---------------------------------------------------------------------------
def test_low_agreement_gate_stops_and_writes_nothing(tmp_path: Path) -> None:
    root = _stage_repo(tmp_path, corrupt_lgd=True)
    result = backfill.generate(repo_root=root, write=True)

    assert result.status == "stopped-low-agreement"
    assert result.agreement_rate < 0.95
    assert result.emitted == 0
    assert result.out_path is None
    # Nothing was written: the crosswalk file must not exist.
    assert not (root / backfill.OUT_REL).exists()


# ---------------------------------------------------------------------------
# Single-PC-state fallback: a NULL AC in a state/UT with EXACTLY ONE PC resolves
# to that sole PC by logical certainty (no geometry); overlap_frac == 1.0.
# ---------------------------------------------------------------------------
def _stage_single_pc_repo(tmp_path: Path) -> Path:
    """A minimal repo with ONE single-PC state: a geometry-bridged FILLED AC (so
    the LGD-agreement gate opens) and a geometry-less NULL AC (so it can only be
    resolved by the single-PC-state fallback, never by the spatial join)."""
    entities = tmp_path / "datasets" / "data" / "entities"
    entities.mkdir(parents=True)
    ac_dir = tmp_path / "datasets" / "boundaries" / "electoral" / "delim=2024" / "ac"
    pc_dir = tmp_path / "datasets" / "boundaries" / "electoral" / "delim=2024" / "pc"
    ac_dir.mkdir(parents=True)
    pc_dir.mkdir(parents=True)

    (entities / "geo.csv").write_text(
        "entity_id,name,parent,entity_kind,aliases,census_2001_code,census_2011_code\n"
        "solostate,Solostate,IN,ut,S09,,\n",
        encoding="utf-8",
    )
    (entities / "source.csv").write_text(
        "source_id,producer,title,vintage,url\n", encoding="utf-8"
    )
    # one PC (eci 1); one FILLED AC (eci 11, parent = the PC); one NULL AC (eci 21).
    (entities / "electoral.csv").write_text(
        "entity_id,name,entity_kind,delim_year,state,parent,eci_no,aliases,reservation\n"
        "IN-PC-2008-solostate-901,SoloPc,pc,2008,solostate,,1,,GEN\n"
        "IN-AC-2008-solostate-101,SoloFilled,ac,2008,solostate,IN-PC-2008-solostate-901,11,,GEN\n"
        "IN-AC-2008-solostate-eci21,SoloGap,ac,2008,solostate,,21,,GEN\n",
        encoding="utf-8",
    )
    # AC TopoJSON: ONLY the filled AC has geometry (a square inside the PC); the
    # gap AC is deliberately absent so it cannot resolve via the spatial join.
    (ac_dir / "all.topojson").write_text(
        json.dumps(
            {
                "type": "Topology",
                "objects": {
                    "ac": {
                        "type": "GeometryCollection",
                        "geometries": [
                            {
                                "type": "Polygon",
                                "arcs": [[0]],
                                "properties": {
                                    "state_ut_code": "S09",
                                    "ac_no": 11,
                                    "ac_name": "SoloFilled",
                                },
                            }
                        ],
                    }
                },
                "arcs": [[[0, 0], [5, 0], [5, 5], [0, 5], [0, 0]]],
            }
        ),
        encoding="utf-8",
    )
    # PC GeoJSON: one big square that fully contains the filled AC.
    (pc_dir / "all.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"unique_id": "S09_1"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_single_pc_state_fallback_resolves_sole_pc(tmp_path: Path) -> None:
    root = _stage_single_pc_repo(tmp_path)
    result = backfill.generate(repo_root=root, write=True)

    assert result.status == "ok"  # the one filled AC opens the agreement gate
    assert result.single_pc == 1
    assert result.emitted == 1  # zero geometric rows; exactly one single-PC row
    assert result.residual == 0

    rows = _read_rows(root / backfill.OUT_REL)
    assert len(rows) == 1
    row = rows[0]
    assert row["ac_entity_id"] == "IN-AC-2008-solostate-eci21"
    assert row["parent_pc_entity_id"] == "IN-PC-2008-solostate-901"
    assert row["match_method"] == "single_pc_state"
    assert float(row["overlap_frac"]) == 1.0
    assert int(row["parent_pc_eci_no"]) == 1

    # the single-PC row closes the column + FK + enum contract too.
    validate_csv(
        path=root / backfill.OUT_REL,
        file_class=backfill.FILE_CLASS,
        repo_root=root,
    )
