"""Build meadow JSON for NAIP IV (NDLM) at district + national grain.

Reads ``.runtime/raw/ndlm/<raw_vintage>/naip_iv_district_state-*.json``
produced by ``tools/ndlm_download.py`` and emits ONE district meadow file
per vintage at:

    datasets/livestock/_meadow/ndlm/<vintage>/naip_iv_district.json

Plus a small national-rollup citation fixture at:

    datasets/livestock/_meadow/ndlm/<vintage>/naip_header_count_national.json

per [ADR-0041](../docs/architecture/decisions/0041-meadow-tier.md) + the
livestock NDLM ingest plan section 5.1.

ROW SHAPE
---------
NAIP IV (National AI Programme - phase IV) is a select-district AI
delivery programme administered by DAHD. Per district, the publisher
emits::

    code, name, targettedPopulation,
    totalAiDone, noOfAnimalsInseminated, totalAiUnderNaip,
    noOfFarmersBenefitted, totalPdDone,
    calvesBornMale, calvesBornFemale, totalCalves

We keep four logical metric families and drop the redundant aggregates:

* ``inseminations``     <- ``totalAiDone`` (AI events; includes repeats)
* ``pregnancy_diagnoses`` <- ``totalPdDone``
* ``calves_born``       <- ``calvesBornMale`` + ``calvesBornFemale``
* ``farmers_benefitted`` <- ``noOfFarmersBenefitted``

Dropped: ``totalAiUnderNaip`` (redundant with totalAiDone for our
purposes); ``noOfAnimalsInseminated`` (duplicates totalAiDone minus
repeat-AIs - revisit only if Hans wants the repeat-AI ratio surfaced);
``totalCalves`` (= calvesBornMale + calvesBornFemale, derivable);
``targettedPopulation`` (often null upstream).

Per the meadow schema (``indicator.schema.json v4.4``,
``rows.items.additionalProperties: false``), the only row-level keys
allowed are ``entity_id``, ``time``, ``value``, ``facet``. The metric
family + calf-sex-split is therefore encoded into the schema-allowed
``facet`` field as ``"<metric_family>|<sex_or_none>"``. The Phase 2
canonical adapter splits the composite back into separate ``metric``
+ ``sex`` columns when it materialises to
``datasets/livestock/livestock_naip_iv_outcomes.parquet`` and maps the
five composite facets onto the eight catalogue indicator slugs
(inseminations, pregnancy_diagnoses, calves_born_male,
calves_born_female, farmers_benefitted at both state + district grain).

Facet vocabulary (5 values):

* ``inseminations|none``         (sex axis collapses; AI events not animals)
* ``pregnancy_diagnoses|none``   (sex axis collapses; pregnancy = dam-only)
* ``calves_born|m``              (calvesBornMale)
* ``calves_born|f``              (calvesBornFemale)
* ``farmers_benefitted|none``    (sex axis not reported by upstream)

NATIONAL HEADER FIXTURE
-----------------------
A separate ``naip_header_count_national.json`` carries the
cumulative-across-programme rollup from
``GET /getNaipHeaderCount?year=YYYY`` (verified static across years
2022-2025). Single country-grain meadow with indicator id
``livestock/naip_header_cumulative_count`` and 3 facets
(``naip_iv|none``, ``abip|none``, ``others|none``). NOT routed to the
8 Phase 2 catalogue slugs; serves as a sanity-check cross-reference
for the totalAiDone summed across districts. The downloader does NOT
fetch this endpoint (its CLI is endpoint-keyed POST only); this lift
fetches it inline via a single GET on the first invocation per
vintage (idempotent: response cached at
``.runtime/raw/ndlm/<vintage>/naip_header_count.json``).

VINTAGE SCOPE
-------------
Default lifts ONLY FY 2024-25 (matches the seeded ``src-93a2a72db482``
source citation in ``datasets/taxonomy/sources.parquet``). CY 2024
remains preserved in raw and will be lifted in a follow-up PR after
the livestock_sources_seed grows to carry a CY vintage triple - same
rationale as the Owner Reg precedent (PR #298, Phase 1.A).

UNAVAILABLE STATES
------------------
NAIP IV is a select-district programme. The 2026-05-25 corpus pull
returned an empty ``totalOutput`` ({}) for 8 states/UTs that NDLM
does not surface on this endpoint (Andaman & Nicobar, Chandigarh,
Delhi, Kerala, Lakshadweep, Puducherry, Punjab, and Dadra & Nagar
Haveli + Daman & Diu). Such states are simply absent from the meadow
file's ``rows[]``; the lift does not invent zero-rows. The coverage
block records the number of states/districts that DID respond so the
citizen-surface can disclose the gap.

USAGE
=====
    python tools/livestock_meadow_naip_iv.py
    python tools/livestock_meadow_naip_iv.py --raw-vintages 2024-25

Output (FY-only default):
    datasets/livestock/_meadow/ndlm/2024-25/naip_iv_district.json
    datasets/livestock/_meadow/ndlm/2024-25/naip_header_count_national.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path

# Five-value composite facet vocabulary. The Phase 2 canonical adapter
# splits these back into (metric_family, sex) columns.
METRIC_FAMILY_INSEMINATIONS = "inseminations"
METRIC_FAMILY_PREGNANCY_DIAGNOSES = "pregnancy_diagnoses"
METRIC_FAMILY_CALVES_BORN = "calves_born"
METRIC_FAMILY_FARMERS_BENEFITTED = "farmers_benefitted"
SEX_NONE = "none"
SEX_MALE = "m"
SEX_FEMALE = "f"

# Seeded citation vintage - the source row in datasets/taxonomy/sources.parquet
# for ndlm_naip_iv (src-93a2a72db482) has vintage="2024-25". The meadow-path
# vintage segment must match this string per ADR-0041 nn4 + ADR-0042.
# Operator-tunable knob: when a future PR rotates the snapshot window
# (e.g. next FY) it bumps this default + the matching seed row in
# backend/yen_gov/canonical/livestock_sources_seed.py in the same
# commit. Override per-run via --meadow-snapshot.
MEADOW_SNAPSHOT_DEFAULT = "2024-25"

SOURCE_ID = "src-93a2a72db482"  # ndlm_naip_iv (seeded PR #276)
SOURCE_URL_DISTRICT = (
    "https://bharatpashudhan-api.ndlm.co.in/epashu/v1/homepage/"
    "getNaipIVDistrict"
)
SOURCE_URL_HEADER = (
    "https://bharatpashudhan-api.ndlm.co.in/epashu/v1/homepage/"
    "getNaipHeaderCount"
)
LICENSE = {
    "id": "GoI-Open",
    "name": "Government of India open publication",
    "url": "https://data.gov.in/government-open-data-license-india",
    "redistributable": True,
}

UA = "yen-gov-recon/1.0 (research)"

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

# Header endpoint returns 3 programme rollups: NAIP IV, ABIP, Others.
HEADER_PROGRAMME_SLUGS = {
    "NAIP IV": "naip_iv",
    "ABIP": "abip",
    "Others": "others",
}


def _load_district_lookup() -> dict[str, str]:
    """Map LGD district code (string) -> yen-gov entity_id."""
    data = json.loads(ENTITIES_JSON.read_text(encoding="utf-8"))
    return {
        e["lgd_code"]: e["entity_id"]
        for e in data["entities"]
        if e.get("entity_type") == "district" and e.get("lgd_code")
    }


def _iter_district_rows(raw_vintage: str):
    """Yield (state_cd, lgd_str, district_name, payload_dict).

    ``payload_dict`` is the raw NDLM district object with all metric
    keys preserved; the caller decides which keys to emit.
    """
    pattern = "naip_iv_district_state-*.json"
    for path in sorted((RAW_ROOT / raw_vintage).glob(pattern)):
        state_cd = path.stem.split("state-")[-1]
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  skip (bad json): {path}", file=sys.stderr)
            continue
        # NAIP IV returns {data: {totalOutput: {districtCd: row}}}
        # (distinct from Owner Reg's flat {data: {districtCd: row}}).
        outer = raw.get("data") or {}
        if not isinstance(outer, dict):
            continue
        total_output = outer.get("totalOutput") or {}
        if not isinstance(total_output, dict):
            continue
        for dist_cd_str, dist_obj in total_output.items():
            if not isinstance(dist_obj, dict):
                continue
            yield (state_cd, dist_cd_str, dist_obj.get("name"), dist_obj)


def _emit_district_rows(
    state_cd: str,
    entity_id: str,
    raw_vintage: str,
    payload: dict,
) -> list[dict]:
    """Emit up to 5 rows for one district from one NAIP IV payload.

    Skips any metric where the upstream value is null. Preserves zero
    values (a district may genuinely have reported zero of one metric).
    """
    rows: list[dict] = []
    pairs = [
        (
            METRIC_FAMILY_INSEMINATIONS,
            SEX_NONE,
            payload.get("totalAiDone"),
        ),
        (
            METRIC_FAMILY_PREGNANCY_DIAGNOSES,
            SEX_NONE,
            payload.get("totalPdDone"),
        ),
        (
            METRIC_FAMILY_CALVES_BORN,
            SEX_MALE,
            payload.get("calvesBornMale"),
        ),
        (
            METRIC_FAMILY_CALVES_BORN,
            SEX_FEMALE,
            payload.get("calvesBornFemale"),
        ),
        (
            METRIC_FAMILY_FARMERS_BENEFITTED,
            SEX_NONE,
            payload.get("noOfFarmersBenefitted"),
        ),
    ]
    for family, sex, value in pairs:
        if value is None:
            continue
        rows.append(
            {
                "entity_id": entity_id,
                "time": raw_vintage,
                "value": int(value),
                "facet": f"{family}|{sex}",
            }
        )
    return rows


def build_district_meadow_doc(
    raw_vintages: tuple[str, ...],
    district_lookup: dict[str, str],
) -> tuple[dict, list[tuple[str, str, str, str]]]:
    """Build the one district meadow JSON dict across all vintages.

    Returns (doc, unresolved).
    """
    rows: list[dict] = []
    unresolved: list[tuple[str, str, str, str]] = []
    seen_states: set[str] = set()
    seen_districts: set[str] = set()
    for raw_vintage in raw_vintages:
        for (state_cd, lgd_str, dist_name, payload) in (
            _iter_district_rows(raw_vintage)
        ):
            entity_id = district_lookup.get(lgd_str)
            if entity_id is None:
                unresolved.append(
                    (raw_vintage, state_cd, lgd_str, dist_name or "")
                )
                continue
            district_rows = _emit_district_rows(
                state_cd, entity_id, raw_vintage, payload
            )
            if not district_rows:
                # All metrics null - skip district. Don't count it as
                # seen (no observation reached the meadow file).
                continue
            seen_states.add(state_cd)
            seen_districts.add(entity_id)
            rows.extend(district_rows)

    rows.sort(key=lambda r: (r["entity_id"], r["time"], r["facet"]))

    description = (
        "NAIP IV (National AI Programme, phase IV) outcomes per "
        "district: artificial-insemination events, pregnancy "
        "diagnoses, calves born (split by sex), and farmers benefitted. "
        "NAIP IV is a select-district programme administered by the "
        "Department of Animal Husbandry & Dairying; many states/UTs "
        "(Kerala, Punjab, Puducherry, and most island UTs) report zero "
        "coverage. AI counts reflect events, not unique animals, so "
        "repeat inseminations on the same dam are counted multiple "
        "times."
    )

    fetched_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "$schema": "https://yen-gov.github.io/schemas/indicator.schema.json",
        "$schema_version": "4.4",
        "sources": [{"url": SOURCE_URL_DISTRICT, "fetched_at": fetched_at}],
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
            "id": "livestock/naip_iv_outcomes_count",
            "title": "NAIP IV outcomes (count)",
            "description": description,
            "entity_kind": "district",
            "time_grain": "fiscal_year",
            "value_kind": "raw",
            "direction": "neutral",
            "scale_hint": "linear",
            "unit": "count",
            "short_unit": "count",
            "attribution_geography": "where_administered",
            "comparability": "directional_only",
            "implementing_authority": "centre",
            "methodology_vintage": (
                f"NDLM Bharat Pashudhan; raw vintages "
                f"{list(raw_vintages)}; snapshot {fetched_at}"
            ),
            "notes": (
                "Each row's `facet` encodes a 2D facet pair as "
                "`<metric_family>|<sex>` (5 combinations: 4 metric "
                "families x sex; sex collapses to `none` for "
                "inseminations, pregnancy diagnoses, and farmers "
                "benefitted; sex splits to `m`/`f` for calves born). "
                "The Phase 2 canonical adapter splits this composite "
                "back into separate `metric` and `sex` columns when it "
                "materialises to "
                "`datasets/livestock/livestock_naip_iv_outcomes.parquet`. "
                "Honest-renderer (Hans): AI counts are EVENTS (repeat "
                "inseminations on the same dam are counted multiple "
                "times); NAIP IV is select-district (states with zero "
                "coverage are NOT failures, they are out-of-scope). "
                "Each row's `time` is the raw NDLM vintage selector "
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
                    "NAIP IV is a select-district programme; many states "
                    "and UTs (Kerala, Punjab, Puducherry, most island "
                    "UTs) report zero coverage on this endpoint. Absent "
                    "states are simply missing from rows[]; the lift "
                    "does not invent zero-rows."
                ),
                (
                    "Insemination counts are EVENTS, not unique animals; "
                    "repeat AIs on the same dam are counted multiple "
                    "times. Pregnancy diagnoses count dam-level events "
                    "(one per pregnancy check), so a single repeat-AI "
                    "dam may contribute multiple inseminations but at "
                    "most one diagnosis per cycle."
                ),
                (
                    "Calves born rows are emitted only when the upstream "
                    "sex split is non-null; districts that report "
                    "totalCalves but not the m/f split are skipped on "
                    "the calves rows (the inseminations and pregnancy "
                    "diagnoses rows for that district are still "
                    "emitted)."
                ),
                (
                    "Some state x vintage combinations may return HTTP 500 "
                    "from the upstream API; absent states are simply "
                    "missing from rows[]. Header-cumulative national "
                    "totals (see naip_header_count_national.json) serve "
                    "as a cross-check but cover all programmes "
                    "(NAIP IV + ABIP + Others) at the national grain."
                ),
            ],
            "notes": [],
        },
        "divergence": None,
    }
    return doc, unresolved


def _fetch_header(raw_vintage: str) -> dict:
    """Fetch ``getNaipHeaderCount?year=YYYY``; cache the raw response.

    The header endpoint is GET-only (distinct from the per-state
    POST endpoint covered by tools/ndlm_download.py); fetch it inline.
    Cache the raw response under .runtime/raw/ndlm/<vintage>/ for
    re-runs.
    """
    year_param = raw_vintage.split("-")[0]
    cache_path = RAW_ROOT / raw_vintage / "naip_header_count.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.is_file():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    req = urllib.request.Request(
        f"{SOURCE_URL_HEADER}?year={year_param}",
        headers={"User-Agent": UA},
    )
    raw = urllib.request.urlopen(req, timeout=30).read()
    cache_path.write_bytes(raw)
    return json.loads(raw)


def build_header_meadow_doc(raw_vintages: tuple[str, ...]) -> dict:
    """Build the national-grain cumulative-rollup meadow JSON dict.

    Emits one row per (vintage, programme) where programme is one of
    NAIP IV / ABIP / Others. Note: values are CUMULATIVE NATIONAL
    totals across all years since programme inception; the upstream
    endpoint accepts a ``?year=YYYY`` parameter but the response has
    been verified static across years 2022-2025. We still bind the
    rows to the snapshot vintage so the canonical adapter can
    distinguish snapshot points if the upstream behaviour changes.
    """
    rows: list[dict] = []
    seen_programmes: set[str] = set()
    for raw_vintage in raw_vintages:
        parsed = _fetch_header(raw_vintage)
        data = parsed.get("data") or {}
        for upstream_name, slug in HEADER_PROGRAMME_SLUGS.items():
            value = data.get(upstream_name)
            if value is None:
                continue
            seen_programmes.add(slug)
            rows.append(
                {
                    "entity_id": "IN",
                    "time": raw_vintage,
                    "value": int(value),
                    "facet": f"{slug}|none",
                }
            )

    rows.sort(key=lambda r: (r["entity_id"], r["time"], r["facet"]))

    description = (
        "Cumulative national rollup of breeding-programme outcomes "
        "(artificial-insemination events) reported by the Bharat "
        "Pashudhan header endpoint. Values are CUMULATIVE since "
        "programme inception across all years; the upstream "
        "endpoint accepts a year parameter but returns the same "
        "numbers across years 2022-2025. Reported per programme: "
        "NAIP IV (National AI Programme phase IV), ABIP (Accelerated "
        "Breed Improvement Programme), and Others (residual). Serves "
        "as a sanity-check cross-reference for the district-grain "
        "naip_iv_district.json; not routed to the Phase 2 catalogue "
        "indicator slugs."
    )

    fetched_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "$schema": "https://yen-gov.github.io/schemas/indicator.schema.json",
        "$schema_version": "4.4",
        "sources": [{"url": SOURCE_URL_HEADER, "fetched_at": fetched_at}],
        "license": LICENSE,
        "coverage": {
            "spatial": "1 country (India)",
            "temporal": ", ".join(raw_vintages),
            "admin_level": "country",
        },
        "indicator": {
            "id": "livestock/naip_header_cumulative_count",
            "title": "Bharat Pashudhan header cumulative rollup (count)",
            "description": description,
            "entity_kind": "country",
            "time_grain": "fiscal_year",
            "value_kind": "raw",
            "direction": "neutral",
            "scale_hint": "linear",
            "unit": "count",
            "short_unit": "count",
            "attribution_geography": "where_administered",
            "comparability": "directional_only",
            "implementing_authority": "centre",
            "methodology_vintage": (
                f"NDLM Bharat Pashudhan header endpoint; "
                f"raw vintages {list(raw_vintages)}; "
                f"snapshot {fetched_at}"
            ),
            "notes": (
                "Each row's `facet` encodes the programme as "
                "`<programme>|none` (3 values: naip_iv, abip, others). "
                "Sanity-check fixture: the NAIP IV programme total "
                "here is the cumulative all-years rollup and should "
                "EXCEED the FY 2024-25 sum of district `inseminations` "
                "rows in naip_iv_district.json (which is a single "
                "fiscal year). Not routed to the Phase 2 catalogue "
                "indicator slugs."
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
                    "Values are CUMULATIVE national rollups since "
                    "programme inception; the upstream year parameter "
                    "is accepted but the response is verified static "
                    "across years 2022-2025."
                ),
                (
                    "The 'Others' bucket is a residual category and is "
                    "NOT methodologically equivalent to the named "
                    "programmes (NAIP IV, ABIP); treat it as 'all other "
                    "AI events reported through Bharat Pashudhan'."
                ),
                (
                    "Serves as a national sanity-check ONLY; the "
                    "Phase 2 canonical adapter does NOT route this "
                    "indicator to any of the 8 catalogue slugs and "
                    "the cumulative semantics make it unsuitable for "
                    "year-over-year comparison."
                ),
            ],
            "notes": [],
        },
        "divergence": None,
    }
    return doc


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
            "datasets/taxonomy/sources.parquet (ndlm_naip_iv, "
            "currently 'src-93a2a72db482' at vintage='2024-25'). "
            "Override only when re-snapshotting in tandem with a "
            "new source seed row."
        ),
    )
    parser.add_argument(
        "--skip-header",
        action="store_true",
        help=(
            "Skip the national header rollup fetch + emit. Default is "
            "to emit naip_header_count_national.json alongside the "
            "district file."
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

    # 1. District meadow.
    district_doc, unresolved = build_district_meadow_doc(
        raw_vintages, district_lookup
    )
    district_rows = len(district_doc["rows"])
    district_path = meadow_dir / "naip_iv_district.json"
    district_path.write_text(
        json.dumps(district_doc, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"  wrote {district_path.relative_to(REPO_ROOT)} "
        f"({district_rows} rows)"
    )

    # 2. National header meadow (sanity-check fixture).
    header_rows = 0
    if not args.skip_header:
        header_doc = build_header_meadow_doc(raw_vintages)
        header_rows = len(header_doc["rows"])
        header_path = meadow_dir / "naip_header_count_national.json"
        header_path.write_text(
            json.dumps(header_doc, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(
            f"  wrote {header_path.relative_to(REPO_ROOT)} "
            f"({header_rows} rows)"
        )

    print()
    print("=== summary ===")
    print(f"raw vintages lifted: {list(raw_vintages)}")
    print(f"district observation rows: {district_rows}")
    print(f"spatial coverage: {district_doc['coverage']['spatial']}")
    print(f"national header rows: {header_rows}")
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
