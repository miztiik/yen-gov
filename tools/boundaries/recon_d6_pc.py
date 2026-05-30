"""Phase D.6 recon: ramSeraph LGD_Parliament_Constituencies vs current
shijithpk PC layer (gating script for the polygon swap).

One-shot, read-only inspection. Fetches the upstream ramSeraph PC
release into the ephemeral ``.runtime/raw/ramseraph/constituencies/``
scratch directory (per CLAUDE.md section 2 — never referenced from
anything committed), enumerates the feature property schema, counts
features, and answers the four D.6 recon-gate questions:

    1. Total feature count = 545 (+/- 1)?
    2. Vintage = 2024 delim? (J&K should have 5 PCs, Telangana ~17,
       Ladakh 1 (post-2019 carve-out from J&K).)
    3. Is ``lgd_pc_code`` present? (CLAUDE.md identifier discipline.)
    4. Any pre-delimitation contamination? (status field check.)

Output of one run is the substance of
docs/archive/notes/2026-05-25-d6-pc-recon.md (quote findings; do not link the raw
file path).

This script does NOT promote anything to the canonical store. It exists
solely to answer the D.6 GO/NO-GO question (per
TODO/20260524-boundary-coverage-expansion-plan.md section D.6). After
D.6 ships, this script becomes dead weight and can be removed.

Dependencies
============

stdlib + ``py7zr`` (same dep as ``snapshot.py``'s geojsonl_7z handler).

Re-running
==========

    python tools/boundaries/recon_d6_pc.py

Re-fetches the archive (idempotent — overwrites the cached file in
place; ``.runtime/raw/`` is ephemeral by convention).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

LGD_PC_URL = (
    "https://github.com/ramSeraph/indian_admin_boundaries/releases/"
    "download/constituencies/LGD_Parliament_Constituencies.geojsonl.7z"
)
USER_AGENT = "yen-gov-boundaries-recon/1.0"
EXPECTED_TOTAL_PC = 543  # constitutional baseline (no nominated Anglo-Indians since 2019)
TOLERANCE = 2  # +/- 2 to absorb upstream cleanup noise


def fetch_archive(url: str, dest: Path) -> tuple[int, str]:
    """Download `url` to `dest` atomically. Returns (bytes, sha256_hex)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    h = hashlib.sha256()
    n = 0
    with urllib.request.urlopen(req) as r, tmp.open("wb") as fh:  # noqa: S310
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
            h.update(chunk)
            n += len(chunk)
    tmp.replace(dest)
    return n, h.hexdigest()


def extract_geojsonl(archive_path: Path, extract_dir: Path) -> Path:
    """7z-extract `archive_path` into `extract_dir`; return the .geojsonl path."""
    try:
        import py7zr  # type: ignore[import-not-found]
    except ImportError as e:
        msg = "py7zr is required (`pip install py7zr`)"
        raise RuntimeError(msg) from e
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(archive_path, mode="r") as zf:
        zf.extractall(path=extract_dir)
    candidates = sorted(extract_dir.rglob("*.geojsonl"))
    if not candidates:
        msg = f"no .geojsonl member in archive {archive_path.name}"
        raise ValueError(msg)
    if len(candidates) > 1:
        msg = (
            f"ambiguous archive {archive_path.name}: expected 1 .geojsonl "
            f"member, found {len(candidates)}: {[c.name for c in candidates]}"
        )
        raise ValueError(msg)
    return candidates[0]


def parse_features(path: Path) -> list[dict[str, Any]]:
    """Parse newline-delimited GeoJSON; strip geometry to save RAM."""
    features: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            feat = json.loads(line)
            feat.pop("geometry", None)
            features.append(feat)
    return features


