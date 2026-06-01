"""Tests for ``tools/migrate/build_ac_crosswalk.py`` (Row A2).

Two surfaces:

* ``test_harvester_*`` - run the harvester end-to-end against a tiny inline
  fixture datasets root (mini SoT + dim_acs + boundary geojson + sources) and
  assert the bijection-and-cover oracle (``backend.yen_gov.canonical.ac_crosswalk
  .assert_bijection``) passes, that spillover features are dropped, and that
  each match_method binds the right ``lgd_ac_id``.
* ``test_shipped_crosswalk_passes_oracle`` - the load-bearing guard on the real
  committed ``datasets/taxonomy/ac_crosswalk.parquet``: it MUST satisfy
  ``assert_bijection`` with exact cover over the SoT AC universe.

The harvester lives in ``tools/`` and may not import ``backend/`` (CLAUDE.md
section 4); the oracle therefore runs here, in the backend test.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import duckdb
import pytest

from yen_gov.canonical.ac_crosswalk import (
    MATCH_METHODS,
    UNMAPPED,
    assert_bijection,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def build_module() -> Any:
    """Import the harvester via its absolute path (cwd-independent)."""
    tools_dir = REPO_ROOT / "tools" / "migrate"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    spec_path = tools_dir / "build_ac_crosswalk.py"
    spec = importlib.util.spec_from_file_location("build_ac_crosswalk", spec_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- fixture datasets root ----------------------------------------------------


def _boundary_feature(ac_id: str, ac_no: int, ac_name: str, st_code: str) -> dict:
    return {
        "type": "Feature",
        "properties": {
            "AC_ID": ac_id,
            "ac_no": ac_no,
            "ac_name": ac_name,
            "st_code": st_code,
            "st_name": "TESTLAND",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[75.0, 33.5], [75.01, 33.5], [75.01, 33.51], [75.0, 33.5]]],
        },
    }


@pytest.fixture
def fixture_root(tmp_path: Path) -> Path:
    """Build a minimal datasets/ root exercising every match_method."""
    root = tmp_path / "datasets"

    # SoT: 4 ACs. eci 1/2 -> lgd_direct, eci 3 -> name_reservation_join,
    # eci 4 -> unmapped (no boundary feature).
    sot_dir = root / "reference" / "in" / "states" / "S99"
    sot_dir.mkdir(parents=True)
    (sot_dir / "constituencies.json").write_text(
        json.dumps(
            {
                "$schema": "../../../../schemas/constituency.schema.json",
                "$schema_version": "4.1",
                "sources": [],
                "state": "S99",
                "body": "AC",
                "status": "final",
                "constituencies": [
                    {"eci_no": 1, "name": "Alpha", "reservation": "GEN"},
                    {"eci_no": 2, "name": "Beta", "reservation": "SC"},
                    {"eci_no": 3, "name": "Gamma", "reservation": "GEN"},
                    {"eci_no": 4, "name": "Delta", "reservation": "GEN"},
                ],
            }
        ),
        encoding="utf-8",
    )

    con = duckdb.connect()

    # dim_acs: a 1976 decoy row for eci 1 + the four 2008 rows.
    dim_rows = [
        ("IN-S99-AC-1976-1", "S99", 1976, 1, "OLD ALPHA", "src-x"),
        ("IN-S99-AC-2008-1", "S99", 2008, 1, "ALPHA", "src-x"),
        ("IN-S99-AC-2008-2", "S99", 2008, 2, "BETA", "src-x"),
        ("IN-S99-AC-2008-3", "S99", 2008, 3, "GAMMA", "src-x"),
        ("IN-S99-AC-2008-4", "S99", 2008, 4, "DELTA", "src-x"),
    ]
    (root / "elections").mkdir(parents=True)
    con.execute(
        "CREATE TABLE dim (ac_id VARCHAR, state_code VARCHAR, delim_year INTEGER, "
        "eci_no INTEGER, name VARCHAR, source_id VARCHAR)"
    )
    con.executemany("INSERT INTO dim VALUES (?, ?, ?, ?, ?, ?)", dim_rows)
    con.execute(
        "COPY dim TO ? (FORMAT PARQUET)",
        [(root / "elections" / "dim_acs.parquet").as_posix()],
    )

    # sources: the HTL triple the harvester resolves by.
    producer, title, vintage = (
        "Hindustan Times Labs",
        "HTL state-AC shapefile bundle",
        "2008 Delimitation",
    )
    (root / "taxonomy").mkdir(parents=True)
    con.execute("CREATE TABLE src (source_id VARCHAR, producer VARCHAR, title VARCHAR, vintage VARCHAR)")
    con.executemany(
        "INSERT INTO src VALUES (?, ?, ?, ?)",
        [("src-htl-test", producer, title, vintage)],
    )
    con.execute(
        "COPY src TO ? (FORMAT PARQUET)",
        [(root / "taxonomy" / "sources.parquet").as_posix()],
    )
    con.close()

    # boundary geojson: 3 in-state features (st_code 99) + 1 spillover (88).
    # The spillover shares ac_no 1 with Alpha; the modal-st_code filter MUST
    # drop it so eci 1 resolves unambiguously to 99001.
    bdir = root / "boundaries" / "in" / "ac" / "state=in_s99"
    bdir.mkdir(parents=True)
    (bdir / "all.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    _boundary_feature("99001", 1, "Alpha", "99"),
                    _boundary_feature("99002", 2, "Beta (SC)", "99"),
                    _boundary_feature("99007", 7, "Gamma", "99"),
                    _boundary_feature("88001", 1, "Foreignville", "88"),
                ],
            }
        ),
        encoding="utf-8",
    )

    return root


def test_harvester_bindings_and_oracle(build_module: Any, fixture_root: Path) -> None:
    con = duckdb.connect()
    rows = build_module.build_rows(fixture_root, con)
    con.close()

    by_eci = {r["eci_no"]: r for r in rows}
    assert len(rows) == 4

    # eci 1: lgd_direct, spillover 88001 dropped -> binds 99001.
    assert by_eci[1]["match_method"] == "lgd_direct"
    assert by_eci[1]["lgd_ac_id"] == 99001
    assert by_eci[1]["ac_id"] == "IN-S99-AC-2008-1"
    assert by_eci[1]["ac_name"] == "ALPHA"
    assert by_eci[1]["delim_year"] == 2008

    # eci 2: lgd_direct with reservation suffix in boundary name.
    assert by_eci[2]["match_method"] == "lgd_direct"
    assert by_eci[2]["lgd_ac_id"] == 99002

    # eci 3: no ac_no==3 boundary feature; name+reservation fallback to 99007.
    assert by_eci[3]["match_method"] == "name_reservation_join"
    assert by_eci[3]["lgd_ac_id"] == 99007

    # eci 4: no boundary feature -> unmapped, null lgd.
    assert by_eci[4]["match_method"] == UNMAPPED
    assert by_eci[4]["lgd_ac_id"] is None

    # all rows cite the resolved HTL source.
    assert {r["source_id"] for r in rows} == {"src-htl-test"}
    assert {r["match_method"] for r in rows} <= MATCH_METHODS

    # the oracle: bijection + exact cover over the SoT universe.
    sot = {("S99", 1), ("S99", 2), ("S99", 3), ("S99", 4)}
    assert_bijection(rows, sot_acs=sot)


def test_harvester_writes_typed_parquet(build_module: Any, fixture_root: Path) -> None:
    con = duckdb.connect()
    rows = build_module.build_rows(fixture_root, con)
    out = fixture_root / "taxonomy" / "ac_crosswalk.parquet"
    build_module.write_parquet(con, rows, out)
    cols = con.execute(
        "SELECT column_name, column_type FROM (DESCRIBE SELECT * FROM read_parquet(?))",
        [out.as_posix()],
    ).fetchall()
    con.close()
    coltypes = dict(cols)
    assert coltypes["lgd_ac_id"] == "INTEGER"
    assert coltypes["eci_no"] == "INTEGER"
    assert coltypes["state_code"] == "VARCHAR"
    # the unmapped row's lgd is NULL on disk.
    con2 = duckdb.connect()
    null_count = con2.execute(
        "SELECT count(*) FROM read_parquet(?) WHERE lgd_ac_id IS NULL",
        [out.as_posix()],
    ).fetchone()[0]
    con2.close()
    assert null_count == 1


def test_shipped_crosswalk_passes_oracle() -> None:
    """Load-bearing guard: the committed crosswalk MUST be a valid bijection
    with exact cover over the real SoT AC universe."""
    datasets = REPO_ROOT / "datasets"
    parquet = datasets / "taxonomy" / "ac_crosswalk.parquet"
    if not parquet.is_file():
        pytest.skip("ac_crosswalk.parquet not built yet")

    con = duckdb.connect()
    rows = [
        dict(zip(("state_code", "eci_no", "lgd_ac_id", "ac_id", "match_method"), r, strict=True))
        for r in con.execute(
            "SELECT state_code, eci_no, lgd_ac_id, ac_id, match_method "
            "FROM read_parquet(?)",
            [parquet.as_posix()],
        ).fetchall()
    ]
    con.close()

    # Independent SoT universe straight from constituencies.json.
    states_dir = datasets / "reference" / "in" / "states"
    sot: set[tuple[str, int]] = set()
    for state_dir in states_dir.iterdir():
        cfile = state_dir / "constituencies.json"
        if not cfile.is_file():
            continue
        doc = json.loads(cfile.read_text(encoding="utf-8"))
        if doc.get("body") != "AC":
            continue
        for ac in doc["constituencies"]:
            sot.add((doc["state"], int(ac["eci_no"])))

    assert_bijection(rows, sot_acs=sot)
