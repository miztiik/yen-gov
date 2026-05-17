"""Cell-sampling strategies over an indicator artifact.

Pure. Operates on the in-memory artifact dict; does not read files. The
sampler decides WHICH (entity_id, time, facet) cells to probe; probe.py
then fetches each cell's upstream value.

Two strategies for now (per Phase 1 of the parity oracle):

  - `all_cells`        — every row in the artifact becomes one cell.
                         Cheap when row counts are small; the natural
                         default for hand-validated baselines.
  - `stratified_sample` — up to `n_per_entity` cells per entity, picked
                         deterministically by seed. Used for indicators
                         with 1k+ rows where probing every cell would be
                         wasteful upstream load.

Neither strategy collapses facetted rows — `(entity, time, facet)` is the
identity tuple end-to-end.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Cell:
    """One (entity, time, facet?) coordinate to probe."""

    entity_id: str
    time: str
    facet: Optional[str] = None


def all_cells(indicator_artifact: dict) -> list[Cell]:
    """Return one Cell per row, in artifact order."""
    return [
        Cell(
            entity_id=row["entity_id"],
            time=row["time"],
            facet=row.get("facet"),
        )
        for row in indicator_artifact.get("rows", [])
    ]


def stratified_sample(
    indicator_artifact: dict,
    *,
    n_per_entity: int = 3,
    seed: int = 0,
) -> list[Cell]:
    """Pick up to `n_per_entity` cells per entity. Deterministic via seed.

    Entities with <= n_per_entity rows contribute all their cells.
    Output is grouped by entity_id sorted ascending — keeps ledger diffs
    deterministic across runs and reviewers.
    """
    if n_per_entity < 1:
        raise ValueError("n_per_entity must be >= 1")
    rng = random.Random(seed)
    by_entity: dict[str, list[Cell]] = {}
    for cell in all_cells(indicator_artifact):
        by_entity.setdefault(cell.entity_id, []).append(cell)
    out: list[Cell] = []
    for entity_id in sorted(by_entity):
        cells = by_entity[entity_id]
        if len(cells) <= n_per_entity:
            out.extend(cells)
        else:
            out.extend(rng.sample(cells, n_per_entity))
    return out
