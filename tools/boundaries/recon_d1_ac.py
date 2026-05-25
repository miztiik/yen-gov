"""Phase D.1 recon: ramSeraph LGD_Assembly_Constituencies parity audit.

One-shot, read-only inspection script. Fetches the upstream LGD AC
release into the ephemeral ``.runtime/raw/ramseraph/constituencies/``
scratch directory (per CLAUDE.md §2 — never referenced from anything
committed), enumerates the feature property schema, groups features by
their state_lgd parent, and reports per-state parity against the
source-of-truth ``datasets/reference/in/states/{S,U}{nn}/constituencies.json``
files.

This script does NOT promote anything to the canonical store. It exists
solely to answer the D.1 gating question (per
TODO/20260524-boundary-coverage-expansion-plan.md §D.1):

    "For state S{nn}, does ramSeraph LGD AC count + names match the
    source-of-truth constituencies.json?"

Output of one run is the substance of notes/2026-05-25-d1-ac-consolidation-recon.md
(quote findings; do not link the raw file path).

Tooling lineage
===============

The plan-doc references ``snapshot.py --source constituencies --kind ac``
as the fetch path. snapshot.py today is purpose-built to fetch AND
emit a canonical shard + parquet ledger row — that is the D.2+ promote
path, not the D.1 recon path. This script keeps recon separate from
ingest so the parquet ledger never carries a recon-only row.

After D.5 (AC consolidation wrap-up) ships, this script becomes dead
weight and should be deleted in the same PR.

Dependencies
============

stdlib + ``py7zr`` (same dep as ``snapshot.py``'s geojsonl_7z handler;
already in the project's pyproject because Phase B/C use it).

Re-running
==========

    python tools/boundaries/recon_d1_ac.py

Re-fetches the archive (idempotent — if already cached at the same
URL, the file is overwritten in place; the underlying
``.runtime/raw/ramseraph/constituencies/`` is ephemeral by convention).

The script is deterministic given the same upstream byte-snapshot:
same state ordering (ECI code asc), same name-match counts, same
verdicts. The upstream LGD release is a rolling vintage so cross-run
deltas reflect upstream churn, not nondeterminism here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import unicodedata
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# CLAUDE.md §4: tools/ MUST NOT import backend/ runtime modules. The
# state_lgd -> ECI map is 36 dict entries; we inline the same logic
# as backend.yen_gov.canonical.state_lgd_resolver.build_state_lgd_to_eci_map
# (PR #257 / #259) — identical filter (entity_type in {state, ut} AND
# entity_valid_to is None) so a historic composite J&K (S09, 1947-2019)
# is excluded and state_lgd=1 correctly maps to U08 (J&K UT post-2019).
# This mirrors the inline pattern PR #267 introduced for the district
# backfill (tools/lgd/backfill_entities_districts.py).

LGD_AC_URL = (
    "https://github.com/ramSeraph/indian_admin_boundaries/releases/"
    "download/constituencies/LGD_Assembly_Constituencies.geojsonl.7z"
)
USER_AGENT = "yen-gov-boundaries-recon/1.0"
NAME_MATCH_THRESHOLD = 0.95  # 95% name-match floor for "eligible-D.2" verdict


# ---------------------------------------------------------------------------
# Inlined helpers (CLAUDE.md §4 conformance)
# ---------------------------------------------------------------------------


def build_state_lgd_to_eci_map(entities: list[dict[str, Any]]) -> dict[int, str]:
    """Inline mirror of backend.yen_gov.canonical.state_lgd_resolver."""
    mapping: dict[int, str] = {}
    for row in entities:
        if row.get("entity_type") not in {"state", "ut"}:
            continue
        if row.get("entity_valid_to") is not None:
            continue
        lgd_str = row.get("lgd_code")
        if lgd_str is None:
            continue
        lgd_int = int(lgd_str)
        eci = row["entity_code"]
        if lgd_int in mapping and mapping[lgd_int] != eci:
            raise ValueError(
                f"duplicate state_lgd {lgd_int}: {mapping[lgd_int]!r} vs {eci!r}"
            )
        mapping[lgd_int] = eci
    return mapping


_RESERVATION_SUFFIXES = (" (sc)", " (st)", " (gen)")


def normalize_name(name: str) -> str:
    """Fold case + diacritics + punctuation/whitespace for AC-name comparison.

    The SoT files come from Wikipedia / ECI-PDF transcription; the LGD
    BharatMaps source uses LGD-internal names (UPPERCASE, mixed
    transliteration, AND a trailing reservation suffix like ' (SC)' or
    ' (ST)'). SoT stores reservation in a separate ``reservation``
    field; LGD inlines it into ``ac_name``. We strip the suffix so the
    name comparison is apples-to-apples (a separate reservation-parity
    pass would compare ``reservation`` fields if needed; the recon
    here is purely name+count parity).

    95% threshold downstream allows small Latin/diacritic noise; this
    normaliser does the heavy lifting (suffix strip + diacritic strip +
    case-fold + collapse non-alphanumerics).
    """
    if not isinstance(name, str):
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.casefold().strip()
    for suffix in _RESERVATION_SUFFIXES:
        if s.endswith(suffix):
            s = s[: -len(suffix)].rstrip()
            break
    out = []
    prev_space = False
    for ch in s:
        if ch.isalnum():
            out.append(ch)
            prev_space = False
        elif not prev_space:
            out.append(" ")
            prev_space = True
    return "".join(out).strip()


# ---------------------------------------------------------------------------
# Fetch + extract
# ---------------------------------------------------------------------------


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
        msg = (
            "py7zr is required (`pip install py7zr`); same dependency as "
            "tools/boundaries/snapshot.py's geojsonl_7z handler"
        )
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
            # Drop geometry: recon only inspects properties.
            feat.pop("geometry", None)
            features.append(feat)
    return features


# ---------------------------------------------------------------------------
# SoT loader
# ---------------------------------------------------------------------------


def load_sot(repo_root: Path) -> dict[str, dict[int, str]]:
    """Load every datasets/reference/in/states/<eci>/constituencies.json.

    Returns ``{ECI_code: {eci_no_int: ac_name}}`` for every state/UT
    that ships a constituencies sidecar.
    """
    sot: dict[str, dict[int, str]] = {}
    base = repo_root / "datasets" / "reference" / "in" / "states"
    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        eci = d.name
        path = d / "constituencies.json"
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as fh:
            doc = json.load(fh)
        if doc.get("body") != "AC":
            continue
        by_no: dict[int, str] = {}
        for c in doc.get("constituencies", []):
            no = c.get("eci_no")
            name = c.get("name")
            if isinstance(no, int) and isinstance(name, str):
                by_no[no] = name
        sot[eci] = by_no
    return sot


# ---------------------------------------------------------------------------
# Inventory + parity
# ---------------------------------------------------------------------------


def discover_schema(features: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Aggregate property keys + sample values across all features."""
    schema: dict[str, dict[str, Any]] = {}
    n = len(features)
    for feat in features:
        props = feat.get("properties") or {}
        for k, v in props.items():
            entry = schema.setdefault(k, {"present": 0, "samples": [], "types": set()})
            entry["present"] += 1
            entry["types"].add(type(v).__name__)
            if v is not None and len(entry["samples"]) < 3 and v not in entry["samples"]:
                entry["samples"].append(v)
    for k, v in schema.items():
        v["coverage"] = round(v["present"] / max(n, 1), 4)
        v["types"] = sorted(v["types"])
    return schema