def discover_schema(features: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate property keys + sample values across all features."""
    schema: dict[str, dict[str, Any]] = {}
    n = len(features)
    for feat in features:
        props = feat.get("properties") or {}
        for k, v in props.items():
            entry = schema.setdefault(
                k, {"present": 0, "samples": [], "types": set()}
            )
            entry["present"] += 1
            entry["types"].add(type(v).__name__)
            if (
                v is not None
                and len(entry["samples"]) < 3
                and v not in entry["samples"]
            ):
                entry["samples"].append(v)
    for v in schema.values():
        v["coverage"] = round(v["present"] / max(n, 1), 4)
        v["types"] = sorted(v["types"])
    return schema


def find_state_grouping_key(features: list[dict[str, Any]]) -> str | None:
    """Detect which property keys parent-state PCs.

    ramSeraph LGD shards use ``state_lgd`` in some layers and ``State_LGD``
    in others; AC layer used ``state_lgd``. Returns the first matching key.
    """
    if not features:
        return None
    props = features[0].get("properties") or {}
    for cand in ("state_lgd", "State_LGD", "STATE_LGD", "state_code", "state_id"):
        if cand in props:
            return cand
    return None


def group_by_state(
    features: list[dict[str, Any]], key: str
) -> Counter[Any]:
    """Group by state property; return counter of state -> PC count."""
    counter: Counter[Any] = Counter()
    for feat in features:
        props = feat.get("properties") or {}
        counter[props.get(key)] += 1
    return counter


def find_status_property(schema: dict[str, dict[str, Any]]) -> str | None:
    """Look for a delimitation/status property indicating pre-delim contam."""
    for k in schema:
        kl = k.lower()
        if "status" in kl or "delim" in kl or "vintage" in kl:
            return k
    return None


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    raw_dir = repo_root / ".runtime" / "raw" / "ramseraph" / "constituencies"
    archive_path = raw_dir / "LGD_Parliament_Constituencies.geojsonl.7z"
    extract_dir = raw_dir / "_extracted_pc"

    print(f"[D.6 recon] fetching {LGD_PC_URL}")
    n_bytes, sha = fetch_archive(LGD_PC_URL, archive_path)
    print(f"[D.6 recon]   bytes={n_bytes} sha256={sha[:16]}...")

    print(f"[D.6 recon] extracting to {extract_dir.relative_to(repo_root)}")
    payload = extract_geojsonl(archive_path, extract_dir)
    print(f"[D.6 recon]   payload={payload.name} ({payload.stat().st_size} bytes)")

    print("[D.6 recon] parsing features")
    features = parse_features(payload)
    n = len(features)
    print(f"[D.6 recon]   feature_count={n}")

    print("[D.6 recon] inferring property schema")
    schema = discover_schema(features)

    print()
    print("=" * 72)
    print("PROPERTY SCHEMA (full enumeration)")
    print("=" * 72)
    for k in sorted(schema):
        e = schema[k]
        print(
            f"  {k!r}: types={e['types']} coverage={e['coverage']:.2%} "
            f"samples={e['samples']!r}"
        )

    print()
    print("=" * 72)
    print("FIRST 5 FEATURES (full property dump)")
    print("=" * 72)
    for i, feat in enumerate(features[:5]):
        print(f"\n--- feature[{i}] ---")
        for k, v in (feat.get("properties") or {}).items():
            print(f"  {k!r}: {v!r}")

    print()
    print("=" * 72)
    print("GATE 1: total feature count")
    print("=" * 72)
    delta = n - EXPECTED_TOTAL_PC
    if abs(delta) <= TOLERANCE:
        print(
            f"  GO: count={n} within tolerance "
            f"({EXPECTED_TOTAL_PC} +/- {TOLERANCE})"
        )
    else:
        print(
            f"  NO-GO: count={n} outside tolerance "
            f"({EXPECTED_TOTAL_PC} +/- {TOLERANCE}; delta={delta:+d})"
        )

    print()
    print("=" * 72)
    print("GATE 2: per-state grouping (sample for vintage check)")
    print("=" * 72)
    grouping_key = find_state_grouping_key(features)
    if grouping_key is None:
        print("  WARN: no state-grouping property found")
    else:
        print(f"  grouping_key={grouping_key!r}")
        groups = group_by_state(features, grouping_key)
        print(f"  distinct states/UTs={len(groups)}")
        print("  per-state PC counts (sorted by state key asc):")
        for k in sorted(groups, key=lambda x: (x is None, str(x))):
            print(f"    {k!r}: {groups[k]}")

    print()
    print("=" * 72)
    print("GATE 3: lgd_pc_code presence")
    print("=" * 72)
    pc_id_candidates = [
        k for k in schema if "pc" in k.lower() and ("code" in k.lower() or "id" in k.lower() or "no" in k.lower())
    ]
    print(f"  PC-id candidate keys: {pc_id_candidates}")
    for k in pc_id_candidates:
        e = schema[k]
        print(
            f"  {k!r}: types={e['types']} coverage={e['coverage']:.2%} "
            f"samples={e['samples']!r}"
        )

    print()
    print("=" * 72)
    print("GATE 4: pre-delim contamination check")
    print("=" * 72)
    status_key = find_status_property(schema)
    if status_key is None:
        print("  no status/delim/vintage property found in schema")
    else:
        values: Counter[Any] = Counter()
        for feat in features:
            values[(feat.get("properties") or {}).get(status_key)] += 1
        print(f"  status_key={status_key!r}; value distribution:")
        for k in sorted(values, key=lambda x: (x is None, str(x))):
            print(f"    {k!r}: {values[k]}")

    print()
    print("[D.6 recon] complete; substance feeds docs/archive/notes/2026-05-25-d6-pc-recon.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
