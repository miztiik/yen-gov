"""Compile boundary geometry inventory to ``datasets/data/entities/boundary_layer.csv``.

X1a-fu2-E (2026-06-07) mechanical rip: the legacy
``datasets/boundaries/boundary_layers.parquet`` was transcoded 1:1 (4014
rows, 18 cols, SELECT *) to the canonical long-format CSV at
``datasets/data/entities/boundary_layer.csv`` and the parquet was
retired in the same PR. The CSV writer is REPLACE not UPSERT - every
``compile_to_csv`` call overwrites the CSV from the current ingest's
full row set. Callers that previously composed a partial-rebuild via
``merge_with_existing=True`` now load the existing CSV via the
``_read_existing_boundary_layers`` helper, merge their new rows in,
and pass the full set back to ``compile_to_csv``. Caller signatures
are unchanged (mechanical rename only).

Outputs:

- ``datasets/data/entities/boundary_layer.csv`` -- one row per boundary
  geometry shard on disk (18 columns; see ``columns.json`` file class).
  FK ``source_id`` resolves to ``datasets/data/entities/source.csv``.

Post-B3-pt2 (2026-06-06): the legacy side-effect of UPSERTing the 8
boundary source rows into ``datasets/taxonomy/sources.parquet`` was
removed. X1b retired ``sources.parquet`` (PR #814); the citation ledger
is now ``datasets/data/entities/source.csv`` and the 8 boundary triples
are seeded there once via the B2a/source_csv path. ``BOUNDARY_SOURCES``
+ ``BOUNDARY_SOURCE_ID_BY_NICKNAME`` + ``BOUNDARY_SOURCE_ID_BY_TRIPLE``
stay because callers (snapshot.py, lift_*.py, ingest_pincode_polygons.py)
look up source_id by nickname/triple and stamp it on every
BoundaryLayerRow; the in-process FK gate in ``compile_to_csv``
(every row's source_id is in ``BOUNDARY_SOURCES``) still catches typos
before any bytes hit disk. Cross-format FK closure against source.csv
is enforced by the B1 fk-validator gate at the CSV write seam.

T.0d role (2026-05-22, fused atomic): consolidates 115 sidecar files
(73 ``.sources.json`` deprecated section 12 v1.x + 39 ``.metadata.json``
+ 2 ``.unkeyed.json`` + 1 ``S22-villages-index.json``) into one queryable
control table. Per ADR-0032 section 12 v2.0: provenance is a TABLE keyed
on ``(producer, title, vintage)``, not a per-shard array smeared with
fetch timestamps. Per ADR-0031 amendment: directory layout switches
from flat ``boundaries/in/geojson/*`` to Hive-partitioned
``boundaries/in/<level>/state=<S>/...`` matching the elections grammar.

Postal sources seeded 2026-05-25 (Phase A.2 of
TODO/20260524-boundary-coverage-expansion-plan.md) - the
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
         section 12 v2.0 shape (source_id + remove fetched_at). Smallest
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

import csv as _csv
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_writer import write_csv
from yen_gov.canonical.envelope import SourceRow
from yen_gov.core.schema_registry import schema_id, schema_version

# File-class key used by the canonical CSV writer (datasets/data/_schema/columns.json).
BOUNDARY_LAYER_FILE_CLASS = "datasets/data/entities/boundary_layer.csv"
# Path relative to ``datasets_root`` used by ``compile_to_csv`` +
# ``_read_existing_boundary_layers``.
_BOUNDARY_LAYER_REL_PATH = Path("data") / "entities" / "boundary_layer.csv"

# Schema metadata sourced via core.schema_registry (CLAUDE.md section 11 - code
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
        # Section-1 (after ``boundaries``) is ``in`` (admin spine, T.0d
        # ADR-0031 Amendment) OR ``electoral`` (ECI constituency layers,
        # G10 of TODO/20260603-data-and-charting-platform-reset-plan.md
        # section 4 EL2). Hive-value charclass widened to include ``-``
        # so hyphenated slugs (``state=andhra-pradesh``) validate
        # alongside the legacy ``state=in_s01`` form.
        pattern=r"^boundaries\.(in|electoral)(\.[a-z]+(=[a-z0-9_-]+)?)+$",
    )
    level: Level
    partition_path: str = Field(
        min_length=1,
        # Per G10 (plan section 4 EL2) electoral layers live under
        # ``boundaries/electoral/delim=<year>/...`` so each ECI
        # Delimitation Commission Order publishes its own coexisting
        # boundary set; the admin spine stays under ``boundaries/in/``.
        pattern=r"^boundaries/(in|electoral)/",
    )
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
    "ramseraph_bhuvan_jk_villages",
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
    # 5b. ramSeraph (Bhuvan-mirror, Census-2011 J&K villages). Same
    #     publisher as 5 (ramSeraph) but a distinct triple per ADR-0032:
    #     different upstream lineage (Bhuvan / NRSC / J&K Revenue Dept
    #     instead of LGD), different vintage (Census-2011 instead of
    #     LGD-current), different license (CC0 1.0 per ramSeraph
    #     release notes instead of CC-BY-4.0). C.4.a single-state
    #     gap-fill for U08 J&K UT + U09 Ladakh UT — both UTs absent
    #     from LGD_Villages.geojsonl per upstream release notes.
    "ramseraph_bhuvan_jk_villages": (
        "ramSeraph (Bhuvan mirror)",
        "Bhuvan J&K Villages (Census-2011 cadastre)",
        "2011-census",
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
        "ramseraph_bhuvan_jk_villages": (
            "CC0-1.0",
            "silver",
            "archived-snapshot",
            False,
            "https://github.com/ramSeraph/indian_admin_boundaries/releases/tag/villages",
            "ramSeraph republishes Bhuvan's J&K village cadastre as 'Bhuvan_JK_Villages.geojsonl.7z' in the villages release. Upstream lineage: Bhuvan (https://bhuvan.nrsc.gov.in/) / ISRO-NRSC / J&K Revenue Department, Census-2011 vintage. License CC0 1.0 per the ramSeraph release-page notes. C.4.a single-state gap-fill closes 2 of 8 LGD-villages-absent UTs (U08 J&K + U09 Ladakh) — both incidentally present in this artefact because Census-2011 predates the 2019 J&K Reorganisation Act UT split. 14 Census-2011 pre-bifurcation districts (12 -> modern U08, 2 -> modern U09); shards keyed by district NAME SLUG (not LGD numeric) because the artefact carries no LGD codes. Post-2007 district bifurcations silently merged in parent shards (documented per-shard in citizen archaeology notes). Property naming is a 4th unique convention (uppercase Census-2011 shape: DIST_NAME / VID / VILL_CODE / NAME).",
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
# Compile to CSV (canonical emission seam)
# ----------------------------------------------------------------------


def _row_to_dict(row: BoundaryLayerRow) -> dict:
    """Project a BoundaryLayerRow to the dict shape consumed by
    ``yen_gov.canonical.csv_writer.write_csv``. The CSV writer enforces
    column-set + dtype against ``BOUNDARY_LAYER_FILE_CLASS`` in
    ``columns.json``; the dict here MUST carry every declared column
    (nullable values are ``None`` and emit as the empty CSV field).
    """
    return {
        "layer_id": row.layer_id,
        "level": row.level,
        "entity_state": row.entity_state,
        "entity_district": row.entity_district,
        "entity_city": row.entity_city,
        "partition_path": row.partition_path,
        "format": row.format,
        "crs": row.crs,
        "simplification_algorithm": row.simplification_algorithm,
        "simplification_tolerance_deg": row.simplification_tolerance_deg,
        "original_feature_count": row.original_feature_count,
        "retained_feature_count": row.retained_feature_count,
        "unkeyed_count": row.unkeyed_count,
        "unkeyed_keys_json": row.unkeyed_keys_json,
        "size_bytes": row.size_bytes,
        "source_id": row.source_id,
        "notes": row.notes,
        "delimitation_vintage": row.delimitation_vintage,
    }


def _read_existing_boundary_layers(datasets_root: Path) -> list[BoundaryLayerRow]:
    """Rehydrate the on-disk ``boundary_layer.csv`` into BoundaryLayerRow
    objects so a ``merge_with_existing=True`` emit can preserve rows the
    current run did not touch. Returns ``[]`` when the CSV does not exist
    (initial bootstrap) so callers can use ``merge_with_existing=True``
    unconditionally without an explicit existence guard.

    Parses with the stdlib ``csv`` module (no duckdb hop). Empty field on
    a nullable column resolves to ``None``; the integer + float columns
    are coerced from their string CSV form. The 18-column shape matches
    the file-class entry in ``datasets/data/_schema/columns.json``.
    """
    csv_path = datasets_root / _BOUNDARY_LAYER_REL_PATH
    if not csv_path.is_file():
        return []
    rows: list[BoundaryLayerRow] = []
    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = _csv.DictReader(fh)
        for raw in reader:
            sim_tol_raw = raw.get("simplification_tolerance_deg") or ""
            rows.append(
                BoundaryLayerRow(
                    layer_id=raw["layer_id"],
                    level=raw["level"],
                    entity_state=raw.get("entity_state") or None,
                    entity_district=raw.get("entity_district") or None,
                    entity_city=raw.get("entity_city") or None,
                    partition_path=raw["partition_path"],
                    format=raw["format"],
                    crs=raw["crs"],
                    simplification_algorithm=raw.get("simplification_algorithm") or None,
                    simplification_tolerance_deg=float(sim_tol_raw) if sim_tol_raw else None,
                    original_feature_count=int(raw["original_feature_count"]),
                    retained_feature_count=int(raw["retained_feature_count"]),
                    unkeyed_count=int(raw["unkeyed_count"]),
                    unkeyed_keys_json=raw.get("unkeyed_keys_json") or None,
                    size_bytes=int(raw["size_bytes"]),
                    source_id=raw["source_id"],
                    notes=raw.get("notes") or None,
                    delimitation_vintage=raw.get("delimitation_vintage") or None,
                )
            )
    return rows


def compile_to_csv(
    layer_rows: list[BoundaryLayerRow] | tuple[BoundaryLayerRow, ...],
    datasets_root: Path,
    *,
    merge_with_existing: bool = False,
) -> int:
    """Emit ``datasets/data/entities/boundary_layer.csv``.

    Args:
        layer_rows: BoundaryLayerRow instances, one per boundary geometry
            shard on disk. Caller builds the list (snapshot.py during a
            fetch run; migrate_to_hive_layout.py during initial migration).
            Empty list is permitted (writes a header-only file, which is
            itself a valid contract surface -- consumers should not
            assume the file always has rows).
        datasets_root: path to ``datasets/``. The function writes:
            * ``data/entities/boundary_layer.csv``
        merge_with_existing: when True, rows already present in the
            on-disk ``boundary_layer.csv`` whose ``layer_id`` is NOT in
            ``layer_rows`` are preserved and re-emitted. Rows in
            ``layer_rows`` take precedence on PK conflict. Default False
            preserves the original "snapshot.py rebuilds everything in
            one shot" semantics; the flag exists so the tool can be used
            incrementally (e.g. add the PC layer without re-fetching the
            other 7 URLs).

    Returns:
        ``layer_count`` -- final on-disk row count (i.e. includes preserved
        rows when ``merge_with_existing=True``). For orchestrator logging.

    X1a-fu2-E (2026-06-07): the legacy
    ``datasets/boundaries/boundary_layers.parquet`` emit was retired
    in favour of the canonical CSV at
    ``datasets/data/entities/boundary_layer.csv``. The writer is REPLACE
    not UPSERT - merge semantics are composed by the helper
    ``_read_existing_boundary_layers`` + the
    ``merge_with_existing=True`` branch below.

    Post-B3-pt2 (2026-06-06): the sibling UPSERT into
    ``datasets/taxonomy/sources.parquet`` was removed because X1b
    (PR #814) retired that file. Boundary source citation rows live in
    ``datasets/data/entities/source.csv``; the 8
    ``(producer, title, vintage)`` triples are seeded there once via
    the B2a/source_csv path, not per boundary-layers emit. The in-process
    FK gate below still rejects a BoundaryLayerRow whose source_id is
    not in ``BOUNDARY_SOURCES`` so typos still fail before any bytes
    hit disk; cross-format FK closure against source.csv is enforced
    by the B1 fk-validator gate at the CSV write seam.

    Invariants enforced at compile time:
        * Denominator transparency: every row's
          ``original_feature_count`` MUST equal
          ``retained_feature_count + unkeyed_count``. Violation raises
          ValueError before any CSV bytes hit disk (citizen-trust
          gate: shrinking the dataset silently is the bug
          ``unkeyed_count`` exists to prevent).
        * FK integrity: every row's ``source_id`` MUST appear in
          ``BOUNDARY_SOURCES``. Violation raises ValueError.
        * PK uniqueness: duplicate ``layer_id`` raises ValueError.
        * Sort stability: rows are sorted by ``layer_id`` by the CSV
          writer's PK-sort path so re-emitting a byte-identical input
          yields a byte-identical CSV (canonical-writer property).
    """
    datasets_root = Path(datasets_root)
    new_rows = list(layer_rows)

    # ----- merge with existing CSV (opt-in) --------------------------
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
    # Every layer's source_id must be one of the BOUNDARY_SOURCES rows.
    # Adding a new boundary source requires extending SOURCE_NICKNAMES +
    # BOUNDARY_SOURCES in the same commit AND seeding the matching row
    # into datasets/data/entities/source.csv via the B2a/source_csv path.
    boundary_source_ids = {row.source_id for row in BOUNDARY_SOURCES}
    for row in rows:
        if row.source_id not in boundary_source_ids:
            raise ValueError(
                f"layer {row.layer_id!r} has source_id={row.source_id!r} which is "
                f"not one of the {len(BOUNDARY_SOURCES)} BOUNDARY_SOURCES. Adding a "
                "new boundary source requires extending boundary_layers_seed.SOURCE_NICKNAMES "
                "+ BOUNDARY_SOURCES in the same commit."
            )

    # ----- emit via canonical CSV writer -----------------------------
    out_path = datasets_root / _BOUNDARY_LAYER_REL_PATH
    write_csv(
        path=out_path,
        file_class=BOUNDARY_LAYER_FILE_CLASS,
        rows=[_row_to_dict(r) for r in rows],
    )

    return len(rows)


__all__ = [
    "BOUNDARY_LAYERS_ROW_SCHEMA_ID",
    "BOUNDARY_LAYERS_ROW_SCHEMA_VERSION",
    "BOUNDARY_LAYERS_SCHEMA_FILENAME",
    "BOUNDARY_LAYER_FILE_CLASS",
    "BOUNDARY_SOURCES",
    "BOUNDARY_SOURCE_ID_BY_NICKNAME",
    "BOUNDARY_SOURCE_ID_BY_TRIPLE",
    "BoundaryLayerRow",
    "Format",
    "Level",
    "SOURCE_NICKNAMES",
    "SimplificationAlgorithm",
    "compile_to_csv",
]
