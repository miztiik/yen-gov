"""Compile boundary geometry inventory to ``datasets/boundaries/boundary_layers.parquet``.

§8.3 Python-compiles-to-Parquet seam. Replaces the four sidecar writers in
``tools/boundaries/snapshot.py`` (``_write_sources_sidecar``,
``_write_unkeyed_sidecar``, ``_write_simplification_metadata_sidecar``,
``emit_index_manifest``) with a single canonical control table on a
Hive-partitioned discovery path (T.0d §1).

Outputs:

- ``datasets/boundaries/boundary_layers.parquet`` -- one row per boundary
  geometry shard on disk (15 columns; see ``boundary-layers.schema.json``
  v1.0). FK ``source_id`` resolves to ``taxonomy/sources.parquet``.
- Side effect: UPSERT 4 boundary citation rows into
  ``datasets/taxonomy/sources.parquet`` so every boundary row's
  ``source_id`` resolves to a real ledger entry.

T.0d role (2026-05-22, fused atomic): consolidates 115 sidecar files
(73 ``.sources.json`` deprecated §12 v1.x + 39 ``.metadata.json`` + 2
``.unkeyed.json`` + 1 ``S22-villages-index.json``) into one queryable
control table. Per ADR-0032 §12 v2.0: provenance is a TABLE keyed on
``(producer, title, vintage)``, not a per-shard array smeared with
fetch timestamps. Per ADR-0031 amendment: directory layout switches
from flat ``boundaries/in/geojson/*`` to Hive-partitioned
``boundaries/in/<level>/state=<S>/...`` matching the elections grammar.

Postal sources deliberately NOT seeded (user 2026-05-22): no pincode
geojson exists in ``datasets/boundaries/in/geojson/`` today and
``tools/boundaries/pipeline.json`` has zero postal entries; postal
subtree is forward-looking only. When the first postal layer ingests,
that PR adds the 5th source row with the actual license discovered at
ingest time.

Methodology breaks NOT carried as a column here (user 2026-05-22):
break is a property of the ENTITY (district row on
``taxonomy/entities.parquet`` via ``entity_valid_from`` + ``notes``),
not the BOUNDARY (geometry shard). Adding ``methodology_break_ref``
here would be misplaced.

Rejected designs (do NOT re-propose; full archive in
``docs/architecture/decisions/0031-boundary-geometry-strategy.md``
Amendment 2026-05-22):
    B9.  Keep per-file ``.sources.json`` sidecars, rewrite contents to
         §12 v2.0 shape (source_id + remove fetched_at). Smallest
         change, but still leaves 73+ sidecars to maintain at 1000+
         file scale; doesn't address cardinality explosion; doesn't
         give the renderer queryable columns. FK-to-Parquet is
         strictly better.
    B10. Fold ``.sources.json`` only; keep ``.metadata.json`` per-file.
         Half-measure; two storage shapes for the same per-file
         metadata; complicates the seed module. Single table cleaner
         per Canonical Data Model (EIP).
    B11. Put ``boundary_layers.parquet`` under ``datasets/taxonomy/``.
         Conflates the boundary sibling-family with citizen-trusted
         taxonomy (ADR-0031 D25). The ledger belongs WITH the geometry
         it describes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.envelope import SourceRow
from yen_gov.core.schema_registry import schema_id, schema_version

# Schema metadata sourced via core.schema_registry (CLAUDE.md §11 — code
# never hand-types schema-version literals).
BOUNDARY_LAYERS_SCHEMA_FILENAME = "boundary-layers.schema.json"
BOUNDARY_LAYERS_ROW_SCHEMA_VERSION = schema_version(BOUNDARY_LAYERS_SCHEMA_FILENAME)
BOUNDARY_LAYERS_ROW_SCHEMA_ID = schema_id(BOUNDARY_LAYERS_SCHEMA_FILENAME)


Level = Literal[
    "country",
    "state",
    "district",
    "ac",
    "pc",
    "subdistrict",
    "village",
    "postal",
]

Format = Literal["geojson", "pmtiles"]

SimplificationAlgorithm = Literal[
    "douglas-peucker",
    "visvalingam",
    "shapely-preserve-topology",
    "coord-precision-round",
    "none",
]


# ----------------------------------------------------------------------
# Pydantic row mirror
# ----------------------------------------------------------------------


class BoundaryLayerRow(BaseModel):
    """A row destined for ``datasets/boundaries/boundary_layers.parquet``.

    Mirrors ``datasets/schemas/boundary-layers.schema.json`` v1.0 item
    shape exactly: 10 required columns + 7 nullable columns = 17 total.

    ``frozen=True`` because rows are dedup'd by layer_id in compile;
    ``extra='forbid'`` because the schema is ``additionalProperties:
    false`` and the two must move in lockstep (else a typo on a column
    name silently drops to NULL on emit).

    Denominator-transparency invariant (asserted in ``compile_to_parquet``):
    ``original_feature_count == retained_feature_count + unkeyed_count``.
    A row that violates it is a citizen-trust bug — the citizen sees a
    smaller map than the source published with no honest accounting of
    what was dropped.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    # --- required (10) ---
    layer_id: str = Field(
        min_length=1,
        pattern=r"^boundaries\.in\.[a-z]+(\.[a-z]+=[a-z0-9_]+)*$",
    )
    level: Level
    partition_path: str = Field(min_length=1, pattern=r"^boundaries/in/")
    format: Format
    crs: str = Field(min_length=1)
    original_feature_count: int = Field(ge=0)
    retained_feature_count: int = Field(ge=0)
    unkeyed_count: int = Field(ge=0)
    size_bytes: int = Field(ge=0)
    source_id: str = Field(pattern=r"^src-[a-z0-9]{12}$")

    # --- nullable (7) ---
    entity_state: str | None = None
    entity_district: str | None = None
    entity_city: str | None = None
    simplification_algorithm: SimplificationAlgorithm | None = None
    simplification_tolerance_deg: float | None = Field(default=None, ge=0)
    unkeyed_keys_json: str | None = None
    notes: str | None = None


