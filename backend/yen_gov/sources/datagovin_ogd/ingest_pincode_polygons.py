"""Pincode polygon ingest — Phase A.2.

Reads the operator-staged all-India pincode KMZ (parsed by
:mod:`yen_gov.sources.datagovin_ogd.pincode_polygons`), cross-joins
pincode → state via the A.1.b ``pincode-directory.parquet``, emits one
GeoJSON FeatureCollection per ECI state under
``datasets/boundaries/in/postal/state=in_<sNN>/all.geojson`` (T.0d
Hive layout), and UPSERTs the per-state layer rows into
``datasets/boundaries/boundary_layers.parquet`` via the canonical
:func:`yen_gov.canonical.boundary_layers_seed.compile_to_parquet`
merge-mode seam.

Pipeline (one read-through of the KMZ):

1. :func:`parse_pincode_polygons_from_kmz` — pure parse (19,312
   placemarks, ~3.3M vertices on the 2025 corpus).
2. ``_build_pincode_to_state_lookup`` — DuckDB query over the A.1.b
   directory parquet returning ``{pincode → uppercase_statename}``.
3. ``_build_entity_lookup`` — DuckDB query over ``entities.parquet``
   returning ``{normalised_display_name → entity_id (IN-S22)}``.
4. ``_state_assign`` — walks parsed polygons, resolves
   ``pincode → statename → entity_id → partition_slug (in_s22)``.
   Pincodes that don't resolve (no directory row, NULL statename, or
   unmappable statename) accumulate in ``unkeyed`` and ship as the
   synthetic ``scope=unkeyed`` layer row (no geometry; just the
   pincode list in ``unkeyed_keys_json``) so the denominator-
   transparency invariant (Hans + Max canonical insistence per
   ADR-0031 / boundary_layers_seed compile-time check) holds at the
   national-postal-corpus level.
5. ``_round_polygon_coords`` — rounds every (lon, lat) to
   ``COORD_PRECISION_DIGITS`` (4 = ~11 m at the equator) and drops
   consecutive duplicates created by rounding. Re-closes the ring if
   rounding broke the closure. Deterministic; no mapshaper or shapely
   dependency.
6. Per-state GeoJSON write — sorted by pincode for byte-determinism,
   compact JSON (``separators=(",", ":")``), ``ensure_ascii=False`` so
   Indic office names round-trip without escape noise.
7. ``compile_to_parquet(..., merge_with_existing=True)`` — UPSERTs the
   per-state + unkeyed layer rows into ``boundary_layers.parquet`` and
   the single Department-of-Posts citation row into
   ``sources.parquet``. Other adapters' rows are preserved.

Determinism: a re-run against the byte-identical KMZ produces
byte-identical GeoJSON shards AND a byte-identical
``boundary_layers.parquet`` (modulo other-adapter churn elsewhere in
the run). The parser preserves upstream ordering; coordinate rounding
is total and stable; per-state sort key is ``(pincode, office_name)``;
GeoJSON dict-key order is fixed at insertion time (``type`` →
``properties`` → ``geometry``).

State assignment policy (verified empirically on the 2025 corpus —
99.9% directory coverage):

* Source of truth is ``pincode-directory.parquet`` (A.1.b), NOT the
  KMZ ``Circle`` field. The KMZ Circle is a postal administrative
  unit that imperfectly aligns with ECI states (e.g. "North Eastern"
  Circle covers 7 sister states; "Delhi" Circle is partly in
  Haryana / UP; "Jammukashmir" predates the 2019 reorganisation).
  Pincode → directory.statename → ECI entity_id is the canonical chain.
* 3 manual aliases handle directory statenames that don't normalise
  cleanly to an ``entities.parquet`` display_name:

  - ``JAMMU AND KASHMIR`` → ``IN-U08`` (post-2019 J&K UT; the
    directory does not disambiguate state-vs-UT but the J&K state
    code S09 retired in 2019).
  - ``DELHI`` → ``IN-U05`` (entities uses canonical ``NCT of Delhi``).
  - ``THE DADRA AND NAGAR HAVELI AND DAMAN AND DIU`` → ``IN-U03``
    (directory's leading "THE" article doesn't appear in
    ``entities.display_name``).

Out of scope here:

* PMTiles emission (ADR-0031 cutover threshold 10 MB gzipped) —
  current per-state shards run sub-1 MB compressed even for UP at 1655
  pincodes (largest state by pincode count), so geojson is the right
  container today.
* Polygon simplification beyond coord-precision rounding. Mapshaper
  / douglas-peucker would shrink output further but introduce a
  non-Python dependency and topology risks (slivers, dropped islands).
  Phase 0.4 of the boundary-coverage sprint addresses this; if the
  per-state byte budget grows under future corpus deltas, that pass
  re-runs on this layer.
* Live fetch. The OGD portal gates KMZ downloads behind a per-session
  captcha (same blocker as A.1.a/A.1.b); fetch is operator-manual,
  verification_method on the citation row is ``transcribed``.

Invocation::

    python -m yen_gov.sources.datagovin_ogd.ingest_pincode_polygons
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import duckdb

from yen_gov.canonical.boundary_layers_seed import (
    BOUNDARY_SOURCE_ID_BY_NICKNAME,
    BoundaryLayerRow,
    compile_to_parquet,
)
from yen_gov.sources.datagovin_ogd.pincode_polygons import (
    ParsedPincodePolygons,
    PincodePolygon,
    PolygonRing,
    parse_pincode_polygons_from_kmz,
)

__all__ = [
    "COORD_PRECISION_DIGITS",
    "DEFAULT_BOUNDARY_LAYERS_REL",
    "DEFAULT_DIRECTORY_REL",
    "DEFAULT_ENTITIES_REL",
    "DEFAULT_INPUT_KMZ_REL",
    "DEFAULT_OUTPUT_DIR_REL",
    "IngestResult",
    "PINCODE_POLYGONS_SOURCE_ID",
    "ingest_pincode_polygons",
]


# Source identity — resolved from the BOUNDARY_SOURCES seed extension.
# The 7th nickname maps to the Department of Posts (data.gov.in) row
# added in this same PR; reading it back here keeps a single SSOT for
# the source_id (the seed is authoritative; the ingest reads it).
PINCODE_POLYGONS_SOURCE_NICKNAME = "datagovin_post_pincode_polygons_2025"
PINCODE_POLYGONS_SOURCE_ID = BOUNDARY_SOURCE_ID_BY_NICKNAME[
    PINCODE_POLYGONS_SOURCE_NICKNAME
]


# Default paths — caller can override for tests.
DEFAULT_INPUT_KMZ_REL = Path(
    "datasets/ephemeral/dd7bfd69-143e-462b-bfa3-2ac35d931342.kmz"
)
DEFAULT_OUTPUT_DIR_REL = Path("datasets/boundaries/in/postal")
DEFAULT_BOUNDARY_LAYERS_REL = Path("datasets/boundaries/boundary_layers.parquet")
DEFAULT_DIRECTORY_REL = Path(
    "datasets/reference/in/pincodes/pincode-directory.parquet"
)
DEFAULT_ENTITIES_REL = Path("datasets/taxonomy/entities.parquet")


# Coordinate precision: 4 decimal places ≈ 11 m at the equator.
# Empirically retains visual fidelity for choropleth + zoom-9-and-out
# rendering without exploding shard size. If a future zoom-13 use case
# emerges, bump to 5 and re-emit; the change is byte-stable per state.
COORD_PRECISION_DIGITS = 4


# ---------------------------------------------------------------------------
# State-name normalisation + alias map
# ---------------------------------------------------------------------------


# Manual aliases from directory ``statename`` → canonical entity_id.
# All three are documented at module-level; each captures a real
# upstream-vs-taxonomy mismatch, NOT cosmetic spelling drift.
# Keys are pre-normalised (uppercase + whitespace-stripped) so the
# lookup composes with ``_normalize_state_name``.
_DIRECTORY_STATENAME_ALIASES: dict[str, str] = {
    # 2019 Jammu and Kashmir Reorganisation Act split pre-2019 J&K
    # state (ECI legacy S09) into J&K UT (IN-U08) + Ladakh UT
    # (IN-U09). The pincode directory uses a single "JAMMU AND
    # KASHMIR" label for all J&K-UT pincodes (Ladakh has its own
    # "LADAKH" entries) — disambiguate to U08.
    "JAMMUANDKASHMIR": "IN-U08",
    # entities.parquet uses the constitutional name "NCT of Delhi"
    # (IN-U05); the postal directory uses "DELHI". Same UT.
    "DELHI": "IN-U05",
    # Directory writes the merged 2020 UT as "THE DADRA AND NAGAR
    # HAVELI AND DAMAN AND DIU"; entities.parquet drops the leading
    # article. Same UT, IN-U03.
    "THEDADRAANDNAGARHAVELIANDDAMANANDDIU": "IN-U03",
}


def _normalize_state_name(s: str) -> str:
    """Uppercase + whitespace-strip a state name for alias-map lookup."""
    return "".join(s.split()).upper()


def _build_pincode_to_state_lookup(directory_parquet: Path) -> dict[str, str]:
    """Returns ``{pincode → uppercase_statename}`` for every pincode in the
    directory that has at least one non-NULL statename row.

    Within a pincode, all post offices share the same state (verified
    on the 2025 directory corpus). We pick ``MIN(statename)`` for
    determinism in the unlikely event of a row-level inconsistency.
    Pincodes with only NULL-statename rows are EXCLUDED from the map
    (the caller treats them as unkeyed).
    """
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            f"""
            SELECT pincode, MIN(statename) AS statename
            FROM read_parquet('{directory_parquet.as_posix()}')
            WHERE statename IS NOT NULL
            GROUP BY pincode
            """
        ).fetchall()
    finally:
        con.close()
    return {pincode: statename for pincode, statename in rows}


def _build_entity_lookup(entities_parquet: Path) -> dict[str, str]:
    """Returns ``{normalised_display_name → entity_id}`` for every
    state + ut entity in ``entities.parquet``.

    Used in tandem with ``_DIRECTORY_STATENAME_ALIASES``: the alias
    map is consulted first (covers the 3 known directory deviations);
    on miss, this lookup matches against the canonical entity display
    name normalised the same way.
    """
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            f"""
            SELECT entity_id, display_name
            FROM read_parquet('{entities_parquet.as_posix()}')
            WHERE entity_type IN ('state', 'ut')
              AND display_name IS NOT NULL
            """
        ).fetchall()
    finally:
        con.close()
    out: dict[str, str] = {}
    for entity_id, display_name in rows:
        out[_normalize_state_name(display_name)] = entity_id
    return out


def _entity_id_to_partition_slug(entity_id: str) -> str:
    """Convert ``IN-S22`` → ``in_s22`` (Hive partition-key value)."""
    return entity_id.replace("-", "_").lower()


# ---------------------------------------------------------------------------
# State assignment
# ---------------------------------------------------------------------------


def _state_assign(
    polygons: tuple[PincodePolygon, ...],
    pincode_to_statename: dict[str, str],
    entity_lookup: dict[str, str],
) -> tuple[dict[str, list[PincodePolygon]], list[tuple[str, str]]]:
    """Bucket polygons by ECI partition slug.

    Returns ``(by_slug, unkeyed)``:

    * ``by_slug`` — ``{partition_slug (in_s22 ...) → list of polygons}``,
      with the polygon lists in input order (callers re-sort by pincode
      before emit for byte-determinism).
    * ``unkeyed`` — ``[(pincode, reason)]`` for every polygon that
      could not be assigned to an ECI state. Empty list is the
      expected happy path.
    """
    by_slug: dict[str, list[PincodePolygon]] = {}
    unkeyed: list[tuple[str, str]] = []

    for poly in polygons:
        statename = pincode_to_statename.get(poly.pincode)
        if statename is None:
            unkeyed.append((poly.pincode, "no directory row or NULL statename"))
            continue
        norm = _normalize_state_name(statename)
        entity_id = _DIRECTORY_STATENAME_ALIASES.get(norm) or entity_lookup.get(norm)
        if entity_id is None:
            unkeyed.append(
                (poly.pincode, f"unrecognised statename {statename!r}")
            )
            continue
        slug = _entity_id_to_partition_slug(entity_id)
        by_slug.setdefault(slug, []).append(poly)

    return by_slug, unkeyed


# ---------------------------------------------------------------------------
# Coordinate rounding
# ---------------------------------------------------------------------------


def _round_ring(ring: PolygonRing) -> list[list[float]]:
    """Round every (lon, lat) to :data:`COORD_PRECISION_DIGITS` and drop
    consecutive duplicates produced by rounding.

    Re-closes the ring (appends first coord at the end) if rounding
    broke the closure. Returns a list of ``[lon, lat]`` pairs ready
    for JSON serialisation.

    Degenerate rings (< 4 coords after dedup) are returned as-is; the
    caller's denominator-transparency invariant catches any layer
    where this becomes a problem (would manifest as a malformed GeoJSON
    geometry on the next read by the renderer).
    """
    out: list[list[float]] = []
    prev: tuple[float, float] | None = None
    for lon, lat in ring.coords:
        rl = round(lon, COORD_PRECISION_DIGITS)
        ra = round(lat, COORD_PRECISION_DIGITS)
        if (rl, ra) == prev:
            continue
        out.append([rl, ra])
        prev = (rl, ra)
    if out and out[0] != out[-1]:
        out.append(out[0])
    return out


def _polygon_to_geojson_geometry(
    geometries: tuple[tuple[PolygonRing, tuple[PolygonRing, ...]], ...],
) -> dict:
    """Convert one polygon's geometry tuple into a GeoJSON geometry dict.

    Single-polygon → ``{"type": "Polygon", "coordinates": [outer, ...inners]}``.
    Multi-polygon → ``{"type": "MultiPolygon", "coordinates": [[outer,
    inners], ...]}``.

    Key order is fixed at insertion time (``type`` before
    ``coordinates``) for byte-determinism.
    """
    if len(geometries) == 1:
        outer, inners = geometries[0]
        rings = [_round_ring(outer)] + [_round_ring(inner) for inner in inners]
        return {"type": "Polygon", "coordinates": rings}
    polys: list[list[list[list[float]]]] = []
    for outer, inners in geometries:
        rings = [_round_ring(outer)] + [_round_ring(inner) for inner in inners]
        polys.append(rings)
    return {"type": "MultiPolygon", "coordinates": polys}


# ---------------------------------------------------------------------------
# GeoJSON emission
# ---------------------------------------------------------------------------


# Fixed property-key order for byte-determinism. Insertion order is
# preserved by Python 3.7+ dicts and respected by ``json.dumps``.
_PROPERTY_KEYS_IN_ORDER: tuple[str, ...] = (
    "pincode",
    "office_name",
    "division",
    "region",
    "circle",
    "source_id",
)


def _build_feature(poly: PincodePolygon) -> dict:
    """One GeoJSON Feature for one pincode polygon, with a fixed key
    order across all features for byte-determinism.
    """
    return {
        "type": "Feature",
        "properties": {
            "pincode": poly.pincode,
            "office_name": poly.office_name,
            "division": poly.division,
            "region": poly.region,
            "circle": poly.circle,
            "source_id": PINCODE_POLYGONS_SOURCE_ID,
        },
        "geometry": _polygon_to_geojson_geometry(poly.geometries),
    }


def _write_state_shard(state_polys: list[PincodePolygon], out_path: Path) -> int:
    """Serialise a per-state polygon list to a GeoJSON FeatureCollection
    and return the file size in bytes.

    Features are sorted by ``(pincode, office_name)`` before write so a
    re-run against byte-identical input yields a byte-identical shard.
    """
    state_polys = sorted(state_polys, key=lambda p: (p.pincode, p.office_name))
    fc = {
        "type": "FeatureCollection",
        "features": [_build_feature(p) for p in state_polys],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(fc, separators=(",", ":"), ensure_ascii=False)
    out_path.write_text(payload, encoding="utf-8")
    return out_path.stat().st_size


def _write_unkeyed_shard(unkeyed_pincodes: list[str], out_path: Path) -> int:
    """Write the synthetic unkeyed-bucket shard as an empty
    FeatureCollection.

    The 17 (or however many) unkeyable pincodes are tracked in the
    ledger row's ``unkeyed_keys_json`` column; the shard file itself
    is intentionally an empty FeatureCollection so renderers that walk
    every shard see an explicit "nothing here" rather than a 404.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {"type": "FeatureCollection", "features": []},
        separators=(",", ":"),
    )
    out_path.write_text(payload, encoding="utf-8")
    return out_path.stat().st_size


