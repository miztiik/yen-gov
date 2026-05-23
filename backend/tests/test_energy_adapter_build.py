"""Contract test for the energy adapter entry point.

Asserts ``build_envelopes(repo_root)`` returns exactly 4 BatchEnvelopes
with the correct ``target_table_stem`` values (one per active P.1.A
fact-table) and that each envelope carries observation rows.

Uses the REAL on-disk shards under ``datasets/indicators/in/energy/`` —
no mocks (CLAUDE.md §10 Holy Law #7). Cheap (~1s); covers the
adapter-build seam end-to-end without invoking the writer.

Pattern source: ``test_canonical_eci_observations.py`` (fixture-driven
against real shards).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yen_gov.canonical.envelope import BatchEnvelope

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARD_DIR = REPO_ROOT / "datasets" / "indicators" / "in" / "energy"


@pytest.mark.skipif(
    not SHARD_DIR.is_dir(),
    reason="energy shards not on disk in this checkout",
)
def test_build_envelopes_returns_four_with_correct_stems() -> None:
    from yen_gov.canonical.adapters.energy import build_envelopes

    envelopes = build_envelopes(REPO_ROOT)
    assert len(envelopes) == 4

    # All four must declare target_family="energy" and a registered stem.
    expected_stems = {
        "energy_installed_capacity",
        "energy_generation",
        "energy_demand_supply",
        "energy_distribution_performance",
    }
    actual_stems = {env.target_table_stem for env in envelopes}
    assert actual_stems == expected_stems, (
        f"build_envelopes() returned wrong stem set: expected {expected_stems!r}, "
        f"got {actual_stems!r}"
    )

    for env in envelopes:
        assert isinstance(env, BatchEnvelope)
        assert env.target_family == "energy"
        # Empty observation_rows on any active P.1.A envelope = lift bug.
        assert env.observation_rows, (
            f"envelope target_table_stem={env.target_table_stem!r} emitted "
            f"zero observation rows; lift adapter is broken"
        )


@pytest.mark.skipif(
    not SHARD_DIR.is_dir(),
    reason="energy shards not on disk in this checkout",
)
def test_all_observation_rows_carry_source_id_and_derivation() -> None:
    """Every emitted row MUST set source_id (FK gate enforces closure at
    write time) and derivation (so D33.8 sub-fuel collapse loss is
    auditable). Catches a regression where a builder forgets either."""
    from yen_gov.canonical.adapters.energy import build_envelopes

    envelopes = build_envelopes(REPO_ROOT)
    for env in envelopes:
        for row in env.observation_rows:
            assert row.source_id, (
                f"row indicator_id={row.indicator_id!r} entity_id={row.entity_id!r} "
                f"missing source_id"
            )
            assert row.derivation in {"raw", "sum"}, (
                f"row indicator_id={row.indicator_id!r} entity_id={row.entity_id!r} "
                f"derivation={row.derivation!r} not in expected set"
            )
