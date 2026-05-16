"""Determinism / idempotency guard for derived documentation generators.

CLAUDE.md \u00a710 anti-pattern: ``datetime.now()`` MUST NOT be used as input
to artifact CONTENT (operational telemetry, not provenance). The 2026-05-16
``fetched_at`` smear cascaded into ``coverage.py`` and
``coverage_indicator_pages.py`` -- every regen re-stamped every doc with
today's date, so a single re-run of ``python -m yen_gov coverage`` rewrote
``docs/reference/data-inventory.md`` and every
``docs/reference/indicators/**/*.md`` even when the inputs were untouched.
Re-running ingest for ONE source then churned hundreds of unrelated doc
lines.

This test pins the fix in place by asserting that the two pure-string
renderers (``render_markdown`` for the inventory; ``render_page`` for each
indicator page) are byte-identical across two back-to-back invocations
against unchanged inputs. If a regression re-introduces ``datetime.now()``
into either renderer's content, this assertion fails on the first re-run
that crosses a UTC date boundary -- and, more practically, fails
immediately if anyone re-introduces a sub-day wall-clock stamp.

We deliberately do NOT assert ``st_mtime_ns`` equality on the written
output files. Unconditional ``Path.write_text`` advances mtime even when
bytes match, and a ``write_text_if_changed`` helper is explicitly off-limits
per the 2026-05-17 design review (rejected design #2 in the folded-indicator
handover: it papers over the real bug rather than fixing it). The
authoritative integration contract is "no diff in ``git status``" =
byte-identical output, which is exactly what is asserted here.
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.coverage import compute_coverage, render_markdown
from yen_gov.coverage_indicator_pages import (
    iter_indicator_artifacts,
    render_page,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_render_markdown_is_byte_identical_across_runs() -> None:
    """``data-inventory.md`` body MUST be deterministic given unchanged inputs."""
    first = render_markdown(compute_coverage(REPO_ROOT))
    second = render_markdown(compute_coverage(REPO_ROOT))
    assert first == second, (
        "render_markdown produced different bytes across two back-to-back "
        "calls with no input change. Likely cause: a wall-clock value "
        "(datetime.now() or similar) has been re-introduced into the "
        "rendered string. See CLAUDE.md \u00a710 anti-pattern."
    )


def test_render_page_is_byte_identical_across_runs() -> None:
    """Every indicator page body MUST be deterministic given an unchanged artifact."""
    artifacts = list(iter_indicator_artifacts(REPO_ROOT))
    assert artifacts, "expected at least one indicator artifact under datasets/indicators/in/"
    for artifact in artifacts:
        first = render_page(artifact)
        second = render_page(artifact)
        assert first == second, (
            f"render_page produced different bytes for {artifact.path_rel} "
            "across two back-to-back calls with no input change. Likely cause: "
            "a wall-clock value (datetime.now() or similar) has been "
            "re-introduced into the rendered string. See CLAUDE.md \u00a710 "
            "anti-pattern."
        )
