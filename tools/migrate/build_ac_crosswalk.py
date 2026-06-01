"""Harvest the AC crosswalk parquet (eci_no <-> lgd_ac_id) from boundary AC_ID.

Producer for the ``ac_crosswalk`` Canonical Data Model defined in Row A1 of
``TODO/20260530-eci-to-lgd-acid-migration-plan.md`` (schema
``datasets/schemas/ac-crosswalk.schema.json``, contract + oracle in
``backend/yen_gov/canonical/ac_crosswalk.py``). This is Row A2.

What it does
------------
Materialises one crosswalk row per ``(state_code, eci_no)`` over the SoT AC
universe (``datasets/reference/in/states/<CODE>/constituencies.json``), binding
each ECI ballot number to its LGD Assembly Constituency code (``lgd_ac_id``)
harvested from the Hindustan Times Labs (HTL) state-AC boundary shards
(``datasets/boundaries/in/ac/state=in_<code>/all.geojson``).

Binding algorithm (per state)
-----------------------------
1. Load the boundary features that carry an ``AC_ID`` property. ``AC_ID`` is an
   LGD code = ``st_code`` (2-digit) ++ ``ac_no`` (3-digit), e.g. ``"33005"``.
2. Drop cross-state spillover: a partition file can contain a handful of
   neighbouring-state features (the S22 / Tamil Nadu file carries a few
   Puducherry features). Keep only the modal ``st_code`` (the dominant state).
3. For each SoT AC ``(eci_no, name, reservation)``:
   * SoT precedence - if the SoT AC item carries a verified ``lgd_ac_id``
     (constituency.schema.json v4.2, Row C1), it is authoritative and outranks
     every boundary-harvested match below; the row is ``lgd_direct``. This is
     the repeatable fill path: progressively, per state, a SoT edit can recover
     an LGD code that is genuinely absent from the in-repo boundary data (no
     value is ever fabricated - the SoT must already hold a verified code).
   * ``lgd_direct`` - a unique boundary feature has ``ac_no == eci_no``. The
     HTL bundle is ECI-numbered, so the ballot number is the binding key. Note
     ``lgd_ac_id = int(AC_ID)`` is taken verbatim - it already encodes
     bifurcations (Andhra Pradesh keeps the undivided unified range ``28120..``,
     Telangana carries the new census code ``36001..``); the two never collide.
   * ``name_reservation_join`` - no ``ac_no`` match, but a unique boundary
     feature matches on normalised ``(name, reservation)``.
   * ``unmapped`` - neither, and no SoT ``lgd_ac_id``; ``lgd_ac_id`` is NULL.
     Whole states with no boundary ``AC_ID`` (S03 / Assam, U08 / J&K) fall here
     until a verified LGD code is added to their SoT.

The ``ac_id`` (entity_id, FK to dim_acs), ``ac_name`` and ``delim_year`` columns
are read straight from ``datasets/elections/dim_acs.parquet`` (delim_year=2008,
the current delimitation) rather than reconstructed, so the crosswalk's
``ac_id`` is byte-identical to the canonical AC entity it will be lifted onto in
Row A3. The SoT AC set is a strict subset of dim_acs(2008) (verified: every SoT
``(state, eci_no)`` has a 2008 dim row); the ~10 S02 dim-only ACs absent from
the SoT are intentionally out of the crosswalk universe.

Layer note (CLAUDE.md section 4)
--------------------------------
``tools/`` MUST NOT import ``backend/`` runtime modules. This script therefore
does NOT import the ``assert_bijection`` oracle or ``derive_source_id``; it
looks the HTL ``source_id`` up from ``sources.parquet`` by its citation triple,
and the bijection-and-completeness oracle runs in
``backend/tests/test_build_ac_crosswalk.py`` against the written table.

Run
---
``python tools/migrate/build_ac_crosswalk.py [--datasets-root .] [--dry-run]``
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import duckdb

# --- constants ----------------------------------------------------------------

#: The current delimitation. dim_acs carries both 1976 and 2008 AC entities;
#: the crosswalk binds the 2008 set (the live constituencies + geometry).
CURRENT_DELIM_YEAR = 2008

#: HTL boundary citation triple (producer, title, vintage). The single AC-level
#: boundary corpus that carries AC_ID. Mirrors the entry in
#: ``backend/yen_gov/canonical/boundary_layers_seed.py``; we look its
#: ``source_id`` up from sources.parquet rather than import the backend.
HTL_TRIPLE = (
    "Hindustan Times Labs",
    "HTL state-AC shapefile bundle",
    "2008 Delimitation",
)

MATCH_LGD_DIRECT = "lgd_direct"
MATCH_NAME_RESERVATION = "name_reservation_join"
MATCH_UNMAPPED = "unmapped"

_RESERVATION_SUFFIX_RE = re.compile(r"\((s[ct])\)", re.IGNORECASE)


# --- normalisation helpers ----------------------------------------------------


def _norm_name(name: str | None) -> str:
    """Lower-case, drop a trailing ``(SC)``/``(ST)`` reservation tag, collapse
    non-alphanumerics to single spaces. Used only for the name fallback join."""
    s = (name or "").lower().strip()
    s = re.sub(r"\(s[ct]\)", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _reservation_from_boundary_name(name: str | None) -> str:
    """Derive ``GEN``/``SC``/``ST`` from a boundary ``ac_name`` suffix."""
    m = _RESERVATION_SUFFIX_RE.search(name or "")
    if not m:
        return "GEN"
    return "SC" if m.group(1).lower() == "sc" else "ST"


# --- loaders ------------------------------------------------------------------


def _load_sot(root: Path) -> list[dict[str, Any]]:
    """Read every SoT ``constituencies.json`` into ordered AC records.

    Returns dicts with ``state_code``, ``eci_no``, ``name``, ``reservation`` and
    ``sot_lgd_ac_id`` (the optional nullable ``lgd_ac_id`` declared on the AC item
    per constituency.schema.json v4.2 / Row C1, or ``None`` when absent). When a
    SoT carries a verified ``lgd_ac_id`` it is authoritative and outranks the
    boundary-harvested ``AC_ID`` in :func:`build_rows`.
    """
    states_dir = root / "reference" / "in" / "states"
    out: list[dict[str, Any]] = []
    for state_dir in sorted(p for p in states_dir.iterdir() if p.is_dir()):
        doc = json.loads(
            (state_dir / "constituencies.json").read_text(encoding="utf-8")
        )
        state_code = doc["state"]
        for ac in doc["constituencies"]:
            raw_lgd = ac.get("lgd_ac_id")
            out.append(
                {
                    "state_code": state_code,
                    "eci_no": int(ac["eci_no"]),
                    "name": ac["name"],
                    "reservation": ac.get("reservation", "GEN"),
                    "sot_lgd_ac_id": int(raw_lgd) if raw_lgd is not None else None,
                }
            )
    return out


def _load_dim_acs(
    con: duckdb.DuckDBPyConnection, root: Path
) -> dict[tuple[str, int], tuple[str, str]]:
    """Map ``(state_code, eci_no) -> (ac_id, name)`` for the current delim year."""
    path = (root / "elections" / "dim_acs.parquet").as_posix()
    rows = con.execute(
        "SELECT state_code, eci_no, ac_id, name FROM read_parquet(?) "
        "WHERE delim_year = ?",
        [path, CURRENT_DELIM_YEAR],
    ).fetchall()
    out: dict[tuple[str, int], tuple[str, str]] = {}
    for state_code, eci_no, ac_id, name in rows:
        out[(str(state_code), int(eci_no))] = (str(ac_id), str(name))
    return out


def _htl_source_id(con: duckdb.DuckDBPyConnection, root: Path) -> str:
    """Resolve the HTL boundary ``source_id`` from sources.parquet by triple."""
    path = (root / "taxonomy" / "sources.parquet").as_posix()
    producer, title, vintage = HTL_TRIPLE
    rows = con.execute(
        "SELECT source_id FROM read_parquet(?) "
        "WHERE producer = ? AND title = ? AND vintage = ?",
        [path, producer, title, vintage],
    ).fetchall()
    if len(rows) != 1:
        raise SystemExit(
            f"expected exactly one sources.parquet row for HTL triple "
            f"{HTL_TRIPLE!r}, found {len(rows)}"
        )
    return str(rows[0][0])


def _boundary_index(
    root: Path, state_code: str
) -> tuple[dict[int, list[dict]], dict[tuple[str, str], list[dict]]] | None:
    """Build ``ac_no -> [feature]`` and ``(norm_name, reservation) -> [feature]``
    indexes for a state's AC boundary, after dropping cross-state spillover.

    Returns ``None`` when the partition is missing or carries no ``AC_ID``.
    """
    path = (
        root
        / "boundaries"
        / "in"
        / "ac"
        / f"state=in_{state_code.lower()}"
        / "all.geojson"
    )
    if not path.is_file():
        return None
    gj = json.loads(path.read_text(encoding="utf-8"))
    props = [
        f["properties"]
        for f in gj.get("features", [])
        if f.get("properties", {}).get("AC_ID")
    ]
    if not props:
        return None
    # Drop spillover: keep only the dominant (modal) st_code.
    modal = Counter(str(p.get("st_code")) for p in props).most_common(1)[0][0]
    feats = [p for p in props if str(p.get("st_code")) == modal]
    by_acno: dict[int, list[dict]] = defaultdict(list)
    by_namer: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for p in feats:
        by_acno[int(p["ac_no"])].append(p)
        by_namer[
            (_norm_name(p.get("ac_name")), _reservation_from_boundary_name(p.get("ac_name")))
        ].append(p)
    return by_acno, by_namer


# --- core build ---------------------------------------------------------------


def build_rows(root: Path, con: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Harvest the full crosswalk: one row per SoT ``(state_code, eci_no)``."""
    sot = _load_sot(root)
    dim = _load_dim_acs(con, root)
    source_id = _htl_source_id(con, root)

    missing_dim = sorted(
        {(r["state_code"], r["eci_no"]) for r in sot}
        - set(dim)
    )
    if missing_dim:
        raise SystemExit(
            f"{len(missing_dim)} SoT AC(s) have no dim_acs({CURRENT_DELIM_YEAR}) "
            f"entry; cannot resolve ac_id: {missing_dim[:10]}"
        )

    # Cache per-state boundary indexes.
    indexes: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    for rec in sot:
        state_code = rec["state_code"]
        eci_no = rec["eci_no"]
        ac_id, ac_name = dim[(state_code, eci_no)]
        if state_code not in indexes:
            indexes[state_code] = _boundary_index(root, state_code)
        idx = indexes[state_code]

        lgd_ac_id: int | None = None
        method = MATCH_UNMAPPED
        sot_lgd = rec.get("sot_lgd_ac_id")
        if sot_lgd is not None:
            # A verified SoT-provided lgd_ac_id (constituency.schema.json v4.2,
            # Row C1) is authoritative and outranks the boundary AC_ID.
            lgd_ac_id = int(sot_lgd)
            method = MATCH_LGD_DIRECT
        elif idx is not None:
            by_acno, by_namer = idx
            acno_codes = sorted({int(p["AC_ID"]) for p in by_acno.get(eci_no, [])})
            if len(acno_codes) == 1:
                lgd_ac_id = acno_codes[0]
                method = MATCH_LGD_DIRECT
            else:
                key = (_norm_name(rec["name"]), rec["reservation"])
                name_codes = sorted({int(p["AC_ID"]) for p in by_namer.get(key, [])})
                if len(name_codes) == 1:
                    lgd_ac_id = name_codes[0]
                    method = MATCH_NAME_RESERVATION

        rows.append(
            {
                "state_code": state_code,
                "eci_no": eci_no,
                "lgd_ac_id": lgd_ac_id,
                "ac_id": ac_id,
                "ac_name": ac_name,
                "delim_year": CURRENT_DELIM_YEAR,
                "match_method": method,
                "source_id": source_id,
            }
        )
    return rows