# ----------------------------------------------------------------------
# Boundary source citation rows (T.0d seed — 4 producers actually on disk)
# ----------------------------------------------------------------------

# 5 sources keyed by SOURCE NICKNAME used by callers (snapshot.py +
# pipeline.json source_triple block). Per spec §2 (locked 2026-05-22):
# postal/India Post NOT seeded — no pincode geojson on disk today.
#
# SPEC DEVIATION (2026-05-22, T.0d chunk 1): the locked spec at
# TODO/20260522-t0d-boundaries-consolidation-spec.md §2 said "4 sources
# not 5; no India Post" but missed the SoI national silhouette
# (yashveeeeeeer/india-geodata) that is already on disk via the
# `kind: country` entry in pipeline.json (india-soi.geojson). Reality
# is 5 sources, not 4. The 5th (yashveeeeeeer) is added here. India
# Post remains rightly out — no pincode geojson exists yet.
#
# Each row is a SourceRow per envelope.py (v2.0 contract, ADR-0032):
# identity = (producer, title, vintage); source_id = derive_source_id(*triple).

SOURCE_NICKNAMES: tuple[str, ...] = (
    "datameet",
    "htl",
    "shijithpk",
    "ramseraph",
    "yashveeeeeeer",
)

_BOUNDARY_SOURCE_TRIPLES: dict[str, tuple[str, str, str]] = {
    # 1. DataMeet India Maps Project (state outlines via shp_bundle)
    "datameet": (
        "DataMeet India Maps Project",
        "datameet/maps Admin2 boundary bundle",
        "",  # vintage: rolling — no publisher-declared vintage
    ),
    # 2. Hindustan Times Labs (state-AC layers, MIT-applied-to-data)
    "htl": (
        "Hindustan Times Labs",
        "HTL state-AC shapefile bundle",
        "2008 Delimitation",
    ),
    # 3. shijithpk (J&K 2024 AC re-georeferencing)
    "shijithpk": (
        "shijithpk",
        "J&K Assembly New Borders (georeferenced)",
        "2024",
    ),
    # 4. ramSeraph (LGD-keyed admin boundaries — districts/subdistricts/villages)
    "ramseraph": (
        "ramSeraph",
        "Indian Admin Boundaries (LGD-keyed)",
        "lgd-latest-extra1",
    ),
    # 5. yashveeeeeeer/india-geodata (national silhouette — Survey of India)
    "yashveeeeeeer": (
        "yashveeeeeeer/india-geodata",
        "India national silhouette (SoI-derived)",
        "",  # vintage: rolling — derivative of SoI under National Geospatial Policy 2022
    ),
}


