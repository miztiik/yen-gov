"""Lift Bhuvan_JK_Villages.geojsonl into per-(state, district-slug) Hive shards.

Phase C.4.a of ``docs/archive/plans/20260529-boundary-rip-and-replace-plan.md``: gap-fill
the LGD-villages-absent J&K UT (and Ladakh UT, included incidentally) by
adopting ramSeraph's mirror of Bhuvan's Census-2011 J&K village cadastre.

**Upstream surprise (locked at first-snapshot probe 2026-05-30)**: the
artefact is NOT current-LGD J&K (which would carry 20 LGD-coded modern
districts under U08 only). It is **Census-2011 vintage** with 14
pre-bifurcation district names mixing both modern UTs (12 mapping to
U08, 2 mapping to U09 Ladakh: ``Kargil`` + ``Ladakh (leh)``). The
property naming is a 4TH unique convention (uppercase Census-2011
shape: ``STAT_NAME`` / ``DIST_NAME`` / ``VILL_CODE`` / ``VID`` / etc.).
See `docs/archive/notes/2026-05-30-c4-jk-villages-source-hunt-verdict.md` §"Recon
UPDATE 2026-05-30" for the full discovery + design rationale.

**Partitioning concession** (deliberate; documented for citizen
archaeology): shards are keyed by Census-2011 district NAME slug
(``district=anantnag``) rather than LGD district code (``district=620``)
because the Bhuvan file carries NO LGD codes — only Census-2011 names.
The post-2007 district bifurcations (Kulgam from Anantnag, Bandipore
from Baramula, Ramban + Kishtwar from Doda, Samba from Jammu, Shopian
from Pulwama, Ganderbal from Srinagar, Reasi from Udhampur) are
SILENTLY MERGED in the parent shard — a citizen looking for a
Kulgam-district village will find it under ``district=anantnag``.
Documented in shard sidecar notes; replaceable if LGD ever publishes
J&K with bifurcated district codes.

Why a dedicated single-source orchestrator (mirrors C.4 recon
recommendation):

* Single source, single state (well — single Census-2011 state that
  spans two modern UTs), single 7z. No state-LGD resolver needed; the
  ``STAT_NAME`` value is always ``"JK"`` per upstream.
* Property convention diverges from BOTH the LGD national lift
  (``state_lgd`` / ``dist_lgd`` / ``village_lgd`` / ``vlgname``) AND
  any other lift in the cohort — augmenting ``lift_villages_national.py``
  with conditional reads would balloon its complexity for zero gain
  outside this one file.
* Partition slug + name->modern-UT mapping is J&K-Bhuvan-specific
  logic that does NOT belong in any reusable helper.

Inputs:
    .runtime/raw/boundaries/snapshot/<bundle>/Bhuvan_JK_Villages.geojsonl.7z
        (fetched if missing; ~3 MB compressed / ~18 MB extracted /
        6,639 features at 2026-05-30 vintage)
    datasets/boundaries/boundary_layers.parquet
        (existing rows; merged via ``merge_with_existing=True``)

Outputs:
    datasets/boundaries/in/villages/state=jammu-and-kashmir/district=<slug>/all.geojson
        (12 shards: anantnag / badgam / baramula / doda / jammu / kathua
        / kupwara / pulwama / punch / rajauri / srinagar / udhampur)
    datasets/boundaries/in/villages/state=ladakh/district=<slug>/all.geojson
        (2 shards: kargil / ladakh_leh)
    datasets/boundaries/boundary_layers.parquet
        (+14 per-(state, district-slug) rows added; all other layers
        preserved via merge_with_existing=True)
    datasets/data/entities/source.csv
        (UPSERTed by compile_to_parquet; new
        ``ramseraph_bhuvan_jk_villages`` source row added)

Determinism: features per shard are sorted by ``(VID, NAME)``; coordinates
rounded to ``coord_precision=4`` (~11 m, matches the LGD national lift).
Two consecutive runs against the same upstream archive produce
byte-identical shards.

Pure stdlib + duckdb (via canonical writer) + py7zr (via
fetch_geojsonl_7z). No external HTTP libs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------
# import dance — see lift_villages_national.py for rationale.
# ---------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
BACKEND = REPO_ROOT / "backend"

if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from _paths import derive_hive  # noqa: E402
from snapshot import (  # noqa: E402
    SNAPSHOT_BYTE_BUDGET,
    _round_coords_geom,
    emit_feature_collection,
    fetch_geojsonl_7z,
)

from yen_gov.canonical.boundary_layers_seed import (  # noqa: E402
    BOUNDARY_SOURCE_ID_BY_NICKNAME,
    BoundaryLayerRow,
    compile_to_parquet,
)

# ---------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------

BHUVAN_JK_VILLAGES_URL = (
    "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/"
    "villages/Bhuvan_JK_Villages.geojsonl.7z"
)

# 4 decimal places ≈ 11 m at the equator; matches LGD villages lift.
COORD_PRECISION = 4

# Source nickname seeded in boundary_layers_seed.py.
SOURCE_NICKNAME = "ramseraph_bhuvan_jk_villages"

# Property names — Census-2011 uppercase convention (4th convention
# observed; see file docstring + C.3.b 3-convention-rule lesson).
DISTRICT_PROPERTY = "DIST_NAME"
ID_PROPERTY = "VID"
NAME_PROPERTY = "NAME"

# Census-2011 J&K district name -> (modern ECI state code, slug for
# partition segment). Slug is ASCII lowercase with non-[a-z0-9_] stripped
# to satisfy the layer_id regex pattern ([a-z0-9_]+).
#
# Mapping rationale:
# - J&K Reorganisation Act 2019 split J&K state into J&K UT (U08) +
#   Ladakh UT (U09). Census-2011 "Ladakh (leh)" + "Kargil" are the two
#   pre-split districts now under U09 Ladakh. All other 12 Census-2011
#   districts remain under U08 J&K UT.
# - Bifurcated districts (post-2007 splits of Anantnag/Baramula/Doda/
#   Jammu/Pulwama/Srinagar/Udhampur) are KEYED BY THEIR CENSUS-2011
#   PARENT — citizen archaeology note: a Kulgam-district village will
#   appear in the anantnag shard; a Kishtwar village in the doda shard;
#   etc. See file docstring for the full bifurcation list.
CENSUS2011_DISTRICT_TO_MODERN: dict[str, tuple[str, str]] = {
    # U08 J&K UT (12 Census-2011 districts; modern LGD lists 20 post-bifurcation):
    "Anantnag": ("U08", "anantnag"),  # Census-2011 parent of modern Anantnag + Kulgam
    "Badgam": ("U08", "badgam"),  # modern name: Budgam (rename only)
    "Baramula": ("U08", "baramula"),  # Census-2011 parent of modern Baramulla + Bandipore
    "Doda": ("U08", "doda"),  # Census-2011 parent of modern Doda + Ramban + Kishtwar
    "Jammu": ("U08", "jammu"),  # Census-2011 parent of modern Jammu + Samba
    "Kathua": ("U08", "kathua"),
    "Kupwara": ("U08", "kupwara"),
    "Pulwama": ("U08", "pulwama"),  # Census-2011 parent of modern Pulwama + Shopian
    "Punch": ("U08", "punch"),  # modern name: Poonch
    "Rajauri": ("U08", "rajauri"),  # modern name: Rajouri
    "Srinagar": ("U08", "srinagar"),  # Census-2011 parent of modern Srinagar + Ganderbal
    "Udhampur": ("U08", "udhampur"),  # Census-2011 parent of modern Udhampur + Reasi
    # U09 Ladakh UT (2 Census-2011 districts, both became modern Ladakh
    # UT districts unchanged in name):
    "Kargil": ("U09", "kargil"),
    "Ladakh (leh)": ("U09", "ladakh_leh"),  # modern name: Leh
}


# ---------------------------------------------------------------------
# pure logic — testable without I/O
# ---------------------------------------------------------------------


def group_features_by_district(
    features: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    """Group features by ``DIST_NAME`` value (Census-2011 district name).

    Returns ``(groups, unkeyed)`` where ``unkeyed`` holds features
    missing ``DIST_NAME`` or carrying a value not in the
    ``CENSUS2011_DISTRICT_TO_MODERN`` mapping (latter is treated as
    upstream-drift surprise — surface, don't drop silently).
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    unkeyed: list[dict[str, Any]] = []
    for f in features:
        props = f.get("properties", {})
        name = props.get(DISTRICT_PROPERTY)
        if not name or name not in CENSUS2011_DISTRICT_TO_MODERN:
            unkeyed.append(f)
            continue
        groups.setdefault(name, []).append(f)
    return groups, unkeyed


def sort_features_deterministically(
    features: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sort features by ``(VID, NAME)`` for byte-determinism.

    ``VID`` is a 16-character hierarchical Census-2011 id
    (``SID + DID + TID + VILL_CODE``) — globally unique by construction.
    ``NAME`` is the secondary fallback in the (unlikely) event two rows
    share a VID.
    """
    return sorted(
        features,
        key=lambda f: (
            f.get("properties", {}).get(ID_PROPERTY, "") or "",
            f.get("properties", {}).get(NAME_PROPERTY, "") or "",
        ),
    )


# ---------------------------------------------------------------------
# main orchestration
# ---------------------------------------------------------------------


def lift_jk_villages_to_per_district_shards(
    geojsonl_path: Path,
    datasets_root: Path,
    *,
    coord_precision: int = COORD_PRECISION,
) -> list[BoundaryLayerRow]:
    """Parse the J&K geojsonl, group by Census-2011 district, emit per shard.

    Returns one ``BoundaryLayerRow`` per emitted shard. Features whose
    ``DIST_NAME`` doesn't map to a known Census-2011 district are
    WARN-logged but do NOT emit a shard.
    """
    import json

    source_id = BOUNDARY_SOURCE_ID_BY_NICKNAME[SOURCE_NICKNAME]

    features: list[dict[str, Any]] = []
    with geojsonl_path.open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            feat = json.loads(line)
            if "geometry" in feat and feat["geometry"]:
                feat["geometry"] = _round_coords_geom(feat["geometry"], coord_precision)
            features.append(feat)

    print(f"  parsed {len(features):,} J&K village features", flush=True)

    groups, unkeyed = group_features_by_district(features)
    print(
        f"  grouped into {len(groups):,} Census-2011 districts "
        f"({len(unkeyed)} feature(s) unkeyed)",
        flush=True,
    )

    # free the parsed list — groups now owns every feature dict.
    del features

    if unkeyed:
        unknown_dists = sorted(
            {
                f.get("properties", {}).get(DISTRICT_PROPERTY, "<missing>")
                for f in unkeyed
            }
        )
        print(
            f"  WARNING: {len(unkeyed)} feature(s) with unmappable DIST_NAME "
            f"({unknown_dists}); skipped",
            flush=True,
        )

    rows: list[BoundaryLayerRow] = []
    simpl_tol = 10**-coord_precision

    # Emit shards in deterministic order: by modern (state, slug).
    sorted_districts = sorted(
        groups,
        key=lambda d: (CENSUS2011_DISTRICT_TO_MODERN[d][0], CENSUS2011_DISTRICT_TO_MODERN[d][1]),
    )
    for census_name in sorted_districts:
        eci_state, slug = CENSUS2011_DISTRICT_TO_MODERN[census_name]
        bucket = groups[census_name]
        partition_path, layer_id = derive_hive(
            kind="villages",
            state=eci_state,
            district_lgd=slug,  # NOTE: slug, not LGD numeric; see file docstring.
        )
        bucket_sorted = sort_features_deterministically(bucket)
        shard_path = datasets_root / partition_path
        emit_feature_collection(shard_path, bucket_sorted)
        size = shard_path.stat().st_size
        if size > SNAPSHOT_BYTE_BUDGET:
            shard_path.unlink()
            print(
                f"    {eci_state}/d={slug}: shard {size / 1024 / 1024:.1f} MB "
                f"exceeds {SNAPSHOT_BYTE_BUDGET / 1024 / 1024:.0f} MB budget — SKIP",
                flush=True,
            )
            continue
        retained = len(bucket_sorted)
        rows.append(
            BoundaryLayerRow(
                layer_id=layer_id,
                level="village",
                partition_path=partition_path,
                format="geojson",
                crs="EPSG:4326",
                original_feature_count=retained,
                retained_feature_count=retained,
                unkeyed_count=0,
                size_bytes=size,
                source_id=source_id,
                entity_state=eci_state,
                entity_district=slug,  # slug, not LGD numeric
                simplification_algorithm="coord-precision-round",
                simplification_tolerance_deg=simpl_tol,
            )
        )
        print(
            f"    {eci_state}/d={slug:>12} ({census_name}): "
            f"{retained:>5,} villages, {size / 1024:>7.1f} KB",
            flush=True,
        )

    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Lift Bhuvan_JK_Villages.geojsonl into per-(state, district-slug) "
            "Hive shards (J&K UT U08 + Ladakh UT U09; Census-2011 vintage)."
        ),
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repo root (default: cwd).",
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help=(
            "Skip the upstream fetch; require the geojsonl.7z to already be "
            "on disk under .runtime/raw/boundaries/snapshot/."
        ),
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    datasets_root = root / "datasets"
    raw_root = root / ".runtime" / "raw" / "boundaries"

    print(f"[lift_villages_jk_bhuvan] root={root}", flush=True)

    bundle_dir = raw_root / "snapshot" / "U08-villages-bhuvan"
    extracted_geojsonl = bundle_dir / "_extracted" / "Bhuvan_JK_Villages.geojsonl"

    if not extracted_geojsonl.exists() and args.skip_fetch:
        print(
            f"  ERROR: --skip-fetch but no geojsonl at {extracted_geojsonl}",
            file=sys.stderr,
            flush=True,
        )
        return 2

    if not extracted_geojsonl.exists():
        print(f"  fetching + extracting {BHUVAN_JK_VILLAGES_URL}", flush=True)
        _ = fetch_geojsonl_7z(
            [BHUVAN_JK_VILLAGES_URL],
            bundle_dir,
            coord_precision=None,  # round in lift loop, not here
        )

    rows = lift_jk_villages_to_per_district_shards(
        extracted_geojsonl,
        datasets_root,
    )

    layer_count, source_count = compile_to_parquet(
        rows,
        datasets_root,
        merge_with_existing=True,
    )
    print(
        f"  boundary_layers.parquet: {layer_count} rows total "
        f"({len(rows)} J&K village rows this lift) | "
        f"sources.parquet: {source_count} rows",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
