"""S03 Assam Tier-4 district fallback snapshot generator.

Generates `datasets/boundaries/in/ac/state=in_s03/all.geojson` as 126 features
where each AC's geometry is its parent district's polygon, sourced from the
all-India districts shard at `datasets/boundaries/in/districts/all.geojson`.

This is the Tier-4 fallback for S03 Assam per A.1.b of
`docs/archive/plans/20260529-boundary-rip-and-replace-plan.md`. Tier-1 (LGD pre-2023) was
exhausted; Tier-3 (Aug 2023 Delimitation Order PDF vectorisation) is
deferred-feasible (~40-60h manual QGIS work, see
`docs/archive/notes/2026-05-29-s03-pdf-probe-verdict.md`); Tier-4 is the immediate
interim that fixes the systematic citizen mis-binding bug (current pre-2023
HTL ACs have 0.8% name parity to post-2023 SoT).

The output features carry:
- `ac_no` (lowercase, 1-based post-2023 ECI numbering, matches SoT eci_no)
- `ac_name` (post-2023 SoT name)
- `reservation` (from SoT)
- `parent_district_id` (3-letter SoT mnemonic)
- `parent_district_lgd` (numeric LGD code)
- `parent_district_name` (full district name from districts geojson)
- `derivation_method` (literal "district-fallback-t4")
- `geometry` (deep copy of parent district's polygon)

Run from worker repo root:
  C:\\Python314\\python.exe tools/boundaries/s03_t4_district_fallback.py
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


# 35-entry mapping from SoT 3-letter district_id codes to dist_lgd numeric
# codes. Authored 2026-05-29 by joining `datasets/reference/in/states/S03/
# constituencies.json` district_ids with Assam districts in
# `datasets/boundaries/in/districts/all.geojson` (stname='ASSAM' subset,
# 35 districts). SRI = Sribhumi (Karimganj renamed in Feb 2024); KAR =
# Karbi Anglong (the SoT uses 3-letter mnemonic, not Karimganj).
SOT_CODE_TO_DIST_LGD: dict[str, int] = {
    "BAK": 616,  # Baksa
    "BJL": 739,  # Bajali
    "BNG": 281,  # Bongaigaon
    "BPT": 280,  # Barpeta
    "BSW": 705,  # Biswanath
    "CAC": 282,  # Cachar
    "CHA": 708,  # Charaideo
    "CHR": 612,  # Chirang
    "DAR": 283,  # Darrang
    "DBR": 286,  # Dibrugarh
    "DHA": 299,  # Dima Hasao
    "DHE": 284,  # Dhemaji
    "DHU": 285,  # Dhubri
    "GLP": 287,  # Goalpara
    "GOL": 288,  # Golaghat
    "HAI": 289,  # Hailakandi
    "HOJ": 709,  # Hojai
    "JOR": 290,  # Jorhat
    "KAM": 291,  # Kamrup
    "KAR": 292,  # Karbi Anglong
    "KMM": 618,  # Kamrup Metro
    "KOK": 294,  # Kokrajhar
    "LAK": 295,  # Lakhimpur
    "MAJ": 706,  # Majuli
    "MOR": 296,  # Marigaon (Morigaon)
    "NAL": 298,  # Nalbari
    "NGN": 297,  # Nagaon
    "SIV": 300,  # Sivasagar
    "SON": 301,  # Sonitpur
    "SRI": 293,  # Sribhumi (was Karimganj before Feb 2024 rename)
    "SSM": 707,  # South Salmara Mancachar
    "TAM": 756,  # Tamulpur
    "TIN": 302,  # Tinsukia
    "UDA": 617,  # Udalguri
    "WKA": 710,  # West Karbi Anglong
}


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]

    sot_path = repo_root / "datasets/reference/in/states/S03/constituencies.json"
    districts_path = repo_root / "datasets/boundaries/in/districts/all.geojson"
    out_path = repo_root / "datasets/boundaries/in/ac/state=in_s03/all.geojson"

    sot = json.loads(sot_path.read_text(encoding="utf-8"))
    districts = json.loads(districts_path.read_text(encoding="utf-8"))

    # Index Assam districts by dist_lgd.
    assam_by_lgd: dict[int, dict] = {}
    for feat in districts["features"]:
        props = feat["properties"]
        if props.get("stname") != "ASSAM":
            continue
        assam_by_lgd[int(props["dist_lgd"])] = feat

    expected_lgds = set(SOT_CODE_TO_DIST_LGD.values())
    actual_lgds = set(assam_by_lgd.keys())
    missing = expected_lgds - actual_lgds
    extra = actual_lgds - expected_lgds
    if missing:
        print(f"FAIL: {len(missing)} mapped dist_lgds not found in Assam districts: {sorted(missing)}", file=sys.stderr)
        return 2
    if extra:
        print(f"NOTE: {len(extra)} Assam districts not referenced by SoT: {sorted(extra)}")

    # Sanity-check SoT codes are all mapped.
    sot_codes = {c["district_id"] for c in sot["constituencies"]}
    unmapped = sot_codes - SOT_CODE_TO_DIST_LGD.keys()
    if unmapped:
        print(f"FAIL: {len(unmapped)} SoT district_ids without mapping: {sorted(unmapped)}", file=sys.stderr)
        return 2

    # Build the 126 fallback features.
    out_features = []
    for c in sot["constituencies"]:
        eci_no = int(c["eci_no"])
        name = c["name"]
        district_id = c["district_id"]
        reservation = c.get("reservation", "GEN")

        dist_lgd = SOT_CODE_TO_DIST_LGD[district_id]
        district_feat = assam_by_lgd[dist_lgd]
        district_props = district_feat["properties"]

        out_features.append({
            "type": "Feature",
            "properties": {
                "ac_no": eci_no,
                "ac_name": name,
                "reservation": reservation,
                "parent_district_id": district_id,
                "parent_district_lgd": dist_lgd,
                "parent_district_name": district_props["dtname"],
                "state_lgd": int(district_props["state_lgd"]),
                "st_name": district_props["stname"],
                "derivation_method": "district-fallback-t4",
            },
            "geometry": copy.deepcopy(district_feat["geometry"]),
        })

    out_features.sort(key=lambda f: f["properties"]["ac_no"])

    out = {
        "type": "FeatureCollection",
        "features": out_features,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, separators=(",", ":")) + "\n", encoding="utf-8")

    size = out_path.stat().st_size
    print(f"OK: wrote {len(out_features)} features to {out_path.relative_to(repo_root).as_posix()} ({size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
