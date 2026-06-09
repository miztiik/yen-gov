"""Tier-A unit tests locking the ``delimitation_vintage`` invariant on
``tools/boundaries/pipeline.json``.

Context: G10 (PR #838) made ``delimitation_vintage`` a required kwarg
on ``tools/boundaries/_paths.py::derive_hive(...)`` whenever
``kind in {"ac", "pc"}``. The 31 AC entries in pipeline.json were not
backfilled at the time (pipeline.json is not exercised by pytest, so
the inputs were dormant). This gate ensures any future drift is caught:

* Every ``kind == "ac"`` entry carries a 4-digit ``delimitation_vintage``
  (extant geometry is delim=2008; the 2024 order takes effect for LS2029).
* Every ``kind == "pc"`` entry carries a 4-digit ``delimitation_vintage``
  (on-disk PC geometry is delim=2024 per G10).
* Every electoral ``(kind, state, delimitation_vintage)`` triple is
  consumable by ``derive_hive(...)`` without raising.
* The count of ``kind == "ac"`` entries equals 31 — locks the inventory
  so that any future add/remove fails this test loudly and the operator
  must consciously update the count.

Per CLAUDE.md sect 15 and Holy Law #7: this is configuration validation
against the real on-disk pipeline.json, not unit logic, so no
``tmp_path`` indirection. No mocks.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PIPELINE_PATH = REPO / "tools" / "boundaries" / "pipeline.json"
sys.path.insert(0, str(REPO))

from tools.boundaries._paths import _eci_to_slug, derive_hive  # noqa: E402


AC_INVENTORY_COUNT = 31


@pytest.fixture(scope="module")
def pipeline_payload() -> dict:
    return json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))


def _electoral_entries(payload: dict, kind: str) -> list[dict]:
    return [e for e in payload["inputs"] if e.get("kind") == kind]


def test_every_ac_entry_carries_4digit_delimitation_vintage(
    pipeline_payload: dict,
) -> None:
    ac_entries = _electoral_entries(pipeline_payload, "ac")
    missing: list[str | None] = []
    bad_shape: list[tuple[str | None, object]] = []
    for entry in ac_entries:
        vintage = entry.get("delimitation_vintage")
        if vintage is None:
            missing.append(entry.get("state"))
            continue
        if not (isinstance(vintage, str) and len(vintage) == 4 and vintage.isdigit()):
            bad_shape.append((entry.get("state"), vintage))
    assert not missing, (
        "AC entries missing delimitation_vintage (G10 PR #838 made this "
        f"required on derive_hive): {missing}"
    )
    assert not bad_shape, (
        "AC delimitation_vintage values must be 4-digit year strings "
        f'(e.g. "2008", "2024"): got {bad_shape}'
    )


def test_every_pc_entry_carries_4digit_delimitation_vintage(
    pipeline_payload: dict,
) -> None:
    pc_entries = _electoral_entries(pipeline_payload, "pc")
    missing: list[str | None] = []
    bad_shape: list[tuple[str | None, object]] = []
    for entry in pc_entries:
        vintage = entry.get("delimitation_vintage")
        if vintage is None:
            missing.append(entry.get("country"))
            continue
        if not (isinstance(vintage, str) and len(vintage) == 4 and vintage.isdigit()):
            bad_shape.append((entry.get("country"), vintage))
    assert not missing, (
        "PC entries missing delimitation_vintage (G10 PR #838 made this "
        f"required on derive_hive): {missing}"
    )
    assert not bad_shape, (
        "PC delimitation_vintage values must be 4-digit year strings "
        f'(e.g. "2024"): got {bad_shape}'
    )


def test_every_electoral_triple_is_consumable_by_derive_hive(
    pipeline_payload: dict,
) -> None:
    failures: list[tuple[str, str | None, str | None, str]] = []
    for entry in pipeline_payload["inputs"]:
        kind = entry.get("kind")
        if kind not in ("ac", "pc"):
            continue
        try:
            # pipeline.json ``state`` is the ECI st_code; translate to
            # LGD-name slug at the derive_hive boundary per the
            # Hans+Max+Gregor verdict (2026-06-09, Item 1 of the G10
            # follow-on). None state (PC national-wide layer) passes
            # through unchanged.
            state = entry.get("state")
            state_slug = _eci_to_slug(state) if state is not None else None
            derive_hive(
                kind=kind,
                state_slug=state_slug,
                delim=entry.get("delimitation_vintage"),
            )
        except Exception as ex:  # noqa: BLE001  -- want every failure mode
            failures.append(
                (
                    kind,
                    entry.get("state"),
                    entry.get("delimitation_vintage"),
                    str(ex),
                )
            )
    assert not failures, (
        "derive_hive rejected one or more pipeline.json electoral "
        f"entries: {failures}"
    )


def test_ac_inventory_count_locked_at_expected(
    pipeline_payload: dict,
) -> None:
    ac_entries = _electoral_entries(pipeline_payload, "ac")
    assert len(ac_entries) == AC_INVENTORY_COUNT, (
        f"AC inventory drift: pipeline.json has {len(ac_entries)} kind='ac' "
        f"entries, expected {AC_INVENTORY_COUNT}. If this drift is "
        "intentional (state added or removed), update "
        "AC_INVENTORY_COUNT in this test in the same commit."
    )
