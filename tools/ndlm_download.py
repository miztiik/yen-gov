"""Bulk NDLM snapshot downloader - all states x {CY,FY} x 4 endpoints.

Generalises `tools/ndlm_download_proof.py` (1 state, 4 endpoints, 2 vintages)
to walk the full 36-state corpus. Writes raw HTTP responses to:

    .runtime/raw/ndlm/<vintage>/<endpoint>_state-<stateCd>.json   (gitignored)

Per ADR-0041 (meadow tier) + Gregor verdict B (snapshot tier under .runtime/):
nothing this tool writes lands in `datasets/`. The meadow lift (PR 3+) is the
gatekeeper that converts these raw snapshots into committed meadow JSON.

USAGE
=====
  # Default: all states discovered via NDLM /getState, both vintages, all 4 endpoints
  python tools/ndlm_download.py

  # Subset (debugging or rate-limit-friendly partial runs):
  python tools/ndlm_download.py --states 33,29        # TN + Karnataka only
  python tools/ndlm_download.py --endpoints pashu_aadhaar,nadcp_vaccination
  python tools/ndlm_download.py --years 2024-25       # FY only

  # Force re-download (default: skip files that already exist on disk):
  python tools/ndlm_download.py --force

  # Custom sleep between calls (default 0.2s; raise if NDLM throttles):
  python tools/ndlm_download.py --sleep 0.5

OUTPUT
======
1. Raw JSON: .runtime/raw/ndlm/<vintage>/<endpoint-stem>_state-<stateCd>.json
2. Summary:  .runtime/raw/ndlm/_summary.json   (one row per (state, vintage, endpoint))

The summary is what downstream meadow-lift PRs cite to know which files exist
and how many districts each contains.

DESIGN NOTES
============
- Idempotent: skips existing files unless --force. Lets you resume a partial
  download after a network blip without re-hammering NDLM.
- Polite: 0.2s sleep between calls + extra 0.4s every 5th call (matches the
  recon tool's pattern). Configurable via --sleep.
- 3-attempt retry on connection errors / 5xx (1s + 4s + 16s backoff).
- 4 endpoints covered: owner_reg, animal_registration (Pashu Aadhaar), NADCP
  vaccination, NAIP IV. Breeding (ABIP/RGM) endpoints are dashboard-level not
  per-state-endpoint - out of scope for this tool; covered by a separate
  discovery PR.

NOT IN SCOPE
============
- Writing to datasets/ - this is the snapshot tier only.
- Producing meadow JSON - PR 3 (Pashu Aadhaar) and PRs 5-7 do that.
- Pagination / cursors - all 4 endpoints return the full state's district
  set in a single response (verified by proof + recon).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://bharatpashudhan-api.ndlm.co.in/epashu/v1/homepage/"
UA = "yen-gov-recon/1.0 (research)"
HEADERS = {"User-Agent": UA, "Content-Type": "application/json"}

ENDPOINTS = {
    "owner_reg_land_holding_district": "getOwnerRegLandHoldingByDistrict",
    "animal_registration_district":    "getAnimalRegistrationDistrictWise",
    "nadcp_vaccination_district":      "getNADCPVaccinationDistrictWise",
    "naip_iv_district":                "getNaipIVDistrict",
}

# Short alias map for CLI --endpoints flag.
ALIASES = {
    "owner_reg":          "owner_reg_land_holding_district",
    "pashu_aadhaar":      "animal_registration_district",
    "animal_reg":         "animal_registration_district",
    "nadcp":              "nadcp_vaccination_district",
    "nadcp_vaccination":  "nadcp_vaccination_district",
    "naip":               "naip_iv_district",
    "naip_iv":            "naip_iv_district",
}

VINTAGE_BODIES = {
    "2024":    {"isYearFinancial": False, "year": 2024},  # CY 2024
    "2024-25": {"isYearFinancial": True,  "year": 2024},  # FY 2024-25
}

OUT_ROOT = Path(".runtime/raw/ndlm")
SUMMARY_PATH = OUT_ROOT / "_summary.json"

MAX_RETRIES = 3
RETRY_BACKOFFS = [1.0, 4.0, 16.0]


def fetch_states() -> list[dict]:
    """Discover all states from NDLM /getState - returns list of {stateCode, stateName}."""
    req = urllib.request.Request(API + "getState", headers={"User-Agent": UA})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())["data"]


def _fetch_once(endpoint: str, body: dict) -> bytes:
    """Single HTTP POST to an NDLM endpoint."""
    payload = json.dumps(body).encode("utf-8")
    # NADCP needs extra disease-code keys; defaults below match the proof tool.
    if endpoint == "getNADCPVaccinationDistrictWise":
        payload = json.dumps({**body, "diseaseCd": 1, "roundNumber": None, "isRoundWise": False}).encode("utf-8")
    req = urllib.request.Request(API + endpoint, data=payload, headers=HEADERS)
    return urllib.request.urlopen(req, timeout=30).read()


def fetch_with_retry(endpoint: str, body: dict) -> bytes:
    """Retry on connection error / 5xx up to 3 attempts with exponential backoff."""
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return _fetch_once(endpoint, body)
        except urllib.error.HTTPError as e:
            # Only retry 5xx; 4xx (bad request) is terminal.
            if e.code < 500:
                raise
            last_err = e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_BACKOFFS[attempt])
    raise RuntimeError(f"Gave up after {MAX_RETRIES} attempts: {last_err}")


def _count_districts(raw: bytes) -> int:
    """Inspect parsed NDLM payload and return the district-row count (0 on parse error)."""
    try:
        parsed = json.loads(raw)
    except Exception:
        return 0
    outer = parsed.get("data") or {}
    if isinstance(outer, dict) and "totalOutput" in outer:
        v = outer["totalOutput"]
        return len(v) if isinstance(v, (dict, list)) else 0
    if isinstance(outer, dict):
        return len(outer)  # owner-reg returns {districtCd: row} flat
    if isinstance(outer, list):
        return len(outer)
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--states", default="", help="Comma-separated state codes (LGD). Default: all NDLM states.")
    p.add_argument("--endpoints", default="", help=f"Comma-separated endpoint names or aliases. Default: all 4. Names: {','.join(ENDPOINTS)}. Aliases: {','.join(ALIASES)}.")
    p.add_argument("--years", default="", help=f"Comma-separated vintages. Default: all. Options: {','.join(VINTAGE_BODIES)}.")
    p.add_argument("--sleep", type=float, default=0.2, help="Seconds to sleep between calls. Default 0.2.")
    p.add_argument("--force", action="store_true", help="Re-download even if file exists on disk.")
    return p.parse_args()


def resolve_endpoints(arg: str) -> dict[str, str]:
    if not arg:
        return dict(ENDPOINTS)
    out: dict[str, str] = {}
    for token in (t.strip() for t in arg.split(",") if t.strip()):
        canonical = ALIASES.get(token, token)
        if canonical not in ENDPOINTS:
            raise SystemExit(f"Unknown endpoint: {token!r}. Valid: {','.join(ENDPOINTS)} or aliases {','.join(ALIASES)}.")
        out[canonical] = ENDPOINTS[canonical]
    return out


def resolve_vintages(arg: str) -> dict[str, dict]:
    if not arg:
        return dict(VINTAGE_BODIES)
    out: dict[str, dict] = {}
    for token in (t.strip() for t in arg.split(",") if t.strip()):
        if token not in VINTAGE_BODIES:
            raise SystemExit(f"Unknown vintage: {token!r}. Valid: {','.join(VINTAGE_BODIES)}.")
        out[token] = VINTAGE_BODIES[token]
    return out


def resolve_states(arg: str) -> list[dict]:
    all_states = fetch_states()
    if not arg:
        return all_states
    wanted = {int(t.strip()) for t in arg.split(",") if t.strip()}
    out = [s for s in all_states if s["stateCode"] in wanted]
    missing = wanted - {s["stateCode"] for s in all_states}
    if missing:
        raise SystemExit(f"State codes not found in NDLM /getState: {sorted(missing)}")
    return out


def main() -> int:
    args = parse_args()
    endpoints = resolve_endpoints(args.endpoints)
    vintages = resolve_vintages(args.years)
    print("[1/2] Discovering NDLM states...")
    states = resolve_states(args.states)
    print(f"      States to walk: {len(states)}")
    print(f"      Endpoints:      {','.join(endpoints)}")
    print(f"      Vintages:       {','.join(vintages)}")
    total_calls = len(states) * len(endpoints) * len(vintages)
    print(f"      Total calls:    {total_calls}")
    print(f"      Polite sleep:   {args.sleep}s between calls (+0.4s every 5th)")
    print(f"      Force re-fetch: {args.force}")

    print("[2/2] Walking corpus...")
    summary_rows: list[dict] = []
    failures: list[dict] = []
    skipped = 0
    fetched = 0
    total_bytes = 0
    call_idx = 0

    for vintage, vintage_body in vintages.items():
        out_dir = OUT_ROOT / vintage
        out_dir.mkdir(parents=True, exist_ok=True)
        for state in states:
            state_cd = state["stateCode"]
            state_name = state["stateName"]
            body = {**vintage_body, "stateCd": state_cd}
            for stem, endpoint in endpoints.items():
                out_path = out_dir / f"{stem}_state-{state_cd}.json"
                call_idx += 1
                if out_path.exists() and not args.force:
                    skipped += 1
                    size = out_path.stat().st_size
                    raw = out_path.read_bytes()
                    districts = _count_districts(raw)
                    summary_rows.append({
                        "vintage": vintage, "stateCd": state_cd, "stateName": state_name,
                        "endpoint": endpoint, "districts": districts, "bytes": size,
                        "file": out_path.as_posix(), "status": "skip-existing",
                    })
                    continue
                prefix = f"  [{call_idx:>4d}/{total_calls}]"
                try:
                    raw = fetch_with_retry(endpoint, body)
                    out_path.write_bytes(raw)
                    size = len(raw)
                    total_bytes += size
                    districts = _count_districts(raw)
                    fetched += 1
                    summary_rows.append({
                        "vintage": vintage, "stateCd": state_cd, "stateName": state_name,
                        "endpoint": endpoint, "districts": districts, "bytes": size,
                        "file": out_path.as_posix(), "status": "ok",
                    })
                    print(f"{prefix} {vintage} {state_cd:>2} {state_name:<22} {stem:<36} OK {size:>7,}B {districts:>3}d")
                except Exception as e:  # pragma: no cover - defensive
                    failures.append({
                        "vintage": vintage, "stateCd": state_cd, "stateName": state_name,
                        "endpoint": endpoint, "error": str(e),
                    })
                    print(f"{prefix} {vintage} {state_cd:>2} {state_name:<22} {stem:<36} FAIL {e}")
                # Polite sleep: extra every 5th call.
                sleep_for = args.sleep + (0.4 if call_idx % 5 == 0 else 0.0)
                time.sleep(sleep_for)

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps({
        "total_calls":  total_calls,
        "fetched":      fetched,
        "skipped":      skipped,
        "failures":     len(failures),
        "total_bytes":  total_bytes,
        "rows":         summary_rows,
        "errors":       failures,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print("")
    print("=== BULK DOWNLOAD SUMMARY ===")
    print(f"  Total calls:       {total_calls}")
    print(f"  Fetched new:       {fetched}")
    print(f"  Skipped (existed): {skipped}")
    print(f"  Failures:          {len(failures)}")
    print(f"  Total bytes new:   {total_bytes:,}")
    print(f"  Summary file:      {SUMMARY_PATH.as_posix()}")
    if failures:
        print("  Re-run to retry; --force to overwrite skipped files.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
