"""One-off driver for B2b.5.0c-2: regenerate electoral.csv +
electoral_district_membership.csv from the committed LGD parsed snapshot, and
ensure the LGD constituency-register source row exists in source.csv.

Run from repo root (cwd=backend for the module path).
"""
from __future__ import annotations

import csv
from pathlib import Path

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_validator import validate_csv
from yen_gov.canonical.seed import electoral_csv_from_snapshot as electoral
from yen_gov.canonical.seed import electoral_district_membership_csv as membership
from yen_gov.canonical.seed import (
    electoral_district_membership_delhi_geometry as delhi_geometry,
)

# The LGD constituency-register snapshot citation (round-8c vintage = download date).
LGD_SOURCE_OWNER = "Local Government Directory (Ministry of Panchayati Raj)"
LGD_SOURCE_TITLE = "LGD Constituency Coverage + Registers"
LGD_SOURCE_VINTAGE = "2026-06-05"
LGD_SOURCE_URL = "https://lgdirectory.gov.in"
LGD_SNAPSHOT = "2026-06-05"


def _ensure_source_row(source_csv: Path, source_id: str) -> None:
    """Append the LGD constituency-register source row if absent (SAME-PR rule)."""
    rows = []
    with source_csv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or ["source_id", "producer", "title", "vintage", "url"]
        rows = list(reader)
    if any(r["source_id"] == source_id for r in rows):
        return
    rows.append(
        {
            "source_id": source_id,
            "producer": LGD_SOURCE_OWNER,
            "title": LGD_SOURCE_TITLE,
            "vintage": LGD_SOURCE_VINTAGE,
            "url": LGD_SOURCE_URL,
        }
    )
    rows.sort(key=lambda r: r["source_id"])
    import io

    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    source_csv.write_text(buf.getvalue(), encoding="utf-8", newline="")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    snapshot = repo_root / "datasets" / "data" / "entities" / "lgd"
    entities = repo_root / "datasets" / "data" / "entities"
    source_csv = entities / "source.csv"

    source_id = derive_source_id(LGD_SOURCE_OWNER, LGD_SOURCE_TITLE, LGD_SOURCE_VINTAGE)
    _ensure_source_row(source_csv, source_id)

    electoral_out = entities / "electoral.csv"
    electoral.emit(
        constituencies_csv=snapshot / "constituencies.csv",
        state_codes_csv=entities / "state_codes.csv",
        out_path=electoral_out,
    )
    validate_csv(path=electoral_out, file_class=electoral.FILE_CLASS, repo_root=repo_root)

    membership_out = entities / "electoral_district_membership.csv"
    membership.emit(
        membership_snapshot_csv=snapshot / "constituency_district_membership.csv",
        state_codes_csv=entities / "state_codes.csv",
        geo_csv=entities / "geo.csv",
        source_id=source_id,
        lgd_snapshot=LGD_SNAPSHOT,
        out_path=membership_out,
    )
    validate_csv(path=membership_out, file_class=membership.FILE_CLASS, repo_root=repo_root)

    # Delhi is an urban NCT with no Panchayati-Raj villages, so the LGD PRI join
    # above emits 0 Delhi edges. Supplement them from the committed ramSeraph /
    # Survey-of-India AC boundary geometry's per-AC district attribute (a
    # property read, no spatial overlay). See the delhi_geometry module.
    n_delhi = delhi_geometry.append_delhi_to_membership(
        membership_csv=membership_out,
        geo_csv=entities / "geo.csv",
        ac_topojson=repo_root / delhi_geometry.AC_TOPOJSON_REL,
    )
    validate_csv(path=membership_out, file_class=membership.FILE_CLASS, repo_root=repo_root)

    n_el = len(electoral_out.read_text(encoding="utf-8").splitlines()) - 1
    n_mem = len(membership_out.read_text(encoding="utf-8").splitlines()) - 1
    print(f"appended {n_delhi} Delhi AC->district edges (geometry-derived)")
    print(f"LGD source_id: {source_id}")
    print(f"wrote electoral.csv ({n_el} rows)")
    print(f"wrote electoral_district_membership.csv ({n_mem} rows)")


if __name__ == "__main__":
    main()
