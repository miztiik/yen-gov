"""One-state download proof — Tamil Nadu (stateCd=33), year 2024, both CY+FY.

Writes raw NDLM HTTP responses to:
  .runtime/raw/ndlm/<vintage>/<endpoint>_<stateCd>.json   (gitignored, ephemeral)

Per Gregor's verdict B: snapshot tier lives at `.runtime/raw/ndlm/...`,
ephemeral, gitignored. This is the PROOF that the pipeline endpoint set works.
A real ingest PR will loop all 36 states × N years × 5 endpoints; this proof
hits just 5 endpoints × 1 state × 2 vintages (CY 2024, FY 2024-25) so the
plan can cite concrete byte counts and shape.

USAGE: python tools/ndlm_download_proof.py
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

API = "https://bharatpashudhan-api.ndlm.co.in/epashu/v1/homepage/"
UA = "yen-gov-recon/1.0 (research)"
HEADERS = {"User-Agent": UA, "Content-Type": "application/json"}

STATE_CD = 33  # Tamil Nadu (LGD=33)

ENDPOINTS = {
    "owner_reg_land_holding_district":  "getOwnerRegLandHoldingByDistrict",
    "animal_registration_district":     "getAnimalRegistrationDistrictWise",
    "nadcp_vaccination_district":       "getNADCPVaccinationDistrictWise",
    "naip_iv_district":                 "getNaipIVDistrict",
    # breeding endpoint: NDLM exposes per-programme rather than one composite.
    # Use NAIP IV as the AI proxy; ABIP/RGM are separate dashboards (out of
    # scope for the proof). The plan-doc itemises the full breeding decomp.
}

VINTAGES = [
    ("2024",    {"isYearFinancial": False, "year": 2024}),  # CY 2024
    ("2024-25", {"isYearFinancial": True,  "year": 2024}),  # FY 2024-25
]


def fetch(endpoint: str, body: dict) -> bytes:
    payload = json.dumps(body).encode("utf-8")
    # NADCP needs extra keys (diseaseCd, roundNumber, isRoundWise).
    # Server tolerates omission (returns empty) but we add sentinels for fidelity.
    if endpoint == "getNADCPVaccinationDistrictWise":
        # Default to FMD (diseaseCd=1; commonest disease) round-aggregate.
        # A real ingest loops all disease codes; this is a single proof.
        payload = json.dumps({**body, "diseaseCd": 1, "roundNumber": None, "isRoundWise": False}).encode("utf-8")
    req = urllib.request.Request(API + endpoint, data=payload, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=30).read()


def main() -> None:
    total_bytes = 0
    rows_summary: list[dict] = []
    for vintage, body in VINTAGES:
        body = {**body, "stateCd": STATE_CD}
        out_dir = Path(".runtime/raw/ndlm") / vintage
        out_dir.mkdir(parents=True, exist_ok=True)
        for stem, endpoint in ENDPOINTS.items():
            out = out_dir / f"{stem}_state-{STATE_CD}.json"
            print(f"  {vintage}  {endpoint}  stateCd={STATE_CD} ...", end=" ", flush=True)
            raw = fetch(endpoint, body)
            out.write_bytes(raw)
            size = len(raw)
            total_bytes += size
            # parse + summarise
            try:
                parsed = json.loads(raw)
                outer = parsed.get("data") or {}
                if isinstance(outer, dict) and "totalOutput" in outer:
                    n = len(outer["totalOutput"])
                elif isinstance(outer, dict):
                    n = len(outer)  # owner-reg returns {districtCd: row} flat
                elif isinstance(outer, list):
                    n = len(outer)
                else:
                    n = 0
                rows_summary.append({"vintage": vintage, "endpoint": endpoint, "districts": n, "bytes": size, "file": out.as_posix()})
                print(f"OK {size:,} bytes, {n} districts")
            except Exception as e:
                rows_summary.append({"vintage": vintage, "endpoint": endpoint, "error": str(e), "bytes": size, "file": out.as_posix()})
                print(f"PARSE-ERROR {e}")
            time.sleep(0.2)

    print("")
    print(f"=== PROOF SUMMARY (Tamil Nadu, stateCd={STATE_CD}, 2024 CY + 2024-25 FY) ===")
    print(f"Total HTTP bytes: {total_bytes:,}")
    print(f"Files written:    {len(rows_summary)}")
    print("")
    for r in rows_summary:
        if "districts" in r:
            print(f"  {r['vintage']:>8}  {r['endpoint']:<42}  {r['districts']:>3} districts  {r['bytes']:>7,} B  -> {r['file']}")
        else:
            print(f"  {r['vintage']:>8}  {r['endpoint']:<42}  ERROR: {r['error']}")

    # Persist summary alongside snapshot for the plan-doc to cite.
    summary_path = Path(".runtime/raw/ndlm/_recon/tn-proof-summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps({
        "stateCd": STATE_CD,
        "stateName": "TAMIL NADU",
        "total_bytes": total_bytes,
        "rows": rows_summary,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSummary: {summary_path.as_posix()}")


if __name__ == "__main__":
    main()