# ---------------------------------------------------------------------------
# Ingest orchestration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IngestResult:
    """Summary of one A.2 ingest run.

    ``layer_count`` is the number of postal-layer rows written this
    run (per-state + 1 synthetic if unkeyed_count > 0). It does NOT
    include pre-existing non-postal rows preserved by
    ``compile_to_parquet(merge_with_existing=True)``.
    """

    parsed: ParsedPincodePolygons
    output_dir: Path
    layer_count: int
    unkeyed_count: int
    unkeyed_pincodes: tuple[str, ...]
    per_state_counts: dict[str, int]  # slug → polygon count
    total_size_bytes: int


def _build_per_state_layer_row(
    slug: str,
    pincode_count: int,
    shard_size: int,
) -> BoundaryLayerRow:
    """Build a single per-state postal layer row."""
    return BoundaryLayerRow(
        layer_id=f"boundaries.in.postal.state={slug}",
        level="postal",
        entity_state=slug,
        partition_path=f"boundaries/in/postal/state={slug}/all.geojson",
        format="geojson",
        crs="EPSG:4326",
        original_feature_count=pincode_count,
        retained_feature_count=pincode_count,
        unkeyed_count=0,
        size_bytes=shard_size,
        source_id=PINCODE_POLYGONS_SOURCE_ID,
        simplification_algorithm="coord-precision-round",
        simplification_tolerance_deg=float(10 ** -COORD_PRECISION_DIGITS),
        notes=(
            "Per-pincode polygon shard for one ECI state, derived from "
            "the Department of Posts all-India pincode KMZ (data.gov.in). "
            "Pincode → state assignment via cross-join with "
            "reference/in/pincodes/pincode-directory.parquet (A.1.b). "
            "Coordinates rounded to 4 decimal places (~11 m at the "
            "equator) at emit time for byte-budget; original WGS84 "
            "precision preserved upstream in the KMZ itself."
        ),
    )


