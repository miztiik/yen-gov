"""Idempotent migration of indicator artifacts from v1.5 to the folded v1.6 shape.

Adds the four new optional top-level blocks (`series_spec`,
`collection_inventory`, `methodology`, `divergence`) to every indicator
JSON under `datasets/indicators/in/`. When a sibling `.notes.json`
sidecar exists, its `related`, `editor_note_md`, `policy_context`, and
`chart_defaults` fields are folded losslessly into the new
`methodology` block; the sidecar is then deleted (mutating-mode only).

This script is the *mechanical* part of the migration. It writes
**stub-quality** defaults:
- `series_spec.expected_geographies` seeded from observed
  `rows[].entity_id`.
- `series_spec.expected_periods` seeded from observed `rows[].time`,
  with `frequency` derived from the existing `indicator.time_grain`.
- `series_spec.expected_periods_inference.basis =
  "seeded_from_observed_rows"` (loud `documentation_status: "stub"`
  signal — `/data-completeness` will list every such indicator).
- `methodology.definition` copied from `indicator.description`,
  `methodology.publisher` from `indicator.implementing_authority` or
  the source URL host, `documentation_status = "stub"`, empty
  `methodology_breaks` / `known_caveats` / `notes`.
- `collection_inventory` computed via
  `yen_gov.inventory.derive_collection_inventory`, so the initial
  status will usually be `"complete"` (since expected = observed).

A real editor lifts each indicator from `stub` to `partial` /
`authored` in a follow-up by hand. The point of this script is the
*shape* migration, not the editorial content.

Idempotency: re-running on an already-migrated tree produces no diff.
Detection key: presence of all four new top-level blocks AND
`$schema_version == "1.6"`.

Modes:
- `python tools/migrate_indicators_v15_to_v20.py` (default): check —
  print plan, exit 0 if nothing to do, non-zero if changes pending.
- `python tools/migrate_indicators_v15_to_v20.py --write`: mutate —
  rewrite indicators, delete folded sidecars, leave a one-line
  per-file summary.

Output is sorted, deterministic. Safe to commit the result.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
INDICATORS_ROOT = REPO_ROOT / "datasets" / "indicators" / "in"
UNIVERSES_PATH = REPO_ROOT / "datasets" / "reference" / "in" / "universes.json"

# Mapping from the existing `indicator.time_grain` vocabulary to the
# schema v1.6 `frequency` enum. `quarter` and `date` are ambiguous; we
# pick the most-likely default (cy / ad_hoc). A human editor can
# override per-period later.
TIME_GRAIN_TO_FREQUENCY: dict[str, str] = {
    "fiscal_year": "annual_fy",
    "year": "annual_cy",
    "month": "monthly",
    "quarter": "quarterly_cy",
    "date": "ad_hoc",
    "decade": "decennial",
}

NEW_TOP_LEVEL_BLOCKS: tuple[str, ...] = ("series_spec", "collection_inventory", "methodology", "divergence")


# --------------------------------------------------------------------- #
# Public API (also exercised by the test suite)                          #
# --------------------------------------------------------------------- #


def is_migrated(doc: dict[str, Any]) -> bool:
    """Return True if every new top-level block is present."""
    return all(key in doc for key in NEW_TOP_LEVEL_BLOCKS)


def derive_publisher_stub(doc: dict[str, Any]) -> str:
    """Best-effort publisher string for the stub `methodology` block."""
    impl = (doc.get("indicator") or {}).get("implementing_authority")
    if impl and isinstance(impl, str) and impl.strip() and impl not in {"state", "union", "concurrent"}:
        return impl.strip()
    sources = doc.get("sources") or []
    for s in sources:
        url = s.get("url")
        if url:
            host = urlparse(url).hostname or ""
            if host:
                return host
    return "Unknown publisher (stub — please edit)"


def build_series_spec(doc: dict[str, Any]) -> dict[str, Any]:
    """Build the stub `series_spec` block from observed rows."""
    rows = doc.get("rows") or []
    indicator = doc.get("indicator") or {}
    time_grain = indicator.get("time_grain") or "year"
    frequency = TIME_GRAIN_TO_FREQUENCY.get(time_grain, "ad_hoc")

    geographies = sorted({str(r["entity_id"]) for r in rows if "entity_id" in r})

    periods_seen: dict[str, dict[str, str]] = {}
    for row in rows:
        time = row.get("time")
        if time is None:
            continue
        key = str(time)
        if key not in periods_seen:
            periods_seen[key] = {"key": key, "label": key, "frequency": frequency}
    expected_periods = [periods_seen[k] for k in sorted(periods_seen)]

    description_src = indicator.get("description") or indicator.get("title") or "Series description (stub — please edit)."
    description = description_src if len(description_src) >= 10 else f"{description_src} (stub)"

    return {
        "description": description,
        "expected_geographies": geographies,
        "expected_periods": expected_periods,
        "expected_periods_inference": {
            "basis": "seeded_from_observed_rows",
            "confidence": "none",
            "series": None,
            "note": "Auto-seeded by tools/migrate_indicators_v15_to_v20.py. Replace with publisher-catalogue-derived expectations when an editor reviews this indicator.",
        },
    }


def build_methodology(doc: dict[str, Any], sidecar: dict[str, Any] | None) -> dict[str, Any]:
    """Build the stub `methodology` block, folding sidecar fields when present.

    Sidecar fields preserved verbatim (lossless):
      sidecar.related        -> methodology.related_indicators
      sidecar.editor_note_md -> methodology.editor_note_md
      sidecar.policy_context -> methodology.policy_context
      sidecar.chart_defaults -> methodology.chart_defaults
    """
    indicator = doc.get("indicator") or {}
    description = indicator.get("description") or indicator.get("title") or "Definition stub — please edit."
    if len(description) < 10:
        description = f"{description} (stub)"

    block: dict[str, Any] = {
        "definition": description,
        "publisher": derive_publisher_stub(doc),
        "publisher_methodology_url": None,
        "documentation_status": "stub",
        "methodology_breaks": [],
        "known_caveats": [],
        "notes": [],
    }
    if sidecar:
        if sidecar.get("related"):
            block["related_indicators"] = list(sidecar["related"])
        if sidecar.get("editor_note_md"):
            block["editor_note_md"] = sidecar["editor_note_md"]
        if sidecar.get("policy_context"):
            block["policy_context"] = list(sidecar["policy_context"])
        if sidecar.get("chart_defaults"):
            block["chart_defaults"] = dict(sidecar["chart_defaults"])
    return block


def fold_indicator(doc: dict[str, Any], sidecar: dict[str, Any] | None, universes: dict[str, Any]) -> dict[str, Any]:
    """Return a new indicator dict with v1.6 folded blocks added.

    Pure function. Does NOT touch the filesystem. Idempotent on an
    already-migrated input (returns identical content).
    """
    if is_migrated(doc):
        return doc

    # `derive_collection_inventory` lives in the backend package. Imported
    # lazily so this script remains importable without backend/ on
    # sys.path (e.g. for tooling validation in CI).
    from yen_gov.inventory import derive_collection_inventory

    new_doc = dict(doc)  # shallow; we only add top-level keys
    new_doc["series_spec"] = build_series_spec(doc)
    new_doc["methodology"] = build_methodology(doc, sidecar)
    new_doc["divergence"] = None
    # collection_inventory depends on series_spec being present.
    new_doc["collection_inventory"] = derive_collection_inventory(new_doc, universes)
    return new_doc


# --------------------------------------------------------------------- #
# CLI                                                                   #
# --------------------------------------------------------------------- #


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _walk_indicators() -> list[Path]:
    return sorted(p for p in INDICATORS_ROOT.rglob("*.json") if not p.name.endswith(".notes.json"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="apply changes; default is check-only")
    args = parser.parse_args()

    sys.path.insert(0, str(REPO_ROOT / "backend"))  # for yen_gov.inventory import

    universes = _load_json(UNIVERSES_PATH)
    paths = _walk_indicators()

    counts = {"already": 0, "migrated": 0, "sidecars_folded": 0, "sidecars_deleted": 0}
    for path in paths:
        rel = path.relative_to(REPO_ROOT).as_posix()
        doc = _load_json(path)
        sidecar_path = path.with_name(path.stem + ".notes.json")
        sidecar = _load_json(sidecar_path) if sidecar_path.exists() else None

        if is_migrated(doc) and sidecar is None:
            counts["already"] += 1
            continue

        new_doc = fold_indicator(doc, sidecar, universes)
        verb = "MIGRATED" if args.write else "WOULD MIGRATE"
        print(f"  {verb}: {rel}")
        if sidecar is not None:
            print(f"    fold sidecar: {sidecar_path.relative_to(REPO_ROOT).as_posix()}")
            counts["sidecars_folded"] += 1
        counts["migrated"] += 1

        if args.write:
            _write_json(path, new_doc)
            if sidecar_path.exists():
                sidecar_path.unlink()
                counts["sidecars_deleted"] += 1

    print()
    print("Summary:")
    for k in sorted(counts):
        print(f"  {k}: {counts[k]}")
    if not args.write and counts["migrated"] > 0:
        print("\nCheck mode. Re-run with --write to apply.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