def per_state_parity(
    features: list[dict[str, Any]],
    state_lgd_to_eci: dict[int, str],
    state_lgd_prop: str,
    ac_no_prop: str,
    name_prop: str,
    sot: dict[str, dict[int, str]],
) -> tuple[dict[str, dict[str, Any]], dict[int, int]]:
    """Group by state_lgd, compute per-state parity vs SoT.

    Returns ``(per_eci_report, unmapped_lgd_counts)``.
    """
    by_lgd: dict[int, list[dict[str, Any]]] = defaultdict(list)
    unmapped: Counter[int] = Counter()
    for feat in features:
        props = feat.get("properties") or {}
        slgd = props.get(state_lgd_prop)
        try:
            slgd_int = int(slgd)
        except (TypeError, ValueError):
            unmapped[-1] += 1
            continue
        if slgd_int not in state_lgd_to_eci:
            unmapped[slgd_int] += 1
            continue
        by_lgd[slgd_int].append(feat)

    report: dict[str, dict[str, Any]] = {}
    for slgd_int, feats in sorted(by_lgd.items()):
        eci = state_lgd_to_eci[slgd_int]
        lgd_pairs: dict[int, str] = {}
        lgd_no_missing = 0
        for f in feats:
            props = f.get("properties") or {}
            no = props.get(ac_no_prop)
            name = props.get(name_prop)
            try:
                no_int = int(no)
            except (TypeError, ValueError):
                lgd_no_missing += 1
                continue
            if isinstance(name, str):
                lgd_pairs[no_int] = name
        sot_pairs = sot.get(eci, {})
        sot_n = len(sot_pairs)
        lgd_n = len(feats)

        name_matches = 0
        name_total_compared = 0
        mismatched_examples: list[str] = []
        no_only_in_lgd: list[int] = []
        no_only_in_sot: list[int] = []
        for no in sorted(set(lgd_pairs) | set(sot_pairs)):
            l_name = lgd_pairs.get(no)
            s_name = sot_pairs.get(no)
            if l_name is None:
                no_only_in_sot.append(no)
                continue
            if s_name is None:
                no_only_in_lgd.append(no)
                continue
            name_total_compared += 1
            if normalize_name(l_name) == normalize_name(s_name):
                name_matches += 1
            elif len(mismatched_examples) < 3:
                mismatched_examples.append(f"AC {no}: LGD={l_name!r} SoT={s_name!r}")

        name_pct = (name_matches / name_total_compared) if name_total_compared else 0.0
        count_match = (lgd_n == sot_n)
        verdict = _verdict(eci, lgd_n, sot_n, name_pct, count_match)
        report[eci] = {
            "state_lgd_int": slgd_int,
            "lgd_count": lgd_n,
            "sot_count": sot_n,
            "lgd_no_missing": lgd_no_missing,
            "count_match": count_match,
            "name_match_pct": round(name_pct, 4),
            "name_matches": name_matches,
            "name_total_compared": name_total_compared,
            "no_only_in_lgd": no_only_in_lgd,
            "no_only_in_sot": no_only_in_sot,
            "mismatched_examples": mismatched_examples,
            "verdict": verdict,
        }
    return report, dict(unmapped)


