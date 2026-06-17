"""Seed the goal-catalogue overlay (frameworks + goals + goal_indicators).

The overlay lets a citizen see a "goals summary" across country / state /
district by mapping curated yen-gov indicators to goal-framework targets
(SDG, NITI SDG India Index, ICRIER, CHIPS, ...). It is a METADATA overlay:
no new datapoints, no change to existing data. The summary view is a
read-time DuckDB join of ``goals`` + ``goal_indicators`` + the existing
datapoint CSVs.

This module seeds the first framework: the UN Sustainable Development
Goals, SDG-3 (Good Health and Well-being) subtree. Design ratified by
Hans + Max on 2026-06-17 (see the plan-doc). Two honesty rails are baked
into the data, not left to the UI:

- ``frameworks.authority_class`` tells a UN agreement apart from a
  think-tank index. SDG is ``intergovernmental_resolution`` - a
  non-binding UN General Assembly Resolution (A/RES/70/1), NOT a treaty.
- ``goals.target_scope`` marks the UN numbers as ``global`` / ``national``
  aspirations, never per-state legal obligations, so the renderer draws a
  national reference line and never a per-district pass/fail.

The ``goal_indicators`` mappings are FK-guarded: a mapping is emitted only
when its ``indicator_id`` already exists in ``variables.csv``. So on a
corpus without the SRS health indicators the mapping file is header-only
(an honest "no yen-gov indicator yet" gap), and the mappings activate
automatically once ``ingest-rbi-hbs`` lands total-fertility-rate /
infant-mortality-rate / life-expectancy. FK closure makes the overlay
self-protecting (no dangling mapping can exist).

Only the citable UN SDG-3 numbers are seeded (MMR <= 70, U5MR <= 25,
neonatal <= 12, all by 2030; A/RES/70/1). NITI SDG India Index bands,
ICRIER indices, and CHIPS are deliberately NOT modelled here - they need
a pinned citation first (Hans + Max open follow-up to docs/research/).
"""
from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.csv_columns import load_columns
from yen_gov.canonical.csv_writer import write_csv

__all__ = ["SeedResult", "seed_goals"]

_FRAMEWORKS_REL = "datasets/data/frameworks.csv"
_GOALS_REL = "datasets/data/goals.csv"
_GOAL_INDICATORS_REL = "datasets/data/goal_indicators.csv"
_VARIABLES_REL = "datasets/data/variables.csv"
_SOURCE_REL = "datasets/data/entities/source.csv"

# --- UN citation (the document that sets the SDG numbers) ------------------
_UN_PRODUCER = "United Nations"
_UN_TITLE = (
    "Transforming our world: the 2030 Agenda for Sustainable Development "
    "(A/RES/70/1)"
)
_UN_VINTAGE = "2015"
_UN_URL = "https://sdgs.un.org/2030agenda"
UN_SOURCE_ID = derive_source_id(_UN_PRODUCER, _UN_TITLE, _UN_VINTAGE)

SDG_FRAMEWORK_ID = "sdg"


def _framework_rows() -> list[dict[str, Any]]:
    return [
        {
            "framework_id": SDG_FRAMEWORK_ID,
            "name": "UN Sustainable Development Goals",
            "publisher": "United Nations",
            "authority_class": "intergovernmental_resolution",
            "disclaimer": (
                "Adopted by all 193 UN member states as General Assembly "
                "Resolution A/RES/70/1 (2015). These are non-binding global "
                "and national aspirations to 2030, not legally enforceable "
                "obligations on any individual state."
            ),
            "homepage_url": "https://sdgs.un.org/goals",
            "baseline_year": 2015,
            "horizon_year": 2030,
            "source_id": UN_SOURCE_ID,
            "description": (
                "The 17 Sustainable Development Goals and their 169 targets - "
                "a shared global agenda to 2030. yen-gov surfaces the goal "
                "text next to each place's trajectory; it does not score "
                "states on-track / off-track."
            ),
        }
    ]


