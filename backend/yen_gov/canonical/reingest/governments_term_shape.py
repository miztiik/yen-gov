"""B3-followup governments parquet -> long-format CSV reingest (term-shape per
plan section 20.4).

Projects the two in-process governments parquets

    datasets/governments/dim_offices.parquet
    datasets/governments/governments_office_holdings.parquet

into the canonical term-shape triple under ``datasets/data/`` mandated by
parent plan section 20.4 (CSV everywhere, no parquet survivor for this
family):

    datasets/data/entities/office.csv
        office_id, name, office_kind, jurisdiction_entity_id, portfolio
    datasets/data/entities/holder.csv
        holder_id, person_name, party_id
    datasets/data/datapoints/office_holdings.csv
        office_id, term_start, holder_id, term_end, source_id

B3-followup (2026-06-07): the two source parquets are no longer
committed under ``datasets/governments/``. The ``emit-taxonomy`` CLI
builds them per-run inside a tempdir (via ``office_holdings_seed.compile_to_parquet``)
and passes that tempdir as the ``parquet_dir`` arg here so the CSV
emit chain continues unbroken. The tempdir is cleaned up after
``emit()`` returns; no parquet survives on disk in citizen-visible
locations.

Projection rules:

- ``office.csv`` row count == ``dim_offices.parquet`` row count.
  - ``office_id`` <- ``office_id`` carried through (e.g. ``IN-PRES``,
    ``IN-S22-CM``).
  - ``name`` <- ``label``.
  - ``office_kind`` <- ``role`` lower-cased (``PRES`` -> ``pres``,
    ``VPRES`` -> ``vpres``, ``CM`` -> ``cm``). The enum is intentionally
    open in the column contract per plan section 20.4 (``cm|pm|president|
    cabinet_minister|...``); B2b.3 only emits what the source carries.
  - ``jurisdiction_entity_id`` <- the ECI-style ``entity_id`` re-keyed to
    the LGD slug used by ``datasets/data/entities/geo.csv`` (``IN`` stays
    ``IN``; ``IN-S22`` -> ``tamil-nadu`` via the ``aliases`` column on
    the geo entity file). This re-key mirrors B2b.1 / B2b.2 and is
    required by parent invariant 22.4#2 (LGD/ECI key separation).
  - ``portfolio`` <- null. The source carries no cabinet/portfolio facet
    today; the column is reserved for the future cabinet-minister rows
    plan section 20.4 names.

- ``holder.csv`` row count == ``COUNT(DISTINCT person_slug)`` in the
  holdings parquet (210 today).
  - ``holder_id`` <- ``person_slug``.
  - ``person_name`` <- ``person_name`` (verified 1:1 with slug on disk).
  - ``party_id`` <- ``party_eci_code`` resolved against
    ``datasets/data/entities/parties.csv`` via its ``eci_codes`` column
    (BIGINT). ``party_eci_code`` is null for ~157 holding rows (e.g.
    Presidents-as-independent or pre-affiliation tenures); the derived
    ``party_id`` is null when the source code is null AND when no
    resolution exists in ``parties.csv`` (the latter raises ``KeyError`` -
    a silent null would mask a missing FK target).

- ``office_holdings.csv`` row count == ``governments_office_holdings.parquet``
  row count.
  - ``office_id`` <- ``office_id``.
  - ``term_start`` <- ``start_date`` formatted ISO ``YYYY-MM-DD``
    (never null on disk; verified during recon).
  - ``holder_id`` <- ``person_slug``; nullable because ~47 rows on
    disk are unassigned term boundaries (e.g. President's Rule /
    interim / vacancy windows) carrying a real ``start_date`` +
    ``source_id`` but no person. A future cleanup may model these as
    a sentinel ``holder_id`` ("vacant"/"presidents-rule") - for now
    the nullable column preserves the source's information without
    inventing a placeholder.
  - ``term_end`` <- ``end_date`` formatted ISO; null = incumbent (parent
    plan section 20.4 explicitly forbids ``datetime.now`` as a stand-in).
  - ``source_id`` <- carried through; FK to ``entities/source.csv``.

  PK is ``(office_id, term_start)`` per the column contract;
  ``(office_id, start_date)`` is verified unique on disk (0 collisions).
  The source columns ``regime``, ``selection_method``, ``tenure_status``,
  ``party_eci_code`` (folded into ``holder.csv``), ``alliance``, and
  ``notes`` are dropped during projection. They are informational and
  not part of the term-shape contract; a future alliance datapoint file
  (parent plan section 20.4 ``datapoints/alliance_membership.csv``)
  will revive the alliance signal at its own time.

Public surface:

    from yen_gov.canonical.reingest.governments_term_shape import emit
    emit(
        parquet_dir=...,
        geo_entities_csv=...,
        party_entities_csv=...,
        out_data_dir=...,
    )

No mocks (Holy Law #7); duckdb reads real parquet + CSV. Tests stage
miniature fixture parquets + geo.csv + parties.csv + source.csv under
``tmp_path``.
"""

