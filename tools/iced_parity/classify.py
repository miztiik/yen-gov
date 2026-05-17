"""Pure status classifier for one cell-for-cell parity comparison.

Implements resolution §5(a) of TODO/20260517-iced-bulk-ingest-and-parity-oracle.md:

    `revised_upstream` if upstream != prior_upstream AND our == prior_upstream.
    `diverge` if our != upstream AND our != prior_upstream.

Six-value enum, never collapsed into a boolean is_ok() per
rejected-design #9 in §8 (operators must read the status, not a tick mark).
"""

from __future__ import annotations

from typing import Optional

from .models import Status

# Tolerance defaults are tight on purpose. ICED API exposes raw numbers;
# rounding/formatting noise should be the only thing `near_match` catches.
# Any wider tolerance is per-indicator and supplied by the caller.
DEFAULT_REL_TOLERANCE: float = 1e-4   # 0.01 %
DEFAULT_ABS_TOLERANCE: float = 1e-9


def _within(a: float, b: float, rel: float, abs_: float) -> bool:
    """True iff |a - b| <= max(abs_, rel * max(|a|, |b|))."""
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))


def classify(
    value_ours: Optional[float],
    value_upstream: Optional[float],
    value_prior_upstream: Optional[float] = None,
    *,
    rel_tolerance: float = DEFAULT_REL_TOLERANCE,
    abs_tolerance: float = DEFAULT_ABS_TOLERANCE,
) -> Status:
    """Classify one parity observation.

    Order of checks matters:
      1. missing-upstream wins over missing-ours when both are None
         (the upstream-perspective label is more actionable for an
         operator triaging an oracle run).
      2. exact equality short-circuits to `match` before tolerance
         arithmetic — preserves the cheap-path for the overwhelmingly
         common case.
      3. `revised_upstream` requires (a) an upstream that has CHANGED
         since the prior observation AND (b) an `our` value that still
         matches the prior upstream within tolerance. Both clauses
         protect against false positives when only one side moved.
      4. `near_match` is the consolation tier for tolerance-window
         agreement that isn't exact equality.
      5. Everything else is `diverge`.
    """
    if value_upstream is None:
        return "missing_upstream"
    if value_ours is None:
        return "missing_ours"
    if value_ours == value_upstream:
        return "match"
    if (
        value_prior_upstream is not None
        and value_upstream != value_prior_upstream
        and _within(value_ours, value_prior_upstream, rel_tolerance, abs_tolerance)
    ):
        return "revised_upstream"
    if _within(value_ours, value_upstream, rel_tolerance, abs_tolerance):
        return "near_match"
    return "diverge"
