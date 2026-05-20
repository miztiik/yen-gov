"""Tier-A tests for the canonical-ECI backfill orchestration.

Covers the in-memory primary API ``build_slice_envelope`` and the byte-identity
proof that the disk-walking ``_process_slice`` wrapper produces the same
canonical rows when fed the same constituencies (round-tripped through
``parties.json`` + ``results/<n>.json`` on tmp_path).

Per CLAUDE.md §10 the test does NOT walk the real ``datasets/`` corpus — it
seeds a minimal ``parties.json`` in ``tmp_path`` and uses the
``_emit_fixtures`` 3-AC slice that PR-O.3a established for the emit tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import _emit_fixtures  # noqa: I001 -- sibling test helper, not a package
import pytest

from yen_gov.canonical.adapters.eci.party_lookup import load_party_lookup
from yen_gov.pipeline.canonical_eci_backfill import (
    _process_slice,
    build_slice_envelope,
)
from yen_gov.canonical.adapters.eci.identity import parse_period_label


# Minimal parties roster covering the 3 fixture parties (AIADMK/DMK/INC) plus
# the sentinels the ECI adapter expects (IND for independents, NOTA for the
# NOTA row, UNK as the lenient-resolution fallback). Kept inline so the test
# file is self-contained — no fixtures/ subdir, no conftest.py needed.
_PARTIES_ROSTER: dict = {
    "$schema": "../schemas/parties.schema.json",
    "$schema_version": "2.0",
    "parties": [
        {
            "party_id": "parties.IN.AIADMK", "short_name": "AIADMK",
            "full_name": "All India Anna Dravida Munnetra Kazhagam",
            "aliases": [], "eci_codes": ["0136"], "state_scope": ["IN"],
            "founded_year": 1972, "dissolved_year": None,
            "successor_party_id": None, "predecessor_party_id": None,
            "alliance_history": [], "notes": "",
        },
        {
            "party_id": "parties.IN.DMK", "short_name": "DMK",
            "full_name": "Dravida Munnetra Kazhagam",
            "aliases": [], "eci_codes": ["0143"], "state_scope": ["IN"],
            "founded_year": 1949, "dissolved_year": None,
            "successor_party_id": None, "predecessor_party_id": None,
            "alliance_history": [], "notes": "",
        },
        {
            "party_id": "parties.IN.INC", "short_name": "INC",
            "full_name": "Indian National Congress",
            "aliases": [], "eci_codes": ["0742"], "state_scope": ["IN"],
            "founded_year": 1885, "dissolved_year": None,
            "successor_party_id": None, "predecessor_party_id": None,
            "alliance_history": [], "notes": "",
        },
        {
            "party_id": "parties.IN.IND", "short_name": "IND",
            "full_name": "Independent",
            "aliases": ["Independent"], "eci_codes": [], "state_scope": ["IN"],
            "founded_year": None, "dissolved_year": None,
            "successor_party_id": None, "predecessor_party_id": None,
            "alliance_history": [], "notes": "Sentinel for independent candidates.",
        },
        {
            "party_id": "parties.IN.NOTA", "short_name": "NOTA",
            "full_name": "None of the Above",
            "aliases": [], "eci_codes": [], "state_scope": ["IN"],
            "founded_year": None, "dissolved_year": None,
            "successor_party_id": None, "predecessor_party_id": None,
            "alliance_history": [], "notes": "Sentinel for NOTA rows.",
        },
        {
            "party_id": "parties.IN.UNK", "short_name": "UNK",
            "full_name": "Unknown party",
            "aliases": [], "eci_codes": [], "state_scope": ["IN"],
            "founded_year": None, "dissolved_year": None,
            "successor_party_id": None, "predecessor_party_id": None,
            "alliance_history": [], "notes": "Lenient-resolution fallback.",
        },
    ],
}


@pytest.fixture
def party_lookup_in(tmp_path: Path):
    """Seed a tmp datasets/taxonomy/parties.json and return the loaded lookup."""
    taxonomy = tmp_path / "taxonomy"
    taxonomy.mkdir(parents=True)
    (taxonomy / "parties.json").write_text(
        json.dumps(_PARTIES_ROSTER, ensure_ascii=False), encoding="utf-8",
    )
    return load_party_lookup(tmp_path)


def test_build_slice_envelope_happy_path(party_lookup_in) -> None:
    """build_slice_envelope returns observations + sources + dims for 3 ACs."""
    period = parse_period_label("AcGenMay2026")
    constituencies = _emit_fixtures.constituency_models()

    rows, sources, unresolved, candidate_dims, ac_dims = build_slice_envelope(
        constituencies=constituencies,
        state_code="S22",
        period=period,
        party_lookup=party_lookup_in,
    )

    # 3 ACs × N candidate rows + per-AC roll-up rows + per-state roll-up rows.
    # The exact row count depends on the adapter's indicator catalogue, which
    # this test doesn't pin (a change there is a different test's concern).
    # What we DO pin: rows is non-empty, sources has 1 entry (all 3 fixture
    # ACs share the same producer/title/vintage triple under v2.0 citation
    # ledger — ADR-0032), 3 AC dim rows, 5 unique candidates × 3 ACs = 15
    # candidate dim rows, no unresolved.
    assert len(rows) > 0
    assert len(sources) == 1, (
        f"expected ONE citation row for the slice (v2.0 citation ledger — "
        f"same producer/title/vintage triple across all 3 ACs of the same "
        f"state×event), got {len(sources)}: {sorted(sources.keys())}"
    )
    assert len(ac_dims) == 3, f"expected 3 AC dim rows, got {len(ac_dims)}"
    assert len(candidate_dims) == 15, (
        f"expected 5 candidates × 3 ACs = 15 candidate dim rows, got "
        f"{len(candidate_dims)}"
    )
    assert unresolved == {}, f"unexpected unresolved parties: {unresolved}"


def test_build_slice_envelope_empty_constituencies(party_lookup_in) -> None:
    """No constituencies → empty rows, empty sources, no unresolved."""
    period = parse_period_label("AcGenMay2026")
    rows, sources, unresolved, candidate_dims, ac_dims = build_slice_envelope(
        constituencies=[],
        state_code="S22",
        period=period,
        party_lookup=party_lookup_in,
    )
    assert rows == []
    assert sources == {}
    assert unresolved == {}
    assert candidate_dims == []
    assert ac_dims == []


def test_disk_wrapper_matches_in_memory(tmp_path: Path, party_lookup_in) -> None:
    """Byte-identity: _process_slice (disk) and build_slice_envelope (in-memory)
    produce the same canonical envelope for the same data.

    The guard against semantic drift between the two paths. If a future
    refactor of either function diverges, this test fires before the
    behavioural PR (PR-O.3b-main) can mis-wire the in-memory caller.
    """
    period = parse_period_label("AcGenMay2026")
    constituencies = _emit_fixtures.constituency_models()

    # --- in-memory path: the new primary API
    mem_rows, mem_sources, mem_unresolved, mem_cand_dims, mem_ac_dims = (
        build_slice_envelope(
            constituencies=constituencies,
            state_code="S22",
            period=period,
            party_lookup=party_lookup_in,
        )
    )

    # --- disk path: materialise the same constituencies and run the wrapper
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    for cr in constituencies:
        # body_payload() excludes `sources` (the writer normally stamps them
        # back at write time). _load_constituency_result calls model_validate
        # on the full dict so the on-disk JSON must carry both — replicate
        # the writer's envelope by merging sources_payload() in.
        payload = cr.body_payload()
        payload["sources"] = [s.to_dict() for s in cr.sources_payload()]
        (results_dir / f"{cr.eci_no}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8",
        )

    disk_rows, disk_sources, disk_ac_count, disk_unresolved, disk_cand_dims, disk_ac_dims = (
        _process_slice(
            results_dir=results_dir,
            state_code="S22",
            period=period,
            party_lookup=party_lookup_in,
        )
    )

    # Byte-identity assertions. Order matters for the lists — both paths emit
    # ACs in eci_no order, and within an AC the candidate order is preserved.
    assert disk_ac_count == 3
    assert disk_rows == mem_rows, "observation rows diverged between paths"
    assert disk_sources == mem_sources, "source rows diverged between paths"
    assert disk_unresolved == mem_unresolved
    assert disk_cand_dims == mem_cand_dims
    assert disk_ac_dims == mem_ac_dims
