"""B2b.5.0c entities/electoral_district_membership.csv emitter (clean-start).

Emits the AC <-> LGD-district 1:many membership table from the committed LGD
parsed snapshot ``datasets/reference/lgd/constituency_district_membership.csv``
(B2b.5.0a), which is sourced from the PRI super-file's per-AC village rows. This
SUPERSEDES + RENAMES the prior ``electoral_lgd_xwalk.csv`` (round-7): the
relation is LGD-canonical (an AC can span districts per the LGD Constituency
Coverage report), not a geometry artifact.

Columns (per ``datasets/data/_schema/columns.json`` after 0c):

- ``electoral_id``    (FK -> ``entities/electoral.csv.entity_id``; the AC)
- ``lgd_district_id`` (FK -> ``entities/geo.csv.entity_id``; the district)
- ``is_primary``      (boolean; the plurality district the AC mostly sits in)
- ``lgd_snapshot``    (the dated LGD snapshot the edge was sourced from)
- ``source_id``       (FK -> ``entities/source.csv.source_id``; the LGD citation)

Resolution: the snapshot carries ``(lgd_state_code, ac_lgd_code, lgd_district_code,
is_primary)``. The AC ``electoral_id`` is rebuilt as
``IN-AC-<delim>-<state-slug>-<ac_lgd_code>`` (matching ``electoral.csv``); the
district geo entity_id is resolved from the ``lgd:<code>`` alias on
``entities/geo.csv``. State slug comes from ``entities/state_codes.csv``.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from yen_gov.canonical.csv_writer import write_csv


FILE_CLASS = "datasets/data/entities/electoral_district_membership.csv"

DELIM_YEAR_V1 = 2008


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _state_slug_index(state_codes_csv: Path) -> dict[str, str]:
    return {r["lgd_state_id"]: r["slug"] for r in _read_csv_rows(state_codes_csv)}


def _district_geo_index(geo_csv: Path) -> dict[str, str]:
    """Map LGD district code -> geo.csv district entity_id via the ``lgd:`` alias."""
    out: dict[str, str] = {}
    for r in _read_csv_rows(geo_csv):
        if r.get("entity_kind") != "district":
            continue
        for token in (r.get("aliases") or "").split("|"):
            token = token.strip()
            if token.startswith("lgd:"):
                out[token[len("lgd:"):]] = r["entity_id"]
                break
    return out


def emit(
    *,
    membership_snapshot_csv: Path,
    state_codes_csv: Path,
    geo_csv: Path,
    source_id: str,
    lgd_snapshot: str,
    out_path: Path,
    delim_year: int = DELIM_YEAR_V1,
) -> Path:
    """Emit ``out_path`` from the LGD membership snapshot; return the path.

    Raises:
        FileNotFoundError: a required input is missing.
        ValueError: an edge references an unknown state code or an LGD district
            code with no geo.csv entity, or ``is_primary`` is not a clean boolean.
    """
    for p in (membership_snapshot_csv, state_codes_csv, geo_csv):
        if not p.exists():
            raise FileNotFoundError(p)

    state_slug_by_code = _state_slug_index(state_codes_csv)
    district_geo_by_code = _district_geo_index(geo_csv)
    snapshot = _read_csv_rows(membership_snapshot_csv)

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for r in snapshot:
        state_code = r["lgd_state_code"]
        state_slug = state_slug_by_code.get(state_code)
        if state_slug is None:
            raise ValueError(f"membership edge references unknown lgd_state_code={state_code!r}")
        electoral_id = f"IN-AC-{delim_year}-{state_slug}-{r['ac_lgd_code']}"
        district_code = r["lgd_district_code"]
        district_geo_id = district_geo_by_code.get(district_code)
        if district_geo_id is None:
            raise ValueError(
                f"membership edge AC {r['ac_lgd_code']} references LGD district "
                f"code {district_code!r} with no geo.csv entity"
            )
        is_primary_raw = (r.get("is_primary") or "").strip().lower()
        if is_primary_raw not in ("true", "false"):
            raise ValueError(
                f"membership edge AC {r['ac_lgd_code']} district {district_code} "
                f"has non-boolean is_primary={r.get('is_primary')!r}"
            )
        key = (electoral_id, district_geo_id)
        if key in seen:
            raise ValueError(f"duplicate membership edge {key!r}")
        seen.add(key)
        rows.append(
            {
                "electoral_id": electoral_id,
                "lgd_district_id": district_geo_id,
                "is_primary": is_primary_raw == "true",
                "lgd_snapshot": lgd_snapshot,
                "source_id": source_id,
            }
        )

    return write_csv(path=out_path, file_class=FILE_CLASS, rows=rows)
