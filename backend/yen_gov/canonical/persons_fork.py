"""ADR-0035 S.1 migration helpers.

The live writer now emits ``dim_persons`` + ``elections_candidacies`` directly.
This module migrates the already-committed pre-S.1 election dimension once so
existing routes keep working through the new join path without rewriting
``election_results``.
"""

from __future__ import annotations

import re
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from yen_gov.canonical.adapters.eci.identity import (
    layer1_person_id,
    layer1_person_id_collision_tiebreak,
)
from yen_gov.canonical.envelope import CandidacyRow, PersonDimRow
from yen_gov.canonical.persons_seed import compile_to_parquet as compile_persons
from yen_gov.canonical.writer import (
    _DIM_SPECS,
    _FAMILY_WIDE_TABLE_SPECS,
    _regenerate_manifest,
    _upsert_dim,
)

_AC_ID_RE = re.compile(r"^IN-([SU]\d{2})-AC-\d{4}-\d+$")


@dataclass(frozen=True)
class PersonsForkResult:
    persons: int
    candidacies: int
    persons_taxonomy: int
    collisions_repaired: int = 0


def _read_rows(parquet_path: Path) -> list[dict[str, Any]]:
    con = duckdb.connect(":memory:")
    try:
        rel = con.execute(
            f"SELECT * FROM read_parquet('{parquet_path.as_posix()}') ORDER BY 1"
        )
        cols = [d[0] for d in rel.description]
        return [dict(zip(cols, row)) for row in rel.fetchall()]
    finally:
        con.close()


def _candidate_fact_maps(elections_dir: Path) -> tuple[dict[str, float], dict[str, float]]:
    glob_path = (elections_dir / "state=*" / "election_results.parquet").as_posix()
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            f"""
            SELECT entity_id, indicator_id, value_numeric
            FROM read_parquet('{glob_path}')
            WHERE indicator_id IN ('candidate-votes-polled', 'candidate-vote-share-pct')
            """
        ).fetchall()
    finally:
        con.close()
    votes: dict[str, float] = {}
    shares: dict[str, float] = {}
    for entity_id, indicator_id, value_numeric in rows:
        if value_numeric is None:
            continue
        if indicator_id == "candidate-votes-polled":
            votes[entity_id] = float(value_numeric)
        elif indicator_id == "candidate-vote-share-pct":
            shares[entity_id] = float(value_numeric)
    return votes, shares


def migrate_dim_candidates_to_persons(datasets_root: Path) -> PersonsForkResult:
    """Convert existing dim_candidates.parquet into S.1 person tables."""
    elections_dir = datasets_root / "elections"
    taxonomy_dir = datasets_root / "taxonomy"
    old_path = elections_dir / "dim_candidates.parquet"
    if not old_path.is_file():
        raise FileNotFoundError(old_path)

    old_rows = _read_rows(old_path)
    votes_by_key, share_by_key = _candidate_fact_maps(elections_dir)

    person_by_id: dict[str, dict[str, Any]] = {}
    seen_person_ids: set[str] = set()
    candidacy_rows: list[dict[str, Any]] = []
    for row in old_rows:
        ac_id = row["ac_id"]
        match = _AC_ID_RE.match(ac_id)
        if not match:
            raise ValueError(f"cannot derive state_code from ac_id={ac_id!r}")
        state_code = match.group(1)
        candidacy_key = row["candidate_id"]
        election_id = row["period_label"]
        person_id = layer1_person_id(
            state_code=state_code,
            ac_id=ac_id,
            election_id=election_id,
            candidate_name=row.get("name"),
        )
        if person_id in seen_person_ids:
            person_id = layer1_person_id_collision_tiebreak(person_id, candidacy_key)
        seen_person_ids.add(person_id)
        person_payload = {
            "person_id": person_id,
            "display_name": row.get("name"),
            "source_id": row["source_id"],
            "sex": row.get("sex"),
            "age": row.get("age"),
            "education": row.get("education"),
            "profession": row.get("profession"),
        }
        PersonDimRow(**person_payload)
        person_by_id[person_id] = person_payload

        candidacy_payload = {
            "candidacy_key": candidacy_key,
            "person_id": person_id,
            "ac_id": ac_id,
            "election_id": election_id,
            "ballot_serial": row["ballot_serial"],
            "party_id": row["party_id"],
            "rank": row["rank"],
            "votes_polled": votes_by_key.get(candidacy_key),
            "vote_share_pct": share_by_key.get(candidacy_key),
            "won": int(row["rank"]) == 1,
            "source_id": row["source_id"],
            "party_short_raw": row.get("party_short_raw"),
            "constituency_type": row.get("constituency_type"),
            "party_type": row.get("party_type"),
        }
        CandidacyRow(**candidacy_payload)
        candidacy_rows.append(candidacy_payload)

    persons_path.unlink(missing_ok=True)
    candidacies_path.unlink(missing_ok=True)
    persons_count = _upsert_dim(
        out_path=elections_dir / "dim_persons.parquet",
        rows=list(person_by_id.values()),
        spec=_DIM_SPECS["person"],
        table_id="elections.dim_persons",
    )
    candidacy_count = _upsert_dim(
        out_path=elections_dir / "elections_candidacies.parquet",
        rows=candidacy_rows,
        spec=_FAMILY_WIDE_TABLE_SPECS[("elections", "candidacy")],
        table_id="elections.elections_candidacies",
    )
    old_path.unlink()
    persons_taxonomy_count = compile_persons(
        person_aliases_json=taxonomy_dir / "person_aliases.json",
        dim_persons_parquet=elections_dir / "dim_persons.parquet",
        persons_out=taxonomy_dir / "persons.parquet",
    )
    _regenerate_manifest(datasets_root)
    return PersonsForkResult(
        persons=persons_count,
        candidacies=candidacy_count,
        persons_taxonomy=persons_taxonomy_count,
    )


