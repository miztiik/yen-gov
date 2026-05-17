"""One-shot: bump $schema_version of every indicator artifact to 4.1
AND retag the four cadence-unambiguous witnesses with `indicator.cadence`.

Per ADR-0027 + TODO/20260517-coverage-temporal-range-plan.md Phase #1.5.

Schema bump v4.0 -> v4.1 is additive (new optional `indicator.cadence`),
but the strict $schema_version == x-version invariant (per v2.0
changelog) forces every artifact's stamp to roll forward. Three witnesses
(RBI external balance, CEA capacity pipeline, HDI) deliberately do NOT
get a cadence here — they need an adapter-quality audit first; see ADR
"Open questions" section.

Safe to re-run.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_VERSION = "4.1"
INDICATORS_DIR = ROOT / "datasets" / "indicators" / "in"

# Cadence retags driven by the Phase #1 spike. Only the four UNAMBIGUOUS
# cases are retagged here; #3 RBI / #4 CEA / #8 HDI remain pending audit.
CADENCE_RETAGS: dict[str, str] = {
    "demography/state_population_by_residence_count.json": "decennial",
    "demography/state_population_by_sex_count.json": "decennial",
    "environment/india_ghg_emissions_by_subsector_ggco2e.json": "ad_hoc",
    "environment/india_ghg_emissions_mtco2e_by_sector.json": "ad_hoc",
}


def _apply_cadence(doc: dict, cadence: str) -> bool:
    """Insert `cadence` into the `indicator` block at a stable position
    (right after `time_grain`). Returns True if the doc changed.
    """
    ind = doc.get("indicator")
    if not isinstance(ind, dict):
        return False
    if ind.get("cadence") == cadence:
        return False
    new_ind: "OrderedDict[str, object]" = OrderedDict()
    inserted = False
    for k, v in ind.items():
        new_ind[k] = v
        if k == "time_grain" and not inserted:
            new_ind["cadence"] = cadence
            inserted = True
    if not inserted:
        new_ind["cadence"] = cadence
    doc["indicator"] = dict(new_ind)
    return True


def main() -> int:
    if not INDICATORS_DIR.exists():
        print(f"missing: {INDICATORS_DIR}", file=sys.stderr)
        return 1
    n_version_changed = 0
    n_cadence_changed = 0
    n_total = 0
    for path in sorted(INDICATORS_DIR.rglob("*.json")):
        if path.name.endswith(".notes.json"):
            continue
        n_total += 1
        text = path.read_text(encoding="utf-8")
        doc = json.loads(text)
        changed = False

        rel = path.relative_to(INDICATORS_DIR).as_posix()
        if rel in CADENCE_RETAGS:
            if _apply_cadence(doc, CADENCE_RETAGS[rel]):
                changed = True
                n_cadence_changed += 1

        if doc.get("$schema_version") != TARGET_VERSION:
            doc["$schema_version"] = TARGET_VERSION
            changed = True
            n_version_changed += 1

        if changed:
            new_text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
            path.write_text(new_text, encoding="utf-8")

    print(
        f"bumped $schema_version on {n_version_changed} / {n_total} artifact(s) to v{TARGET_VERSION}"
    )
    print(f"applied cadence on {n_cadence_changed} witness(es)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