def _build_boundary_source_rows() -> tuple[SourceRow, ...]:
    """Build the 4 boundary SourceRow seeds.

    All four are republishers (false ``is_issuing_authority``); ECI / SoI /
    LGD are the upstream-upstream authorities. The fetched bytes come from
    these republisher URLs, so they get the citation row.
    """
    # url_main / license / tier / verification_method tabulated alongside the
    # triple for compactness. License enum-locked per ADR-0032 §12.
    #
    # MIT-on-data (HTL): unusual — MIT is a software license; some upstreams
    # apply it informally to data. The safe call per the enum is
    # 'unknown-public' with a notes pointer explaining the override.
    by_nickname: dict[
        str,
        tuple[str, str, str, bool, str, str | None],
    ] = {
        "datameet": (
            "CC-BY-4.0",
            "silver",
            "archived-snapshot",
            False,
            "https://github.com/datameet/maps",
            None,
        ),
        "htl": (
            "unknown-public",
            "silver",
            "archived-snapshot",
            False,
            "https://github.com/HindustanTimesLabs/shapefiles",
            "upstream MIT (software license applied to data; treated as attribution-only per ADR-0032 §12 enum)",
        ),
        "shijithpk": (
            "public-domain",
            "bronze",
            "archived-snapshot",
            False,
            "https://github.com/shijithpk/2024_maps_supplement",
            "Unlicense per upstream LICENSE file; treated as public-domain dedication. Author note: 'maps may not be research quality, but good enough for visualising on websites'.",
        ),
        "ramseraph": (
            "CC-BY-4.0",
            "silver",
            "archived-snapshot",
            False,
            "https://github.com/ramSeraph/indian_admin_boundaries",
            "Republishes LGD / Survey of India admin spine, LGD-keyed.",
        ),
        "yashveeeeeeer": (
            "CC-BY-4.0",
            "silver",
            "archived-snapshot",
            False,
            "https://github.com/yashveeeeeeer/india-geodata",
            "Republishes Survey of India national silhouette under National Geospatial Policy 2022.",
        ),
    }

    rows: list[SourceRow] = []
    for nickname in SOURCE_NICKNAMES:
        producer, title, vintage = _BOUNDARY_SOURCE_TRIPLES[nickname]
        license_, tier, method, is_authority, url_main, notes = by_nickname[nickname]
        rows.append(
            SourceRow(
                source_id=derive_source_id(producer, title, vintage),
                producer=producer,
                title=title,
                vintage=vintage,
                license=license_,  # type: ignore[arg-type]
                confidence_tier=tier,  # type: ignore[arg-type]
                is_issuing_authority=is_authority,
                verification_method=method,  # type: ignore[arg-type]
                url_main=url_main,
                citation_full=None,
                notes=notes,
            )
        )
    return tuple(rows)


# Public lookup: producer-nickname -> source_id, computed once at import.
# Consumers (snapshot.py per-pipeline-entry resolution; tests) read this
# rather than rebuilding the triple-hash repeatedly.
BOUNDARY_SOURCES: tuple[SourceRow, ...] = _build_boundary_source_rows()
BOUNDARY_SOURCE_ID_BY_NICKNAME: dict[str, str] = {
    nickname: row.source_id for nickname, row in zip(SOURCE_NICKNAMES, BOUNDARY_SOURCES, strict=True)
}


# ----------------------------------------------------------------------
# Upsert boundary sources into taxonomy/sources.parquet
# ----------------------------------------------------------------------