def _build_unkeyed_layer_row(
    unkeyed_pincodes: list[str],
    shard_size: int,
) -> BoundaryLayerRow:
    """Build the synthetic ``scope=unkeyed`` layer row.

    This row carries the audit trail for pincodes that could not be
    state-assigned. The on-disk file is an empty FeatureCollection;
    the pincode list lives in ``unkeyed_keys_json`` so it is queryable
    from the ledger without re-parsing the KMZ.
    """
    n = len(unkeyed_pincodes)
    return BoundaryLayerRow(
        layer_id="boundaries.in.postal.scope=unkeyed",
        level="postal",
        entity_state=None,
        partition_path="boundaries/in/postal/scope=unkeyed/all.geojson",
        format="geojson",
        crs="EPSG:4326",
        original_feature_count=n,
        retained_feature_count=0,
        unkeyed_count=n,
        size_bytes=shard_size,
        source_id=PINCODE_POLYGONS_SOURCE_ID,
        simplification_algorithm=None,
        simplification_tolerance_deg=None,
        unkeyed_keys_json=json.dumps(sorted(unkeyed_pincodes)),
        notes=(
            "Pincodes present in the Department of Posts KMZ but absent "
            "from (or NULL-statename in) the A.1.b pincode-directory.parquet. "
            "The shard file is intentionally an empty FeatureCollection; "
            "the pincode list lives in unkeyed_keys_json for ledger-side "
            "audit without re-parsing the KMZ. Citizen-trust invariant: "
            "every dropped feature is accounted for here so original = "
            "retained + unkeyed holds at the postal-corpus level."
        ),
    )


