"""Tier-A unit tests locking the ``out`` field invariant on every
electoral entry in ``tools/boundaries/pipeline.json``.

Context: G10 (PR #838) moved the AC + PC boundary geometry from
``datasets/boundaries/in/{ac,pc}/...`` to
``datasets/boundaries/electoral/delim=<year>/<kind>/...``. PR #842
backfilled ``delimitation_vintage`` on the 31 + 1 electoral entries so
``derive_hive(...)`` no longer raises. This gate locks the remaining
seam — every electoral entry's ``out`` field must:

* point under ``../electoral/...`` (relative to ``outputs_dir``);
* resolve to a real on-disk path under
  ``datasets/boundaries/electoral/...`` (NOT under
  ``datasets/boundaries/in/...``);
* match exactly what ``tools/boundaries/_paths.py::derive_hive(...)``
  produces for the entry's ``(kind, state, delimitation_vintage)``
  triple — the canonical Hive layout contract is the single source
  of truth.
* leave no trace of the legacy admin-spine substrings
  ``boundaries/in/ac/`` or ``boundaries/in/pc/`` (regression guard).

Complements ``test_pipeline_json_delim_vintage.py`` from PR #842, which
locks the ``delimitation_vintage`` field; this file locks the ``out``
field that consumes that vintage.

Per CLAUDE.md sect 15 and Holy Law #7: this is configuration validation
against the real on-disk pipeline.json, not unit logic, so no
``tmp_path`` indirection. No mocks.
"""

from __future__ import annotations

import json
import sys
from pathlib import PurePosixPath

import pytest

# pathlib-aware repo root: this test lives at backend/tests/<file>.py.
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PIPELINE_PATH = REPO / "tools" / "boundaries" / "pipeline.json"
sys.path.insert(0, str(REPO))

from tools.boundaries._paths import derive_hive  # noqa: E402

OUTPUTS_DIR_REL = "datasets/boundaries/in"
ELECTORAL_PREFIX = "datasets/boundaries/electoral/"
LEGACY_AC_SUBSTRING = "boundaries/in/ac/"
LEGACY_PC_SUBSTRING = "boundaries/in/pc/"


@pytest.fixture(scope="module")
def pipeline_payload() -> dict:
    return json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))


def _electoral_entries(payload: dict, kind: str) -> list[dict]:
    return [e for e in payload["inputs"] if e.get("kind") == kind]


def _resolve_out(out_value: str) -> str:
    """Resolve an entry's ``out`` field against ``outputs_dir`` and
    normalize ``..`` segments. Returns a repo-relative POSIX path.
    """
    # PurePosixPath does NOT collapse ``..`` automatically; do it via
    # parts walking so the assertion lands on the intended path.
    combined = PurePosixPath(OUTPUTS_DIR_REL) / out_value
    parts: list[str] = []
    for segment in combined.parts:
        if segment == "..":
            assert parts, f"out={out_value!r} escapes repo root"
            parts.pop()
        elif segment != ".":
            parts.append(segment)
    return "/".join(parts)


def test_every_ac_entry_out_starts_with_electoral_relative_path(
    pipeline_payload: dict,
) -> None:
    """Test 1: every kind=ac entry's ``out`` is the relative-up
    ``../electoral/delim=2008/ac/state=...`` form. Locks the syntactic
    shape of the rewrite so future drift back to ``ac/`` is caught.
    """
    ac_entries = _electoral_entries(pipeline_payload, "ac")
    wrong: list[tuple[str | None, str | None]] = []
    expected_prefix = "../electoral/delim=2008/ac/state="
    for entry in ac_entries:
        out_value = entry.get("out")
        if not isinstance(out_value, str) or not out_value.startswith(expected_prefix):
            wrong.append((entry.get("state"), out_value if isinstance(out_value, str) else None))
    assert not wrong, (
        f"AC entries with ``out`` not starting with {expected_prefix!r}: {wrong}"
    )


def test_every_pc_entry_out_starts_with_electoral_relative_path(
    pipeline_payload: dict,
) -> None:
    """Test 2: every kind=pc entry's ``out`` is the relative-up
    ``../electoral/delim=<vintage>/pc/`` form. Locks the syntactic shape
    of the rewrite so future drift back to ``pc/delim=2024/`` is caught.
    """
    pc_entries = _electoral_entries(pipeline_payload, "pc")
    wrong: list[tuple[str | None, str | None]] = []
    for entry in pc_entries:
        out_value = entry.get("out")
        vintage = entry.get("delimitation_vintage")
        expected_prefix = f"../electoral/delim={vintage}/pc/"
        if not isinstance(out_value, str) or not out_value.startswith(expected_prefix):
            wrong.append((vintage if isinstance(vintage, str) else None, out_value if isinstance(out_value, str) else None))
    assert not wrong, (
        "PC entries with ``out`` not starting with "
        f"``../electoral/delim=<vintage>/pc/``: {wrong}"
    )