def _verdict(
    eci: str, lgd_n: int, sot_n: int, name_pct: float, count_match: bool,
) -> str:
    """Per-state verdict per plan-doc §D.1 acceptance gate."""
    if eci == "S03":  # Assam: D.3 special case (2023 re-delim gate)
        if count_match and name_pct >= NAME_MATCH_THRESHOLD:
            return "Assam-D.3: count + names match SoT (eligible if SoT is 2023 delim)"
        return f"Assam-D.3: parity-mismatch (LGD {lgd_n} vs SoT {sot_n}, names {name_pct:.0%})"
    if eci == "U08":  # J&K: D.4 special case (90-AC 2022 re-delim gate)
        if count_match and lgd_n == 90 and name_pct >= NAME_MATCH_THRESHOLD:
            return "J&K-D.4: 90-AC layout + names match (eligible-D.4 promote)"
        if lgd_n == 87:
            return "J&K-D.4: pre-statehood 87-AC layout (keep shijithpk)"
        return f"J&K-D.4: parity-mismatch (LGD {lgd_n} vs SoT {sot_n}, names {name_pct:.0%})"
    if count_match and name_pct >= NAME_MATCH_THRESHOLD:
        return "eligible-D.2"
    if not count_match:
        return f"keep-current (count mismatch LGD {lgd_n} vs SoT {sot_n})"
    return f"keep-current (name-match {name_pct:.0%} < {NAME_MATCH_THRESHOLD:.0%})"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def render_report(
    archive_url: str,
    archive_bytes: int,
    archive_sha256: str,
    payload_name: str,
    feature_total: int,
    schema: dict[str, dict[str, Any]],
    state_lgd_prop: str,
    ac_no_prop: str,
    name_prop: str,
    per_eci: dict[str, dict[str, Any]],
    unmapped: dict[int, int],
    sot: dict[str, dict[int, str]],
) -> str:
    """Render the recon markdown to stdout (operator paste-ready)."""
    lines: list[str] = []
    lines.append("# Phase D.1 recon: ramSeraph LGD_Assembly_Constituencies parity audit")
    lines.append("")
    lines.append(f"- Upstream URL: {archive_url}")
    lines.append(f"- Archive bytes: {archive_bytes:,}")
    lines.append(f"- Archive SHA-256: {archive_sha256}")
    lines.append(f"- Payload member: {payload_name}")
    lines.append(f"- Total features: {feature_total:,}")
    lines.append(f"- state_lgd property: {state_lgd_prop!r}")
    lines.append(f"- ac_no property: {ac_no_prop!r}")
    lines.append(f"- name property: {name_prop!r}")
    lines.append("")
    lines.append("## Feature property schema (verbatim)")
    lines.append("")
    lines.append("| Property | Coverage | Types | Sample values |")
    lines.append("| --- | ---: | --- | --- |")
    for k in sorted(schema):
        v = schema[k]
        samples = ", ".join(repr(s) for s in v["samples"])
        types = ",".join(v["types"])
        lines.append(f"| `{k}` | {v['coverage']:.0%} | {types} | {samples} |")
    lines.append("")
    lines.append("## Per-state inventory + parity verdicts")
    lines.append("")
    lines.append(
        "| ECI | state_lgd | LGD count | SoT count | Count match | Name match % | Verdict |"
    )
    lines.append("| --- | ---: | ---: | ---: | :---: | ---: | --- |")
    eligible = 0
    sot_eci_set = set(sot)
    seen_eci: set[str] = set()
    for eci in sorted(per_eci):
        r = per_eci[eci]
        seen_eci.add(eci)
        mark = "Y" if r["count_match"] else "N"
        lines.append(
            f"| {eci} | {r['state_lgd_int']} | {r['lgd_count']} | "
            f"{r['sot_count']} | {mark} | {r['name_match_pct']:.0%} | "
            f"{r['verdict']} |"
        )
        if r["verdict"] == "eligible-D.2":
            eligible += 1
    lines.append("")
    sot_missing = sorted(sot_eci_set - seen_eci)
    if sot_missing:
        lines.append("### SoT states with no LGD AC features")
        lines.append("")
        for eci in sot_missing:
            lines.append(f"- {eci}: SoT carries {len(sot[eci])} ACs; LGD release has none.")
        lines.append("")
    if unmapped:
        lines.append("### Unmapped state_lgd values (features that route nowhere)")
        lines.append("")
        for slgd, n in sorted(unmapped.items()):
            label = "non-int" if slgd == -1 else str(slgd)
            lines.append(f"- state_lgd={label}: {n} feature(s)")
        lines.append("")
    lines.append("## National totals")
    lines.append("")
    total_lgd_seen = sum(r["lgd_count"] for r in per_eci.values())
    total_unmapped = sum(unmapped.values())
    total_sot = sum(len(v) for v in sot.values())
    lines.append(f"- LGD features mapped to ECI states: {total_lgd_seen:,}")
    lines.append(f"- LGD features unmapped: {total_unmapped:,}")
    lines.append(f"- LGD features grand total: {feature_total:,}")
    lines.append(f"- SoT grand total (all constituencies.json): {total_sot:,}")
    lines.append("")
    lines.append("## Roll-up")
    lines.append("")
    lines.append(f"- Eligible for D.2 promotion: {eligible} states/UTs")
    lines.append(
        f"- Assam (S03): {per_eci.get('S03', {}).get('verdict', 'NOT PRESENT IN LGD')}"
    )
    lines.append(
        f"- J&K (U08): {per_eci.get('U08', {}).get('verdict', 'NOT PRESENT IN LGD')}"
    )
    keep = [eci for eci, r in per_eci.items() if r["verdict"].startswith("keep-current")]
    lines.append(f"- Keep current source: {len(keep)} states/UTs ({', '.join(sorted(keep)) or 'none'})")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".", help="Repo root (default: cwd).")
    parser.add_argument(
        "--state-lgd-prop",
        default="state_lgd",
        help="Property carrying the LGD state code (default: state_lgd; "
        "auto-detected if absent — pass to override on first failure).",
    )
    parser.add_argument(
        "--ac-no-prop",
        default="ac_no",
        help="Property carrying the LGD AC number (default: ac_no).",
    )
    parser.add_argument(
        "--name-prop",
        default="ac_name",
        help="Property carrying the AC display name (default: ac_name).",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional output path for the markdown report (default: stdout).",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    raw_dir = root / ".runtime" / "raw" / "ramseraph" / "constituencies"
    archive_path = raw_dir / "LGD_Assembly_Constituencies.geojsonl.7z"
    extract_dir = raw_dir / "_extracted"

    print(f"fetching {LGD_AC_URL} ...", file=sys.stderr, flush=True)
    n_bytes, sha = fetch_archive(LGD_AC_URL, archive_path)
    print(f"  {n_bytes:,} bytes; sha256={sha}", file=sys.stderr, flush=True)

    payload = extract_geojsonl(archive_path, extract_dir)
    print(f"extracted {payload.name}", file=sys.stderr, flush=True)

    features = parse_features(payload)
    print(f"parsed {len(features):,} features", file=sys.stderr, flush=True)

    schema = discover_schema(features)
    print("schema keys:", sorted(schema), file=sys.stderr, flush=True)

    # Auto-detect property names: look for the conventional LGD shapes.
    state_lgd_prop = args.state_lgd_prop
    ac_no_prop = args.ac_no_prop
    name_prop = args.name_prop
    if state_lgd_prop not in schema:
        for candidate in (
            "state_lgd", "State_LGD", "STATE_LGD", "st_lgd",
            "state_code", "STCODE", "STCODE11",
        ):
            if candidate in schema:
                state_lgd_prop = candidate
                break
    if ac_no_prop not in schema:
        for candidate in (
            "ac_no", "AC_NO", "ac_lgd", "AC_LGD",
            "lgd_ac_code", "AC_CODE", "ac_code",
        ):
            if candidate in schema:
                ac_no_prop = candidate
                break
    if name_prop not in schema:
        for candidate in (
            "ac_name", "AC_NAME", "ACNAME", "name",
            "AcName", "AC_Name",
        ):
            if candidate in schema:
                name_prop = candidate
                break
    print(
        f"resolved property names: state_lgd={state_lgd_prop!r} "
        f"ac_no={ac_no_prop!r} name={name_prop!r}",
        file=sys.stderr,
        flush=True,
    )

    entities_path = root / "datasets" / "taxonomy" / "entities.json"
    with entities_path.open(encoding="utf-8") as fh:
        ent_doc = json.load(fh)
    state_lgd_to_eci = build_state_lgd_to_eci_map(ent_doc["entities"])
    print(
        f"state_lgd map: {len(state_lgd_to_eci)} entries",
        file=sys.stderr,
        flush=True,
    )

    sot = load_sot(root)
    print(f"loaded SoT for {len(sot)} states/UTs", file=sys.stderr, flush=True)

    per_eci, unmapped = per_state_parity(
        features,
        state_lgd_to_eci,
        state_lgd_prop=state_lgd_prop,
        ac_no_prop=ac_no_prop,
        name_prop=name_prop,
        sot=sot,
    )

    report = render_report(
        archive_url=LGD_AC_URL,
        archive_bytes=n_bytes,
        archive_sha256=sha,
        payload_name=payload.name,
        feature_total=len(features),
        schema=schema,
        state_lgd_prop=state_lgd_prop,
        ac_no_prop=ac_no_prop,
        name_prop=name_prop,
        per_eci=per_eci,
        unmapped=unmapped,
        sot=sot,
    )

    if args.out:
        out_path = root / args.out if not Path(args.out).is_absolute() else Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"\nwrote {out_path}", file=sys.stderr, flush=True)
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