from __future__ import annotations

import csv
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import duckdb

from yen_gov.canonical.csv_writer import write_csv

__all__ = [
    "FILE_CLASS_OFFICE",
    "FILE_CLASS_HOLDER",
    "FILE_CLASS_HOLDINGS",
    "emit",
    "load_eci_state_to_geo_entity",
    "load_party_eci_to_party_id",
]


FILE_CLASS_OFFICE = "datasets/data/entities/office.csv"
FILE_CLASS_HOLDER = "datasets/data/entities/holder.csv"
FILE_CLASS_HOLDINGS = "datasets/data/datapoints/office_holdings.csv"
COUNTRY_ENTITY_ID = "IN"


def load_eci_state_to_geo_entity(geo_entities_csv: Path) -> dict[str, str]:
    """Return ``ECI st_code -> geo.csv entity_id`` for every state row.

    Parses the ``aliases`` column of ``datasets/data/entities/geo.csv``
    (pipe-delimited tokens) and harvests the ``S<NN>`` / ``U<NN>`` ECI
    token from each ``entity_kind=state`` row.
    """
    out: dict[str, str] = {}
    with geo_entities_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("entity_kind") != "state":
                continue
            entity_id = row.get("entity_id") or ""
            aliases = row.get("aliases") or ""
            if not entity_id:
                continue
            for token in aliases.split("|"):
                token = token.strip()
                if len(token) >= 2 and token[0] in ("S", "U") and token[1:].isdigit():
                    out[token] = entity_id
                    break
    return out


def load_party_eci_to_party_id(party_entities_csv: Path) -> dict[str, str]:
    """Return ``ECI party code (as string) -> party_id`` from parties.csv.

    ``parties.csv.eci_codes`` is a BIGINT column today (single ECI code per
    party row). Rows with a null ``eci_codes`` are skipped.
    """
    out: dict[str, str] = {}
    with party_entities_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            party_id = row.get("party_id") or ""
            eci_raw = (row.get("eci_codes") or "").strip()
            if not party_id or not eci_raw:
                continue
            out[eci_raw] = party_id
    return out


def _map_jurisdiction(
    eci_entity_id: str,
    eci_state_to_geo: Mapping[str, str],
) -> str:
    if eci_entity_id == COUNTRY_ENTITY_ID:
        return COUNTRY_ENTITY_ID
    if not eci_entity_id.startswith("IN-"):
        raise ValueError(
            f"unrecognised office entity_id {eci_entity_id!r}; expected "
            "'IN' or 'IN-<eci_st_code>'"
        )
    tail = eci_entity_id[len("IN-") :]
    if tail not in eci_state_to_geo:
        raise KeyError(
            f"no geo.csv entity for ECI st_code {tail!r} "
            f"(office entity_id {eci_entity_id!r})"
        )
    return eci_state_to_geo[tail]


def _project_offices(
    parquet_path: Path,
    eci_state_to_geo: Mapping[str, str],
) -> list[dict[str, Any]]:
    rel = duckdb.sql(
        "SELECT office_id, entity_id, role, label "
        f"FROM read_parquet('{parquet_path.as_posix()}') "
        "ORDER BY office_id"
    )
    rows: list[dict[str, Any]] = []
    for office_id, entity_id, role, label in rel.fetchall():
        rows.append(
            {
                "office_id": office_id,
                "name": label,
                "office_kind": str(role).lower(),
                "jurisdiction_entity_id": _map_jurisdiction(
                    entity_id, eci_state_to_geo
                ),
                "portfolio": None,
            }
        )
    return rows


