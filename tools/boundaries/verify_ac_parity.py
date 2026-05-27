"""Verify Phase D.2 AC promote parity per state.

After `python -m tools.boundaries.snapshot --kind ac --state S04 ...` rewrites
`datasets/boundaries/in/ac/state=in_<eci_lc>/all.geojson` for each D.2 target
state with the ramSeraph LGD slice, this tool re-asserts the parity invariants
that D.1 recon (`tools/boundaries/recon_d1_ac.py`, PR #270) measured on the
unfiltered upstream:

    1. **Count match** — the snapshot geojson has exactly as many features as
       the SoT `datasets/reference/in/states/<eci>/constituencies.json` lists.
    2. **`ac_no` coverage** — every `eci_no` in SoT appears as an `ac_no` in
       the geojson exactly once; no extras.
    3. **Name parity >= 95%** — normalised (NFKD + reservation-suffix strip +
       casefold) names match SoT for at least 95% of ACs. Threshold is the
       same as D.1 recon's `eligible-D.2` gate.

Exits non-zero on any per-state failure. Single-state mode (`--state S04`)
runs one; repeating the flag runs many; no `--state` runs the 10-state D.2
default set.

This tool is permanent (unlike `recon_d1_ac.py`, which retires after D.5):
future D.2-style promotions for more states will re-use it in their PRs to
prove the per-state contract holds before commit.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

# Default D.2 target set (PR <this-PR>, 2026-05-25).
DEFAULT_STATES: tuple[str, ...] = (
    "S04",  # Bihar
    "S07",  # Haryana
    "S08",  # Himachal Pradesh
    "S17",  # Nagaland
    "S18",  # Odisha
    "S19",  # Punjab
    "S23",  # Tripura
    "S26",  # Chhattisgarh
    "S28",  # Uttarakhand
    "U05",  # NCT of Delhi
)

NAME_PARITY_THRESHOLD: float = 0.95
"""Default name-parity floor for D.2 promotions. Override per state via
the ``--threshold`` CLI flag (e.g. Assam S03 historically lands ~0.85 due
to upstream transliteration drift; see PR #270 D.1 recon)."""

_RESERVATION_SUFFIX_RE = re.compile(r"\s*\((sc|st|gen)\)\s*$", re.IGNORECASE)


def normalize_name(name: str | None) -> str:
    """Fold a name for SoT vs LGD comparison.

    Mirrors `tools/boundaries/recon_d1_ac.py::normalize_name`: NFKD strip
    diacritics, casefold, drop trailing reservation suffix (` (SC)` /
    ` (ST)` / ` (GEN)`), collapse non-alphanumerics to single spaces.
    """
    if not isinstance(name, str):
        return ""
    s = unicodedata.normalize("NFKD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.casefold().strip()
    s = _RESERVATION_SUFFIX_RE.sub("", s)
    out: list[str] = []
    prev_space = False
    for ch in s:
        if ch.isalnum():
            out.append(ch)
            prev_space = False
        elif not prev_space:
            out.append(" ")
            prev_space = True
    return "".join(out).strip()


def load_sot(repo_root: Path, eci: str) -> dict[int, str]:
    """Return ``{eci_no: name}`` from the state's SoT constituencies.json."""
    path = repo_root / "datasets" / "reference" / "in" / "states" / eci / "constituencies.json"
    if not path.is_file():
        msg = f"SoT not found for {eci}: {path}"
        raise FileNotFoundError(msg)
    with path.open(encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("body") != "AC":
        msg = f"SoT for {eci} is not body=AC: {doc.get('body')!r}"
        raise ValueError(msg)
    by_no: dict[int, str] = {}
    for c in doc.get("constituencies", []):
        no = c.get("eci_no")
        name = c.get("name")
        if isinstance(no, int) and isinstance(name, str):
            by_no[no] = name
    return by_no


def load_geojson_features(repo_root: Path, eci: str) -> list[dict]:
    """Return the FeatureCollection's features for the per-state geojson."""
    path = (
        repo_root
        / "datasets"
        / "boundaries"
        / "in"
        / "ac"
        / f"state=in_{eci.lower()}"
        / "all.geojson"
    )
    if not path.is_file():
        msg = f"snapshot geojson not found for {eci}: {path}"
        raise FileNotFoundError(msg)
    with path.open(encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("type") != "FeatureCollection":
        msg = f"{path} is not a FeatureCollection (got {doc.get('type')!r})"
        raise ValueError(msg)
    return doc.get("features", [])


def verify_state(
    repo_root: Path,
    eci: str,
    threshold: float = NAME_PARITY_THRESHOLD,
    *,
    allow_extras: bool = False,
    undercoverage_tolerance: float = 0.0,
) -> tuple[bool, list[str], dict]:
    """Run the 3 checks; return (passed, errors, stats).

    ``threshold`` is the name-parity floor (default 0.95). Callers may relax
    it per state (e.g. Assam S03 ~0.85 due to upstream transliteration drift).

    ``allow_extras`` (D.7 universal LGD swap, 2026-05-27) relaxes the
    count + ``ac_no``-set checks one-sidedly: snapshot may contain EXTRA
    features beyond SoT (LGD often carries pre-bifurcation residue that
    renders as no-fill polygons — citizen-harmless). Undercoverage
    (snapshot missing real SoT ACs) STILL fails by default because that
    breaks the choropleth.

    ``undercoverage_tolerance`` (D.7, default 0.0 = strict) further relaxes
    the undercoverage check: snapshot may be missing up to
    ``ceil(sot_count * tolerance)`` ACs without failing. Used for D.7 to
    accept e.g. West Bengal S25 LGD 293 vs SoT 294 (1-AC residue drift).
    The hard floor on bigger losses (Gujarat S06 -18 historical case)
    still fires via the safety-net revert rule in the plan-doc.
    """
    errors: list[str] = []
    sot = load_sot(repo_root, eci)
    features = load_geojson_features(repo_root, eci)

    # Check 1: count match. With allow_extras, only undercoverage fails.
    # With undercoverage_tolerance > 0, small shortfalls are accepted.
    snap_count = len(features)
    sot_count = len(sot)
    shortfall = max(0, sot_count - snap_count)
    allowed_shortfall = int(sot_count * undercoverage_tolerance)
    if allow_extras:
        if shortfall > allowed_shortfall:
            errors.append(
                f"undercoverage: snapshot has {snap_count} features, SoT has "
                f"{sot_count} (shortfall {shortfall} > allowed {allowed_shortfall})"
            )
    elif snap_count != sot_count:
        errors.append(
            f"count mismatch: snapshot has {snap_count} features, SoT has {sot_count}"
        )

    # Check 2: ac_no coverage (set-equality on eci_no <-> ac_no).
    snap_acno: dict[int, int] = {}
    for feat in features:
        props = feat.get("properties") or {}
        raw = props.get("ac_no")
        try:
            n = int(raw)
        except (TypeError, ValueError):
            errors.append(f"feature with non-integer ac_no: {raw!r}")
            continue
        snap_acno[n] = snap_acno.get(n, 0) + 1
    duplicates = {n: c for n, c in snap_acno.items() if c > 1}
    if duplicates:
        errors.append(f"duplicate ac_no in snapshot: {duplicates}")
    snap_set = set(snap_acno.keys())
    sot_set = set(sot.keys())
    missing = sot_set - snap_set
    extras = snap_set - sot_set
    if missing and len(missing) > allowed_shortfall:
        errors.append(f"ac_no(s) in SoT but missing from snapshot: {sorted(missing)}")
    if extras and not allow_extras:
        errors.append(f"ac_no(s) in snapshot but not in SoT: {sorted(extras)}")

    # Check 3: name parity (>=95% after normalisation, over shared ac_no set).
    shared = snap_set & sot_set
    name_matches = 0
    for feat in features:
        props = feat.get("properties") or {}
        try:
            n = int(props.get("ac_no"))
        except (TypeError, ValueError):
            continue
        if n not in shared:
            continue
        snap_name = normalize_name(props.get("ac_name"))
        sot_name = normalize_name(sot.get(n))
        if snap_name and snap_name == sot_name:
            name_matches += 1
    name_parity = name_matches / len(shared) if shared else 0.0
    if name_parity < threshold:
        errors.append(
            f"name parity {name_parity:.1%} < {threshold:.0%} "
            f"({name_matches}/{len(shared)} matched)"
        )

    stats = {
        "snap_count": snap_count,
        "sot_count": sot_count,
        "name_matches": name_matches,
        "shared": len(shared),
        "name_parity": name_parity,
    }
    return not errors, errors, stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--state",
        action="append",
        metavar="ECI",
        help="ECI state code; repeat for many; omit to run the D.2 default 10-state set.",
    )
    p.add_argument(
        "--root",
        default=".",
        type=Path,
        help="Repo root (default `.`).",
    )
    p.add_argument(
        "--threshold",
        type=float,
        default=NAME_PARITY_THRESHOLD,
        help=(
            f"Name-parity floor (default {NAME_PARITY_THRESHOLD:.2f}). "
            "Lower for states with documented upstream transliteration "
            "drift (e.g. Assam S03 ~0.85)."
        ),
    )
    p.add_argument(
        "--allow-extras",
        action="store_true",
        help=(
            "D.7 universal LGD swap (2026-05-27): allow snapshot to contain "
            "MORE ac_no values than SoT (LGD pre-bifurcation residue renders "
            "as no-fill polygons — citizen-harmless). Undercoverage "
            "(snapshot missing real SoT ACs) still fails by default."
        ),
    )
    p.add_argument(
        "--undercoverage-tolerance",
        type=float,
        default=0.0,
        help=(
            "D.7 universal LGD swap (2026-05-27): allow snapshot to be "
            "missing up to TOLERANCE * sot_count ACs (default 0.0 = strict). "
            "Use with --allow-extras to accept tiny LGD residue drift e.g. "
            "West Bengal S25 LGD 293 vs SoT 294 (1-AC shortfall)."
        ),
    )
    args = p.parse_args(argv)
    repo_root = args.root.resolve()
    targets = tuple(args.state) if args.state else DEFAULT_STATES
    threshold: float = args.threshold
    allow_extras: bool = args.allow_extras
    undercoverage_tolerance: float = args.undercoverage_tolerance
    if not (0.0 <= threshold <= 1.0):
        print(
            f"--threshold must be in [0.0, 1.0], got {threshold}",
            file=sys.stderr,
        )
        return 2
    if not (0.0 <= undercoverage_tolerance <= 1.0):
        print(
            f"--undercoverage-tolerance must be in [0.0, 1.0], got {undercoverage_tolerance}",
            file=sys.stderr,
        )
        return 2

    all_ok = True
    for eci in targets:
        try:
            ok, errors, stats = verify_state(
                repo_root, eci, threshold=threshold,
                allow_extras=allow_extras,
                undercoverage_tolerance=undercoverage_tolerance,
            )
        except (FileNotFoundError, ValueError) as e:
            print(f"FAIL  {eci}  -> {e}", flush=True)
            all_ok = False
            continue
        if ok:
            print(
                f"OK    {eci}  count={stats['snap_count']}  "
                f"name_parity={stats['name_parity']:.1%} "
                f"({stats['name_matches']}/{stats['shared']})",
                flush=True,
            )
        else:
            all_ok = False
            print(
                f"FAIL  {eci}  count={stats['snap_count']}/{stats['sot_count']}  "
                f"name_parity={stats['name_parity']:.1%}",
                flush=True,
            )
            for err in errors:
                print(f"      - {err}", flush=True)

    extras_note = " allow_extras=on" if allow_extras else ""
    if all_ok:
        print(
            f"\nAll {len(targets)} state(s) passed AC parity "
            f"(threshold={threshold:.2f}{extras_note}).",
            flush=True,
        )
        return 0
    print(
        f"\nAt least one of {len(targets)} state(s) failed parity "
        f"(threshold={threshold:.2f}{extras_note}).",
        flush=True,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
