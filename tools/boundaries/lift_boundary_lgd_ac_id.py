"""Stamp ``lgd_ac_id`` onto the consolidated AC boundary TopoJSON from the crosswalk.

ADR-0049: ``lgd_ac_id`` is the canonical INTERNAL AC join key. The canonical
AC crosswalk (``datasets/data/entities/ac_crosswalk.csv``) is the single
source of truth for the ``eci_no <-> lgd_ac_id`` binding. This module copies
the raw upstream ``AC_ID`` onto a stable ``lgd_ac_id`` feature property, GATED
by crosswalk membership: only features whose ``AC_ID`` is a covered
``lgd_ac_id`` in the crosswalk receive the property. Boundary ``lgd_ac_id`` is
therefore always a SUBSET of the crosswalk-covered set.

After the 2026-06-16 map-geometry rip (TODO/20260603-data-and-charting-platform-reset-plan.md
Row 3) the AC geometry is ONE national, derived TopoJSON
``datasets/boundaries/electoral/delim=2024/ac/all.topojson`` (object ``ac``),
not the 31 per-state ``delim=2008`` GeoJSON shards this tool used to walk
(those shards were deleted in that rip, and the retired
``datasets/taxonomy/ac_crosswalk.parquet`` it used to read is gone too). The
frontend AC choropleth (``StateAcMapD3.svelte``) joins each polygon to its
winner via this ``lgd_ac_id`` property (``featureEci`` -> ``recoverEciNo`` ->
the per-state crosswalk), so an unstamped feature greys. Stamping every
covered feature here is what colours the assembly choropleth on every state.

Features without ``AC_ID`` (U08 J&K ``seat_id``, S03 Assam district-fallback)
and cross-state spillover slivers whose ``AC_ID`` falls outside the covered
set are left untouched; they ride their own join property directly. The
existing ``ac_no`` property is kept; ``lgd_ac_id`` is additive and parallel.
The operation is idempotent: a feature that already carries a non-null
``lgd_ac_id`` (the AP / TG features stamped via the ac_no-rewrite path) is
skipped, so re-running over an already-stamped tree is a byte-stable no-op.

TopoJSON PROPERTIES are not quantized (only the shared ``arcs`` coordinates
are), so editing properties in place is lossless and needs no mapshaper
re-encode. Serialisation matches the mapshaper output byte-for-byte
(``json.dumps(..., ensure_ascii=False, separators=(",", ":"))``, no trailing
newline) so the diff is exactly the added properties.

Pure ``tools/`` module: duckdb + stdlib only, no ``backend`` import
(CLAUDE.md s4). ``snapshot.py`` calls :func:`stamp_consolidated_topojson` at
end-of-run so every future snapshot re-applies the property.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

# Both relative to the ``datasets/`` root passed in as ``datasets_root``.
AC_CROSSWALK_CSV = Path("data") / "entities" / "ac_crosswalk.csv"
AC_TOPOJSON = Path("boundaries") / "electoral" / "delim=2024" / "ac" / "all.topojson"
AC_TOPOJSON_OBJECT = "ac"


def load_covered_lgd_ac_ids(datasets_root: Path) -> set[int]:
    """Return the set of covered ``lgd_ac_id`` values from the canonical crosswalk.

    Reads ``datasets/data/entities/ac_crosswalk.csv`` (the X1a-followup CSV that
    replaced the retired ``taxonomy/ac_crosswalk.parquet``). Empty when the
    crosswalk file is absent.
    """
    cx_path = datasets_root / AC_CROSSWALK_CSV
    if not cx_path.is_file():
        return set()
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            "SELECT DISTINCT lgd_ac_id FROM read_csv(?) WHERE lgd_ac_id IS NOT NULL",
            [cx_path.as_posix()],
        ).fetchall()
    finally:
        con.close()
    return {int(r[0]) for r in rows}


def _stamp_geometries(geometries: list[dict], covered: set[int]) -> tuple[int, int]:
    """Set ``lgd_ac_id`` on every covered, not-yet-stamped TopoJSON geometry.

    Returns ``(newly_stamped, already_stamped)``. A geometry already carrying a
    non-null ``lgd_ac_id`` is skipped (idempotent); one with no parseable
    ``AC_ID`` or an ``AC_ID`` outside ``covered`` is left untouched.
    """
    stamped = 0
    already = 0
    for feat in geometries:
        props = feat.get("properties")
        if not isinstance(props, dict):
            continue
        if props.get("lgd_ac_id") is not None:
            already += 1
            continue
        ac_id = props.get("AC_ID")
        if ac_id is None:
            continue
        try:
            ac_id_int = int(ac_id)
        except (TypeError, ValueError):
            continue
        if ac_id_int in covered:
            props["lgd_ac_id"] = ac_id_int
            stamped += 1
    return stamped, already


def stamp_consolidated_topojson(
    datasets_root: Path, *, dry_run: bool = False
) -> dict[str, int]:
    """Stamp ``lgd_ac_id`` onto the consolidated AC TopoJSON in place.

    Returns ``{"total", "stamped", "already", "covered"}`` where ``stamped`` is
    the count of features newly given a ``lgd_ac_id`` this run. No write happens
    when nothing was newly stamped (idempotent re-run) or under ``dry_run``.
    """
    covered = load_covered_lgd_ac_ids(datasets_root)
    topo_path = datasets_root / AC_TOPOJSON
    if not topo_path.is_file() or not covered:
        return {"total": 0, "stamped": 0, "already": 0, "covered": len(covered)}

    topo = json.loads(topo_path.read_bytes())
    obj = (topo.get("objects") or {}).get(AC_TOPOJSON_OBJECT) or {}
    geometries = obj.get("geometries") or []
    stamped, already = _stamp_geometries(geometries, covered)
    if stamped and not dry_run:
        # Byte-for-byte match the mapshaper output (compact separators, no
        # trailing newline) so the diff is exactly the added properties.
        topo_path.write_bytes(
            json.dumps(topo, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        )
    return {
        "total": len(geometries),
        "stamped": stamped,
        "already": already,
        "covered": len(covered),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description="Stamp lgd_ac_id onto the consolidated AC TopoJSON (ADR-0049)"
    )
    ap.add_argument("--datasets-root", default="datasets")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    report = stamp_consolidated_topojson(Path(args.datasets_root), dry_run=args.dry_run)
    print(
        f"lgd_ac_id stamped: {report['stamped']} features newly stamped on the "
        f"consolidated AC topojson ({report['total']} total, "
        f"{report['already']} pre-stamped, {report['covered']} crosswalk-covered)"
        + (" (dry-run)" if args.dry_run else "")
    )


__all__ = ["load_covered_lgd_ac_ids", "stamp_consolidated_topojson"]


if __name__ == "__main__":
    main()
