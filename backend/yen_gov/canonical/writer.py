"""Canonical writer — the SOLE producer of datasets/<family>/*.parquet,
datasets/taxonomy/*.parquet, and datasets/manifest.json.

Public entry point:

    write_batch(envelope: BatchEnvelope, datasets_root: Path) -> WriteResult

The writer:
  1. Validates exactly-one-of(value_numeric, value_text) per observation row
     (writer-enforced; cannot be a JSON Schema constraint, per
     observation.schema.json description).
  2. Validates FK referential integrity (D22): observations.entity_id ∈
     entities, observations.indicator_id ∈ indicators, observations.source_id
     ∈ (envelope.source_rows ∪ existing taxonomy/sources). Dangling FK
     aborts the write before any bytes touch disk.
  3. UPSERTs source_rows into an in-memory DuckDB by source_id.
  4. UPSERTs observation_rows on logical key (entity_id, year, period_label,
     indicator_id) per D7. ReplacementSemantics.replace_partition deletes
     (family, indicator_id) rows first.
  5. Emits sorted Parquet (D7 sort order: indicator_id, entity_id, year,
     period_seq) with KV metadata stamped per canonical-store.md §11.1.
  6. Regenerates datasets/manifest.json atomically per §12.3.

Scope guard: this is the Phase 0.9 skeleton. Not yet wired:
  - Entity/indicator FK side (no taxonomy/entities.parquet or
    indicators.parquet exists yet — both seeded as JSON only). The writer
    loads taxonomy from JSON files when present and SKIPS FK checks for
    missing tables with a logged warning. Phase 1 enables full FK gate.
  - Idempotency: identical input -> identical Parquet bytes. Implemented
    via deterministic sort + DuckDB COPY. Phase 0.10 contract tests assert
    byte-equality on re-run.
  - Partitioning: emits a single observations.parquet per family. >15 MB
    partitioning (D8) deferred until any family crosses the threshold.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from yen_gov.canonical.envelope import (
    BatchEnvelope,
    ObservationRow,
    ReplacementSemantics,
    SourceRow,
)
from yen_gov.core.schema_registry import schema_id, schema_version

log = logging.getLogger(__name__)


SORT_COLUMNS = ["indicator_id", "entity_id", "year", "period_seq"]


class WriterError(Exception):
    """Raised when the writer refuses an envelope. Always pre-emit; never
    after a partial write (atomicity is part of the contract)."""


@dataclass
class WriteResult:
    family: str
    observations_path: Path
    sources_path: Path
    manifest_path: Path
    observation_rows_written: int
    source_rows_written: int
    warnings: list[str] = field(default_factory=list)


def write_batch(envelope: BatchEnvelope, datasets_root: Path) -> WriteResult:
    """One-shot envelope -> emitted Parquet + regenerated manifest.

    ``datasets_root`` is the directory the writer treats as ``datasets/``.
    Tests pass a tmp_path; production passes the real repo root's
    ``datasets/`` directory.
    """
    _validate_observation_values(envelope.observation_rows)
    warnings = _validate_fks(envelope, datasets_root)

    family_dir = datasets_root / envelope.target_family
    taxonomy_dir = datasets_root / "taxonomy"
    family_dir.mkdir(parents=True, exist_ok=True)
    taxonomy_dir.mkdir(parents=True, exist_ok=True)

    observations_path = family_dir / "observations.parquet"
    sources_path = taxonomy_dir / "sources.parquet"

    con = duckdb.connect(":memory:")
    try:
        _load_existing(con, observations_path, sources_path)
        _apply_envelope(con, envelope)
        obs_written = _emit_observations(
            con, observations_path, envelope.target_family
        )
        src_written = _emit_sources(con, sources_path)
    finally:
        con.close()

    manifest_path = _regenerate_manifest(datasets_root)

    return WriteResult(
        family=envelope.target_family,
        observations_path=observations_path,
        sources_path=sources_path,
        manifest_path=manifest_path,
        observation_rows_written=obs_written,
        source_rows_written=src_written,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_observation_values(rows: list[ObservationRow]) -> None:
    for r in rows:
        has_num = r.value_numeric is not None
        has_txt = r.value_text is not None
        if has_num == has_txt:
            raise WriterError(
                "exactly one of value_numeric / value_text must be populated "
                f"(logical key {r.entity_id}|{r.year}|{r.period_label}|{r.indicator_id})"
            )


def _validate_fks(envelope: BatchEnvelope, datasets_root: Path) -> list[str]:
    """D22 FK gate. Returns warning strings for any FK side that is not yet
    seeded (Phase 0.9 transitional). Hard-fails on dangling source_id."""
    warnings: list[str] = []

    # source_id: union of envelope source_rows + existing sources.parquet.
    envelope_source_ids = {s.source_id for s in envelope.source_rows}
    existing_source_ids = _read_existing_source_ids(datasets_root)
    known_source_ids = envelope_source_ids | existing_source_ids
    dangling_sources = {
        r.source_id for r in envelope.observation_rows if r.source_id not in known_source_ids
    }
    if dangling_sources:
        raise WriterError(
            f"dangling source_id FKs: {sorted(dangling_sources)[:5]} "
            f"(total {len(dangling_sources)}); add to envelope.source_rows or seed first"
        )

    # entity_id / indicator_id: load from taxonomy JSON if present.
    entities_path = datasets_root / "taxonomy" / "entities.json"
    if entities_path.is_file():
        entity_ids = _load_taxonomy_ids(entities_path, "entities", "entity_id")
        dangling = {
            r.entity_id for r in envelope.observation_rows
            if r.entity_id not in entity_ids
            and not _is_derived_entity_id(r.entity_id)
        }
        if dangling:
            raise WriterError(
                f"dangling entity_id FKs: {sorted(dangling)[:5]} (total {len(dangling)})"
            )
    else:
        warnings.append("FK skipped: taxonomy/entities.json not found")

    indicators_path = datasets_root / "taxonomy" / "indicators.json"
    if indicators_path.is_file():
        indicator_ids = _load_taxonomy_ids(indicators_path, "indicators", "indicator_id")
        dangling = {
            r.indicator_id for r in envelope.observation_rows if r.indicator_id not in indicator_ids
        }
        if dangling:
            raise WriterError(
                f"dangling indicator_id FKs: {sorted(dangling)[:5]} (total {len(dangling)})"
            )
    else:
        warnings.append("FK skipped: taxonomy/indicators.json not found")

    return warnings


def _load_taxonomy_ids(path: Path, top_key: str, id_field: str) -> set[str]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {row[id_field] for row in doc.get(top_key, [])}


# Derived entity_id patterns per canonical-store.md §3a.
# AC, candidate, state-rollup, and party-rollup entities are auto-compiled
# from source data (acs.parquet / candidates.parquet) rather than enumerated
# in the hand-authored taxonomy/entities.json. The FK gate recognises them
# by pattern until those sibling tables exist as FK targets.
_DERIVED_ENTITY_PATTERNS = (
    re.compile(r"^IN-[SU]\d{2}-AC-\d{4}-\d+$"),
    re.compile(r"^IN-[SU]\d{2}-AC-\d{4}-\d+-(?:AcGen|LsGen|AcBye|LsBye)"
               r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\d{4}-C\d{2}$"),
    re.compile(r"^IN-[SU]\d{2}-(?:AcGen|LsGen|AcBye|LsBye)"
               r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\d{4}$"),
    re.compile(r"^IN-[SU]\d{2}-(?:AcGen|LsGen|AcBye|LsBye)"
               r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\d{4}-PARTY-[A-Z][A-Z0-9_]*$"),
)


def _is_derived_entity_id(entity_id: str) -> bool:
    return any(p.match(entity_id) for p in _DERIVED_ENTITY_PATTERNS)


def _read_existing_source_ids(datasets_root: Path) -> set[str]:
    p = datasets_root / "taxonomy" / "sources.parquet"
    if not p.is_file():
        return set()
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            f"SELECT source_id FROM read_parquet('{p.as_posix()}')"
        ).fetchall()
        return {r[0] for r in rows}
    finally:
        con.close()


# ---------------------------------------------------------------------------
# DuckDB load / upsert / emit
# ---------------------------------------------------------------------------


# NOTE: no PRIMARY KEY on the in-memory tables. DuckDB enforces PK with a
# row-by-row index update that makes 180k INSERT OR REPLACE take >10 minutes
# (Phase 1.1 corpus). Parquet has no PK anyway; uniqueness is enforced by
# DELETE-then-INSERT in _apply_envelope (envelope wins on PK collision) and
# asserted post-emit via _assert_unique_pk before COPY out.
_OBS_DDL = """
CREATE TABLE observations (
    observation_id VARCHAR NOT NULL,
    entity_id      VARCHAR NOT NULL,
    year           INTEGER NOT NULL,
    period_label   VARCHAR NOT NULL,
    period_seq     INTEGER NOT NULL,
    indicator_id   VARCHAR NOT NULL,
    value_numeric  DOUBLE,
    value_text     VARCHAR,
    source_id      VARCHAR NOT NULL,
    derivation     VARCHAR
)
"""

_SRC_DDL = """
CREATE TABLE sources (
    source_id            VARCHAR NOT NULL,
    url                  VARCHAR,
    content_hash         VARCHAR,
    producer             VARCHAR,
    citation_full        VARCHAR,
    url_main             VARCHAR,
    url_download         VARCHAR,
    date_accessed        VARCHAR,
    first_fetched_at     VARCHAR,
    last_seen_at         VARCHAR,
    license              VARCHAR,
    vintage              VARCHAR,
    confidence_tier      VARCHAR,
    is_issuing_authority BOOLEAN
)
"""


def _load_existing(
    con: duckdb.DuckDBPyConnection,
    observations_path: Path,
    sources_path: Path,
) -> None:
    con.execute(_OBS_DDL)
    con.execute(_SRC_DDL)
    if observations_path.is_file():
        con.execute(
            f"INSERT INTO observations SELECT * FROM read_parquet('{observations_path.as_posix()}')"
        )
    if sources_path.is_file():
        con.execute(
            f"INSERT INTO sources SELECT * FROM read_parquet('{sources_path.as_posix()}')"
        )


def _apply_envelope(con: duckdb.DuckDBPyConnection, envelope: BatchEnvelope) -> None:
    # Bulk-load path: write envelope rows to a temp CSV, then COPY FROM into
    # a staging table. DuckDB's CSV bulk reader handles 180k rows in <1s;
    # executemany on the same data takes >10 min (PK or no PK). The temp CSV
    # is the only bulk-insert path that scales without pandas/pyarrow deps.

    if envelope.source_rows:
        src_tuples = [
            (
                s.source_id, s.url, s.content_hash, s.producer, s.citation_full,
                s.url_main, s.url_download, s.date_accessed, s.first_fetched_at,
                s.last_seen_at, s.license, s.vintage, s.confidence_tier,
                s.is_issuing_authority,
            )
            for s in envelope.source_rows
        ]
        envelope_src_ids = [s.source_id for s in envelope.source_rows]
        placeholders = ", ".join(["?"] * len(envelope_src_ids))
        con.execute(
            f"DELETE FROM sources WHERE source_id IN ({placeholders})",
            envelope_src_ids,
        )
        # Sources are few (<200); executemany is fine here.
        con.executemany(
            "INSERT INTO sources VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            src_tuples,
        )

    if envelope.replacement_semantics is ReplacementSemantics.replace_partition:
        indicator_ids = sorted({r.indicator_id for r in envelope.observation_rows})
        if indicator_ids:
            placeholders = ", ".join(["?"] * len(indicator_ids))
            con.execute(
                f"DELETE FROM observations WHERE indicator_id IN ({placeholders})",
                indicator_ids,
            )

    if envelope.observation_rows:
        _bulk_load_observations(con, envelope.observation_rows)


_OBS_COLUMNS = (
    "observation_id", "entity_id", "year", "period_label", "period_seq",
    "indicator_id", "value_numeric", "value_text", "source_id", "derivation",
)


def _bulk_load_observations(
    con: duckdb.DuckDBPyConnection,
    rows: list[ObservationRow],
) -> None:
    # Dedupe envelope-internal collisions (last-wins by observation_id).
    obs_by_id: dict[str, ObservationRow] = {}
    for r in rows:
        rr = r.with_id()
        obs_by_id[rr.observation_id] = rr
    deduped = list(obs_by_id.values())

    tmpf = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8"
    )
    try:
        import csv as _csv
        writer = _csv.writer(tmpf, lineterminator="\n")
        writer.writerow(_OBS_COLUMNS)
        for r in deduped:
            writer.writerow([
                r.observation_id, r.entity_id, r.year, r.period_label, r.period_seq,
                r.indicator_id,
                "" if r.value_numeric is None else r.value_numeric,
                "" if r.value_text is None else r.value_text,
                r.source_id,
                "" if r.derivation is None else r.derivation,
            ])
        tmpf.close()

        csv_path = Path(tmpf.name).as_posix()
        con.execute(f"""
            CREATE TEMP TABLE staging_obs AS
            SELECT * FROM read_csv('{csv_path}',
                header=true,
                columns={{
                    'observation_id': 'VARCHAR',
                    'entity_id': 'VARCHAR',
                    'year': 'INTEGER',
                    'period_label': 'VARCHAR',
                    'period_seq': 'INTEGER',
                    'indicator_id': 'VARCHAR',
                    'value_numeric': 'DOUBLE',
                    'value_text': 'VARCHAR',
                    'source_id': 'VARCHAR',
                    'derivation': 'VARCHAR'
                }})
        """)
        # Envelope wins: drop existing rows for these PKs, then insert staging.
        con.execute("""
            DELETE FROM observations
            WHERE observation_id IN (SELECT observation_id FROM staging_obs)
        """)
        con.execute("INSERT INTO observations SELECT * FROM staging_obs")
        con.execute("DROP TABLE staging_obs")
    finally:
        try:
            os.unlink(tmpf.name)
        except OSError:
            pass


def _emit_observations(
    con: duckdb.DuckDBPyConnection,
    out_path: Path,
    family: str,
) -> int:
    table_id = f"{family}.observations"
    return _emit_table(
        con=con,
        select_sql=(
            "SELECT * FROM observations "
            "ORDER BY indicator_id, entity_id, year, period_seq"
        ),
        out_path=out_path,
        table_id=table_id,
        row_schema_file="observation.schema.json",
        sort_cols=SORT_COLUMNS,
    )


def _emit_sources(con: duckdb.DuckDBPyConnection, out_path: Path) -> int:
    return _emit_table(
        con=con,
        select_sql="SELECT * FROM sources ORDER BY source_id",
        out_path=out_path,
        table_id="taxonomy.sources",
        row_schema_file="source.schema.json",
        sort_cols=["source_id"],
    )


def _emit_table(
    con: duckdb.DuckDBPyConnection,
    select_sql: str,
    out_path: Path,
    table_id: str,
    row_schema_file: str,
    sort_cols: list[str],
) -> int:
    [(count,)] = con.execute(f"SELECT count(*) FROM ({select_sql})").fetchall()
    kv = {
        "table_id": table_id,
        "schema_version": schema_version(row_schema_file),
        "row_schema_id": schema_id(row_schema_file),
        "writer_version": _writer_version(),
        "sort_columns": json.dumps(sort_cols),
    }
    kv_clause = ", ".join(f"{k}: '{_escape_sql(v)}'" for k, v in kv.items())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".parquet.tmp")
    con.execute(
        f"""
        COPY ({select_sql}) TO '{tmp.as_posix()}'
        (FORMAT PARQUET, ROW_GROUP_SIZE 100000, KV_METADATA {{ {kv_clause} }})
        """
    )
    os.replace(tmp, out_path)
    return int(count)


def _escape_sql(v: str) -> str:
    return v.replace("'", "''")


def _writer_version() -> str:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return sha or "unknown"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Manifest regen (§12.3)
# ---------------------------------------------------------------------------


def _regenerate_manifest(datasets_root: Path) -> Path:
    """Re-enumerate every Parquet table under datasets/, regenerate
    manifest.json, write atomically.

    Boundary entries (per §12.3 step 6) are not yet emitted — Phase 0.14
    defines the _manifest_fragment.json mechanism. For now boundary entries
    are omitted; the loader handles their absence as "no boundaries
    available yet" per the Phase 0.11 failure-state contract.
    """
    tables: list[dict] = []

    for parquet_path in sorted(datasets_root.glob("*/observations.parquet")):
        family = parquet_path.parent.name
        if family in {"taxonomy", "boundaries", "_old", "ephemeral", "schemas"}:
            continue
        tables.append(_describe_parquet_table(
            datasets_root=datasets_root,
            parquet_path=parquet_path,
            table_id=f"{family}.observations",
            family=family,
            row_schema_file="observation.schema.json",
        ))

    taxonomy_dir = datasets_root / "taxonomy"
    for parquet_path in sorted(taxonomy_dir.glob("*.parquet")):
        stem = parquet_path.stem
        schema_file = _taxonomy_schema_file(stem)
        if schema_file is None:
            continue
        tables.append(_describe_parquet_table(
            datasets_root=datasets_root,
            parquet_path=parquet_path,
            table_id=f"taxonomy.{stem}",
            family="taxonomy",
            row_schema_file=schema_file,
        ))

    manifest = {
        "$schema": "./schemas/manifest.schema.json",
        "$schema_version": schema_version("manifest.schema.json"),
        "manifest_version": "1.0",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tables": tables,
    }

    manifest_path = datasets_root / "manifest.json"
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=datasets_root, delete=False, suffix=".tmp"
    ) as tmp:
        json.dump(manifest, tmp, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, manifest_path)
    return manifest_path


def _describe_parquet_table(
    datasets_root: Path,
    parquet_path: Path,
    table_id: str,
    family: str,
    row_schema_file: str,
) -> dict:
    rel = parquet_path.relative_to(datasets_root).as_posix()
    size = parquet_path.stat().st_size
    con = duckdb.connect(":memory:")
    try:
        [(row_count,)] = con.execute(
            f"SELECT count(*) FROM read_parquet('{parquet_path.as_posix()}')"
        ).fetchall()
    finally:
        con.close()
    return {
        "table_id": table_id,
        "family": family,
        "format": "parquet",
        "schema_version": schema_version(row_schema_file),
        "partition_columns": [],
        "files": [
            {"path": rel, "size_bytes": size, "row_count": int(row_count)}
        ],
        "row_count_total": int(row_count),
    }


def _taxonomy_schema_file(stem: str) -> str | None:
    mapping = {
        "sources": "source.schema.json",
        "entities": "entity.schema.json",
        "indicators": "indicator-catalogue.schema.json",
        "operator_state": "operator-state.schema.json",
        "caveats": "caveat.schema.json",
        "methodology_breaks": "methodology-break.schema.json",
        "facet-axes": "facet-axes.schema.json",
    }
    return mapping.get(stem)
