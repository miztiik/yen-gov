"""One-shot LGD-district recon — does NDLM district `code` ≡ LGD-district-code?

Per Gregor's verdict (G in subagent report): the #1 architectural risk for the
livestock family is whether NDLM's district `code` field (576=Karur, 577=Krishnagiri
etc.) is the same numeric space as the LGD MoHA district code held in
`datasets/taxonomy/entities.parquet WHERE entity_type='district'` (PR #267's
784-row backfill).

This script:
1. Pulls NDLM `getNaipIVDistrict` for ALL 36 states for year 2024 (CY).
2. Collects the union of district `code` values that NDLM returns.
3. Loads yen-gov's `entities.json` and extracts every `lgd_code` where
   `entity_type=='district'`.
4. Prints (a) NDLM count, (b) yen-gov count, (c) intersection, (d) NDLM-only
   (would be silently FK-dropped by the writer), (e) yen-gov-only (would be
   missing data).

Output written to .runtime/raw/ndlm/_recon/lgd-district-alignment.json so the
plan-doc can cite an exact number.

USAGE: python tools/ndlm_recon_lgd_districts.py
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://bharatpashudhan-api.ndlm.co.in/epashu/v1/homepage/"
UA = "yen-gov-recon/1.0 (https://github.com/<your-handle>/yen-gov; research)"
HEADERS = {"User-Agent": UA, "Content-Type": "application/json"}

OUT_DIR = Path(".runtime/raw/ndlm/_recon")
OUT_DIR.mkdir(parents=True, exist_ok=True)
SUMMARY = OUT_DIR / "lgd-district-alignment.json"


def fetch_states() -> list[dict]:
    req = urllib.request.Request(API + "getState", headers={"User-Agent": UA})
    return json.loads(urllib.request.urlopen(req, timeout=15).read())["data"]


def fetch_naip_districts(state_cd: int, year: int = 2024) -> dict:
    payload = json.dumps({
        "isYearFinancial": False,
        "year": year,
        "stateCd": state_cd,
    }).encode("utf-8")
    req = urllib.request.Request(API + "getNaipIVDistrict", data=payload, headers=HEADERS)
    try:
        body = urllib.request.urlopen(req, timeout=15).read()
        return json.loads(body)
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}", "_body": e.read()[:200].decode("utf-8", "replace")}
    except Exception as e:
        return {"_error": str(e)}


def load_yen_gov_lgd_districts() -> dict[str, str]:
    """Returns {lgd_code: entity_id} for every entity_type=='district' row."""
    entities = json.loads(Path("datasets/taxonomy/entities.json").read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for e in entities["entities"]:
        if e.get("entity_type") != "district":
            continue
        lgd = e.get("lgd_code")
        if lgd:
            # Normalize: store as string; LGD codes in yen-gov are strings ("06", "28").
            out[str(int(lgd))] = e["entity_id"]
    return out


def main() -> None:
    print("[1/3] Loading yen-gov LGD-district map...")
    lgd_map = load_yen_gov_lgd_districts()
    print(f"      yen-gov districts with lgd_code: {len(lgd_map)}")

    print("[2/3] Fetching NDLM states...")
    states = fetch_states()
    print(f"      NDLM states: {len(states)}")

    ndlm_district_codes: dict[str, dict] = {}  # code -> {name, stateCd, stateName}
    failed_states: list[dict] = []

    print("[3/3] Walking states for NAIP IV district sets...")
    for i, s in enumerate(states):
        state_cd = s["stateCode"]
        state_name = s["stateName"]
        if i and i % 5 == 0:
            time.sleep(0.4)  # be polite to NDLM
        else:
            time.sleep(0.1)
        resp = fetch_naip_districts(state_cd, 2024)
        if "_error" in resp:
            failed_states.append({"stateCd": state_cd, "stateName": state_name, "error": resp["_error"]})
            print(f"  [{i+1:02d}/36] {state_cd:>2} {state_name:<35} ERROR: {resp['_error']}")
            continue
        out_block = (resp.get("data") or {}).get("totalOutput") or {}
        for code_s, row in out_block.items():
            code = str(int(code_s))
            ndlm_district_codes[code] = {
                "name": row.get("name"),
                "stateCd": state_cd,
                "stateName": state_name,
            }
        print(f"  [{i+1:02d}/36] {state_cd:>2} {state_name:<35} +{len(out_block):>3} districts (running total: {len(ndlm_district_codes)})")

    ndlm_set = set(ndlm_district_codes.keys())
    yen_set = set(lgd_map.keys())
    intersect = sorted(ndlm_set & yen_set, key=int)
    ndlm_only = sorted(ndlm_set - yen_set, key=int)
    yen_only = sorted(yen_set - ndlm_set, key=int)

    summary = {
        "$generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ndlm_district_count": len(ndlm_set),
        "yen_gov_lgd_district_count": len(yen_set),
        "intersection_count": len(intersect),
        "ndlm_only_count": len(ndlm_only),
        "yen_gov_only_count": len(yen_only),
        "failed_states": failed_states,
        "ndlm_only_sample_first_20": [
            {"code": c, **ndlm_district_codes[c]} for c in ndlm_only[:20]
        ],
        "yen_gov_only_sample_first_20": yen_only[:20],
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("")
    print("=== ALIGNMENT REPORT ===")
    print(f"NDLM district codes returned (union over 36 states): {len(ndlm_set)}")
    print(f"yen-gov district lgd_codes (PR #267 backfill):       {len(yen_set)}")
    print(f"Intersection (joinable rows):                        {len(intersect)}")
    print(f"NDLM-only (would FK-drop in writer):                 {len(ndlm_only)}")
    print(f"yen-gov-only (would be missing from NDLM data):      {len(yen_only)}")
    if failed_states:
        print(f"Failed-state fetches: {len(failed_states)}  (see {SUMMARY.as_posix()})")
    print(f"\nFull report: {SUMMARY.as_posix()}")


if __name__ == "__main__":
    main()
