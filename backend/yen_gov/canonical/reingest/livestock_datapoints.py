"""B2b.2 livestock parquet -> long-format CSV reingest.

Transcodes the three surviving livestock parquets under
``datasets/livestock/*.parquet`` into per-indicator long-format CSVs at
``datasets/data/datapoints/geo/<indicator_id>.csv`` (parent plan section
21.2 / 21.6; sub-plan B2b.2).

Source parquet shape (all three share columns):

    observation_id, entity_id, year, period_label, period_seq,
    indicator_id, value_numeric, value_text, source_id, derivation

Target CSV shape (``datasets/data/datapoints/geo/*.csv``):

    entity_id, time, value, source_id

Projection rules (mirror B2b.1 with a district extension):

- ``time`` <- ``year`` (parquets carry one row per
  (entity, year, indicator); on-disk reconnaissance: 0 duplicate PKs across
  all three livestock parquets, 0 null value_numeric rows, 0 value_text-only
  rows - so the value column stays numeric and the file class is
  ``datasets/data/datapoints/geo/*.csv``).
- ``value`` <- ``value_numeric`` (``value_text`` is null across the entire
  livestock corpus on disk; if a future emit lands a text value, this module
  must split into a separate text-typed file class).
- ``entity_id`` <- the ECI-style id re-keyed to the LGD slug used by
  ``datasets/data/entities/geo.csv``. Three shapes appear in the livestock
  corpus and are handled here:

    * ``IN`` -> ``IN`` (country sentinel, preserved as-is).
    * ``IN-<eci_st_code>`` -> state slug via
      ``datasets/taxonomy/lgd_states.json``.
    * ``IN-<eci_st_code>-D<lgd_district_id>`` -> the
      ``<state-slug>/<district-slug>`` geo.csv entity_id resolved via the
      ``lgd:<id>`` alias column on ``datasets/data/entities/geo.csv``.

  This re-key is necessary because the geo entity file class FKs to LGD,
  not ECI (parent plan invariant 22.4#2 LGD/ECI key separation).
- ``source_id`` <- carried through; FK to ``entities/source.csv``.

The four parquet columns dropped during projection (``observation_id``,
``period_label``, ``period_seq``, ``derivation``) are informational and not
part of the long-format CSV contract; provenance for analytical lineage is
covered by ``source_id`` + the citation ledger.

Public surface:

    from yen_gov.canonical.reingest.livestock_datapoints import emit
    emit(parquet_dir=..., lgd_states_json=..., geo_entities_csv=..., out_dir=...)

No mocks (Holy Law #7); duckdb reads the real parquet + CSV files. Tests
stage miniature fixture parquets + geo.csv + lgd_states.json under
``tmp_path`` to exercise the path.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import duckdb

from yen_gov.canonical.csv_writer import write_csv

__all__ = [
    "FILE_CLASS",
    "emit",
    "load_eci_to_slug",
    "load_lgd_district_to_geo_entity",
]


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


def load_lgd_district_to_geo_entity(geo_entities_csv: Path) -> dict[str, str]:
    """Return the ``lgd_district_id -> geo.csv entity_id`` map.

    Parses the ``aliases`` column of ``datasets/data/entities/geo.csv``,
    extracting the ``lgd:<id>`` token on each ``entity_kind=district`` row.
    """
    out: dict[str, str] = {}
    with geo_entities_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("entity_kind") != "district":
                continue
            aliases = row.get("aliases") or ""
            entity_id = row.get("entity_id") or ""
            if not entity_id:
                continue
            for alias in aliases.split("|"):
                if alias.startswith("lgd:"):
                    lgd_id = alias[len("lgd:") :]
                    if lgd_id:
                        out[lgd_id] = entity_id
                    break
    return out


def _map_entity(
    eci_entity_id: str,
    eci_to_slug: Mapping[str, str],
    lgd_district_to_entity: Mapping[str, str],
) -> str:
    if eci_entity_id == COUNTRY_ENTITY_ID:
        return COUNTRY_ENTITY_ID
    if not eci_entity_id.startswith("IN-"):
        raise ValueError(
            f"unrecognised entity_id shape {eci_entity_id!r}; expected 'IN', "
            "'IN-<eci_st_code>' or 'IN-<eci_st_code>-D<lgd_district_id>'"
        )
    tail = eci_entity_id[len("IN-") :]
    if "-D" in tail:
        state_code, _, district_id = tail.partition("-D")
        if state_code not in eci_to_slug:
            raise KeyError(
                f"no LGD slug for ECI st_code {state_code!r} "
                f"(entity_id {eci_entity_id!r})"
            )
        if district_id not in lgd_district_to_entity:
            raise KeyError(
                f"no geo.csv entity for LGD district id {district_id!r} "
                f"(entity_id {eci_entity_id!r})"
            )
        return lgd_district_to_entity[district_id]
    if tail not in eci_to_slug:
        raise KeyError(
            f"no LGD slug for ECI st_code {tail!r} (entity_id {eci_entity_id!r})"
        )
    return eci_to_slug[tail]


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
    geo_entities_csv: Path,
    out_dir: Path,
    parquet_glob: str = "*.parquet",
) -> list[Path]:
    """Transcode every parquet under ``parquet_dir`` into per-indicator CSVs.

    Args:
        parquet_dir: directory containing the livestock parquets (typically
            ``datasets/livestock``).
        lgd_states_json: path to ``datasets/taxonomy/lgd_states.json`` (the
            ECI <-> LGD state lookup).
        geo_entities_csv: path to ``datasets/data/entities/geo.csv`` (the
            FK target for ``entity_id``; carries the
            ``lgd:<id>`` alias used for district resolution).
        out_dir: directory to emit ``<indicator_id>.csv`` into (typically
            ``datasets/data/datapoints/geo``).
        parquet_glob: override for tests; production uses the default.

    Returns:
        Sorted list of emitted CSV paths.

    Raises:
        FileNotFoundError: ``parquet_dir`` is empty / missing.
        KeyError: an entity_id carries an ECI st_code or LGD district id
            with no entry in the lookup tables.
        ValueError: an entity_id is neither ``IN`` nor
            ``IN-<eci_st_code>[-D<lgd_district_id>]``.
    """
    parquet_paths = sorted(parquet_dir.glob(parquet_glob))
    if not parquet_paths:
        raise FileNotFoundError(
            f"no parquet files match {parquet_dir / parquet_glob}"
        )

    eci_to_slug = load_eci_to_slug(lgd_states_json)
    lgd_district_to_entity = load_lgd_district_to_geo_entity(geo_entities_csv)

    by_indicator: dict[str, list[dict[str, Any]]] = {}
    for parquet_path in parquet_paths:
        for row in _project_parquet(parquet_path):
            indicator_id = row["indicator_id"]
            entity_id = _map_entity(
                row["entity_id"], eci_to_slug, lgd_district_to_entity
            )
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
