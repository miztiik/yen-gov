"""B2b.1 energy parquet -> long-format CSV reingest.

Transcodes the six surviving energy parquets under ``datasets/energy/*.parquet``
into per-indicator long-format CSVs at
``datasets/data/datapoints/geo/<indicator_id>.csv`` (parent plan section
21.2 / 21.6; sub-plan B2b.1).

Source parquet shape (all six share columns):

    observation_id, entity_id, year, period_label, period_seq,
    indicator_id, value_numeric, value_text, source_id, derivation

Target CSV shape (``datasets/data/datapoints/geo/*.csv``):

    entity_id, time, value, source_id

Projection rules:

- ``time`` <- ``year`` (parquets already have one row per (entity, year,
  indicator); the period_label/period_seq carry sub-annual tagging but
  uniqueness holds at annual grain - verified during sub-plan reconnaissance).
- ``value`` <- ``value_numeric`` (``value_text`` is null across all six
  parquets in the on-disk corpus; if a future emit lands a text value, this
  module must split into a separate text-typed file class).
- ``entity_id`` <- ECI-style ``IN-S<NN>`` re-keyed to LGD slug via
  ``datasets/taxonomy/lgd_states.json`` (the country sentinel ``IN`` is
  preserved as-is; matches ``entities/geo.csv.entity_id`` keyed by LGD slug).
  This re-key is necessary because the geo entity file class FKs to LGD,
  not ECI (parent plan invariant 22.4#2 LGD/ECI key separation).
- ``source_id`` <- carried through; FK to ``entities/source.csv``.

The four parquet columns dropped during projection (``observation_id``,
``period_label``, ``period_seq``, ``derivation``) are informational and not
part of the long-format CSV contract; provenance for analytical lineage is
covered by ``source_id`` + the citation ledger.

Public surface:

    from yen_gov.canonical.reingest.energy_datapoints import emit
    emit(parquet_dir=..., lgd_states_json=..., out_dir=...)

No mocks (Holy Law #7); duckdb reads the real parquet files. Tests stage
miniature fixture parquets under ``tmp_path`` to exercise the path.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import duckdb

from yen_gov.canonical.csv_writer import write_csv

__all__ = ["FILE_CLASS", "emit", "load_eci_to_slug"]


FILE_CLASS = "datasets/data/datapoints/geo/*.csv"
COUNTRY_ENTITY_ID = "IN"


def load_eci_to_slug(lgd_states_json: Path) -> dict[str, str]:
    """Return the ``eci_st_code -> lgd-slug`` map from the LGD register."""
    payload = json.loads(lgd_states_json.read_text(encoding="utf-8"))
    states = payload.get("states")
    if not isinstance(states, list):
        raise ValueError(
            f"{lgd_states_json}: missing or non-list 'states' key"
        )
    out: dict[str, str] = {}
    for row in states:
        code = row.get("eci_st_code")
        slug = row.get("slug")
        if not code or not slug:
            continue
        out[str(code)] = str(slug)
    return out


def _map_entity(eci_entity_id: str, eci_to_slug: Mapping[str, str]) -> str:
    if eci_entity_id == COUNTRY_ENTITY_ID:
        return COUNTRY_ENTITY_ID
    if not eci_entity_id.startswith("IN-"):
        raise ValueError(
            f"unrecognised entity_id shape {eci_entity_id!r}; expected 'IN' or 'IN-<eci_st_code>'"
        )
    code = eci_entity_id[len("IN-") :]
    slug = eci_to_slug.get(code)
    if slug is None:
        raise KeyError(
            f"no LGD slug for ECI st_code {code!r} (entity_id {eci_entity_id!r})"
        )
    return slug


def _project_parquet(parquet_path: Path) -> list[dict[str, Any]]:
    sql = (
        "SELECT entity_id, year AS time, value_numeric AS value, "
        "indicator_id, source_id "
        f"FROM read_parquet('{parquet_path.as_posix()}') "
        "ORDER BY indicator_id, entity_id, year"
    )
    rel = duckdb.sql(sql)
    cols = [d[0] for d in rel.description]
    rows: list[dict[str, Any]] = []
    for tup in rel.fetchall():
        rows.append(dict(zip(cols, tup, strict=True)))
    return rows


def emit(
    *,
    parquet_dir: Path,
    lgd_states_json: Path,
    out_dir: Path,
    parquet_glob: str = "*.parquet",
) -> list[Path]:
    """Transcode every parquet under ``parquet_dir`` into per-indicator CSVs.

    Args:
        parquet_dir: directory containing the energy parquets (typically
            ``datasets/energy``).
        lgd_states_json: path to ``datasets/taxonomy/lgd_states.json`` (the
            ECI <-> LGD lookup; CLAUDE.md F3 / sub-plan reconnaissance).
        out_dir: directory to emit ``<indicator_id>.csv`` into (typically
            ``datasets/data/datapoints/geo``).
        parquet_glob: override for tests; production uses the default.

    Returns:
        Sorted list of emitted CSV paths.

    Raises:
        FileNotFoundError: ``parquet_dir`` is empty / missing.
        KeyError: an entity_id carries an ECI st_code with no LGD slug.
        ValueError: an entity_id is neither ``IN`` nor ``IN-<eci_st_code>``.
    """
    parquet_paths = sorted(parquet_dir.glob(parquet_glob))
    if not parquet_paths:
        raise FileNotFoundError(
            f"no parquet files match {parquet_dir / parquet_glob}"
        )

    eci_to_slug = load_eci_to_slug(lgd_states_json)

    by_indicator: dict[str, list[dict[str, Any]]] = {}
    for parquet_path in parquet_paths:
        for row in _project_parquet(parquet_path):
            indicator_id = row["indicator_id"]
            entity_id = _map_entity(row["entity_id"], eci_to_slug)
            by_indicator.setdefault(indicator_id, []).append(
                {
                    "entity_id": entity_id,
                    "time": row["time"],
                    "value": row["value"],
                    "source_id": row["source_id"],
                }
            )

    out_dir.mkdir(parents=True, exist_ok=True)
    emitted: list[Path] = []
    for indicator_id, rows in sorted(by_indicator.items()):
        target = out_dir / f"{indicator_id}.csv"
        write_csv(path=target, file_class=FILE_CLASS, rows=rows)
        emitted.append(target)
    return emitted
