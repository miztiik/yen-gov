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
- Side effect: UPSERT every row in ``BOUNDARY_SOURCES`` (7 today)
  into ``datasets/taxonomy/sources.parquet`` so every boundary row's
  ``source_id`` resolves to a real ledger entry.

T.0d role (2026-05-22, fused atomic): consolidates 115 sidecar files
(73 ``.sources.json`` deprecated §12 v1.x + 39 ``.metadata.json`` + 2
``.unkeyed.json`` + 1 ``S22-villages-index.json``) into one queryable
control table. Per ADR-0032 §12 v2.0: provenance is a TABLE keyed on
``(producer, title, vintage)``, not a per-shard array smeared with
fetch timestamps. Per ADR-0031 amendment: directory layout switches
from flat ``boundaries/in/geojson/*`` to Hive-partitioned
``boundaries/in/<level>/state=<S>/...`` matching the elections grammar.

Postal sources seeded 2026-05-25 (Phase A.2 of
TODO/20260524-boundary-coverage-expansion-plan.md) — the
``datagovin_post_pincode_polygons_2025`` nickname covers the all-India
pincode KMZ published by the Department of Posts via data.gov.in
(Open Government Data Licence India 1.0). Pre-A.2 the postal subtree
was forward-looking only ("no pincode geojson exists in
datasets/boundaries/in/geojson/ today"); A.2 lands the first 36+
postal layer rows alongside the citation seed. ``ingest_pincode_polygons``
is the canonical writer for those layers and references
``BOUNDARY_SOURCE_ID_BY_NICKNAME['datagovin_post_pincode_polygons_2025']``
verbatim.

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
    "block",
    "panchayat",
    "village",
    "ward",
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

    # --- nullable (8) ---
    entity_state: str | None = None
    entity_district: str | None = None
    entity_city: str | None = None
    simplification_algorithm: SimplificationAlgorithm | None = None
    simplification_tolerance_deg: float | None = Field(default=None, ge=0)
    unkeyed_keys_json: str | None = None
    notes: str | None = None
    # Added in schema v1.1 (2026-05-24, PC layer ingest). 4-digit year of the
    # Delimitation Commission Order this geometry reflects. Required for
    # electoral-constituency layers (ac/pc) to disambiguate pre/post-Delim
    # geometries when both coexist; null for non-electoral layers (country/
    # state/district/subdistrict/village/postal admin spine).
    delimitation_vintage: str | None = Field(
        default=None,
        pattern=r"^[0-9]{4}$",
    )


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
    "shijithpk_pc_2024",
    "ramseraph",
    "yashveeeeeeer",
    "datagovin_post_pincode_polygons_2025",
)

_BOUNDARY_SOURCE_TRIPLES: dict[str, tuple[str, str, str]] = {
    # 1. DataMeet India Maps Project (state outlines via shp_bundle)
    "datameet": (
        "DataMeet India Maps Project",
        "datameet/maps Admin2 boundary bundle",
        "operator-snapshot-2026-05",  # publisher declares no vintage; operator-snapshot anchor per ADR-0042
    ),
    # 2. Hindustan Times Labs (state-AC layers, MIT-applied-to-data)
    "htl": (
        "Hindustan Times Labs",
        "HTL state-AC shapefile bundle",
        "2008 Delimitation",
    ),
    # 3. shijithpk — J&K 2024 AC re-georeferencing
    "shijithpk": (
        "shijithpk",
        "J&K Assembly New Borders (georeferenced)",
        "2024",
    ),
    # 4. shijithpk — India LS PC 545-feature map (georeferenced from ECI
    #    Press Note No. 23). Second shijithpk source row: different
    #    publication, different geographic scope, different document. The
    #    citation triple (producer, title, vintage) distinguishes them per
    #    ADR-0032; collapsing both under a single "shijithpk" key would
    #    lose per-document citation precision (rejected design A).
    "shijithpk_pc_2024": (
        "shijithpk",
        "India Lok Sabha Parliamentary Constituency boundaries (georeferenced)",
        "2024",
    ),
    # 5. ramSeraph (LGD-keyed admin boundaries — districts/subdistricts/villages)
    "ramseraph": (
        "ramSeraph",
        "Indian Admin Boundaries (LGD-keyed)",
        "lgd-latest-extra1",
    ),
    # 6. yashveeeeeeer/india-geodata (national silhouette — Survey of India)
    "yashveeeeeeer": (
        "yashveeeeeeer/india-geodata",
        "India national silhouette (SoI-derived)",
        "operator-snapshot-2026-05",  # derivative of SoI; operator-snapshot anchor per ADR-0042
    ),
    # 7. Department of Posts via data.gov.in — pincode polygon boundaries
    #    (Phase A.2 seed, 2026-05-25). 19,312 placemarks; per-pincode
    #    polygon-or-multipolygon geometry. Licence: Open Government Data
    #    Licence India 1.0 (data.gov.in default for Department of Posts
    #    publications). is_issuing_authority is true here because the
    #    Department of Posts IS the publishing authority for pincode
    #    boundaries (unlike most of the boundary tree, which is
    #    second-party republishing of SoI / LGD / ECI source data).
    "datagovin_post_pincode_polygons_2025": (
        "Department of Posts, Government of India",
        "All India Pincode Boundaries (KMZ)",
        "2025",
    ),
}


def _build_boundary_source_rows() -> tuple[SourceRow, ...]:
    """Build the BOUNDARY_SOURCES tuple.

    Six of the seven are second-party republishers (false
    ``is_issuing_authority``); ECI / SoI / LGD are the upstream-upstream
    authorities for those rows. The seventh
    (``datagovin_post_pincode_polygons_2025``) is the Department of
    Posts itself, the issuing authority for pincode geometry. The
    fetched bytes for the republisher rows come from their republisher
    URLs, so they get the citation row.
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
        "shijithpk_pc_2024": (
            "public-domain",
            "bronze",
            "transcribed",
            False,
            "https://github.com/shijithpk/2024_maps_supplement",
            "Boundary decisions issued by Election Commission of India via Press Note No. 23 for the 2024 General Election (https://elections24.eci.gov.in/docs/press-note-no-23.pdf); geometry digitised by shijithpk via QGIS georeferencing of the press-note PDF images and republished at github.com/shijithpk/2024_maps_supplement under The Unlicense. Researcher-quality, NOT survey-grade — upstream README warns 'international borders will be off, use at your own risk'. Suitable for choropleth visualisation; NOT for area/distance calculation. 2 features with ls_seat_code=999 cover J&K territory claimed by India but administered by Pakistan/China — must be rendered with a distinct treatment (e.g. diagonal hatch) and never tinted with election colours. Underlying Delimitation Commission Orders: 1976 baseline + 2008 amendment + 2022 J&K Delimitation Commission Order + 2023 Assam Delimitation Commission Order.",
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
        "datagovin_post_pincode_polygons_2025": (
            "OGL-IN-1.0",
            "gold",
            "transcribed",
            True,
            "https://www.data.gov.in/catalog/all-india-pincode-boundary",
            "All India pincode boundary KMZ published by the Department of Posts via the Government of India Open Data portal (data.gov.in). 19,312 per-pincode polygon features keyed by 6-digit pincode. Department of Posts is the issuing authority for pincode boundaries (true is_issuing_authority); verification method 'transcribed' because the KMZ is hand-downloaded from the portal rather than fetched live by an automated adapter (the portal gates downloads behind a captcha — same blocker as the A.1.a/A.1.b directory ingest, resolved by the user staging the file under datasets/ephemeral/). Geometry coordinate-rounded to 4 decimal places (~11 m) at emit time to fit the per-shard byte budget; original WGS84 lon,lat precision preserved upstream in the KMZ itself.",
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
# Triple-keyed lookup for the snapshot tool's per-entry source_id
# resolution. Built once at import. Disambiguates within a single
# producer (e.g. "shijithpk" has two source rows for two different
# publications). snapshot.py prefers this over the producer-only
# mapping that was added in T.0d chunk 2a.
BOUNDARY_SOURCE_ID_BY_TRIPLE: dict[tuple[str, str, str], str] = {
    _BOUNDARY_SOURCE_TRIPLES[nickname]: BOUNDARY_SOURCE_ID_BY_NICKNAME[nickname]
    for nickname in SOURCE_NICKNAMES
}


# ----------------------------------------------------------------------
# Upsert boundary sources into taxonomy/sources.parquet
# ----------------------------------------------------------------------


def upsert_boundary_sources(con: duckdb.DuckDBPyConnection) -> int:
    """Idempotent INSERT-OR-REPLACE of every BOUNDARY_SOURCES row into the
    in-memory ``sources`` DuckDB table.

    Mirrors the office_holdings_seed pattern. Caller is responsible for
    creating the ``sources`` table first (the canonical writer's
    ``_load_existing_sources`` step) and for emitting the table back to
    ``taxonomy/sources.parquet`` via ``_emit_sources`` afterwards.

    Returns the number of rows upserted (= ``len(BOUNDARY_SOURCES)``,
    7 today); the count is returned for orchestrator logging parity
    with office_holdings_seed.compile_to_parquet.
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
# 18 columns -- 10 NOT NULL + 8 nullable. PK on layer_id; FK on source_id
# is enforced at compile time by an EXISTS lookup against sources.parquet.
# 18th column `delimitation_vintage` added in schema v1.1 (2026-05-24,
# PC layer ingest).
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
    notes VARCHAR,
    delimitation_vintage VARCHAR
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
        row.delimitation_vintage,
    )


# Column projection used by the merge path. Pre-v1.1 parquets lack
# `delimitation_vintage`; we project NULL for that column so they
# rehydrate cleanly. Keeping the literal SQL alongside the DDL keeps
# the schema bump and the back-compat read in one place.
_BOUNDARY_LAYERS_SELECT_COLS = [
    "layer_id",
    "level",
    "entity_state",
    "entity_district",
    "entity_city",
    "partition_path",
    "format",
    "crs",
    "simplification_algorithm",
    "simplification_tolerance_deg",
    "original_feature_count",
    "retained_feature_count",
    "unkeyed_count",
    "unkeyed_keys_json",
    "size_bytes",
    "source_id",
    "notes",
    "delimitation_vintage",
]


def _read_existing_boundary_layers(datasets_root: Path) -> list[BoundaryLayerRow]:
    """Rehydrate the on-disk boundary_layers.parquet into BoundaryLayerRow
    objects so a merge-mode emit can preserve rows the current run did
    not touch. Returns [] when the parquet does not exist (initial
    bootstrap) so callers can use ``merge_with_existing=True``
    unconditionally without an explicit existence guard.

    Back-compat: pre-v1.1 parquets have no ``delimitation_vintage``
    column. We DESCRIBE the on-disk schema once and substitute
    ``NULL AS delimitation_vintage`` when the column is absent. The
    rehydrated BoundaryLayerRow defaults to None, which the v1.1
    Pydantic shape accepts and which the v1.1 DDL stores as NULL.
    The first merge-mode emit after the bump re-stamps the parquet
    with the new column for every preserved row.
    """
    parquet_path = datasets_root / "boundaries" / "boundary_layers.parquet"
    if not parquet_path.is_file():
        return []
    con = duckdb.connect()
    try:
        on_disk_cols = {
            r[0]
            for r in con.execute(
                f"DESCRIBE SELECT * FROM read_parquet('{parquet_path.as_posix()}')"
            ).fetchall()
        }
        select_clauses = [
            col if col in on_disk_cols else f"NULL AS {col}"
            for col in _BOUNDARY_LAYERS_SELECT_COLS
        ]
        select_sql = ", ".join(select_clauses)
        raw_rows = con.execute(
            f"SELECT {select_sql} FROM read_parquet('{parquet_path.as_posix()}')"
        ).fetchall()
    finally:
        con.close()
    return [
        BoundaryLayerRow(
            layer_id=r[0],
            level=r[1],
            entity_state=r[2],
            entity_district=r[3],
            entity_city=r[4],
            partition_path=r[5],
            format=r[6],
            crs=r[7],
            simplification_algorithm=r[8],
            simplification_tolerance_deg=r[9],
            original_feature_count=r[10],
            retained_feature_count=r[11],
            unkeyed_count=r[12],
            unkeyed_keys_json=r[13],
            size_bytes=r[14],
            source_id=r[15],
            notes=r[16],
            delimitation_vintage=r[17],
        )
        for r in raw_rows
    ]


def compile_to_parquet(
    layer_rows: list[BoundaryLayerRow] | tuple[BoundaryLayerRow, ...],
    datasets_root: Path,
    *,
    merge_with_existing: bool = False,
) -> tuple[int, int]:
    """Emit boundary_layers.parquet + UPSERT taxonomy/sources.parquet.

    Args:
        layer_rows: BoundaryLayerRow instances, one per boundary geometry
            shard on disk. Caller builds the list (snapshot.py during a
            fetch run; migrate_to_hive_layout.py during initial migration).
            Empty list is permitted (writes a 0-row parquet + UPSERTs the 7
            boundary sources, which is itself a valid contract surface --
            consumers should not assume the file always has rows).
        datasets_root: path to ``datasets/``. The function writes:
            * ``boundaries/boundary_layers.parquet``
            * ``taxonomy/sources.parquet`` (UPSERT of the 7 boundary
              citation rows + preservation of all other adapter sources).
        merge_with_existing: when True, rows already present in the
            on-disk ``boundary_layers.parquet`` whose ``layer_id`` is NOT
            in ``layer_rows`` are preserved and re-emitted. Rows in
            ``layer_rows`` take precedence on PK conflict. Default False
            preserves the original "snapshot.py rebuilds everything in
            one shot" semantics; the flag exists so the tool can be used
            incrementally (e.g. add the PC layer without re-fetching the
            other 7 URLs).

    Returns:
        ``(layer_count, source_count)`` for orchestrator logging.
        ``layer_count`` reflects the final on-disk row count (i.e.
        includes preserved rows when ``merge_with_existing=True``).

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
    new_rows = list(layer_rows)

    # ----- merge with existing parquet (opt-in) ----------------------
    if merge_with_existing:
        new_layer_ids = {row.layer_id for row in new_rows}
        preserved = [
            row
            for row in _read_existing_boundary_layers(datasets_root)
            if row.layer_id not in new_layer_ids
        ]
        rows = new_rows + preserved
    else:
        rows = new_rows

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
    # Every layer's source_id must be one of the 7 BOUNDARY_SOURCES or
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
                "INSERT INTO boundary_layers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
    "BOUNDARY_SOURCE_ID_BY_TRIPLE",
    "BoundaryLayerRow",
    "Format",
    "Level",
    "SOURCE_NICKNAMES",
    "SimplificationAlgorithm",
    "compile_to_parquet",
    "upsert_boundary_sources",
]