def write_parquet(
    con: duckdb.DuckDBPyConnection, rows: list[dict[str, Any]], out_path: Path
) -> None:
    """Write the crosswalk rows to a typed parquet (nullable ``lgd_ac_id``)."""
    con.execute(
        """
        CREATE OR REPLACE TABLE _cx (
            state_code   VARCHAR,
            eci_no       INTEGER,
            lgd_ac_id    INTEGER,
            ac_id        VARCHAR,
            ac_name      VARCHAR,
            delim_year   INTEGER,
            match_method VARCHAR,
            source_id    VARCHAR
        )
        """
    )
    con.executemany(
        "INSERT INTO _cx VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                r["state_code"],
                r["eci_no"],
                r["lgd_ac_id"],
                r["ac_id"],
                r["ac_name"],
                r["delim_year"],
                r["match_method"],
                r["source_id"],
            )
            for r in rows
        ],
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    con.execute(
        "COPY (SELECT * FROM _cx ORDER BY state_code, eci_no) TO ? (FORMAT PARQUET)",
        [out_path.as_posix()],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--datasets-root",
        default="datasets",
        help="path to the datasets/ root (default: ./datasets)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="harvest + report distribution but do not write the parquet",
    )
    args = parser.parse_args()

    root = Path(args.datasets_root)
    con = duckdb.connect()
    rows = build_rows(root, con)

    dist = Counter(r["match_method"] for r in rows)
    mapped = sum(1 for r in rows if r["lgd_ac_id"] is not None)
    print(f"crosswalk rows: {len(rows)}")
    print(f"  match_method : {dict(dist)}")
    print(f"  mapped       : {mapped} / {len(rows)} "
          f"({100 * mapped / len(rows):.1f}%)")

    if args.dry_run:
        print("dry-run: parquet not written")
        return

    out_path = root / "taxonomy" / "ac_crosswalk.parquet"
    write_parquet(con, rows, out_path)
    print(f"wrote {out_path.as_posix()}")


if __name__ == "__main__":
    main()