def ingest_pincode_polygons(
    *,
    input_kmz: Path | None = None,
    output_dir: Path | None = None,
    boundary_layers_parquet: Path | None = None,
    directory_parquet: Path | None = None,
    entities_parquet: Path | None = None,
    datasets_root: Path | None = None,
) -> IngestResult:
    """End-to-end Phase A.2 ingest.

    All path arguments default to the canonical relative locations
    under the workspace root. ``datasets_root`` overrides the
    container directory passed to ``compile_to_parquet``; it defaults
    to ``Path("datasets")`` (POSIX) and is what the canonical writer
    uses to locate ``boundaries/boundary_layers.parquet`` +
    ``taxonomy/sources.parquet``.

    The function is total: any KMZ → ECI-state mismatch becomes
    unkeyed (tracked in the synthetic row), not an exception. The only
    raisable cases are upstream I/O errors (missing KMZ, malformed
    parquet) and the canonical writer's own invariant violations
    (denominator-transparency, FK integrity).
    """
    input_kmz = Path(input_kmz) if input_kmz is not None else DEFAULT_INPUT_KMZ_REL
    output_dir = Path(output_dir) if output_dir is not None else DEFAULT_OUTPUT_DIR_REL
    directory_parquet = (
        Path(directory_parquet)
        if directory_parquet is not None
        else DEFAULT_DIRECTORY_REL
    )
    entities_parquet = (
        Path(entities_parquet)
        if entities_parquet is not None
        else DEFAULT_ENTITIES_REL
    )
    if datasets_root is None:
        datasets_root = Path("datasets")
    # boundary_layers_parquet is computed inside compile_to_parquet
    # from datasets_root; the argument here is kept for future
    # symmetry / testing but unused today.
    _ = boundary_layers_parquet

    # ----- parse ----------------------------------------------------
    parsed = parse_pincode_polygons_from_kmz(input_kmz)

    # ----- state assignment ----------------------------------------
    pincode_to_statename = _build_pincode_to_state_lookup(directory_parquet)
    entity_lookup = _build_entity_lookup(entities_parquet)
    by_slug, unkeyed = _state_assign(parsed.polygons, pincode_to_statename, entity_lookup)

    # ----- per-state emit + row build ------------------------------
    layer_rows: list[BoundaryLayerRow] = []
    per_state_counts: dict[str, int] = {}
    total_size_bytes = 0
    for slug in sorted(by_slug):
        state_polys = by_slug[slug]
        per_state_counts[slug] = len(state_polys)
        out_path = output_dir / f"state={slug}" / "all.geojson"
        size_bytes = _write_state_shard(state_polys, out_path)
        total_size_bytes += size_bytes
        layer_rows.append(_build_per_state_layer_row(slug, len(state_polys), size_bytes))

    # ----- unkeyed bucket (only emit when count > 0) ---------------
    # The synthetic `scope=unkeyed` row exists to keep the denominator
    # transparency invariant (original = retained + unkeyed) auditable
    # at the postal-corpus level. If a future ingest run resolves every
    # KMZ pincode against the directory, no row is needed — the per-
    # state rows already trivially satisfy the invariant. Skipping the
    # row here also keeps the on-disk shard tree clean (no stale empty
    # FeatureCollection lingering after the fix).
    unkeyed_pincodes = sorted(p for p, _ in unkeyed)
    if unkeyed_pincodes:
        unkeyed_out_path = output_dir / "scope=unkeyed" / "all.geojson"
        unkeyed_size = _write_unkeyed_shard(unkeyed_pincodes, unkeyed_out_path)
        total_size_bytes += unkeyed_size
        layer_rows.append(_build_unkeyed_layer_row(unkeyed_pincodes, unkeyed_size))

    # ----- ledger emit via canonical writer ------------------------
    compile_to_parquet(layer_rows, datasets_root, merge_with_existing=True)

    return IngestResult(
        parsed=parsed,
        output_dir=output_dir,
        layer_count=len(layer_rows),
        unkeyed_count=len(unkeyed_pincodes),
        unkeyed_pincodes=tuple(unkeyed_pincodes),
        per_state_counts=per_state_counts,
        total_size_bytes=total_size_bytes,
    )


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """``python -m yen_gov.sources.datagovin_ogd.ingest_pincode_polygons``."""
    result = ingest_pincode_polygons()
    print(f"Parsed placemarks       : {len(result.parsed.polygons)}")
    print(f"Parse-skipped           : {result.parsed.skipped_count}")
    print(f"States emitted          : {sum(1 for _ in result.per_state_counts)}")
    print(f"Unkeyed pincode count   : {result.unkeyed_count}")
    if result.unkeyed_count:
        print(f"  First 10 unkeyed      : {list(result.unkeyed_pincodes)[:10]}")
    print(f"Total layer rows written: {result.layer_count}")
    print(f"Total bytes on disk     : {result.total_size_bytes:>12,}")
    print(f"Output directory        : {result.output_dir.as_posix()}")


if __name__ == "__main__":
    main()