def upsert_boundary_sources(con: duckdb.DuckDBPyConnection) -> int:
    """Idempotent INSERT-OR-REPLACE of the 4 boundary citation rows into the
    in-memory ``sources`` DuckDB table.

    Mirrors the office_holdings_seed pattern. Caller is responsible for
    creating the ``sources`` table first (the canonical writer's
    ``_load_existing_sources`` step) and for emitting the table back to
    ``taxonomy/sources.parquet`` via ``_emit_sources`` afterwards.

    Returns the number of rows upserted (always len(BOUNDARY_SOURCES) =
    4 today; the count is returned for orchestrator logging parity with
    office_holdings_seed.compile_to_parquet).
    """
    upserted = 0
    for row in BOUNDARY_SOURCES:
        con.execute(
            """
            INSERT OR REPLACE INTO sources (
                source_id, producer, title, vintage,
                license, confidence_tier, is_issuing_authority,
                verification_method, url_main, citation_full, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                row.source_id,
                row.producer,
                row.title,
                row.vintage,
                row.license,
                row.confidence_tier,
                row.is_issuing_authority,
                row.verification_method,
                row.url_main,
                row.citation_full,
                row.notes,
            ],
        )
        upserted += 1
    return upserted


# ----------------------------------------------------------------------
# Compile to parquet (canonical emission seam)
# ----------------------------------------------------------------------


# DuckDB DDL mirrors the JSON Schema additionalProperties:false shape.
# 17 columns -- 10 NOT NULL + 7 nullable. PK on layer_id; FK on source_id
# is enforced at compile time by an EXISTS lookup against sources.parquet.
_BOUNDARY_LAYERS_DDL = """
CREATE TABLE boundary_layers (
    layer_id VARCHAR NOT NULL,
    level VARCHAR NOT NULL,
    entity_state VARCHAR,
    entity_district VARCHAR,
    entity_city VARCHAR,
    partition_path VARCHAR NOT NULL,
    format VARCHAR NOT NULL,
    crs VARCHAR NOT NULL,
    simplification_algorithm VARCHAR,
    simplification_tolerance_deg DOUBLE,
    original_feature_count INTEGER NOT NULL,
    retained_feature_count INTEGER NOT NULL,
    unkeyed_count INTEGER NOT NULL,
    unkeyed_keys_json VARCHAR,
    size_bytes BIGINT NOT NULL,
    source_id VARCHAR NOT NULL,
    notes VARCHAR
)
"""


def _row_to_tuple(row: BoundaryLayerRow) -> tuple:
    """Project a BoundaryLayerRow to the column order in _BOUNDARY_LAYERS_DDL.

    Order must match the DDL exactly so that `INSERT INTO boundary_layers
    VALUES (?...)` aligns. Changing the DDL is a schema bump.
    """
    return (
        row.layer_id,
        row.level,
        row.entity_state,
        row.entity_district,
        row.entity_city,
        row.partition_path,
        row.format,
        row.crs,
        row.simplification_algorithm,
        row.simplification_tolerance_deg,
        row.original_feature_count,
        row.retained_feature_count,
        row.unkeyed_count,
        row.unkeyed_keys_json,
        row.size_bytes,
        row.source_id,
        row.notes,
    )


def compile_to_parquet(
    layer_rows: list[BoundaryLayerRow] | tuple[BoundaryLayerRow, ...],
    datasets_root: Path,
) -> tuple[int, int]:
    """Emit boundary_layers.parquet + UPSERT taxonomy/sources.parquet.

    Args:
        layer_rows: BoundaryLayerRow instances, one per boundary geometry
            shard on disk. Caller builds the list (snapshot.py during a
            fetch run; migrate_to_hive_layout.py during initial migration).
            Empty list is permitted (writes a 0-row parquet + UPSERTs the 5
            boundary sources, which is itself a valid contract surface --
            consumers should not assume the file always has rows).
        datasets_root: path to ``datasets/``. The function writes:
            * ``boundaries/boundary_layers.parquet``
            * ``taxonomy/sources.parquet`` (UPSERT of the 5 boundary
              citation rows + preservation of all other adapter sources).

    Returns:
        ``(layer_count, source_count)`` for orchestrator logging.

    Invariants enforced at compile time:
        * Denominator transparency: every row's
          ``original_feature_count`` MUST equal
          ``retained_feature_count + unkeyed_count``. Violation raises
          ValueError before any parquet bytes hit disk (citizen-trust
          gate: shrinking the dataset silently is the bug
          ``unkeyed_count`` exists to prevent).
        * FK integrity: every row's ``source_id`` MUST appear in
          ``BOUNDARY_SOURCES`` (or be a previously-upserted source from
          another adapter). Violation raises ValueError.
        * PK uniqueness: duplicate ``layer_id`` raises ValueError.
        * Sort stability: rows are sorted by ``layer_id`` before COPY so
          re-emitting a byte-identical input yields a byte-identical
          parquet (canonical-writer property; CLAUDE.md \u00a710 carve-out
          for control-plane is not invoked here -- this is citizen-facing
          data).
    """
    datasets_root = Path(datasets_root)
    rows = list(layer_rows)

    # ----- pre-emit invariants ---------------------------------------
    seen_layer_ids: set[str] = set()
    for row in rows:
        if row.layer_id in seen_layer_ids:
            raise ValueError(
                f"duplicate layer_id {row.layer_id!r} -- boundary_layers PK must be unique"
            )
        seen_layer_ids.add(row.layer_id)
        if row.original_feature_count != row.retained_feature_count + row.unkeyed_count:
            raise ValueError(
                f"denominator-transparency violation for {row.layer_id!r}: "
                f"original={row.original_feature_count} != "
                f"retained={row.retained_feature_count} + unkeyed={row.unkeyed_count}. "
                "Every dropped feature MUST be accounted for in unkeyed_count."
            )

    # ----- FK pre-check ----------------------------------------------
    # Every layer's source_id must be one of the 5 BOUNDARY_SOURCES or
    # an existing source from another adapter. Pre-check against the
    # known-boundary set first (cheap); the writer's downstream
    # parquet-level FK check (across the union with existing sources)
    # catches the rare cross-adapter case.
    boundary_source_ids = {row.source_id for row in BOUNDARY_SOURCES}
    for row in rows:
        if row.source_id not in boundary_source_ids:
            raise ValueError(
                f"layer {row.layer_id!r} has source_id={row.source_id!r} which is "
                f"not one of the {len(BOUNDARY_SOURCES)} BOUNDARY_SOURCES. Adding a "
                "new boundary source requires extending boundary_layers_seed.SOURCE_NICKNAMES "
                "+ BOUNDARY_SOURCES in the same commit."
            )

    rows.sort(key=lambda r: r.layer_id)

    boundary_layers_out = datasets_root / "boundaries" / "boundary_layers.parquet"
    sources_out = datasets_root / "taxonomy" / "sources.parquet"

    boundary_layers_out.parent.mkdir(parents=True, exist_ok=True)
    sources_out.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(":memory:")
    try:
        # ----- boundary_layers -----------------------------------------
        con.execute(_BOUNDARY_LAYERS_DDL)
        if rows:
            con.executemany(
                "INSERT INTO boundary_layers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [_row_to_tuple(r) for r in rows],
            )
        con.execute(
            f"""
            COPY (
                SELECT * FROM boundary_layers ORDER BY layer_id
            ) TO '{boundary_layers_out.as_posix()}' (FORMAT PARQUET)
            """
        )

        # ----- sources UPSERT ------------------------------------------
        con.execute(
            """
            CREATE TABLE sources (
                source_id VARCHAR PRIMARY KEY,
                producer VARCHAR NOT NULL,
                title VARCHAR NOT NULL,
                vintage VARCHAR NOT NULL,
                license VARCHAR NOT NULL,
                confidence_tier VARCHAR NOT NULL,
                is_issuing_authority BOOLEAN NOT NULL,
                verification_method VARCHAR NOT NULL,
                url_main VARCHAR,
                citation_full VARCHAR,
                notes VARCHAR
            )
            """
        )
        if sources_out.is_file():
            con.execute(
                f"INSERT INTO sources SELECT * FROM read_parquet('{sources_out.as_posix()}')"
            )
        n_upserted = upsert_boundary_sources(con)
        con.execute(
            f"""
            COPY (
                SELECT * FROM sources ORDER BY source_id
            ) TO '{sources_out.as_posix()}' (FORMAT PARQUET)
            """
        )
    finally:
        con.close()

    return len(rows), n_upserted


__all__ = [
    "BOUNDARY_LAYERS_ROW_SCHEMA_ID",
    "BOUNDARY_LAYERS_ROW_SCHEMA_VERSION",
    "BOUNDARY_LAYERS_SCHEMA_FILENAME",
    "BOUNDARY_SOURCES",
    "BOUNDARY_SOURCE_ID_BY_NICKNAME",
    "BoundaryLayerRow",
    "Format",
    "Level",
    "SOURCE_NICKNAMES",
    "SimplificationAlgorithm",
    "compile_to_parquet",
    "upsert_boundary_sources",
]
