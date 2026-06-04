"""B2b.4.4 election_events parquet -> long-format CSV reingest.

Transcodes ``datasets/taxonomy/election_events.parquet`` (339 rows;
per-state election event register) into
``datasets/data/election_events.csv`` (parent plan section 21.6 / 22.4;
sub-sub-plan B2b.4 row B2b.4.4).

The source column ``state_code`` carries the ECI S/U code (e.g. ``S01``).
On emit it is re-keyed to the LGD state ``entity_id`` (e.g.
``andhra-pradesh``) via ``datasets/taxonomy/lgd_states.json`` and renamed
to ``state_entity_id`` so the FK target into
``datasets/data/entities/geo.csv.entity_id`` is explicit. PK
``(state_entity_id, event_id)``.

``polled_on`` and ``term_end_estimated`` arrive as ``datetime.date``
from duckdb; the column contract has no native date dtype
(csv-column-contract section 4), so they are serialised as
ISO-8601 ``YYYY-MM-DD`` strings.

Public surface:

    from yen_gov.canonical.reingest.election_events import emit
    emit(parquet_path=..., out_path=..., lgd_states_json=...)

No mocks (Holy Law #7); duckdb reads the real parquet file. Tests stage a
miniature fixture parquet under ``tmp_path`` to exercise the path.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Mapping

import duckdb

from yen_gov.canonical.csv_writer import write_csv
from yen_gov.canonical.reingest.energy_datapoints import load_eci_to_slug

__all__ = ["FILE_CLASS", "emit", "load_eci_to_slug"]


FILE_CLASS = "datasets/data/election_events.csv"


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime.date):
        return value.isoformat()
    return str(value)


def _project_parquet(
    parquet_path: Path, eci_to_slug: Mapping[str, str]
) -> list[dict[str, Any]]:
    sql = (
        "SELECT state_code, event_id, kind, display, polled_on, "
        "term_end_estimated, data_status, notes "
        f"FROM read_parquet('{parquet_path.as_posix()}') "
        "ORDER BY state_code, event_id"
    )
    rows: list[dict[str, Any]] = []
    for (
        state_code,
        event_id,
        kind,
        display,
        polled_on,
        term_end_estimated,
        data_status,
        notes,
    ) in duckdb.sql(sql).fetchall():
        slug = eci_to_slug.get(state_code)
        if slug is None:
            raise KeyError(
                f"no LGD slug for ECI st_code {state_code!r} "
                f"(event_id {event_id!r})"
            )
        rows.append(
            {
                "state_entity_id": slug,
                "event_id": event_id,
                "kind": kind,
                "display": display,
                "polled_on": _iso(polled_on),
                "term_end_estimated": _iso(term_end_estimated),
                "data_status": data_status,
                "notes": notes,
            }
        )
    rows.sort(key=lambda r: (r["state_entity_id"], r["event_id"]))
    return rows


def emit(
    *,
    parquet_path: Path,
    out_path: Path,
    lgd_states_json: Path,
) -> Path:
    """Transcode the election_events parquet into the long-format CSV.

    Args:
        parquet_path: path to ``datasets/taxonomy/election_events.parquet``.
        out_path: target CSV path (``datasets/data/election_events.csv``).
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
