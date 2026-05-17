"""Determinism guard for ``tools/emit_indicators_completeness_index.py``.

Regenerating the completeness index on an unchanged corpus MUST produce
byte-identical output. This is the test we wish we'd had before the
2026-05-16 ``fetched_at`` smear (see ``/memories/lessons.md``): every
re-emit must be a function of input bytes + input mtimes only, never of
the wall clock at emit time.

The test runs the emitter twice in-process on the live corpus and asserts
the two resulting payloads are byte-identical. We do NOT call ``--write``
(no on-disk mutation); we exercise ``build_index()`` directly because
that is the seam where determinism actually lives.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EMIT_PATH = REPO_ROOT / "tools" / "emit_indicators_completeness_index.py"


def _load_emit_module():
    # Ensure the tool can find yen_gov.
    backend = REPO_ROOT / "backend"
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    spec = importlib.util.spec_from_file_location("emit_completeness", EMIT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(
    not (REPO_ROOT / "datasets" / "indicators" / "in").exists(),
    reason="indicator corpus not present",
)
def test_emit_is_byte_deterministic_over_two_runs() -> None:
    mod = _load_emit_module()
    first = json.dumps(mod.build_index(), indent=2, ensure_ascii=False) + "\n"
    second = json.dumps(mod.build_index(), indent=2, ensure_ascii=False) + "\n"
    assert first == second, "build_index() output drifted between two back-to-back runs"


@pytest.mark.skipif(
    not (REPO_ROOT / "datasets" / "reference" / "in" / "indicators-completeness.json").exists(),
    reason="completeness index not yet generated",
)
def test_on_disk_index_matches_fresh_emit() -> None:
    """If this fails, run ``python tools/emit_indicators_completeness_index.py --write``."""
    mod = _load_emit_module()
    fresh = json.dumps(mod.build_index(), indent=2, ensure_ascii=False) + "\n"
    on_disk = (REPO_ROOT / "datasets" / "reference" / "in" / "indicators-completeness.json").read_text(encoding="utf-8")
    assert fresh == on_disk, (
        "On-disk index drifted from a fresh emit. Re-run "
        "`python tools/emit_indicators_completeness_index.py --write` and commit."
    )
