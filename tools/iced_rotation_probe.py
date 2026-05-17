"""Probe alternate paths for the 9 path-rotation failures from
.runtime/iced_recon/triage_20260517075101.csv (Phase 1 step 2).

Usage:
    .\\.venv\\Scripts\\python.exe tools\\iced_rotation_probe.py

For each failing endpoint, tries a small fixed list of likely alternate
paths and reports HTTP status. Output is human-eyeballable; no artifact
is produced.
"""
from __future__ import annotations

import io
import sys
import time
import urllib.error
import urllib.request


sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


HOST = "https://icedapi.niti.gov.in"
V1 = f"{HOST}/v1"

# (label, current-failing-path, [candidate-alternatives])
CANDIDATES: list[tuple[str, str, list[str]]] = [
    ("distinct_values", "/distinct-values", [
        "/distinct-values",  # 400 — likely needs a parameter
        "/distinctValues",
        "/distinct-values?key=state",
        "/distinct-values?type=state",
        "/distinct-values?for=state",
        "/v1/distinct-values",
        "/v1/distinct-values?key=state",
    ]),
    ("home_map", "/homeMap", [
        "/homeMap",
        "/home-map",
        "/v1/homeMap",
        "/v1/home-map",
    ]),
    ("power_generation", "/energy/generation", [
        "/energy/generation",
        "/energy/electricity/generation",
        "/energy/electricity/capacity/generation",
        "/v1/energy/generation",
        "/v1/generation",
        "/v1/power-generation",
        "/energy/powerGeneration",
    ]),
    ("retired_capacity_plants", "/retired-capacity-plants", [
        "/retired-capacity-plants",
        "/v1/retired-capacity-plants",
        "/energy/retired-capacity-plants",
        "/energy/electricity/retired-capacity-plants",
        "/energy/electricity/capacity/retired",
        "/v1/retiredCapacityPlants",
    ]),
    ("plant_pipeline_info", "/plantPipelineInfo", [
        "/plantPipelineInfo",
        "/v1/plantPipelineInfo",
        "/v1/plant-pipeline-info",
        "/energy/plantPipelineInfo",
        "/energy/electricity/plant-pipeline-info",
        "/energy/electricity/capacity/upcoming",
    ]),
    ("power_plants_listing", "/powerPlantsListing", [
        "/powerPlantsListing",
        "/v1/powerPlantsListing",
        "/v1/power-plants-listing",
        "/energy/powerPlantsListing",
        "/energy/electricity/power-plants-listing",
    ]),
    ("plant_list_by_source", "/plantListBySource", [
        "/plantListBySource",
        "/v1/plantListBySource",
        "/v1/plant-list-by-source",
        "/energy/plantListBySource",
        "/energy/electricity/plant-list-by-source",
    ]),
    ("capacity_metatable", "/capacity-metatable-data", [
        "/capacity-metatable-data",
        "/v1/capacity-metatable-data",
        "/energy/capacity-metatable-data",
        "/energy/electricity/capacity-metatable-data",
        "/energy/capacityMetatableData",
    ]),
    ("discoms_list", "/discoms", [
        "/discoms",
        "/v1/discoms",
        "/energy/discoms",
        "/energy/electricity/distribution/discoms",
        "/discomsList",
        "/v1/discoms-list",
    ]),
]


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def probe(path: str) -> tuple[int, int]:
    """Return (status, content_length). status=-1 on connection error."""
    url = f"{HOST}{path}"
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://iced.niti.gov.in/",
        "Origin": "https://iced.niti.gov.in",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read()
            return (resp.status, len(body))
    except urllib.error.HTTPError as e:
        return (e.code, 0)
    except Exception:
        return (-1, 0)


def main() -> int:
    for label, current, paths in CANDIDATES:
        print(f"\n=== {label}  (current: {current}) ===", flush=True)
        for p in paths:
            status, length = probe(p)
            marker = "OK " if status == 200 else "   "
            print(f"  {marker}[{status:>4}] {length:>8}B  {p}", flush=True)
            time.sleep(0.25)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
