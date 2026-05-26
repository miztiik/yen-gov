"""Build meadow JSON for Pashu Aadhaar (NDLM) at district + species granularity.

Reads ``.runtime/raw/ndlm/<raw_vintage>/animal_registration_district_state-*.json``
produced by ``tools/ndlm_download.py`` and emits per-species meadow files
under ``datasets/livestock/_meadow/ndlm/2024-25/`` per ADR-0041.

One meadow file per species, holding observation rows for BOTH raw
vintages NDLM exposes (CY 2024 + FY 2024-25). The meadow path's
``2024-25`` vintage segment matches the (producer, title, vintage)
triple that PR #276 seeded into ``sources.parquet`` (see
``backend/yen_gov/canonical/livestock_sources_seed.py``); per ADR-0041
non-negotiable #4 + ADR-0042, the meadow-path vintage MUST equal an
existing citation row's vintage. The CY 2024 vs FY 2024-25 distinction
is carried on each observation row via its ``time`` field (decoded
into ``period_label`` by the canonical adapter's ``parse_ndlm_period``).

The district-level grand total is a compute-on-read parent (no meadow
file, no observation rows) per the energy ``national-installed-capacity-mw``
precedent. Gender breakdown is retained in the raw responses
(``.runtime/raw/ndlm/``) and may be lifted to a ``-male`` / ``-female``
grandchild indicator family in a follow-up PR.

Hans honest-renderer doctrine: "Pashu Aadhaar count" is the count of
animals issued a Pashu Aadhaar tag, NOT the actual livestock population
of the district. Coverage varies by state (rollout in progress) so the
indicator carries ``comparability="directional_only"`` and
``renderer_rules=["no_rank_table"]`` at the catalogue level.

Usage::

    python tools/livestock_meadow_pashu_aadhaar.py
    python tools/livestock_meadow_pashu_aadhaar.py --raw-vintages 2024-25
    python tools/livestock_meadow_pashu_aadhaar.py --species cattle,buffalo

Output: ``datasets/livestock/_meadow/ndlm/2024-25/district-pashu-aadhaar-count-<species>.json``
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

# Species enum derived from the full Pashu Aadhaar corpus walk (10 NDLM species).
# (speciesCd, kebab-slug, display name, citizen-readable description noun)
SPECIES: list[tuple[int, str, str, str]] = [
    (1, "cattle", "Cattle", "cattle"),
    (2, "buffalo", "Buffalo", "buffaloes"),
    (3, "yak", "Yak", "yaks"),
    (4, "mithun", "Mithun", "mithun"),
    (5, "sheep", "Sheep", "sheep"),
    (6, "goat", "Goat", "goats"),
    (7, "pig", "Pig", "pigs"),
    (10, "horse", "Horse", "horses"),
    (11, "donkey", "Donkey", "donkeys"),
    (12, "mule", "Mule", "mules"),
]

# Seeded citation vintage - the source row in datasets/taxonomy/sources.parquet
# for ndlm_pashu_aadhaar has vintage="2024-25". The meadow-path vintage segment
# must match this string per ADR-0041 nn4 + ADR-0042.
# Operator-tunable knob: when a future PR rotates the snapshot window
# (e.g. next FY) it bumps this default + the matching seed row in
# backend/yen_gov/canonical/livestock_sources_seed.py in the same
# commit. Override per-run via --meadow-snapshot.
MEADOW_SNAPSHOT_DEFAULT = "2024-25"

SOURCE_ID = "src-7e5d4aac4995"  # ndlm_pashu_aadhaar (seeded in PR #276)
SOURCE_URL = (
    "https://bharatpashudhan-api.ndlm.co.in/epashu/v1/homepage/"
    "getAnimalRegistrationDistrictWise"
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
    """Map LGD district code (string) -> yen-gov entity_id.

    Mirrors ``yen_gov.canonical.lgd.load_district_lookup`` (extracted
    in PR #_pending_, plan-doc Q#4 / Gregor verdict E). This tool keeps
    its own copy to remain runnable as a standalone script without a
    backend import path; future NDLM meadow tools (owner_reg, naip_iv,
    nadcp, breeding) MUST import the canonical resolver instead of
    inlining a third copy (rule-of-three trigger).
    """
    data = json.loads(ENTITIES_JSON.read_text(encoding="utf-8"))
    return {
        e["lgd_code"]: e["entity_id"]
        for e in data["entities"]
        if e.get("entity_type") == "district" and e.get("lgd_code")
    }


def _iter_district_observations(raw_vintage: str):
    """Yield (lgd_code_str, state_code_str, district_name, species_cd, value_total)."""
    pattern = "animal_registration_district_state-*.json"
    for path in sorted((RAW_ROOT / raw_vintage).glob(pattern)):
        state_cd = path.stem.split("state-")[-1]
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  skip (bad json): {path}", file=sys.stderr)
            continue
        total_output = (raw.get("data") or {}).get("totalOutput") or {}
        if not isinstance(total_output, dict):
            continue
        for dist_cd_str, dist_obj in total_output.items():
            details = dist_obj.get("details") or {}
            for sp_cd_str, sp_obj in details.items():
                try:
                    sp_cd = int(sp_cd_str)
                except (TypeError, ValueError):
                    continue
                total = sp_obj.get("total")
                if total is None:
                    continue
                yield (
                    dist_cd_str,
                    state_cd,
                    dist_obj.get("name"),
                    sp_cd,
                    int(total),
                )


def build_meadow_for_species(
    raw_vintages: tuple[str, ...],
    species_cd: int,
    species_slug: str,
    species_display: str,
    species_noun: str,
    district_lookup: dict[str, str],
) -> tuple[dict, list[tuple[str, str, str, str]]]:
    """Build meadow JSON dict for one species across all raw vintages.

    Returns (doc, unresolved). Each row carries its raw_vintage as the
    ``time`` field so the canonical adapter can decode it to a period_label.
    """
    rows: list[dict] = []
    unresolved: list[tuple[str, str, str, str]] = []
    seen_states: set[str] = set()
    seen_districts: set[str] = set()
    for raw_vintage in raw_vintages:
        for (lgd_str, state_cd, dist_name, sp_cd, value) in (
            _iter_district_observations(raw_vintage)
        ):
            if sp_cd != species_cd:
                continue
            entity_id = district_lookup.get(lgd_str)
            if entity_id is None:
                unresolved.append((raw_vintage, state_cd, lgd_str, dist_name or ""))
                continue
            rows.append(
                {"entity_id": entity_id, "time": raw_vintage, "value": value}
            )
            seen_states.add(state_cd)
            seen_districts.add(entity_id)

    # Sort by (entity_id, time) so the meadow file is deterministic across
    # re-runs - byte-identical output reduces diff noise.
    rows.sort(key=lambda r: (r["entity_id"], r["time"]))

    description = (
        f"Number of {species_noun} tagged with Pashu Aadhaar (NDLM) in "
        f"each district. Pashu Aadhaar is the UIDAI-style 12-digit tag "
        f"issued by the National Digital Livestock Mission to individual "
        f"animals; the count here is a count of tags issued, NOT an "
        f"estimate of the actual {species_noun} population of the "
        f"district. Coverage varies by state as the rollout is in progress."
    )

    fetched_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "$schema": "https://yen-gov.github.io/schemas/indicator.schema.json",
        "$schema_version": "4.4",
        "sources": [{"url": SOURCE_URL, "fetched_at": fetched_at}],
        "license": LICENSE,
        "coverage": {
            "spatial": f"{len(seen_states)} states/UTs, {len(seen_districts)} districts",
            "temporal": ", ".join(raw_vintages),
            "admin_level": "district",
        },
        "indicator": {
            "id": f"livestock/pashu_aadhaar_count_{species_slug}",
            "title": f"Pashu Aadhaar tagged - {species_display}",
            "description": description,
            "entity_kind": "district",
            "time_grain": "fiscal_year",
            "value_kind": "raw",
            "direction": "neutral",
            "scale_hint": "linear",
            "unit": "animals",
            "short_unit": "head",
            "attribution_geography": "where_resident",
            "comparability": "directional_only",
            "implementing_authority": "centre",
            "methodology_vintage": (
                f"NDLM Bharat Pashudhan; raw vintages "
                f"{list(raw_vintages)}; snapshot {fetched_at}"
            ),
            "notes": (
                "Hans honest-renderer: tagged count is NOT a livestock-population "
                "estimate. Indicator carries renderer_rules=[no_rank_table] in the "
                "canonical catalogue. Animals without a recorded total are skipped "
                "(NDLM may emit null totals for species with only male xor female "
                "counts present). Each row's `time` is the raw NDLM vintage "
                "selector (`2024` for CY 2024, `2024-25` for FY 2024-25); the "
                "canonical adapter decodes this to (period_label, year, period_seq)."
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
                "Pashu Aadhaar tagging coverage varies sharply by state and is in active rollout; this is a tag-count, not a livestock population estimate.",
                "Animals without a recorded total are skipped (NDLM emits null total when only male xor female sub-counts are present).",
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
            "datasets/taxonomy/sources.parquet (ndlm_pashu_aadhaar, "
            "currently 'src-7e5d4aac4995' at vintage='2024-25'). "
            "Override only when re-snapshotting in tandem with a "
            "new source seed row."
        ),
    )
    parser.add_argument(
        "--species",
        default=None,
        help="Comma-separated species slugs to lift (default: all 10).",
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

    species_filter = None
    if args.species:
        species_filter = {s.strip() for s in args.species.split(",") if s.strip()}

    district_lookup = _load_district_lookup()
    print(f"district lgd lookup: {len(district_lookup)} entries")
    print(f"raw vintages: {list(raw_vintages)}")
    print(f"meadow snapshot: {args.meadow_snapshot}")

    total_files = 0
    total_rows = 0
    all_unresolved: dict[tuple[str, str, str, str], int] = {}
    meadow_dir = _meadow_dir(args.meadow_snapshot)
    meadow_dir.mkdir(parents=True, exist_ok=True)
    for sp_cd, sp_slug, sp_display, sp_noun in SPECIES:
        if species_filter is not None and sp_slug not in species_filter:
            continue
        doc, unresolved = build_meadow_for_species(
            raw_vintages, sp_cd, sp_slug, sp_display, sp_noun, district_lookup
        )
        row_count = len(doc["rows"])
        out_path = meadow_dir / f"district-pashu-aadhaar-count-{sp_slug}.json"
        out_path.write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"  wrote {out_path.relative_to(REPO_ROOT)} ({row_count} rows)")
        total_files += 1
        total_rows += row_count
        for u in unresolved:
            all_unresolved[u] = all_unresolved.get(u, 0) + 1

    print()
    print("=== summary ===")
    print(f"raw vintages lifted: {list(raw_vintages)}")
    print(f"meadow files written: {total_files} under {meadow_dir.relative_to(REPO_ROOT)}")
    print(f"observation rows: {total_rows}")
    if all_unresolved:
        print(f"unresolved district LGD codes ({len(all_unresolved)}):")
        for (rv, sc, lc, nm), cnt in sorted(all_unresolved.items()):
            print(
                f"  raw_vintage={rv} state={sc} lgd={lc} name={nm}  "
                f"(skipped in {cnt} species cuts)"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
