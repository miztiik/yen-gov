"""Regression guard for PR-O.3b-main (TODO ``1.8b-writers-b-main``).

The legacy per-AC ``results/<n>.json`` / ``result.summary.json`` /
``parties.json`` writers in the live-fetch pipeline retired when the
canonical store (``datasets/elections/election_results.parquet``) became
the single source of truth for election rows. Re-introducing
``write_artifact`` into ``backend/yen_gov/pipeline/run.py`` would silently
fork the contract surface again (CLAUDE.md Holy Law #10 — "Emit JSON
projections of canonical data for the citizen frontend").

This test scans the file as source text (no AST parse needed — the goal
is to catch the symbol re-appearing in any form, including a comment that
hints the writer is being revived). The companion ``canonical_eci_backfill``
module continues to consume the legacy JSON corpus pending PR-O.4 cleanup,
so this guard is scoped narrowly to ``pipeline/run.py``.
"""

from __future__ import annotations

from pathlib import Path


PIPELINE_RUN = (
    Path(__file__).resolve().parents[1]
    / "yen_gov" / "pipeline" / "run.py"
)


def test_pipeline_run_does_not_call_write_artifact() -> None:
    """pipeline/run.py MUST NOT call ``write_artifact`` — the canonical
    Parquet writer (``yen_gov.canonical.writer.write_batch``) is the only
    legal write seam from this module."""
    text = PIPELINE_RUN.read_text(encoding="utf-8")
    assert "write_artifact(" not in text, (
        "pipeline/run.py reintroduced a write_artifact(...) call. "
        "The live-fetch pipeline writes ONLY to the canonical Parquet "
        "store via write_batch (PR-O.3b-main, TODO row 1.8b-writers-b-main). "
        "Re-emitting per-AC JSON shards forks the contract surface and "
        "violates CLAUDE.md Holy Law #10."
    )


def test_pipeline_run_does_not_import_write_artifact() -> None:
    """No import of ``write_artifact`` in pipeline/run.py — the symbol
    is dead-code for this module and importing it signals the writer is
    about to come back."""
    text = PIPELINE_RUN.read_text(encoding="utf-8")
    assert "write_artifact" not in text, (
        "pipeline/run.py imports or references 'write_artifact'. The "
        "canonical Parquet writer (write_batch) is the only legal write "
        "seam from this module after PR-O.3b-main."
    )