def test_every_electoral_resolved_out_lands_under_electoral_subtree(
    pipeline_payload: dict,
) -> None:
    """Test 3: every electoral ``out``, resolved against
    ``outputs_dir=datasets/boundaries/in``, lands UNDER
    ``datasets/boundaries/electoral/...`` (NOT under
    ``datasets/boundaries/in/...``). Catches any ``..`` arithmetic that
    accidentally lands back inside the admin spine.
    """
    misrouted: list[tuple[str, str | None, str]] = []
    for entry in pipeline_payload["inputs"]:
        kind = entry.get("kind")
        if kind not in ("ac", "pc"):
            continue
        out_value = entry.get("out")
        assert isinstance(out_value, str), f"electoral entry has no string out: {entry}"
        resolved = _resolve_out(out_value)
        if not resolved.startswith(ELECTORAL_PREFIX):
            misrouted.append((str(kind), entry.get("state"), resolved))
    assert not misrouted, (
        "Electoral entries whose resolved ``out`` lands outside "
        f"``{ELECTORAL_PREFIX}``: {misrouted}"
    )


def test_every_electoral_out_matches_derive_hive_contract(
    pipeline_payload: dict,
) -> None:
    """Test 4: every electoral ``out`` resolves to exactly what
    ``derive_hive(kind=, state=, delim=, ext=)`` produces (prefixed with
    ``datasets/`` to lift derive_hive's repo-relative path into the
    outputs_dir-resolved form). This is the load-bearing consistency
    assertion: the pipeline's persisted ``out`` field must agree with
    the canonical Hive layout contract.

    The extension is preserved per-entry from the existing ``out`` —
    AC entries publish ``.pmtiles`` (tippecanoe output), the PC entry
    publishes ``.geojson`` (raw passthrough). derive_hive's basename
    convention (``all.<ext>``) is honoured.
    """
    mismatches: list[tuple[str, str | None, str, str]] = []
    for entry in pipeline_payload["inputs"]:
        kind = entry.get("kind")
        if kind not in ("ac", "pc"):
            continue
        out_value = entry.get("out")
        state = entry.get("state")
        delim = entry.get("delimitation_vintage")
        assert isinstance(out_value, str), f"electoral entry has no string out: {entry}"
        # Extract extension from current ``out`` (preserved by the
        # repoint script per the operator's per-entry format choice).
        ext = PurePosixPath(out_value).suffix.lstrip(".")
        assert ext, f"out={out_value!r} has no extension"
        partition_path, _layer_id = derive_hive(
            kind=str(kind),
            delim=str(delim) if delim is not None else None,
            state=str(state) if state is not None else None,
            ext=ext,
        )
        expected_resolved = f"datasets/{partition_path}"
        actual_resolved = _resolve_out(out_value)
        if actual_resolved != expected_resolved:
            mismatches.append((str(kind), state, expected_resolved, actual_resolved))
    assert not mismatches, (
        "Electoral entries whose ``out`` does not match derive_hive's "
        f"canonical Hive layout: {mismatches}"
    )


def test_no_electoral_out_contains_legacy_admin_spine_substrings(
    pipeline_payload: dict,
) -> None:
    """Test 5: regression guard — NO electoral ``out`` field contains
    the substrings ``boundaries/in/ac/`` or ``boundaries/in/pc/``.
    These are the legacy admin-spine paths G10 vacated; any future drift
    back to them (intentional or accidental) is caught here.
    """
    offenders: list[tuple[str, str | None, str]] = []
    for entry in pipeline_payload["inputs"]:
        kind = entry.get("kind")
        if kind not in ("ac", "pc"):
            continue
        out_value = entry.get("out")
        assert isinstance(out_value, str), f"electoral entry has no string out: {entry}"
        if LEGACY_AC_SUBSTRING in out_value or LEGACY_PC_SUBSTRING in out_value:
            offenders.append((str(kind), entry.get("state"), out_value))
    assert not offenders, (
        "Electoral entries whose ``out`` still references the legacy "
        f"admin-spine paths ({LEGACY_AC_SUBSTRING!r} / {LEGACY_PC_SUBSTRING!r}): "
        f"{offenders}"
    )
