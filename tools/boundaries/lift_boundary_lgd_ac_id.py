"""Stamp ``lgd_ac_id`` onto AC boundary features from the crosswalk (Row B1).

ADR-0049: ``lgd_ac_id`` is the canonical INTERNAL AC join key. The Row A2
crosswalk (``datasets/taxonomy/ac_crosswalk.parquet``) is the single source
of truth for the ``eci_no <-> lgd_ac_id`` binding. This module copies the
raw upstream ``AC_ID`` onto a stable ``lgd_ac_id`` feature property, GATED by
crosswalk membership: only features whose ``AC_ID`` is a covered
``lgd_ac_id`` in the crosswalk receive the property. Boundary ``lgd_ac_id``
is therefore always a SUBSET of the crosswalk-covered set (the B1 contract).

Features without ``AC_ID`` (S03 Assam district-fallback, U08 J&K ``seat_id``)
and cross-state spillover features whose ``AC_ID`` falls outside the covered
set are left untouched. The existing ``ac_no`` property is kept; ``lgd_ac_id``
is additive and parallel. The operation is idempotent (S01, which already
carries ``lgd_ac_id`` from the ac_no-rewrite path, re-confirms the same
value).

Pure ``tools/`` module: duckdb + stdlib only, no ``backend`` import
(CLAUDE.md s4). Serialisation matches ``snapshot.py``
(``json.dump(..., ensure_ascii=False)``, default separators, no trailing
newline) so re-running over an already-stamped tree is a byte-stable no-op.
``snapshot.py`` calls :func:`lift_all` at end-of-run so every future snapshot
re-applies the property.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb


def load_covered_lgd_ac_ids(datasets_root: Path) -> set[int]:
    """Return the set of covered ``lgd_ac_id`` values from the crosswalk.

    Empty when the crosswalk parquet is absent.
    """
    cx_path = datasets_root / "taxonomy" / "ac_crosswalk.parquet"
    if not cx_path.is_file():
        return set()
    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            "SELECT DISTINCT lgd_ac_id FROM read_parquet(?) "
            "WHERE lgd_ac_id IS NOT NULL",
            [cx_path.as_posix()],
        ).fetchall()
    finally:
        con.close()
    return {int(r[0]) for r in rows}


def _stamp_features(features: list[dict], covered: set[int]) -> int:
    """Set ``lgd_ac_id`` on every feature whose ``AC_ID`` is covered.

    Returns the number of features stamped.
    """
    stamped = 0
    for feat in features:
        props = feat.get("properties")
        if not isinstance(props, dict):
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
    return stamped


def lift_all(
    datasets_root: Path, *, dry_run: bool = False
) -> dict[str, tuple[int, int]]:
    """Stamp ``lgd_ac_id`` on every AC state shard under ``boundaries/in/ac``.

    Returns ``{state_partition: (total_features, stamped_features)}``.
    """
    covered = load_covered_lgd_ac_ids(datasets_root)
    ac_root = datasets_root / "boundaries" / "in" / "ac"
    report: dict[str, tuple[int, int]] = {}
    if not ac_root.is_dir() or not covered:
        return report

    for state_dir in sorted(ac_root.glob("state=in_*")):
        shard = state_dir / "all.geojson"
        if not shard.is_file():
            continue
        data = json.loads(shard.read_text(encoding="utf-8"))
        features = data.get("features") or []
        stamped = _stamp_features(features, covered)
        report[state_dir.name] = (len(features), stamped)
        if stamped and not dry_run:
            with shard.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)
    return report


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description="Stamp lgd_ac_id onto AC boundary features (Row B1)"
    )
    ap.add_argument("--datasets-root", default="datasets")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    report = lift_all(Path(args.datasets_root), dry_run=args.dry_run)
    total_stamped = sum(s for _, s in report.values())
    covered_states = sum(1 for _, s in report.values() if s)
    print(
        f"lgd_ac_id stamped: {total_stamped} features across "
        f"{covered_states}/{len(report)} AC shards"
        + (" (dry-run)" if args.dry_run else "")
    )
    for name, (total, stamped) in sorted(report.items()):
        if stamped:
            print(f"  {name}: {stamped}/{total}")


__all__ = ["load_covered_lgd_ac_ids", "lift_all"]


if __name__ == "__main__":
    main()
