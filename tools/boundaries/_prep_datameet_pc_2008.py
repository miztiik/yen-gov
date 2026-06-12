"""One-shot operator tool: stage datameet's india_pc_2019_simplified.geojson
as the local_file input for the delim=2008 PC boundary layer.

Reads the upstream simplified GeoJSON from a download/clone location,
normalises feature properties to the canonical shape that the snapshot
tool + frontend consumer expect, and writes the staged file to
``datasets/ephemeral/india_pc_2008_simplified.geojson`` (gitignored
via ``datasets/ephemeral/*``; rebuildable from upstream + this script).

Operator workflow
-----------------
1.  Clone the datameet maps repo (sparse to one subdir is fine)::

      git clone --depth 1 https://github.com/datameet/maps \\
          "$env:TEMP/yen-gov-datameet-probe"

2.  Run this preprocessor::

      python -m tools.boundaries._prep_datameet_pc_2008

    Default ``--input`` points at the clone path above; default
    ``--output`` is the gitignored ``datasets/ephemeral/...`` stage path
    referenced by the new pipeline.json entry.

3.  Run the snapshot pipeline::

      python -m tools.boundaries.snapshot --preserve-existing

    The new pipeline.json entry (``kind: pc``, ``delimitation_vintage:
    2008``, ``format: local_file``) reads the staged file and emits
    ``datasets/boundaries/electoral/delim=2008/pc/all.geojson`` plus
    a boundary_layer.csv row.

4.  Run the topojson converter to produce the ``.topojson`` sibling::

      python -m tools.topojson.convert_layer \\
          --input  datasets/boundaries/electoral/delim=2008/pc/all.geojson \\
          --output datasets/boundaries/electoral/delim=2008/pc/all.topojson \\
          --layer  pc

Provenance
----------
* Upstream artifact: ``india_pc_2019_simplified.geojson`` from
  https://github.com/datameet/maps/tree/master/parliamentary-constituencies
* Author of the simplified derivative: Arun Ganesh (per the upstream
  ``README.md``).
* License: CC0 1.0 Universal (Public Domain Dedication).
* Feature count: 543 (one polygon per Lok Sabha Parliamentary
  Constituency under the 2008 Delimitation Commission Order; the 6
  states exempted from re-delimitation under the same Order — J&K,
  Jharkhand, Arunachal Pradesh, Assam, Manipur, Nagaland — retain
  their 1976 boundaries and carry ``status='Pre delimitation'`` on the
  upstream features; that flag is preserved as ``pre_delim_2008: true``
  on the output for the citizen methodology footer).

Output schema (per feature properties)
--------------------------------------
* ``state_ut_code`` (str): canonical ECI ``S##`` / ``U##`` code derived
  from the upstream ``st_name`` via slug + alias map. Ladakh is
  special-cased: the upstream feature carries ``st_name='Jammu &
  Kashmir'`` but the canonical store models it as the post-2019
  Ladakh UT (U09), so the Ladakh PC alone (``pc_no=4`` under that
  st_name) maps to ``U09`` while the other 5 J&K features map to
  ``U08`` (post-2019 J&K UT). This matches the temporal split in
  ``datasets/data/entities/electoral.csv``.
* ``state_ut_name`` (str): canonical state/UT name (Title Case, ASCII;
  ``&`` -> ``and``). Mirrors the existing 2024 PC emit's
  ``state_ut_name`` shape so the cross-layer tooltip card writes
  identically.
* ``ls_seat_name`` (str): upstream ``pc_name`` verbatim (Title Case).
* ``ls_seat_code`` (str): upstream ``pc_no`` as a decimal string (the
  per-state ECI numbering 1..N; matches the existing 2024 emit's
  string-typed ``ls_seat_code``).
* ``pc_name_slug`` (str): ``slugify(ls_seat_name)`` — kebab-case ASCII
  derived via the same NFKD + alphanum rule the frontend uses
  (``frontend/src/lib/slug.ts``). This is the join key against
  ``electoral.csv`` because canonical's ``eci_no`` values are
  unreliable for delim=2008 PCs (see V6 pre-flight verdict in
  ``TODO/20260612-pc-delim-2008-boundary-ingest-plan.md``).
* ``unique_id`` (str): ``"<state_ut_code>_<pc_name_slug>"``. The
  ``INDIA_PC_2008`` ``BoundaryEntry.join_property`` reads this; the
  frontend builds the matching key from the canonical row's ``state``
  + ``name`` for delim=2008 events.
* ``pc_category`` (str): GEN | SC | ST verbatim from upstream.
* ``pre_delim_2008`` (bool): ``true`` when the upstream feature
  carries ``status='Pre delimitation'`` (the 6 exempted states). The
  citizen-facing methodology footer surfaces a one-line note for
  these features so the carve-out is honest.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Slug helpers (mirror frontend/src/lib/slug.ts::slugify exactly)
# ---------------------------------------------------------------------------


def slugify(s: str) -> str:
    """Match ``frontend/src/lib/slug.ts::slugify`` byte-for-byte.

    Rule: NFKD normalise, strip combining marks, lowercase, collapse
    runs of non-``[a-z0-9]`` to a single dash, trim leading/trailing
    dashes. Used to derive a join-stable PC name slug that aligns
    against the canonical ``electoral.csv`` ``name`` column after the
    same client-side rule.
    """
    nfkd = unicodedata.normalize("NFKD", s)
    no_marks = "".join(c for c in nfkd if not unicodedata.combining(c))
    lower = no_marks.lower()
    dashed = re.sub(r"[^a-z0-9]+", "-", lower)
    return dashed.strip("-")


# ---------------------------------------------------------------------------
# State-name normalisation
# ---------------------------------------------------------------------------

# Mirror of MODERN_STATE_SLUG_BY_ECI_CODE inverted (slug -> ECI code).
# Hand-authored to avoid pulling in the full taxonomy loader for a
# 36-row map; parity with
# ``backend/yen_gov/canonical/historical_state_slug.py`` is asserted by
# the test suite. The J&K + Ladakh entry pair encodes the post-2019
# split (datameet's pre-2019 J&K composite is split here to the
# current spine values).
SLUG_TO_ECI: dict[str, str] = {
    "andhra-pradesh": "S01",
    "arunachal-pradesh": "S02",
    "assam": "S03",
    "bihar": "S04",
    "goa": "S05",
    "gujarat": "S06",
    "haryana": "S07",
    "himachal-pradesh": "S08",
    "karnataka": "S10",
    "kerala": "S11",
    "madhya-pradesh": "S12",
    "maharashtra": "S13",
    "manipur": "S14",
    "meghalaya": "S15",
    "mizoram": "S16",
    "nagaland": "S17",
    "odisha": "S18",
    "punjab": "S19",
    "rajasthan": "S20",
    "sikkim": "S21",
    "tamil-nadu": "S22",
    "tripura": "S23",
    "uttar-pradesh": "S24",
    "west-bengal": "S25",
    "chhattisgarh": "S26",
    "jharkhand": "S27",
    "uttarakhand": "S28",
    "telangana": "S29",
    "andaman-and-nicobar-islands": "U01",
    "chandigarh": "U02",
    "dadra-and-nagar-haveli-and-daman-and-diu": "U03",
    "lakshadweep": "U04",
    "delhi": "U05",
    "puducherry": "U07",
    "jammu-and-kashmir": "U08",  # post-2019 J&K UT
    "ladakh": "U09",
}

# datameet st_name slug -> canonical slug. The entries here are the
# unambiguous temporal/spelling drifts surfaced by the V6 pre-flight.
# NOTE: the frontend slugify rule collapses any run of non-[a-z0-9] to
# a single dash, so "Daman & Diu" -> "daman-diu" (not "daman-and-diu").
# Each upstream st_name's slug is listed verbatim here.
#   - "orissa" was officially renamed to "odisha" in 2011.
#   - "andaman-nicobar" is the upstream short form; the canonical
#     spine uses the full "...-islands" suffix.
#   - the two pre-2020 separate UTs (DNH + DD) merged into one
#     "dadra-and-nagar-haveli-and-daman-and-diu" UT under the
#     Dadra and Nagar Haveli and Daman and Diu (Merger of Union
#     Territories) Act, 2019 (effective 26 January 2020).
#   - "jammu-kashmir" (datameet's slugify of "Jammu & Kashmir") maps
#     to the post-2019 J&K UT slug "jammu-and-kashmir" (the canonical
#     spine entry). Ladakh is special-cased on pc_name within
#     normalise_state().
DATAMEET_SLUG_ALIAS: dict[str, str] = {
    "orissa": "odisha",
    "andaman-nicobar": "andaman-and-nicobar-islands",
    "dadra-nagar-haveli": "dadra-and-nagar-haveli-and-daman-and-diu",
    "daman-diu": "dadra-and-nagar-haveli-and-daman-and-diu",
    "jammu-kashmir": "jammu-and-kashmir",
}

# Canonical Title-Case state/UT name keyed by slug. Used to emit
# ``state_ut_name`` matching the existing 2024 emit shape.
CANONICAL_STATE_NAME_BY_SLUG: dict[str, str] = {
    "andhra-pradesh": "Andhra Pradesh",
    "arunachal-pradesh": "Arunachal Pradesh",
    "assam": "Assam",
    "bihar": "Bihar",
    "goa": "Goa",
    "gujarat": "Gujarat",
    "haryana": "Haryana",
    "himachal-pradesh": "Himachal Pradesh",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "madhya-pradesh": "Madhya Pradesh",
    "maharashtra": "Maharashtra",
    "manipur": "Manipur",
    "meghalaya": "Meghalaya",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "odisha": "Odisha",
    "punjab": "Punjab",
    "rajasthan": "Rajasthan",
    "sikkim": "Sikkim",
    "tamil-nadu": "Tamil Nadu",
    "tripura": "Tripura",
    "uttar-pradesh": "Uttar Pradesh",
    "west-bengal": "West Bengal",
    "chhattisgarh": "Chhattisgarh",
    "jharkhand": "Jharkhand",
    "uttarakhand": "Uttarakhand",
    "telangana": "Telangana",
    "andaman-and-nicobar-islands": "Andaman and Nicobar Islands",
    "chandigarh": "Chandigarh",
    "dadra-and-nagar-haveli-and-daman-and-diu": "Dadra and Nagar Haveli and Daman and Diu",
    "lakshadweep": "Lakshadweep",
    "delhi": "Delhi",
    "puducherry": "Puducherry",
    "jammu-and-kashmir": "Jammu and Kashmir",
    "ladakh": "Ladakh",
}


def normalise_state(st_name_upstream: str, pc_name_upstream: str) -> tuple[str, str]:
    """Return (state_ut_code, state_ut_name) for one upstream feature.

    Handles the Ladakh split: when ``st_name=='Jammu & Kashmir'`` and
    ``pc_name=='Ladakh'``, the feature maps to U09 / "Ladakh" rather
    than U08 / "Jammu and Kashmir".
    """
    if (
        pc_name_upstream.strip().lower() == "ladakh"
        and "jammu" in st_name_upstream.lower()
    ):
        return "U09", CANONICAL_STATE_NAME_BY_SLUG["ladakh"]
    # Slugify upstream st_name with the same rule the frontend uses,
    # then apply the alias map to land on a canonical slug.
    upstream_slug = slugify(st_name_upstream)
    canonical_slug = DATAMEET_SLUG_ALIAS.get(upstream_slug, upstream_slug)
    code = SLUG_TO_ECI.get(canonical_slug)
    if code is None:
        raise ValueError(
            f"unable to map upstream st_name to canonical ECI code: "
            f"st_name={st_name_upstream!r} slug={upstream_slug!r} "
            f"aliased_slug={canonical_slug!r}"
        )
    name = CANONICAL_STATE_NAME_BY_SLUG[canonical_slug]
    return code, name


# ---------------------------------------------------------------------------
# Per-feature transform
# ---------------------------------------------------------------------------


def normalise_feature(upstream: dict) -> dict:
    """Return a new feature with normalised properties + the upstream
    geometry preserved byte-identically."""
    props = upstream.get("properties") or {}
    st_name = str(props.get("st_name") or "")
    pc_name = str(props.get("pc_name") or "")
    pc_no_raw = props.get("pc_no")
    pc_category = str(props.get("pc_category") or "")
    status = props.get("status")

    if not st_name or not pc_name or pc_no_raw is None:
        raise ValueError(
            f"upstream feature missing required keys: properties={props!r}"
        )

    state_ut_code, state_ut_name = normalise_state(st_name, pc_name)
    ls_seat_code = str(int(pc_no_raw))
    pc_name_slug = slugify(pc_name)
    unique_id = f"{state_ut_code}_{pc_name_slug}"
    pre_delim_2008 = status == "Pre delimitation"

    out_props = {
        "state_ut_code": state_ut_code,
        "state_ut_name": state_ut_name,
        "ls_seat_name": pc_name,
        "ls_seat_code": ls_seat_code,
        "pc_name_slug": pc_name_slug,
        "unique_id": unique_id,
        "pc_category": pc_category,
        "pre_delim_2008": pre_delim_2008,
    }
    return {
        "type": "Feature",
        "properties": out_props,
        "geometry": upstream.get("geometry"),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.boundaries._prep_datameet_pc_2008",
        description=(
            "Stage datameet's india_pc_2019_simplified.geojson as the "
            "delim=2008 PC local_file input for snapshot.py."
        ),
    )
    default_input = Path(
        os.environ.get("TEMP", "/tmp"),
        "yen-gov-datameet-probe",
        "parliamentary-constituencies",
        "india_pc_2019_simplified.geojson",
    )
    default_output = REPO_ROOT / "datasets" / "ephemeral" / "india_pc_2008_simplified.geojson"
    parser.add_argument(
        "--input",
        type=Path,
        default=default_input,
        help=f"Path to the upstream simplified geojson (default: {default_input}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output,
        help=(
            f"Path to write the normalised staged geojson "
            f"(default: {default_output})."
        ),
    )
    args = parser.parse_args(argv)

    if not args.input.is_file():
        sys.stderr.write(
            f"error: input not found: {args.input}\n"
            "  Sparse-clone datameet/maps first per the docstring.\n"
        )
        return 2

    with args.input.open("r", encoding="utf-8") as fh:
        upstream = json.load(fh)
    if not isinstance(upstream, dict) or upstream.get("type") != "FeatureCollection":
        sys.stderr.write(
            f"error: input is not a GeoJSON FeatureCollection: {args.input}\n"
        )
        return 2
    feats_in = upstream.get("features") or []
    if not isinstance(feats_in, list):
        sys.stderr.write(f"error: input has no 'features' array: {args.input}\n")
        return 2

    feats_out: list[dict] = []
    state_counts: dict[str, int] = {}
    pre_delim_count = 0
    for f in feats_in:
        out = normalise_feature(f)
        feats_out.append(out)
        p = out["properties"]
        state_counts[p["state_ut_code"]] = state_counts.get(p["state_ut_code"], 0) + 1
        if p["pre_delim_2008"]:
            pre_delim_count += 1

    # Verify Ladakh got split: U09 should carry exactly one feature
    # and U08 should carry five (5 J&K PCs + 1 Ladakh = 6 upstream J&K
    # features after the split).
    if state_counts.get("U09", 0) != 1:
        sys.stderr.write(
            f"error: expected 1 Ladakh PC under U09; got {state_counts.get('U09', 0)}.\n"
            "  Upstream may have renamed the Ladakh seat; revisit normalise_state().\n"
        )
        return 3
    if state_counts.get("U08", 0) != 5:
        sys.stderr.write(
            f"error: expected 5 J&K PCs under U08; got {state_counts.get('U08', 0)}.\n"
        )
        return 3

    out_doc = {
        "type": "FeatureCollection",
        "name": "india_pc_2008_simplified",
        "crs": upstream.get("crs"),
        "features": feats_out,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        json.dump(out_doc, fh, ensure_ascii=False)
        fh.write("\n")

    # Summary
    sys.stdout.write(
        f"wrote {len(feats_out)} features to {args.output}\n"
        f"  bytes:                  {args.output.stat().st_size:,}\n"
        f"  distinct state_ut_code: {len(state_counts)}\n"
        f"  pre_delim_2008=true:    {pre_delim_count} features "
        "(6 exempted states: J&K, Jharkhand, Arunachal, Assam, Manipur, Nagaland)\n"
        f"  per-state counts:       {dict(sorted(state_counts.items()))}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