def repair_layer1_person_id_collisions(datasets_root: Path) -> PersonsForkResult:
    """Repair repeated Layer-1 ids in already-migrated S.1 tables."""
    elections_dir = datasets_root / "elections"
    taxonomy_dir = datasets_root / "taxonomy"
    persons_path = elections_dir / "dim_persons.parquet"
    candidacies_path = elections_dir / "elections_candidacies.parquet"
    con = duckdb.connect(":memory:")
    try:
        con.execute(f"""
            CREATE TABLE repaired AS
            WITH joined AS (
                SELECT
                    ec.*,
                    p.display_name,
                    p.sex,
                    p.age,
                    p.education,
                    p.profession,
                    p.source_id AS person_source_id,
                    substr(sha256(
                        regexp_extract(ec.ac_id, '^IN-([SU][0-9]{{2}})-AC', 1)
                        || '|' || ec.ac_id
                        || '|' || ec.election_id
                        || '|' || trim(both '-' from regexp_replace(lower(coalesce(p.display_name, '')), '[^a-z0-9]+', '-', 'g'))
                    ), 1, 16) AS base_person_id
                FROM read_parquet('{candidacies_path.as_posix()}') ec
                JOIN read_parquet('{persons_path.as_posix()}') p
                  ON p.person_id = ec.person_id
            ), ranked AS (
                SELECT
                    *,
                    row_number() OVER (PARTITION BY base_person_id ORDER BY candidacy_key) AS base_rn
                FROM joined
            )
            SELECT
                CASE WHEN base_rn = 1
                    THEN base_person_id
                    ELSE substr(sha256(base_person_id || '|' || candidacy_key), 1, 16)
                END AS new_person_id,
                *
            FROM ranked
        """)
        [(repaired,)] = con.execute(
            "SELECT count(*) FROM repaired WHERE new_person_id <> person_id"
        ).fetchall()
        if int(repaired) > 0:
            persons_tmp = persons_path.with_suffix(".parquet.tmp")
            candidacies_tmp = candidacies_path.with_suffix(".parquet.tmp")
            con.execute(f"""
                COPY (
                    SELECT DISTINCT
                        new_person_id AS person_id,
                        display_name,
                        person_source_id AS source_id,
                        sex,
                        age,
                        education,
                        profession
                    FROM repaired
                    ORDER BY person_id
                ) TO '{persons_tmp.as_posix()}' (FORMAT PARQUET)
            """)
            con.execute(f"""
                COPY (
                    SELECT
                        candidacy_key,
                        new_person_id AS person_id,
                        ac_id,
                        election_id,
                        ballot_serial,
                        party_id,
                        rank,
                        votes_polled,
                        vote_share_pct,
                        won,
                        source_id,
                        party_short_raw,
                        constituency_type,
                        party_type
                    FROM repaired
                    ORDER BY election_id, ac_id, rank, candidacy_key
                ) TO '{candidacies_tmp.as_posix()}' (FORMAT PARQUET)
            """)
            os.replace(persons_tmp, persons_path)
            os.replace(candidacies_tmp, candidacies_path)
        [(persons_count,)] = con.execute("SELECT count(DISTINCT new_person_id) FROM repaired").fetchall()
        [(candidacy_count,)] = con.execute("SELECT count(*) FROM repaired").fetchall()
    finally:
        con.close()
    persons_taxonomy_count = compile_persons(
        person_aliases_json=taxonomy_dir / "person_aliases.json",
        dim_persons_parquet=persons_path,
        persons_out=taxonomy_dir / "persons.parquet",
    )
    _regenerate_manifest(datasets_root)
    return PersonsForkResult(
        persons=persons_count,
        candidacies=candidacy_count,
        persons_taxonomy=persons_taxonomy_count,
        collisions_repaired=repaired,
    )


__all__ = [
    "PersonsForkResult",
    "migrate_dim_candidates_to_persons",
    "repair_layer1_person_id_collisions",
]
