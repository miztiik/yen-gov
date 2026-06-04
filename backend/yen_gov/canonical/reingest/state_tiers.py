"""B2b.4.3 state_tiers parquet -> long-format CSV reingest.

Transcodes ``datasets/taxonomy/state_tiers.parquet`` (104 rows; M:N
tier -> state register) into ``datasets/data/state_tiers.csv`` (parent
plan section 21.6 / 22.4; sub-sub-plan B2b.4 row B2b.4.3).

The source column ``state_code`` carries the ECI S/U code (e.g. ``S01``).
On emit it is re-keyed to the LGD state ``entity_id`` (e.g.
``andhra-pradesh``) via ``datasets/taxonomy/lgd_states.json`` and renamed
to ``state_entity_id`` so the FK target into
``datasets/data/entities/geo.csv.entity_id`` is explicit. PK
``(tier_id, state_entity_id)``.

Public surface:

    from yen_gov.canonical.reingest.state_tiers import emit
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


FILE_CLASS = "datasets/data/state_tiers.csv"

_COLUMNS = (
    "tier_id",
    "tier_label",
    "definition_kind",
    "definition",
    "authority",
    "state_entity_id",
    "notes",
)


def _project_parquet(
    parquet_path: Path, eci_to_slug: Mapping[str, str]
) -> list[dict[str, Any]]:
    sql = (
        "SELECT tier_id, tier_label, definition_kind, definition, "
        "authority, state_code, notes "
        f"FROM read_parquet('{parquet_path.as_posix()}') "
        "ORDER BY tier_id, state_code"
    )
    rows: list[dict[str, Any]] = []
    for (
        tier_id,
        tier_label,
        definition_kind,
        definition,
        authority,
        state_code,
        notes,
    ) in duckdb.sql(sql).fetchall():
        slug = eci_to_slug.get(state_code)
        if slug is None:
            raise KeyError(
                f"no LGD slug for ECI st_code {state_code!r} "
                f"(tier_id {tier_id!r})"
            )
        rows.append(
            {
                "tier_id": tier_id,
                "tier_label": tier_label,
                "definition_kind": definition_kind,
                "definition": definition,
                "authority": authority,
                "state_entity_id": slug,
                "notes": notes,
            }
        )
    rows.sort(key=lambda r: (r["tier_id"], r["state_entity_id"]))
    return rows


def emit(
    *,
    parquet_path: Path,
    out_path: Path,
    lgd_states_json: Path,
) -> Path:
    """Transcode the state_tiers parquet into the long-format CSV.

    Args:
        parquet_path: path to ``datasets/taxonomy/state_tiers.parquet``.
        out_path: target CSV path (``datasets/data/state_tiers.csv``).
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
