"""Pure summariser: roll a list of ParityObservations into the
`upstream_parity` object that step 7 splices into each indicator
artifact's `divergence` slot.

Rejected-design #1 (TODO §8): full `divergent_cells[]` arrays do NOT
belong inline — the citizen artifact carries only the summary verdict.
This module produces that summary; cell-level history stays on the
ledger.

Rejected-design #9 (TODO §8): NO is_ok() / boolean collapse anywhere.
The verdict carries the underlying counts so consumers can format
honestly without re-reading the ledger.
"""

from __future__ import annotations

from typing import Iterable, Optional

from .models import STATUS_VALUES, ParityObservation


def summarise(observations: Iterable[ParityObservation]) -> dict:
    """Roll observations into the inline `upstream_parity` object.

    Shape (stable; matches what step 7 will splice into the
    indicator artifact's required-null `divergence` slot):

        {
          "sample_size": int,
          "divergent_count": int,
          "status_counts": {match, near_match, diverge,
                            revised_upstream, missing_upstream,
                            missing_ours},
          "last_run_id": str | null,
          "last_sampled_at": str | null,
        }

    `divergent_count` = diverge + revised_upstream + missing_upstream +
    missing_ours. This is the same sum used as the sort key on the
    aggregate `indicators-parity.json` (`divergent_cell_count` per the
    sibling schema).

    Empty input returns the zero-sample shape; the inline object is
    never `None` once the oracle has run, even when nothing was
    sampled — distinguishing "we tried and got 0 cells" from "the
    oracle never visited this indicator" is the operator's job, made
    via `last_run_id is None`.
    """
    observations = list(observations)
    counts: dict[str, int] = {s: 0 for s in STATUS_VALUES}
    last_run_id: Optional[str] = None
    last_sampled_at: Optional[str] = None
    for obs in observations:
        counts[obs.status] += 1
        if last_sampled_at is None or obs.sampled_at > last_sampled_at:
            last_sampled_at = obs.sampled_at
            last_run_id = obs.run_id
    divergent = (
        counts["diverge"]
        + counts["revised_upstream"]
        + counts["missing_upstream"]
        + counts["missing_ours"]
    )
    return {
        "sample_size": len(observations),
        "divergent_count": divergent,
        "status_counts": counts,
        "last_run_id": last_run_id,
        "last_sampled_at": last_sampled_at,
    }
