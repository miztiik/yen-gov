"""Delhi AC <-> district membership supplement (geometry-derived).

WHY this exists: Delhi is an urban NCT with essentially no Panchayati-Raj
villages, so its AC->district edges are ABSENT from the LGD PRI super-file that
``electoral_district_membership_csv`` consumes -- LGD returns 0 rows for state
code 7 (re-confirmed by a fresh 2026-06-23 Delhi PRI export: header only, 0 data
rows; and the LGD all-states Constituency Coverage report omits state 7
entirely). The AC->district relation DOES exist as a per-AC ``Dist_LGD`` /
``dist_name`` PROPERTY on the committed Survey-of-India / ramSeraph Assembly
Constituency boundary geometry
``datasets/boundaries/electoral/delim=2024/ac/all.topojson`` (source
``src-a1dd899f902d``, cited by ``boundary_layer.csv`` for
``boundaries.electoral.delim=2024.ac``).

This module reads that district ATTRIBUTE (a property read -- NO spatial
overlay) and APPENDS the 70 Delhi AC->district edges to
``electoral_district_membership.csv``. The join key is the same ``lgd:<code>``
alias the LGD builder uses: each AC's ``Dist_LGD`` (an LGD district code)
resolves to a ``geo.csv`` district ``entity_id``. Delhi's electoral_ids use the
``IN-AC-2008-delhi-eci<ac_no>`` form (electoral.csv built Delhi from the ECI
constituency list, since the LGD register had no Delhi ACs).

It is idempotent: existing Delhi rows are dropped before the fresh ones are
appended, and ``write_csv`` re-sorts by the composite PK, so a re-run is stable.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_writer import write_csv

FILE_CLASS = "datasets/data/entities/electoral_district_membership.csv"

# The committed ramSeraph "Indian Admin Boundaries (LGD-keyed)" AC topojson is
# the origin of the district attribute; REUSE its existing source row (the same
# id boundary_layer.csv cites for boundaries.electoral.delim=2024.ac).
SOURCE_ID = "src-a1dd899f902d"
# Snapshot tag = the map-geometry consolidation that produced the committed AC
# topojson (boundary_layer.csv note, 2026-06-16).
GEOMETRY_SNAPSHOT = "2026-06-16"

DELIM_YEAR = 2008
STATE_CODE = "07"  # LGD / census-2011 state code for NCT of Delhi
STATE_SLUG = "delhi"
AC_TOPOJSON_REL = "datasets/boundaries/electoral/delim=2024/ac/all.topojson"


def load_delhi_ac_props(ac_topojson: Path) -> list[dict[str, Any]]:
    """Return the property dicts of every Delhi AC geometry in the AC topojson."""
    topo = json.loads(ac_topojson.read_text(encoding="utf-8"))
    geoms = topo["objects"]["ac"]["geometries"]
    return [
        g["properties"]
        for g in geoms
        if str(g["properties"].get("st_code")) == STATE_CODE
    ]


def load_geo_lgd_index(geo_csv: Path) -> dict[str, str]:
    """Map LGD district code -> geo.csv district entity_id via the ``lgd:`` alias."""
    out: dict[str, str] = {}
    with geo_csv.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if r.get("entity_kind") != "district":
                continue
            for token in (r.get("aliases") or "").split("|"):
                token = token.strip()
                if token.startswith("lgd:"):
                    out[token[len("lgd:") :]] = r["entity_id"]
                    break
    return out


def build_delhi_membership_rows(
    ac_props: list[dict[str, Any]],
    geo_lgd_index: dict[str, str],
    *,
    source_id: str = SOURCE_ID,
    lgd_snapshot: str = GEOMETRY_SNAPSHOT,
) -> list[dict[str, Any]]:
    """Pure builder: Delhi AC geometry props -> membership rows.

    Raises ``ValueError`` when an AC's ``Dist_LGD`` has no ``geo.csv`` district
    (so a missing FK target is loud, never silently dropped).
    """
    rows: list[dict[str, Any]] = []
    for p in ac_props:
        ac_no = int(p["ac_no"])
        dist_lgd = str(p["Dist_LGD"])
        district_geo_id = geo_lgd_index.get(dist_lgd)
        if district_geo_id is None:
            raise ValueError(
                f"Delhi AC {ac_no} ({p.get('ac_name')!r}) Dist_LGD={dist_lgd} has "
                f"no geo.csv district entity (expected alias lgd:{dist_lgd})"
            )
        rows.append(
            {
                "electoral_id": f"IN-AC-{DELIM_YEAR}-{STATE_SLUG}-eci{ac_no}",
                "lgd_district_id": district_geo_id,
                "is_primary": True,
                "lgd_snapshot": lgd_snapshot,
                "source_id": source_id,
            }
        )
    return rows


def append_delhi_to_membership(
    *,
    membership_csv: Path,
    geo_csv: Path,
    ac_topojson: Path,
    source_id: str = SOURCE_ID,
    lgd_snapshot: str = GEOMETRY_SNAPSHOT,
) -> int:
    """Append the geometry-derived Delhi edges to ``membership_csv`` in place.

    Idempotent: any existing Delhi rows are dropped first. ``write_csv`` re-sorts
    by the composite PK and re-validates the column contract. Returns the number
    of Delhi rows written.
    """
    delhi_prefix = f"IN-AC-{DELIM_YEAR}-{STATE_SLUG}-"
    with membership_csv.open(encoding="utf-8", newline="") as fh:
        kept = [
            r
            for r in csv.DictReader(fh)
            if not r["electoral_id"].startswith(delhi_prefix)
        ]

    delhi_rows = build_delhi_membership_rows(
        load_delhi_ac_props(ac_topojson),
        load_geo_lgd_index(geo_csv),
        source_id=source_id,
        lgd_snapshot=lgd_snapshot,
    )
    write_csv(path=membership_csv, file_class=FILE_CLASS, rows=kept + delhi_rows)
    return len(delhi_rows)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    entities = repo_root / "datasets" / "data" / "entities"
    n = append_delhi_to_membership(
        membership_csv=entities / "electoral_district_membership.csv",
        geo_csv=entities / "geo.csv",
        ac_topojson=repo_root / AC_TOPOJSON_REL,
    )
    print(f"appended {n} Delhi AC->district edges (geometry-derived)")


if __name__ == "__main__":
    main()