def _goal_rows() -> list[dict[str, Any]]:
    """SDG-3 subtree. Targets live on the node; one number per leaf."""

    def node(
        goal_id: str,
        code: str,
        node_kind: str,
        name: str,
        *,
        statement: str | None = None,
        parent: str | None = None,
        target_value: float | None = None,
        target_bound: str | None = None,
        better_direction: str | None = None,
        target_year: int | None = None,
        target_scope: str | None = None,
        source_id: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        return {
            "goal_id": goal_id,
            "framework_id": SDG_FRAMEWORK_ID,
            "code": code,
            "node_kind": node_kind,
            "name": name,
            "statement": statement,
            "parent": parent,
            "target_value": target_value,
            "target_bound": target_bound,
            "better_direction": better_direction,
            "target_year": target_year,
            "target_scope": target_scope,
            "source_id": source_id,
            "description": description,
        }

    return [
        node(
            "sdg-3", "3", "goal", "Good Health and Well-being",
            statement="Ensure healthy lives and promote well-being for all at all ages",
            better_direction="higher", target_scope="national",
            description="SDG 3 - the whole-of-population health goal.",
        ),
        node(
            "sdg-3.1", "3.1", "target", "Reduce maternal mortality",
            statement=(
                "By 2030, reduce the global maternal mortality ratio to less "
                "than 70 per 100,000 live births"
            ),
            parent="sdg-3", better_direction="lower", target_year=2030,
            target_scope="national",
        ),
        node(
            "sdg-3.1.1", "3.1.1", "indicator", "Maternal mortality ratio",
            statement="Maternal mortality ratio (deaths per 100,000 live births)",
            parent="sdg-3.1", target_value=70, target_bound="at_most",
            better_direction="lower", target_year=2030, target_scope="global",
            source_id=UN_SOURCE_ID,
        ),
        node(
            "sdg-3.2", "3.2", "target",
            "End preventable deaths of newborns and under-5 children",
            statement=(
                "By 2030, end preventable deaths of newborns and children "
                "under 5 years of age, with all countries aiming to reduce "
                "neonatal mortality to at least as low as 12 per 1,000 live "
                "births and under-5 mortality to at least as low as 25 per "
                "1,000 live births"
            ),
            parent="sdg-3", better_direction="lower", target_year=2030,
            target_scope="national",
        ),
        node(
            "sdg-3.2.1", "3.2.1", "indicator", "Under-5 mortality rate",
            statement="Under-5 mortality rate (deaths per 1,000 live births)",
            parent="sdg-3.2", target_value=25, target_bound="at_most",
            better_direction="lower", target_year=2030, target_scope="global",
            source_id=UN_SOURCE_ID,
        ),
        node(
            "sdg-3.2.2", "3.2.2", "indicator", "Neonatal mortality rate",
            statement="Neonatal mortality rate (deaths per 1,000 live births)",
            parent="sdg-3.2", target_value=12, target_bound="at_most",
            better_direction="lower", target_year=2030, target_scope="global",
            source_id=UN_SOURCE_ID,
        ),
        node(
            "sdg-3.7", "3.7", "target",
            "Universal access to reproductive health and family planning",
            statement=(
                "By 2030, ensure universal access to sexual and reproductive "
                "health-care services, including for family planning, "
                "information and education"
            ),
            parent="sdg-3", better_direction="neutral", target_year=2030,
            target_scope="national",
        ),
    ]


# Candidate goal -> indicator mappings. Each is FK-guarded against
# variables.csv at emit time; only the present indicators are written.
# The honest set per Hans + Max: IMR is a proxy under SDG 3.2; TFR is
# family-planning CONTEXT (no SDG fertility target); life-expectancy is
# whole-goal outcome CONTEXT. crude-birth-rate / crude-death-rate are
# DELIBERATELY UNMAPPED (no honest direction-of-good; a scorecard arrow
# on them is a category error - Hans verdict).
_CANDIDATE_MAPPINGS: tuple[dict[str, Any], ...] = (
    {
        "goal_id": "sdg-3.2",
        "indicator_id": "infant-mortality-rate-per-1000",
        "mapping_method": "editorial_judgement",
        "mapping_confidence": "proxy",
        "caveat": (
            "IMR (infant, under-1) is a major component of under-5 mortality "
            "but is NOT the SDG indicator: SDG 3.2 sets its thresholds on "
            "under-5 mortality (<=25) and neonatal mortality (<=12), not IMR. "
            "Shown as a proxy; no SDG target number is inherited."
        ),
    },
    {
        "goal_id": "sdg-3.7",
        "indicator_id": "total-fertility-rate",
        "mapping_method": "editorial_judgement",
        "mapping_confidence": "context",
        "caveat": (
            "SDG sets no fertility threshold. Replacement-level 2.1 is a "
            "demographic benchmark, not an SDG target; fertility is a stage "
            "of the demographic transition, not a governance score. Shown as "
            "context for family-planning access."
        ),
    },
    {
        "goal_id": "sdg-3",
        "indicator_id": "life-expectancy-at-birth-years",
        "mapping_method": "editorial_judgement",
        "mapping_confidence": "context",
        "caveat": (
            "A summary health outcome for the whole goal, not a single SDG "
            "indicator. Published on overlapping multi-year windows, so a "
            "point labelled 2020-2024 is a five-year-window estimate."
        ),
    },
)


@dataclass(frozen=True)
class SeedResult:
    """Operator-visible summary of one seed run."""

    framework_count: int
    goal_count: int
    mapping_count: int
    skipped_mappings: tuple[str, ...]  # indicator_ids absent from variables.csv


def seed_goals(*, repo_root: Path) -> SeedResult:
    """Seed the SDG framework + SDG-3 goals tree + FK-guarded mappings.

    frameworks.csv and goals.csv are upserted unconditionally (they FK only
    to source.csv + self). goal_indicators.csv is FK-guarded: a mapping is
    written only when its indicator_id is present in variables.csv, so the
    overlay never carries a dangling FK. Idempotent: the canonical writer
    skip-writes byte-identical output.

    Returns a :class:`SeedResult`. Also registers the UN citation row in
    source.csv if absent.
    """
    contract = load_columns()

    _upsert(repo_root, _FRAMEWORKS_REL, _framework_rows(), contract=contract)
    goal_rows = _goal_rows()
    _upsert(repo_root, _GOALS_REL, goal_rows, contract=contract)

    present = _present_indicator_ids(repo_root)
    mappings = [m for m in _CANDIDATE_MAPPINGS if m["indicator_id"] in present]
    skipped = tuple(
        m["indicator_id"]
        for m in _CANDIDATE_MAPPINGS
        if m["indicator_id"] not in present
    )
    _upsert(repo_root, _GOAL_INDICATORS_REL, mappings, contract=contract)

    _register_un_source(repo_root, contract=contract)

    return SeedResult(
        framework_count=len(_framework_rows()),
        goal_count=len(goal_rows),
        mapping_count=len(mappings),
        skipped_mappings=skipped,
    )


def _present_indicator_ids(repo_root: Path) -> set[str]:
    """Indicator ids already in variables.csv (empty set if absent)."""
    path = repo_root / _VARIABLES_REL
    if not path.exists():
        return set()
    with path.open(encoding="utf-8", newline="") as fh:
        return {
            (row.get("indicator_id") or "").strip()
            for row in csv.DictReader(fh)
            if (row.get("indicator_id") or "").strip()
        }


def _register_un_source(repo_root: Path, *, contract: Any) -> None:
    """Upsert the UN 2030-Agenda citation row into source.csv."""
    row = {
        "source_id": UN_SOURCE_ID,
        "producer": _UN_PRODUCER,
        "title": _UN_TITLE,
        "vintage": _UN_VINTAGE,
        "url": _UN_URL,
    }
    _upsert(repo_root, _SOURCE_REL, [row], contract=contract)


def _upsert(
    repo_root: Path,
    rel_path: str,
    new_rows: Iterable[dict[str, Any]],
    *,
    contract: Any,
) -> Path:
    """Merge ``new_rows`` into the catalogue CSV at ``rel_path`` by PK.

    Existing rows are preserved; new rows overlay by primary key. The
    canonical writer sorts by PK and skip-writes when nothing changed.
    An empty ``new_rows`` against a non-existent file yields a header-only
    file (the honest "no mappings yet" state for goal_indicators.csv).
    """
    path = repo_root / rel_path
    fc = contract.for_glob(rel_path)
    names = [c.name for c in fc.columns]
    pk_names = [c.name for c in fc.pk_columns]

    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    if path.exists():
        with path.open(encoding="utf-8", newline="") as fh:
            for raw in csv.DictReader(fh):
                row = {
                    name: (raw.get(name) if (raw.get(name) or "") != "" else None)
                    for name in names
                }
                merged[tuple(_key(row[k]) for k in pk_names)] = row
    for row in new_rows:
        merged[tuple(_key(row.get(k)) for k in pk_names)] = {
            name: row.get(name) for name in names
        }

    return write_csv(
        path=path,
        file_class=rel_path,
        rows=list(merged.values()),
        contract=contract,
    )


def _key(value: Any) -> Any:
    return str(value) if value is not None else None
