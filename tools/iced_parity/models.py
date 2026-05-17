"""Per-record data model for one line of `datasets/parity/in/<id>.ledger.jsonl`.

Mirrors `datasets/schemas/parity-observation.schema.json` v1.0 exactly.
The to_jsonl_dict() method serialises in the schema's required-fields-
first order so `git diff` on ledger lines stays predictable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

Status = Literal[
    "match",
    "near_match",
    "diverge",
    "revised_upstream",
    "missing_upstream",
    "missing_ours",
]

STATUS_VALUES: tuple[Status, ...] = (
    "match",
    "near_match",
    "diverge",
    "revised_upstream",
    "missing_upstream",
    "missing_ours",
)


@dataclass(frozen=True)
class ParityObservation:
    """One cell-for-cell comparison result. Frozen so the same object can
    be both ledger-appended and rolled up by banner.summarise() without
    mutation hazard."""

    entity_id: str
    time: str
    value_ours: Optional[float]
    value_upstream: Optional[float]
    status: Status
    sampled_at: str
    upstream_url: str
    facet: Optional[str] = None
    value_prior_upstream: Optional[float] = None
    delta: Optional[float] = None
    delta_pct: Optional[float] = None
    tolerance_used: Optional[float] = None
    run_id: Optional[str] = None

    def to_jsonl_dict(self) -> dict:
        """Schema-order serialisation. Optionals are omitted when None to
        keep ledger lines compact and diff-friendly."""
        out: dict = {
            "entity_id": self.entity_id,
            "time": self.time,
            "value_ours": self.value_ours,
            "value_upstream": self.value_upstream,
            "status": self.status,
            "sampled_at": self.sampled_at,
            "upstream_url": self.upstream_url,
        }
        if self.facet is not None:
            out["facet"] = self.facet
        if self.value_prior_upstream is not None:
            out["value_prior_upstream"] = self.value_prior_upstream
        if self.delta is not None:
            out["delta"] = self.delta
        if self.delta_pct is not None:
            out["delta_pct"] = self.delta_pct
        if self.tolerance_used is not None:
            out["tolerance_used"] = self.tolerance_used
        if self.run_id is not None:
            out["run_id"] = self.run_id
        return out
