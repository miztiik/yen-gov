"""Tier-A pytest gate for per-state AC parity invariants.

Promotes `tools/boundaries/verify_ac_parity.py` from a manual CLI to a
CI-enforced gate so that any PR that breaks per-state name parity,
count match, or ac_no coverage on the 10 D.2 promotion states fails
`pytest -q`.

The tool's `verify_state(repo_root, eci)` returns `(passed, errors, stats)`;
this test invokes it for each DEFAULT_STATES entry and asserts no errors.

Reads 10 known-fixed files per state (constituencies.json + boundary
geojson). NOT a corpus-walk (no globbing / discovery); reading specific
known paths is permitted per CLAUDE.md anti-pattern carve-out.

Per [docs/archive/plans/20260530-boundary-followups-execution-plan.md] Row 4.8 (was Row 5.22 pre-PR #471 cleanup; shipped via PR #475).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Make tools/ importable.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.boundaries.verify_ac_parity import (  # noqa: E402
    DEFAULT_STATES,
    NAME_PARITY_THRESHOLD,
    verify_state,
)


@pytest.mark.parametrize("eci", DEFAULT_STATES)
def test_ac_parity_per_state(eci: str) -> None:
    """Each D.2 state passes count + ac_no coverage + name-parity (>=95%)."""
    ok, errors, stats = verify_state(REPO_ROOT, eci)
    assert ok, (
        f"AC parity failed for {eci}:\n  "
        + "\n  ".join(errors)
        + f"\n  stats={stats}"
    )


def test_default_states_is_non_empty_and_stable() -> None:
    """Guard: the DEFAULT_STATES tuple must stay non-empty and >= 10 states.

    If a future PR shrinks this set without bumping the gate, this test
    catches the silent regression of coverage.
    """
    assert len(DEFAULT_STATES) >= 10, (
        f"DEFAULT_STATES shrunk below 10 ({len(DEFAULT_STATES)}); "
        "this gate's coverage has silently weakened. "
        "Either re-expand the set or update this assertion explicitly."
    )


def test_name_parity_threshold_unchanged() -> None:
    """Guard: NAME_PARITY_THRESHOLD must stay at the D.1 recon value (0.95)."""
    assert NAME_PARITY_THRESHOLD == 0.95, (
        f"NAME_PARITY_THRESHOLD changed from 0.95 to {NAME_PARITY_THRESHOLD}; "
        "weakening this gate must be an explicit decision, not silent drift."
    )
