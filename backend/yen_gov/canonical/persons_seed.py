"""Compile ADR-0035 person taxonomy rows.

``datasets/taxonomy/person_aliases.json`` is the hand-authored merge overlay.
``datasets/taxonomy/persons.parquet`` is the compiled registry the frontend
and future government/election joins can read. Day one has no merge clusters:
every ``dim_persons`` row compiles as a self-alias person row.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field


PERSONS_ROW_SCHEMA_VERSION = "1.0"
PERSONS_PARQUET_COLUMNS = (
    "person_id",
    "display_name",
    "source_id",
    "confidence_tier",
    "evidence_note_md",
    "cluster_id",
    "merged_candidacy_count",
)


class PersonAliasCluster(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cluster_id: str = Field(pattern=r"^[a-z][a-z0-9_/-]*$")
    candidacy_keys: list[str] = Field(min_length=1)
    display_name: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    evidence_note_md: str = Field(min_length=1)
    confidence_tier: Literal["gold", "silver", "bronze"]


class PersonAliasesFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    clusters: list[PersonAliasCluster] = Field(default_factory=list)


def merged_person_id(candidacy_keys: list[str], source_ids: list[str]) -> str:
    """Content-addressable merged identity from ADR-0035 Layer 4."""
    key = "|".join(sorted(candidacy_keys)) + "|" + "|".join(sorted(source_ids))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _read_aliases(path: Path) -> PersonAliasesFile:
    if not path.is_file():
        return PersonAliasesFile(clusters=[])
    raw = json.loads(path.read_text(encoding="utf-8"))
    return PersonAliasesFile(clusters=raw.get("clusters") or [])


def _self_alias_rows(dim_persons_parquet: Path) -> list[dict]:
    if not dim_persons_parquet.is_file():
        return []
    con = duckdb.connect(":memory:")
    try:
        rel = con.execute(
            f"""
            SELECT person_id, display_name, source_id
            FROM read_parquet('{dim_persons_parquet.as_posix()}')
            ORDER BY person_id
            """
        )
        return [
            {
                "person_id": person_id,
                "display_name": display_name,
                "source_id": source_id,
                "confidence_tier": "gold",
                "evidence_note_md": "Layer-1 self alias from the candidacy row.",
                "cluster_id": None,
                "merged_candidacy_count": 1,
            }
            for person_id, display_name, source_id in rel.fetchall()
        ]
    finally:
        con.close()


def compile_to_parquet(
    *,
    person_aliases_json: Path,
    dim_persons_parquet: Path,
    persons_out: Path,
) -> int:
    """Compile person aliases + dim_persons self-aliases to persons.parquet."""
    aliases = _read_aliases(person_aliases_json)
    rows = _self_alias_rows(dim_persons_parquet)
    for cluster in aliases.clusters:
        rows.append({
            "person_id": merged_person_id(cluster.candidacy_keys, [cluster.source_id]),
            "display_name": cluster.display_name,
            "source_id": cluster.source_id,
            "confidence_tier": cluster.confidence_tier,
            "evidence_note_md": cluster.evidence_note_md,
            "cluster_id": cluster.cluster_id,
            "merged_candidacy_count": len(cluster.candidacy_keys),
        })

    con = duckdb.connect(":memory:")
    try:
        con.execute(
            """
            CREATE TABLE persons (
                person_id VARCHAR NOT NULL,
                display_name VARCHAR,
                source_id VARCHAR NOT NULL,
                confidence_tier VARCHAR NOT NULL,
                evidence_note_md VARCHAR NOT NULL,
                cluster_id VARCHAR,
                merged_candidacy_count INTEGER NOT NULL
            )
            """
        )
        if rows:
            _bulk_insert_persons(con, rows)
        persons_out.parent.mkdir(parents=True, exist_ok=True)
        con.execute(
            f"""
            COPY (
                SELECT * FROM persons
                ORDER BY person_id, cluster_id NULLS FIRST
            ) TO '{persons_out.as_posix()}'
            (FORMAT PARQUET, KV_METADATA {{
                table_id: 'taxonomy.persons',
                schema_version: '{PERSONS_ROW_SCHEMA_VERSION}',
                row_schema_id: './persons.schema.json',
                sort_columns: '["person_id","cluster_id"]'
            }})
            """
        )
        return int(con.execute("SELECT count(*) FROM persons").fetchone()[0])
    finally:
        con.close()


def _bulk_insert_persons(con: duckdb.DuckDBPyConnection, rows: list[dict]) -> None:
    tmpf = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8"
    )
    try:
        import csv as _csv

        writer = _csv.writer(tmpf, lineterminator="\n")
        writer.writerow(PERSONS_PARQUET_COLUMNS)
        for row in rows:
            writer.writerow(["" if row[col] is None else row[col] for col in PERSONS_PARQUET_COLUMNS])
        tmpf.close()
        csv_path = Path(tmpf.name).as_posix()
        con.execute(f"""
            CREATE TEMP TABLE staging_persons AS
            SELECT * FROM read_csv('{csv_path}',
                header=true,
                delim=',',
                quote='"',
                escape='"',
                columns={{
                    'person_id': 'VARCHAR',
                    'display_name': 'VARCHAR',
                    'source_id': 'VARCHAR',
                    'confidence_tier': 'VARCHAR',
                    'evidence_note_md': 'VARCHAR',
                    'cluster_id': 'VARCHAR',
                    'merged_candidacy_count': 'INTEGER'
                }})
        """)
        con.execute("INSERT INTO persons BY NAME SELECT * FROM staging_persons")
        con.execute("DROP TABLE staging_persons")
    finally:
        try:
            os.unlink(tmpf.name)
        except OSError:
            pass


__all__ = [
    "PersonAliasCluster",
    "PersonAliasesFile",
    "compile_to_parquet",
    "merged_person_id",
]
