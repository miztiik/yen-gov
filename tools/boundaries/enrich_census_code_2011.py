"""Enrich datasets/boundaries/in/districts/all.{geojson,topojson} with `census_code_2011`.

PR-3 of TODO/20260611-elections-off-maplibre-and-map-ux-plan.md (Hans + Max
authority, user pre-approved 2026-06-11). Closes the citizen-facing gap where
Census-2011-keyed indicators (Census demographics, SECC-2011, NFHS-4) had to
carry their own LGD <-> Census-2011 crosswalk; after this lands, every
district feature carries an `census_code_2011` property at boundary-load time.

Pipeline (all stages are idempotent):

  1. Snapshot: download the Census 2011 district topology from
     https://data-analytics.github.io/Choropleth_India_Map/map.json (641
     features carrying `censuscode` + `st_cen_cd` + `st_nm` + `district`).
     Cached at `.runtime/raw/census/data-analytics-map.json` per ADR-0003.
  2. Normalise: lower-case + strip diacritics + strip punctuation +
     collapse whitespace for both LGD and Census feature names; map a small
     curated alias table for state-name spelling differences (Andaman &
     Nicobar vs Andaman and Nicobar Islands, Census's `Arunanchal` typo
     vs canonical `Arunachal`, the LGD post-2020 D&N-DD merger that
     covers two separate Census UTs, Ladakh post-2019 carve-out from J&K).
  3. Join + fallback chain per LGD district:
       a. Exact (state_norm, district_norm) hit in the Census 2011 map.
       b. Strip a trailing direction word (north/south/east/west/...)
          or parenthetical, retry.
       c. Fall back to the upstream LGD's own `dtcode11` field when it
          is a valid Census 2011 code (<= 640) AND the state matches.
       d. Set to None and emit an unmatched row to the coverage report.
  4. Emit:
       - `datasets/boundaries/in/districts/census_code_2011.json` (sidecar
         lookup: {dist_lgd -> code | null}).
       - `datasets/_ops/census-code-2011-coverage.json` (coverage report
         with embedded source provenance).
       - In-place rewrite of `datasets/boundaries/in/districts/all.geojson`
         adding `census_code_2011` to every feature's properties.
       - In-place rewrite of `datasets/boundaries/in/districts/all.topojson`
         adding `census_code_2011` to every geometry's properties.

CLI::

    python -m tools.boundaries.enrich_census_code_2011 \
        [--repo-root <path>] \
        [--snapshot-only] \
        [--no-fetch]

`--snapshot-only` stops after Stage 1 (refresh the cached Census topology).
`--no-fetch` skips Stage 1's HTTP request and uses the cached snapshot.

Self-contained per CLAUDE.md section 4 (`tools/` MUST NOT import from
`backend/`). Stdlib only.

Re-snapshotting `all.geojson` from upstream (via `tools/boundaries/snapshot.py`)
wipes the `census_code_2011` enrichment; re-run this tool to restore. The
sidecar JSON survives the snapshot rerun, so the merge is mechanical and free.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths (everything POSIX-relative on emit per CLAUDE.md section 2).
# ---------------------------------------------------------------------------

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
CENSUS_TOPOLOGY_URL = "https://data-analytics.github.io/Choropleth_India_Map/map.json"
RAW_CACHE_RELPATH = ".runtime/raw/census/data-analytics-map.json"
DISTRICTS_GEOJSON_RELPATH = "datasets/boundaries/in/districts/all.geojson"
DISTRICTS_TOPOJSON_RELPATH = "datasets/boundaries/in/districts/all.topojson"
SIDECAR_RELPATH = "datasets/boundaries/in/districts/census_code_2011.json"
COVERAGE_RELPATH = "datasets/_ops/census-code-2011-coverage.json"
SIDECAR_SCHEMA_REF = "./census-code-2011-sidecar.schema.json"
COVERAGE_SCHEMA_REF = "./census-code-2011-coverage.schema.json"

USER_AGENT = "yen-gov-boundaries-census-enrich/1.0"

# ---------------------------------------------------------------------------
# State-name normalisation. Both LGD (uppercase, ampersand variants) and
# the Census 2011 topology (mixed case, two spelling typos preserved
# verbatim) need to fold to a single canonical key for join-by-name.
# ---------------------------------------------------------------------------

# Map from a normalised-input variant to the canonical normalised state
# name. Keys are post-`norm_state_raw` strings (lower-case, ascii, single-
# space-collapsed); values are the canonical form used as the lookup
# half-key. Pure data; reviewers add new variants here without code edits.
STATE_ALIASES: dict[str, str] = {
    # LGD ships "ANDAMAN & NICOBAR"; Census ships "Andaman & Nicobar Island"
    # (note: NO trailing 's'). Both fold to plural canonical.
    "andaman & nicobar": "andaman and nicobar islands",
    "andaman & nicobar island": "andaman and nicobar islands",
    "andaman & nicobar islands": "andaman and nicobar islands",
    "a & n islands": "andaman and nicobar islands",
    # Census 2011 ships an upstream typo `Arunanchal` (extra N); LGD has
    # the canonical spelling `Arunachal`.
    "arunanchal pradesh": "arunachal pradesh",
    # LGD post-2020 merger of Dadra & Nagar Haveli + Daman & Diu into one
    # UT; Census 2011 still has them as two separate UTs. Use the per-
    # district expansion table below to try the LGD merged state against
    # both Census UT names.
    "dadara & nagar havelli": "dadra and nagar haveli",
    "dadar & nagar haveli": "dadra and nagar haveli",
    "dadra & nagar haveli": "dadra and nagar haveli",
    "daman & diu": "daman and diu",
    # Other historical aliases (pre-rename forms operators may still use).
    "pondicherry": "puducherry",
    "orissa": "odisha",
    "uttaranchal": "uttarakhand",
    "jammu & kashmir": "jammu and kashmir",
    "jammu&kashmir": "jammu and kashmir",
    "nct of delhi": "delhi",
    "national capital territory of delhi": "delhi",
    "delhi nct": "delhi",
}

# An LGD state name may, after normalisation, need to be searched under
# MULTIPLE Census state names. Two cases today: (i) the LGD post-2020 D&N-DD
# merger collapses two Census UTs into one; (ii) the LGD Ladakh UT (post-
# 2019 carve-out) contains districts that Census 2011 enumerated under J&K.
LGD_STATE_EXPANSIONS: dict[str, list[str]] = {
    "dadra,nagar haveli,daman & diu": [
        "dadra and nagar haveli",
        "daman and diu",
    ],
    "ladakh": [
        "ladakh",
        "jammu and kashmir",
    ],
}

# District-name suffix words to strip when the exact join misses.
# Conservative list: only directional words and a couple of common
# rural/urban splits; aggressive stripping risks false positives.
DISTRICT_SUFFIX_STRIPS: frozenset[str] = frozenset(
    {"north", "south", "east", "west", "central", "upper", "lower"}
)

# ---------------------------------------------------------------------------
# Pure helpers (no I/O; unit-testable).
# ---------------------------------------------------------------------------


def _strip_diacritics(s: str) -> str:
    return (
        unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    )


def norm_state_raw(s: str) -> str:
    """Lower + ascii + collapse whitespace; no alias lookup."""
    s = _strip_diacritics(s).lower().strip()
    return re.sub(r"\s+", " ", s)


def norm_state(s: str) -> str:
    """Lower + ascii + collapse whitespace + alias lookup."""
    n = norm_state_raw(s)
    return STATE_ALIASES.get(n, n)


def norm_district(s: str) -> str:
    """Lower + ascii + strip punct (.-/,'\\`()) + collapse whitespace."""
    s = _strip_diacritics(s).lower()
    s = re.sub(r"[.\-/,\'`()]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def root_district(s: str) -> str:
    """`norm_district`, then strip a parenthetical and a trailing direction word.

    Example: "North 24 Parganas" -> "24 parganas"; "Chennai (city)" -> "chennai".
    """
    s = re.sub(r"\s*\([^)]*\)\s*", " ", _strip_diacritics(s).lower()).strip()
    s = re.sub(r"[.\-/,\'`]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    parts = s.split()
    if len(parts) >= 2 and parts[-1] in DISTRICT_SUFFIX_STRIPS:
        parts = parts[:-1]
    return " ".join(parts)


def candidate_lgd_states(lgd_state_raw_value: str) -> list[str]:
    """Return the list of canonical Census state names to search for an LGD state.

    Most LGD states resolve to a single Census state; the LGD merged
    D&N-DD UT and the LGD Ladakh UT expand to two via `LGD_STATE_EXPANSIONS`.
    """
    n = norm_state(lgd_state_raw_value)
    return LGD_STATE_EXPANSIONS.get(norm_state_raw(lgd_state_raw_value), [n])


def utc_now_rfc3339() -> str:
    """RFC 3339 UTC timestamp; matches CLAUDE.md section 12 fetched_at convention."""
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------
# Stage 1 - snapshot.
# ---------------------------------------------------------------------------


def _download_to_cache(url: str, cache_path: Path) -> tuple[bytes, str, str]:
    """Stream URL to local cache and return (bytes, sha256, fetched_at).

    Atomic via .part rename so a partial fetch never masquerades as
    a complete artifact on retry.
    """
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_path.with_suffix(cache_path.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    # The data-analytics.github.io origin is a static GitHub Pages site
    # serving Census 2011 derivatives. CC0/MIT-comparable; bandit S310
    # is OK to ignore (pattern matches snapshot.py / build.py).
    with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
        body = r.read()
    tmp.write_bytes(body)
    tmp.replace(cache_path)
    return body, sha256_bytes(body), utc_now_rfc3339()


def snapshot_census_topology(
    repo_root: Path,
    *,
    fetch: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (parsed topology, source-provenance dict).

    When `fetch=False` and the cache is present, reads it back from disk
    and re-computes sha256 + reads fetched_at off the cache mtime. When
    `fetch=True` (default) always re-downloads.
    """
    cache_path = repo_root / RAW_CACHE_RELPATH
    if fetch:
        body, sha, fetched_at = _download_to_cache(CENSUS_TOPOLOGY_URL, cache_path)
        topology = json.loads(body)
    else:
        if not cache_path.is_file():
            msg = (
                f"--no-fetch: cache {cache_path} is absent. Run once without "
                "--no-fetch to populate it, then re-run with --no-fetch."
            )
            raise FileNotFoundError(msg)
        body = cache_path.read_bytes()
        topology = json.loads(body)
        sha = sha256_bytes(body)
        fetched_at = (
            dt.datetime.fromtimestamp(cache_path.stat().st_mtime, dt.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ")
        )
    objects = topology.get("objects") or {}
    if not objects:
        msg = f"Census topology has no top-level `objects`: {CENSUS_TOPOLOGY_URL}"
        raise ValueError(msg)
    first_object_name = next(iter(objects))
    geoms = objects[first_object_name].get("geometries") or []
    provenance = {
        "url": CENSUS_TOPOLOGY_URL,
        "fetched_at": fetched_at,
        "content_sha256": sha,
        "feature_count": len(geoms),
    }
    return topology, provenance


# ---------------------------------------------------------------------------
# Stage 2 - build Census 2011 lookup tables.
# ---------------------------------------------------------------------------


def build_census_lookups(
    topology: dict[str, Any],
) -> tuple[dict[tuple[str, str], int], dict[int, tuple[str, str]]]:
    """Return ({(state_norm, district_norm) -> censuscode}, {censuscode -> (state_norm, district_norm)}).

    The forward map is the primary join key; the inverse map is used by
    the dtcode11 fallback to verify state-name agreement.
    """
    objects = topology["objects"]
    first_object_name = next(iter(objects))
    geoms = objects[first_object_name]["geometries"]
    fwd: dict[tuple[str, str], int] = {}
    inv: dict[int, tuple[str, str]] = {}
    for geom in geoms:
        props = geom.get("properties") or {}
        censuscode = props.get("censuscode")
        st_nm = props.get("st_nm")
        district = props.get("district")
        if censuscode is None or st_nm is None or district is None:
            continue
        snorm = norm_state(str(st_nm))
        dnorm = norm_district(str(district))
        fwd[(snorm, dnorm)] = int(censuscode)
        inv[int(censuscode)] = (snorm, dnorm)
    return fwd, inv


# ---------------------------------------------------------------------------
# Stage 3 - join + fallback chain.
# ---------------------------------------------------------------------------


def _parse_dtcode11(value: Any) -> int | None:
    """Parse the upstream LGD `dtcode11` value into an int (None on failure).

    Upstream ships strings like '603' or '003'. Empty / non-numeric ->
    None (the fallback will skip this row).
    """
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def _classify_unmatched_reason(
    year_stat: str | None,
    dtcode11: int | None,
    state_raw: str,
    district_raw: str,
) -> str:
    """Categorise an unmatched LGD district for the coverage report."""
    snorm = norm_state(state_raw)
    if snorm == "jammu and kashmir" and (
        district_raw.lower() in {"mirpur", "muzaffarabad"}
        or (dtcode11 is not None and dtcode11 >= 990)
    ):
        return "out_of_country"
    if year_stat:
        post_2011_markers = (
            "update2014",
            "2012_c",
            "2014_c",
            "2015_c",
            "2016_c",
            "2017_c",
            "2018",
            "2019",
            "201920",
            "2020",
            "2022",
            "2023",
        )
        if year_stat in post_2011_markers:
            return "post_2011_bifurcation_no_parent_map"
    if dtcode11 is not None and dtcode11 <= 640:
        # 2011_c label but the dtcode11 belongs to a different state.
        return "name_disambiguation"
    return "no_match"


def join_lgd_to_census(
    lgd_features: list[dict[str, Any]],
    fwd: dict[tuple[str, str], int],
    inv: dict[int, tuple[str, str]],
) -> tuple[
    dict[str, int | None],
    dict[str, int],
    list[dict[str, Any]],
]:
    """Return (sidecar map, per-method counts, unmatched rows).

    sidecar map: {stringified-dist_lgd -> census_code | None}.
    per-method counts: {"exact": int, "root_strip": int, "dtcode11_fallback": int}.
    unmatched rows: shape matching `census-code-2011-coverage.schema.json` items.
    """
    sidecar: dict[str, int | None] = {}
    counts = {"exact": 0, "root_strip": 0, "dtcode11_fallback": 0}
    unmatched: list[dict[str, Any]] = []
    for feature in lgd_features:
        props = feature.get("properties") or {}
        dist_lgd = props.get("dist_lgd")
        if dist_lgd is None:
            continue
        key = str(int(dist_lgd))
        stname_raw = str(props.get("stname") or "")
        dtname_raw = str(props.get("dtname") or "")
        year_stat = props.get("year_stat")
        dtcode11 = _parse_dtcode11(props.get("dtcode11"))

        dnorm = norm_district(dtname_raw)
        droot = root_district(dtname_raw)
        candidates = candidate_lgd_states(stname_raw)

        matched_code: int | None = None
        matched_method: str | None = None
        for snorm in candidates:
            if (snorm, dnorm) in fwd:
                matched_code = fwd[(snorm, dnorm)]
                matched_method = "exact"
                break
        if matched_method is None:
            for snorm in candidates:
                if (snorm, droot) in fwd:
                    matched_code = fwd[(snorm, droot)]
                    matched_method = "root_strip"
                    break
        if matched_method is None and dtcode11 is not None and dtcode11 in inv:
            cen_state, _ = inv[dtcode11]
            if cen_state in candidates:
                matched_code = dtcode11
                matched_method = "dtcode11_fallback"

        if matched_method is not None and matched_code is not None:
            sidecar[key] = matched_code
            counts[matched_method] += 1
        else:
            sidecar[key] = None
            unmatched.append(
                {
                    "state": stname_raw,
                    "district": dtname_raw,
                    "dist_lgd": int(dist_lgd),
                    "year_stat": str(year_stat) if year_stat is not None else "",
                    "dtcode11": props.get("dtcode11"),
                    "reason": _classify_unmatched_reason(
                        year_stat, dtcode11, stname_raw, dtname_raw
                    ),
                }
            )
    return sidecar, counts, unmatched


# ---------------------------------------------------------------------------
# Stage 4 - emit.
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: Any) -> None:
    """Pretty-print JSON with trailing newline. Stable for git diffs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False)
    path.write_text(text + "\n", encoding="utf-8")


def write_sidecar(repo_root: Path, sidecar: dict[str, int | None]) -> Path:
    """Write the per-dist_lgd lookup map as a stable, sorted-key JSON envelope."""
    out_path = repo_root / SIDECAR_RELPATH
    # Sort numerically by LGD code so the file diffs cleanly when new LGD
    # rows arrive (LGD codes are dense but not strictly sequential).
    by_dist_lgd = {k: sidecar[k] for k in sorted(sidecar, key=int)}
    envelope = {
        "$schema": SIDECAR_SCHEMA_REF,
        "$schema_version": "1.0",
        "by_dist_lgd": by_dist_lgd,
    }
    _write_json(out_path, envelope)
    return out_path


def write_coverage_report(
    repo_root: Path,
    provenance: dict[str, Any],
    sidecar: dict[str, int | None],
    counts: dict[str, int],
    unmatched: list[dict[str, Any]],
    lgd_feature_count: int,
) -> Path:
    """Write the operator coverage report with embedded source provenance.

    Denominator is the LGD feature count (NOT the sidecar key count): the
    LGD source ships two POK features both keyed under `dist_lgd=0` which
    collapse to a single sidecar entry. Coverage is measured against the
    on-disk feature count for citizen-trust transparency.
    """
    out_path = repo_root / COVERAGE_RELPATH
    matched_count = lgd_feature_count - len(unmatched)
    total = lgd_feature_count
    envelope = {
        "$schema": COVERAGE_SCHEMA_REF,
        "$schema_version": "1.0",
        "source": provenance,
        "matched_count": matched_count,
        "total": total,
        "coverage_pct": round(100.0 * matched_count / total, 1) if total else 0.0,
        "matched_by_method": counts,
        "unmatched_districts": sorted(
            unmatched, key=lambda r: (r["state"], r["district"])
        ),
    }
    _write_json(out_path, envelope)
    return out_path


def _merge_into_geojson(
    geojson: dict[str, Any], sidecar: dict[str, int | None]
) -> int:
    """Add `census_code_2011` to every feature's properties (in-place).

    Returns the number of features touched (a sanity-check ratchet so a
    silent feature-count drift fails the operator's terminal output, not
    just the contract test).
    """
    features = geojson.get("features") or []
    touched = 0
    for feature in features:
        props = feature.setdefault("properties", {})
        dist_lgd = props.get("dist_lgd")
        if dist_lgd is None:
            # Feature with no join key gets explicit null so the schema
            # contract ("property is PRESENT") still holds.
            props["census_code_2011"] = None
        else:
            props["census_code_2011"] = sidecar.get(str(int(dist_lgd)))
        touched += 1
    return touched


def _merge_into_topojson(
    topology: dict[str, Any], sidecar: dict[str, int | None]
) -> int:
    """Add `census_code_2011` to every geometry's properties (in-place).

    TopoJSON properties live on each `geometry` within `objects[<name>].geometries`,
    NOT on a top-level features array.
    """
    objects = topology.get("objects") or {}
    if not objects:
        msg = "topology has no `objects`; refusing to merge"
        raise ValueError(msg)
    first_object_name = next(iter(objects))
    geoms = objects[first_object_name].get("geometries") or []
    touched = 0
    for geom in geoms:
        props = geom.setdefault("properties", {})
        dist_lgd = props.get("dist_lgd")
        if dist_lgd is None:
            props["census_code_2011"] = None
        else:
            props["census_code_2011"] = sidecar.get(str(int(dist_lgd)))
        touched += 1
    return touched


def enrich_geojson_and_topojson(
    repo_root: Path, sidecar: dict[str, int | None]
) -> tuple[int, int]:
    """Rewrite all.geojson + all.topojson in-place with the sidecar merge."""
    geo_path = repo_root / DISTRICTS_GEOJSON_RELPATH
    topo_path = repo_root / DISTRICTS_TOPOJSON_RELPATH
    geojson = json.loads(geo_path.read_text(encoding="utf-8"))
    topology = json.loads(topo_path.read_text(encoding="utf-8"))
    geo_touched = _merge_into_geojson(geojson, sidecar)
    topo_touched = _merge_into_topojson(topology, sidecar)
    # Match the existing geojson writer style (compact, single-line, no
    # trailing newline before the last `}` per existing all.geojson on
    # disk; ensure trailing `\n` consistent with snapshot.py).
    with geo_path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(geojson, fh, ensure_ascii=False)
        fh.write("\n")
    with topo_path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(topology, fh, ensure_ascii=False)
        fh.write("\n")
    return geo_touched, topo_touched


# ---------------------------------------------------------------------------
# Orchestration.
# ---------------------------------------------------------------------------


def run(
    repo_root: Path,
    *,
    snapshot_only: bool = False,
    fetch: bool = True,
) -> dict[str, Any]:
    """End-to-end pipeline. Returns a summary dict (printed to stdout)."""
    topology, provenance = snapshot_census_topology(repo_root, fetch=fetch)
    if snapshot_only:
        return {
            "stage": "snapshot_only",
            "source": provenance,
            "cache_path": str(Path(RAW_CACHE_RELPATH).as_posix()),
        }

    fwd, inv = build_census_lookups(topology)
    geo_path = repo_root / DISTRICTS_GEOJSON_RELPATH
    if not geo_path.is_file():
        msg = f"LGD districts geojson absent: {geo_path}"
        raise FileNotFoundError(msg)
    lgd_geojson = json.loads(geo_path.read_text(encoding="utf-8"))
    lgd_features = lgd_geojson.get("features") or []
    if not lgd_features:
        msg = f"LGD districts geojson has no features: {geo_path}"
        raise ValueError(msg)

    sidecar, counts, unmatched = join_lgd_to_census(lgd_features, fwd, inv)

    write_sidecar(repo_root, sidecar)
    write_coverage_report(
        repo_root, provenance, sidecar, counts, unmatched, len(lgd_features)
    )
    geo_touched, topo_touched = enrich_geojson_and_topojson(repo_root, sidecar)

    matched = len(lgd_features) - len(unmatched)
    return {
        "stage": "complete",
        "source": provenance,
        "lgd_feature_count": len(lgd_features),
        "matched": matched,
        "unmatched": len(unmatched),
        "coverage_pct": round(100.0 * matched / len(lgd_features), 1),
        "matched_by_method": counts,
        "geojson_features_touched": geo_touched,
        "topojson_geometries_touched": topo_touched,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m tools.boundaries.enrich_census_code_2011",
        description=__doc__.splitlines()[0] if __doc__ else "",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=DEFAULT_REPO_ROOT,
        help="Repo root (defaults to the worktree containing this script).",
    )
    parser.add_argument(
        "--snapshot-only",
        action="store_true",
        help="Refresh the Census 2011 topology cache and stop.",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip the Stage-1 HTTP request and use the cached snapshot.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    summary = run(
        repo_root,
        snapshot_only=args.snapshot_only,
        fetch=not args.no_fetch,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