def _project_holders(
    holdings_parquet: Path,
    party_eci_to_id: Mapping[str, str],
) -> list[dict[str, Any]]:
    rel = duckdb.sql(
        "SELECT person_slug, ANY_VALUE(person_name) AS person_name, "
        "ANY_VALUE(CAST(party_eci_code AS VARCHAR)) AS party_eci_code "
        f"FROM read_parquet('{holdings_parquet.as_posix()}') "
        "WHERE person_slug IS NOT NULL "
        "GROUP BY person_slug "
        "ORDER BY person_slug"
    )
    rows: list[dict[str, Any]] = []
    for person_slug, person_name, party_eci_code in rel.fetchall():
        party_id: str | None
        if party_eci_code is None:
            party_id = None
        else:
            if party_eci_code not in party_eci_to_id:
                raise KeyError(
                    f"no party_id for ECI party code {party_eci_code!r} "
                    f"(holder {person_slug!r})"
                )
            party_id = party_eci_to_id[party_eci_code]
        rows.append(
            {
                "holder_id": person_slug,
                "person_name": person_name,
                "party_id": party_id,
            }
        )
    return rows


def _project_holdings(holdings_parquet: Path) -> list[dict[str, Any]]:
    rel = duckdb.sql(
        "SELECT office_id, "
        "strftime(start_date, '%Y-%m-%d') AS term_start, "
        "person_slug AS holder_id, "
        "CASE WHEN end_date IS NULL THEN NULL "
        "ELSE strftime(end_date, '%Y-%m-%d') END AS term_end, "
        "source_id "
        f"FROM read_parquet('{holdings_parquet.as_posix()}') "
        "ORDER BY office_id, term_start"
    )
    cols = [d[0] for d in rel.description]
    return [dict(zip(cols, tup, strict=True)) for tup in rel.fetchall()]


def emit(
    *,
    parquet_dir: Path,
    geo_entities_csv: Path,
    party_entities_csv: Path,
    out_data_dir: Path,
) -> dict[str, Path]:
    """Emit the term-shape triple from the governments parquets.

    Args:
        parquet_dir: directory containing both governments parquets
            (typically ``datasets/governments``).
        geo_entities_csv: path to ``datasets/data/entities/geo.csv``.
        party_entities_csv: path to ``datasets/data/entities/parties.csv``.
        out_data_dir: ``datasets/data`` root; the function writes
            ``entities/office.csv``, ``entities/holder.csv``, and
            ``datapoints/office_holdings.csv`` underneath.

    Returns:
        Mapping of file class -> emitted path.

    Raises:
        FileNotFoundError: either parquet is missing.
        KeyError: an entity_id or party_eci_code has no lookup target.
        ValueError: an entity_id is neither ``IN`` nor ``IN-<eci_st_code>``.
    """
    offices_parquet = parquet_dir / "dim_offices.parquet"
    holdings_parquet = parquet_dir / "governments_office_holdings.parquet"
    for required in (offices_parquet, holdings_parquet):
        if not required.exists():
            raise FileNotFoundError(required)

    eci_state_to_geo = load_eci_state_to_geo_entity(geo_entities_csv)
    party_eci_to_id = load_party_eci_to_party_id(party_entities_csv)

    office_rows = _project_offices(offices_parquet, eci_state_to_geo)
    holder_rows = _project_holders(holdings_parquet, party_eci_to_id)
    holding_rows = _project_holdings(holdings_parquet)

    office_path = out_data_dir / "entities" / "office.csv"
    holder_path = out_data_dir / "entities" / "holder.csv"
    holdings_path = out_data_dir / "datapoints" / "office_holdings.csv"

    write_csv(path=office_path, file_class=FILE_CLASS_OFFICE, rows=office_rows)
    write_csv(path=holder_path, file_class=FILE_CLASS_HOLDER, rows=holder_rows)
    write_csv(
        path=holdings_path, file_class=FILE_CLASS_HOLDINGS, rows=holding_rows
    )

    return {
        FILE_CLASS_OFFICE: office_path,
        FILE_CLASS_HOLDER: holder_path,
        FILE_CLASS_HOLDINGS: holdings_path,
    }
