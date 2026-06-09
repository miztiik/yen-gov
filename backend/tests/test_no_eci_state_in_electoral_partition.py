"""Tier-A regression guard: no derive_hive output for any pipeline.json
electoral entry contains the legacy ``state=in_<lc>`` partition value.

Positive symmetric to Hans's regression guard: every electoral
``(kind, state, delimitation_vintage)`` triple in
``tools/boundaries/pipeline.json``, when fed through derive_hive via
``_eci_to_slug`` translation at the call site, MUST produce a
``partition_path`` and ``layer_id`` whose ``state=`` Hive value is an
LGD-name slug verbatim (``state=tamil-nadu``) - NEVER the pre-2026-06-09
``state=in_<lc>`` form (``state=in_s22``).

This complements ``test_pipeline_json_out_paths.py``
(test_no_electoral_out_contains_legacy_admin_spine_substrings) on the
DERIVATION side: that test locks the persisted ``out`` field; this test
locks the in-process derivation that produces shard paths at snapshot
time.

Hans+Max+Gregor converged verdict (2026-06-09, Item 1 of the G10
follow-on): plan-doc round-8 decommissioned ``eci_st_code`` as "a
column, join key, or partition value" - the partition value is now the
LGD-name slug verbatim. This test catches any future drift that would
re-encode publisher-specific codes in the partition.

Per CLAUDE.md sect 15 and Holy Law #7: configuration validation against
the real on-disk pipeline.json + the real on-disk lgd_states.json;
no tmp_path indirection, no mocks.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PIPELINE_PATH = REPO / "tools" / "boundaries" / "pipeline.json"
sys.path.insert(0, str(REPO))

from tools.boundaries._paths import _eci_to_slug, derive_hive  # noqa: E402


# Regex matching the legacy ``state=in_<lc>`` partition value (e.g.
# ``state=in_s22``, ``state=in_u05``) in either the partition_path or
# the dot-grammar layer_id. The negative assertion is symmetric on
# both surfaces; either appearing is a regression.
LEGACY_PARTITION_RE = re.compile(r"state=in_[su][0-9]{2}")


@pytest.fixture(scope="module")
def pipeline_payload() -> dict:
    return json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))


def _electoral_entries(payload: dict) -> list[dict]:
    return [e for e in payload["inputs"] if e.get("kind") in ("ac", "pc")]


def test_no_derive_hive_output_for_pipeline_json_carries_legacy_eci_state() -> None:
    """Run every electoral entry in pipeline.json through derive_hive
    via _eci_to_slug at the call site (the contract every caller is
    expected to honour 2026-06-09 onward) and assert NEITHER the
    returned partition_path NOR the layer_id contains the legacy
    ``state=in_<lc>`` token.
    """
    payload = json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))
    offenders: list[tuple[str, str | None, str | None, str, str]] = []
    for entry in _electoral_entries(payload):
        kind = entry.get("kind")
        state = entry.get("state")
        delim = entry.get("delimitation_vintage")
        # pipeline.json ``state`` is the ECI st_code; translate to slug
        # at the derive_hive boundary per the Hans+Max+Gregor verdict
        # (2026-06-09). None state (PC national-wide) passes through.
        state_slug = _eci_to_slug(str(state)) if state is not None else None
        partition_path, layer_id = derive_hive(
            kind=str(kind),
            delim=str(delim) if delim is not None else None,
            state_slug=state_slug,
        )
        if LEGACY_PARTITION_RE.search(partition_path):
            offenders.append(
                (str(kind), state, delim, partition_path, "partition_path")
            )
        if LEGACY_PARTITION_RE.search(layer_id):
            offenders.append(
                (str(kind), state, delim, layer_id, "layer_id")
            )
    assert not offenders, (
        "derive_hive produced a legacy ``state=in_<lc>`` partition "
        f"value for one or more pipeline.json electoral entries: {offenders}"
    )


def test_all_31_ac_entries_resolve_to_slug_keyed_partition() -> None:
    """Positive assertion: every AC entry in pipeline.json produces a
    partition path under ``state=<slug>/`` (NOT ``state=in_<lc>``). The
    31-entry inventory is locked by
    ``test_pipeline_json_delim_vintage.test_ac_inventory_count_locked_at_expected``;
    here we lock the SHAPE of each entry's derived partition.
    """
    payload = json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))
    ac_entries = [e for e in payload["inputs"] if e.get("kind") == "ac"]
    assert len(ac_entries) == 31, (
        f"AC inventory drifted: expected 31 entries, got {len(ac_entries)}"
    )
    bad_shape: list[tuple[str | None, str, str]] = []
    expected_prefix = "boundaries/electoral/delim=2008/ac/state="
    for entry in ac_entries:
        state = entry.get("state")
        assert state is not None, (
            f"AC entry has no ``state`` field: {entry}"
        )
        state_slug = _eci_to_slug(str(state))
        partition_path, _layer_id = derive_hive(
            kind="ac",
            delim="2008",
            state_slug=state_slug,
        )
        if not partition_path.startswith(expected_prefix):
            bad_shape.append((state, partition_path, "prefix-miss"))
            continue
        partition_state_value = partition_path[len(expected_prefix) :].split("/", 1)[0]
        if partition_state_value != state_slug:
            bad_shape.append((state, partition_path, "slug-mismatch"))
    assert not bad_shape, (
        "AC entries whose derived partition_path is not ``state=<slug>``: "
        f"{bad_shape}"
    )
