"""Backfill ``concept_id`` FK on every row of
``datasets/taxonomy/indicators.json`` (guardrail #13, PR-Z3b-tail-conceptFK
Carve 1).

Strategy per ``docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md``
section Z3b-tail:

1. For each indicator row, derive ``(noun, unit, normalisation, entity_kind)``
   tuple from existing fields:

   * ``noun`` = ``label_short``
   * ``unit`` = ``unit`` (passed verbatim to find_overlap)
   * ``normalisation`` = derived from ``value_kind`` + ``unit`` heuristics
     (mirrors the rules the PR-Z3a seed used; output enum
     ``{absolute, share, index, ratio, per_capita, per_area}``)
   * ``entity_kind`` = ``default_entity_kind``

2. Call ``find_overlap()`` against ``concepts.json``. If the best match
   scores >= 0.95, FK to it.

3. Otherwise auto-mint a stub concept derived from ``label_short`` (kebab
   ``^[a-z][a-z0-9]*(-[a-z0-9]+)*$``, max 40 chars; collision -> ``-2``,
   ``-3``, ...). Add the stub to ``concepts.json`` with
   ``description_short = "Auto-minted stub for indicator <id>."`` and FK to
   it. Stubs are flagged by their description prefix so Tier-B follow-ups
   and human curators can identify them.

Idempotent: re-running over already-backfilled input is a no-op (rows
that already carry ``concept_id`` are skipped; auto-mint stub concepts
that already exist in concepts.json keep their description).

Usage::

    python -m tools.migrate.backfill_concept_id_fk

or::

    python tools/migrate/backfill_concept_id_fk.py

Re-emit ``indicators.parquet`` via ``python -m yen_gov emit-taxonomy``
after running this script.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from yen_gov.canonical.concept_registry import find_overlap  # noqa: E402

INDICATORS_PATH = ROOT / "datasets" / "taxonomy" / "indicators.json"
CONCEPTS_PATH = ROOT / "datasets" / "taxonomy" / "concepts.json"
HIGH_CONFIDENCE_THRESHOLD = 0.95
STUB_DESCRIPTION_PREFIX = "Auto-minted stub for indicator "


def derive_normalisation(row: dict) -> str:
    """Map an indicator row to a concept ``normalisation`` enum value."""

    value_kind = row.get("value_kind", "")
    unit = (row.get("unit") or "").lower()
    if (
        value_kind == "percentage"
        or unit in ("%", "percent")
        or unit.endswith("_pct")
        or "share" in unit
    ):
        return "share"
    if value_kind == "index" or "index" in unit:
        return "index"
    if value_kind == "rate":
        return "ratio"
    if "per_capita" in unit or "per capita" in unit:
        return "per_capita"
    if "per_km" in unit or "/km" in unit or "per_sq_km" in unit:
        return "per_area"
    return "absolute"


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 40) -> str:
    """Kebab-case a label short, capped at ``max_len`` chars."""

    slug = _SLUG_RE.sub("-", text.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    if not slug or not slug[0].isalpha():
        slug = "x-" + slug
    return slug[:max_len].rstrip("-")


def unique_slug(base: str, taken: set[str]) -> str:
    if base not in taken:
        return base
    for i in range(2, 1000):
        suffix = f"-{i}"
        trimmed = base[: 40 - len(suffix)].rstrip("-")
        candidate = trimmed + suffix
        if candidate not in taken:
            return candidate
    raise RuntimeError(f"cannot mint unique slug for base {base!r}")


def backfill(
    indicators_path: Path = INDICATORS_PATH,
    concepts_path: Path = CONCEPTS_PATH,
) -> tuple[int, int]:
    """Backfill ``concept_id`` on every indicator row.

    Returns ``(high_confidence_count, minted_count)``.
    """

    ind_payload = json.loads(indicators_path.read_text(encoding="utf-8"))
    con_payload = json.loads(concepts_path.read_text(encoding="utf-8"))
    concepts: list[dict] = con_payload["concepts"]
    taken_ids: set[str] = {c["concept_id"] for c in concepts}

    high_confidence = 0
    minted = 0

    for row in ind_payload["indicators"]:
        if row.get("concept_id"):
            high_confidence += 1
            continue
        norm = derive_normalisation(row)
        matches = find_overlap(
            noun=row["label_short"],
            unit=row["unit"],
            normalisation=norm,
            entity_kind=row["default_entity_kind"],
            concepts=concepts,
            top_n=1,
        )
        best = matches[0] if matches else None
        if best is not None and best.match_score >= HIGH_CONFIDENCE_THRESHOLD:
            row["concept_id"] = best.concept_id
            high_confidence += 1
            continue
        base = slugify(row["label_short"])
        new_id = unique_slug(base, taken_ids)
        taken_ids.add(new_id)
        concepts.append(
            {
                "concept_id": new_id,
                "noun": row["label_short"][:80],
                "unit_canonical": row["unit"],
                "normalisation": norm,
                "entity_kinds": list(row["entity_kinds"]),
                "description_short": (
                    STUB_DESCRIPTION_PREFIX + row["indicator_id"] + "."
                ),
                "sources": [],
            }
        )
        row["concept_id"] = new_id
        minted += 1

    concepts.sort(key=lambda c: c["concept_id"])
    con_payload["concepts"] = concepts

    indicators_path.write_text(
        json.dumps(ind_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    concepts_path.write_text(
        json.dumps(con_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return high_confidence, minted


def main() -> int:
    high, minted = backfill()
    total = high + minted
    print(
        f"backfill: {high} high-confidence FKs (>={HIGH_CONFIDENCE_THRESHOLD}); "
        f"{minted} auto-minted stub concepts; {total} indicator rows total."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
