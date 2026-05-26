"""Build meadow JSON for Owner Registration + Land Holding (NDLM) at district grain.

Reads ``.runtime/raw/ndlm/<raw_vintage>/owner_reg_land_holding_district_state-*.json``
produced by ``tools/ndlm_download.py`` and emits ONE meadow file per
vintage at:

    datasets/livestock/_meadow/ndlm/<vintage>/owner_reg_land_holding_district.json

per [ADR-0041](../docs/architecture/decisions/0041-meadow-tier.md) + the
livestock NDLM ingest plan section 5.1.

ROW SHAPE
---------
Owner Reg counts livestock-owner identity records on the Bharat
Pashudhan portal, broken down by district x landholding bracket x
gender. The publisher emits, per district::

    code, name, maleCount, femaleCount,
    details: {
        "0": { ownerLandHoldingCd=0, ownerLandHoldingDesc=null,
               maleCount, femaleCount, total },  # not-specified bucket
        "1": { ownerLandHoldingDesc="Landless/Marginal (<1 Ha)",
               maleCount, femaleCount, total },
        "2": { ownerLandHoldingDesc="Small (1-1.99 Ha)", ... },
        "3": { ownerLandHoldingDesc="Semi-Medium (2-3.99 Ha)", ... },
        "4": { ownerLandHoldingDesc="Medium (4-9.99 Ha)", ... },
        "5": { ownerLandHoldingDesc="Large (>10 Ha)", ... }
    }

Per the meadow schema (``indicator.schema.json v4.4``,
``rows.items.additionalProperties: false``), the only row-level keys
allowed are ``entity_id``, ``time``, ``value``, ``facet``, plus a few
optional ones. The two facet axes (landholding x gender) are therefore
encoded into the schema-allowed ``facet`` field as
``"<landholding>|<gender>"``. The Phase 2 canonical adapter splits the
composite back into two columns
(``landholding`` + ``gender``) when it materialises to Parquet.

Facet vocabulary (12 values = 6 landholding x 2 gender):

* landholding ladder slugified from the NDLM ``ownerLandHoldingDesc``:
  ``not_specified``, ``landless_marginal``, ``small``, ``semi_medium``,
  ``medium``, ``large``
* gender: ``male`` (from ``maleCount``) and ``female`` (from
  ``femaleCount``). The publisher does NOT emit a third gender; this
  matches the NDLM upstream contract.

VINTAGE SCOPE
-------------
Default lifts ONLY FY 2024-25 (matches the seeded ``src-d98dc531ef7e``
source citation in ``datasets/taxonomy/sources.parquet``). CY 2024
remains preserved in raw and will be lifted in a follow-up PR after
the livestock_sources_seed grows to carry a CY vintage triple - same
rationale as the Pashu Aadhaar precedent (the inventory deriver
rejects heterogeneous ``time`` vocabularies within one indicator and
the seeded source vintage is FY-only today).

UNAVAILABLE STATES
------------------
NDLM upstream may return HTTP 500 for a small number of state x
endpoint combinations (Uttarakhand state-5 owner_reg returned 500 on
3 retries during the 2026-05-25 corpus pull). Such states are simply
absent from the meadow file's ``rows[]``; the lift does not invent
zero-rows. The coverage block records the number of states/districts
that DID respond so the citizen-surface can disclose the gap.

USAGE
=====
    python tools/livestock_meadow_owner_reg.py
    python tools/livestock_meadow_owner_reg.py --raw-vintages 2024-25

Output (FY-only default):
    datasets/livestock/_meadow/ndlm/2024-25/owner_reg_land_holding_district.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

# Landholding ladder. NDLM emits codes 0-5 with the descriptions captured
# in LANDHOLDING_DESC; the slug column is the schema-allowed
# (snake_case, ASCII-only) facet-value half.
# Code 0 carries ownerLandHoldingDesc=null in the NDLM payload; we slug
# it as "not_specified" rather than dropping it because for many
# districts this bucket holds the bulk of registrations (the user
# declined to declare a land-holding bracket).
LANDHOLDING: list[tuple[int, str, str]] = [
    (0, "not_specified", "Not specified (land-holding undeclared)"),
    (1, "landless_marginal", "Landless/Marginal (<1 Ha)"),
    (2, "small", "Small (1-1.99 Ha)"),
    (3, "semi_medium", "Semi-Medium (2-3.99 Ha)"),
    (4, "medium", "Medium (4-9.99 Ha)"),
    (5, "large", "Large (>10 Ha)"),
]
LANDHOLDING_SLUG_BY_CD: dict[int, str] = {cd: slug for cd, slug, _ in LANDHOLDING}

# Seeded citation vintage - the source row in datasets/taxonomy/sources.parquet
# for ndlm_owner_registration has vintage="2024-25". The meadow-path vintage
# segment must match this string per ADR-0041 nn4 + ADR-0042.
# Operator-tunable knob: when a future PR rotates the snapshot window
# (e.g. next FY) it bumps this default + the matching seed row in
# backend/yen_gov/canonical/livestock_sources_seed.py in the same
# commit. Override per-run via --meadow-snapshot.
MEADOW_SNAPSHOT_DEFAULT = "2024-25"

SOURCE_ID = "src-d98dc531ef7e"  # ndlm_owner_registration (seeded PR #276)
SOURCE_URL = (
    "https://bharatpashudhan-api.ndlm.co.in/epashu/v1/homepage/"
    "getOwnerRegLandHoldingByDistrict"
)
LICENSE = {
    "id": "GoI-Open",
    "name": "Government of India open publication",
    "url": "https://data.gov.in/government-open-data-license-india",
    "redistributable": True,
}

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = REPO_ROOT / ".runtime" / "raw" / "ndlm"
MEADOW_ROOT = REPO_ROOT / "datasets" / "livestock" / "_meadow" / "ndlm"
ENTITIES_JSON = REPO_ROOT / "datasets" / "taxonomy" / "entities.json"


def _meadow_dir(snapshot_window: str) -> Path:
    """Compute the meadow output dir for a named snapshot window.

    Lifted out of a module-level constant so the snapshot can rotate
    via --meadow-snapshot at run time without code edits. Each
    snapshot window is one operator-snapshot per ADR-0042 and FKs to
    one citation row in datasets/taxonomy/sources.parquet.
    """
    return MEADOW_ROOT / snapshot_window


def _discover_fy_raw_vintages() -> tuple[str, ...]:
    """Auto-discover FY-shaped raw vintage dirs under .runtime/raw/ndlm/.

    FY shape: ``YYYY-YY`` (e.g. ``2010-11`` through ``2025-26``).
    CY dirs (``YYYY``) are deliberately excluded because the inventory
    deriver rejects mixed CY+FY vocabularies within a single indicator;
    a future CY lift PR will add a separate ``--vintage-type cy`` mode
    that emits CY-only into separate indicator slugs.

    Returns the sorted tuple of FY raw-vintage dir names found, or
    () if RAW_ROOT does not exist (operator must then pass
    --raw-vintages explicitly).
    """
    if not RAW_ROOT.is_dir():
        return ()
    return tuple(
        sorted(
            p.name
            for p in RAW_ROOT.iterdir()
            if p.is_dir() and len(p.name) == 7 and p.name[4] == "-"
        )
    )


def _load_district_lookup() -> dict[str, str]:
    """Map LGD district code (string) -> yen-gov entity_id."""
    data = json.loads(ENTITIES_JSON.read_text(encoding="utf-8"))
    return {
        e["lgd_code"]: e["entity_id"]
        for e in data["entities"]
        if e.get("entity_type") == "district" and e.get("lgd_code")
    }


def _iter_district_landholding_rows(raw_vintage: str):
    """Yield (state_cd_str, lgd_str, district_name, lh_cd, male, female).

    Skips rows where both male and female counts are null. NDLM emits
    integer or null per gender per landholding bracket.
    """
    pattern = "owner_reg_land_holding_district_state-*.json"
    for path in sorted((RAW_ROOT / raw_vintage).glob(pattern)):
        state_cd = path.stem.split("state-")[-1]
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  skip (bad json): {path}", file=sys.stderr)
            continue
        # Owner Reg returns {data: {districtCd: row}} flat (no totalOutput
        # wrapper - distinct from Pashu Aadhaar's nested shape; see
        # tools/ndlm_download.py:_count_districts).
        outer = raw.get("data") or {}
        if not isinstance(outer, dict):
            continue
        for dist_cd_str, dist_obj in outer.items():
            if not isinstance(dist_obj, dict):
                continue
            details = dist_obj.get("details") or {}
            for lh_cd_str, lh_obj in details.items():
                try:
                    lh_cd = int(lh_cd_str)
                except (TypeError, ValueError):
                    continue
                if lh_cd not in LANDHOLDING_SLUG_BY_CD:
                    # New bracket added by NDLM after this script was
                    # written - surface as a stderr warning so we know
                    # to extend the enum, but don't crash the lift.
                    print(
                        f"  warn: unknown landholding code {lh_cd} in "
                        f"state={state_cd} district={dist_cd_str} "
                        f"({dist_obj.get('name')!r}); skipping",
                        file=sys.stderr,
                    )
                    continue
                male = lh_obj.get("maleCount")
                female = lh_obj.get("femaleCount")
                yield (
                    state_cd,
                    dist_cd_str,
                    dist_obj.get("name"),
                    lh_cd,
                    male,
                    female,
                )


def build_meadow_doc(
    raw_vintages: tuple[str, ...],
    district_lookup: dict[str, str],
) -> tuple[dict, list[tuple[str, str, str, str]]]:
    """Build the one meadow JSON dict for Owner Reg across all vintages.

    Returns (doc, unresolved). Each row carries its raw_vintage as the
    ``time`` field so the canonical adapter can decode it to a period_label.
    """
    rows: list[dict] = []
    unresolved: list[tuple[str, str, str, str]] = []
    seen_states: set[str] = set()
    seen_districts: set[str] = set()
    for raw_vintage in raw_vintages:
        for (state_cd, lgd_str, dist_name, lh_cd, male, female) in (
            _iter_district_landholding_rows(raw_vintage)
        ):
            entity_id = district_lookup.get(lgd_str)
            if entity_id is None:
                unresolved.append((raw_vintage, state_cd, lgd_str, dist_name or ""))
                continue
            seen_states.add(state_cd)
            seen_districts.add(entity_id)
            lh_slug = LANDHOLDING_SLUG_BY_CD[lh_cd]
            # Emit one row per gender per landholding. Skip null/zero
            # gender counts (publisher emits null when a (district, lh,
            # gender) combination had no registrations recorded). We
            # PRESERVE zero counts because they may be meaningful
            # (district reported, but no owners in that bracket); we
            # drop nulls only.
            if male is not None:
                rows.append(
                    {
                        "entity_id": entity_id,
                        "time": raw_vintage,
                        "value": int(male),
                        "facet": f"{lh_slug}|male",
                    }
                )
            if female is not None:
                rows.append(
                    {
                        "entity_id": entity_id,
                        "time": raw_vintage,
                        "value": int(female),
                        "facet": f"{lh_slug}|female",
                    }
                )

    # Sort by (entity_id, time, facet) so the meadow file is deterministic
    # across re-runs - byte-identical output reduces diff noise.
    rows.sort(key=lambda r: (r["entity_id"], r["time"], r["facet"]))

    description = (
        "Number of registered livestock owners on the Bharat Pashudhan "
        "portal in each district, broken down by land-holding bracket "
        "and gender. The land-holding bracket is the owner's "
        "self-declared agricultural land holding in hectares "
        "(Landless/Marginal < 1 Ha; Small 1-1.99 Ha; Semi-Medium "
        "2-3.99 Ha; Medium 4-9.99 Ha; Large > 10 Ha); the 'not "
        "specified' bucket captures owners who did not declare a "
        "land-holding at registration time and typically carries the "
        "bulk of registrations. Gender is captured by NDLM as "
        "male/female only; the upstream contract does not emit a third "
        "category. Counts are owner identity records on the portal, "
        "NOT a census of agricultural households."
    )

    fetched_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "$schema": "https://yen-gov.github.io/schemas/indicator.schema.json",
        "$schema_version": "4.4",
        "sources": [{"url": SOURCE_URL, "fetched_at": fetched_at}],
        "license": LICENSE,
        "coverage": {
            "spatial": (
                f"{len(seen_states)} states/UTs, "
                f"{len(seen_districts)} districts"
            ),
            "temporal": ", ".join(raw_vintages),
            "admin_level": "district",
        },
        "indicator": {
            "id": "livestock/owner_registration_count",
            "title": "Registered livestock owners (count)",
            "description": description,
            "entity_kind": "district",
            "time_grain": "fiscal_year",
            "value_kind": "raw",
            "direction": "neutral",
            "scale_hint": "linear",
            "unit": "owners",
            "short_unit": "owners",
            "attribution_geography": "where_resident",
            "comparability": "directional_only",
            "implementing_authority": "centre",
            "methodology_vintage": (
                f"NDLM Bharat Pashudhan; raw vintages "
                f"{list(raw_vintages)}; snapshot {fetched_at}"
            ),
            "notes": (
                "Each row's `facet` encodes a 2D facet pair as "
                "`<landholding>|<gender>` (12 combinations: 6 "
                "landholding brackets x 2 genders). The Phase 2 "
                "canonical adapter splits this composite back into "
                "separate `landholding` and `gender` columns when it "
                "materialises to "
                "`datasets/livestock/livestock_owner_registrations.parquet`. "
                "Honest-renderer (Hans): this is a count of owner "
                "registrations on the portal, NOT a census of "
                "agricultural households - coverage varies sharply by "
                "state as NDLM rollout is in progress. Each row's "
                "`time` is the raw NDLM vintage selector "
                "(`2024-25` for FY 2024-25); the canonical adapter "
                "decodes this to (period_label, year, period_seq)."
            ),
        },
        "rows": rows,
        "series_spec": {
            "description": description,
        },
        "methodology": {
            "definition": description,
            "publisher": (
                "Department of Animal Husbandry & Dairying, "
                "Ministry of Fisheries, Animal Husbandry & Dairying, "
                "Government of India"
            ),
            "publisher_methodology_url": None,
            "documentation_status": "stub",
            "methodology_breaks": [],
            "known_caveats": [
                (
                    "Owner registration coverage on the Bharat Pashudhan "
                    "portal varies sharply by state and is in active rollout; "
                    "this is a count of owner identity records on the portal, "
                    "NOT a census of agricultural households or livestock "
                    "owners overall."
                ),
                (
                    "The 'not_specified' land-holding bucket captures owners "
                    "who did not declare a land-holding bracket at "
                    "registration time and typically holds the bulk of "
                    "registrations in many districts - it is NOT an "
                    "additional methodologically distinct bracket."
                ),
                (
                    "Gender is captured by NDLM as male/female only; the "
                    "upstream contract does not emit a third category. Rows "
                    "with null gender counts are skipped (NDLM emits null "
                    "when no registrations of that gender in that bracket)."
                ),
                (
                    "Some state x vintage combinations may return HTTP 500 "
                    "from the upstream API; absent states are simply missing "
                    "from rows[] (the lift does not invent zero-rows)."
                ),
            ],
            "notes": [],
        },
        "divergence": None,
    }
    return doc, unresolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--raw-vintages",
        default="",
        help=(
            "Comma-separated raw NDLM vintages to lift. Default "
            "(empty string) auto-discovers every FY-shaped dir "
            "(YYYY-YY) under .runtime/raw/ndlm/ -- today this is the "
            "full FY 2010-11..2025-26 range. Pass an explicit list "
            "(e.g. '2024-25,2025-26') to scope the lift. The "
            "inventory deriver requires a homogeneous `time` "
            "vocabulary per indicator: CY dirs (YYYY shape) are "
            "excluded from auto-discovery because mixing CY+FY into "
            "one indicator would fail the deriver (mixed year + "
            "year_month shapes)."
        ),
    )
    parser.add_argument(
        "--meadow-snapshot",
        default=MEADOW_SNAPSHOT_DEFAULT,
        help=(
            "Operator snapshot window per ADR-0042 (the vintage "
            "segment of the meadow output path). Must match the "
            "vintage of the seeded citation row in "
            "datasets/taxonomy/sources.parquet (ndlm_owner_registration, "
            "currently 'src-d98dc531ef7e' at vintage='2024-25'). "
            "Override only when re-snapshotting in tandem with a "
            "new source seed row."
        ),
    )
    args = parser.parse_args()

    if args.raw_vintages.strip():
        raw_vintages = tuple(
            v.strip() for v in args.raw_vintages.split(",") if v.strip()
        )
    else:
        raw_vintages = _discover_fy_raw_vintages()
    if not raw_vintages:
        print(
            "ERROR: no raw vintages to lift (auto-discovery found 0 "
            "FY-shaped dirs under .runtime/raw/ndlm/; pass "
            "--raw-vintages explicitly or run tools/ndlm_download.py).",
            file=sys.stderr,
        )
        return 1

    district_lookup = _load_district_lookup()
    print(f"district lgd lookup: {len(district_lookup)} entries")
    print(f"raw vintages: {list(raw_vintages)}")
    print(f"meadow snapshot: {args.meadow_snapshot}")

    meadow_dir = _meadow_dir(args.meadow_snapshot)
    meadow_dir.mkdir(parents=True, exist_ok=True)
    doc, unresolved = build_meadow_doc(raw_vintages, district_lookup)
    row_count = len(doc["rows"])
    out_path = meadow_dir / "owner_reg_land_holding_district.json"
    out_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"  wrote {out_path.relative_to(REPO_ROOT)} ({row_count} rows)")

    print()
    print("=== summary ===")
    print(f"raw vintages lifted: {list(raw_vintages)}")
    print(f"meadow file: {out_path.relative_to(REPO_ROOT)}")
    print(f"observation rows: {row_count}")
    print(f"spatial coverage: {doc['coverage']['spatial']}")
    if unresolved:
        print(f"unresolved district LGD codes ({len(unresolved)}):")
        seen: set[tuple[str, str, str, str]] = set()
        for u in unresolved:
            if u in seen:
                continue
            seen.add(u)
            rv, sc, lc, nm = u
            print(f"  raw_vintage={rv} state={sc} lgd={lc} name={nm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
