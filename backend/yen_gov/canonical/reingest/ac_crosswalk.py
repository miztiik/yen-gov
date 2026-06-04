"""B2b.4.6 ac_crosswalk parquet -> long-format CSV reingest.

Transcodes ``datasets/taxonomy/ac_crosswalk.parquet`` (4113 rows; the
authoritative ECI-no -> LGD-AC-id mapping per delim) into
``datasets/data/entities/ac_crosswalk.csv`` (parent plan section 21.6 /
22.4; sub-sub-plan B2b.4 row B2b.4.6).

The source column ``state_code`` carries the ECI S/U code (e.g. ``S01``).
On emit it is re-keyed to the LGD state ``entity_id`` (e.g.
``andhra-pradesh``) via ``datasets/taxonomy/lgd_states.json`` and renamed
to ``state_entity_id`` so the FK target into
``datasets/data/entities/geo.csv.entity_id`` is explicit. PK
``(state_entity_id, delim_year, eci_no)``.

This file is the authoritative ECI-no -> LGD-AC-id mapping. It is NOT the
same as ``datasets/data/entities/electoral_lgd_xwalk.csv`` (253 rows;
boundary-overlap decay-receipt shape).

Public surface:

    from yen_gov.canonical.reingest.ac_crosswalk import emit
    emit(parquet_path=..., out_path=..., lgd_states_json=...)

No mocks (Holy Law #7); duckdb reads the real parquet file. Tests stage a
miniature fixture parquet under ``tmp_path`` to exercise the path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import duckdb

from yen_gov.canonical.csv_writer import write_csv
from yen_gov.canonical.reingest.energy_datapoints import load_eci_to_slug

__all__ = ["FILE_CLASS", "emit", "load_eci_to_slug"]


FILE_CLASS = "datasets/data/entities/ac_crosswalk.csv"


def _project_parquet(
    parquet_path: Path, eci_to_slug: Mapping[str, str]
) -> list[dict[str, Any]]:
    sql = (
        "SELECT state_code, eci_no, lgd_ac_id, ac_id, ac_name, "
        "delim_year, match_method, source_id "
        f"FROM read_parquet('{parquet_path.as_posix()}') "
        "ORDER BY state_code, delim_year, eci_no"
    )
    rows: list[dict[str, Any]] = []
    for (
        state_code,
        eci_no,
        lgd_ac_id,
        ac_id,
        ac_name,
        delim_year,
        match_method,
        source_id,
    ) in duckdb.sql(sql).fetchall():
        slug = eci_to_slug.get(state_code)
        if slug is None:
            raise KeyError(
                f"no LGD slug for ECI st_code {state_code!r} "
                f"(eci_no {eci_no!r}, delim_year {delim_year!r})"
            )
        rows.append(
            {
                "state_entity_id": slug,
                "delim_year": delim_year,
                "eci_no": eci_no,
                "lgd_ac_id": lgd_ac_id,
                "ac_id": ac_id,
                "ac_name": ac_name,
                "match_method": match_method,
                "source_id": source_id,
            }
        )
    rows.sort(
        key=lambda r: (r["state_entity_id"], r["delim_year"], r["eci_no"])
    )
    return rows


def emit(
    *,
    parquet_path: Path,
    out_path: Path,
    lgd_states_json: Path,
) -> Path:
    """Transcode the ac_crosswalk parquet into the long-format CSV.

    Args:
        parquet_path: path to ``datasets/taxonomy/ac_crosswalk.parquet``.
        out_path: target CSV path
            (``datasets/data/entities/ac_crosswalk.csv``).
        lgd_states_json: path to ``datasets/taxonomy/lgd_states.json``
            used for the ECI -> LGD slug re-key.

    Returns:
        The resolved CSV path.

    Raises:
        FileNotFoundError: ``parquet_path`` does not exist.
        KeyError: a row's ``state_code`` has no LGD slug in the register.
    """
    if not parquet_path.exists():
        raise FileNotFoundError(parquet_path)
    eci_to_slug = load_eci_to_slug(lgd_states_json)
    rows = _project_parquet(parquet_path, eci_to_slug)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    return write_csv(path=out_path, file_class=FILE_CLASS, rows=rows)
