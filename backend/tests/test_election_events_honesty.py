"""Tier-A gate: catalogue events declared `data_status: "complete"` MUST
have their per-event CSV files on disk.

The hand-authored `datasets/taxonomy/election_events.json` catalogue is the
single source of truth for the frontend's elections firehose
(`/t/elections`, `frontend/src/routes/ElectionsFirehose.svelte`). The
firehose loads each event's per-event `summary.csv` to derive the leading
party / seats / turnout cells; when a 404 lands it renders an amber
"error" badge that citizens read as "yen-gov is broken".

The fix (2026-06-11, this PR) is two-part:

  * **Data side**: the operator runs `python -m tools.election_events_honesty`
    to flip the catalogue's `data_status` from "complete" to
    "pending_upstream" for any event whose per-event CSVs are not on
    disk. The frontend then renders a calm slate "Pending" badge for
    those rows rather than an amber "error".

  * **Frontend side**: pre-skip pending_upstream rows in the firehose
    loader and reserve the "error" badge for genuine unexpected
    failures (catalogue says complete but the load fails - a real bug).

This test is the regression gate: any future ingest that adds catalogue
events MUST either emit the per-event files in the same PR OR mark them
pending_upstream. The gate makes the catalogue's contract with the
on-disk truth machine-checkable, so the noisy "error" badge cannot
silently re-appear when a new event is minted but its files have not
landed.

The gate uses the same disk-path logic as the operator tool
(`tools.election_events_honesty.build_honesty_report`) so the two
contracts stay in lockstep: if the tool would flip an event, the test
fails; if the test passes, the tool's dry-run reports zero flips.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# tools/ is at the repo root - importable when PYTHONPATH includes the
# repo root or when invoked from the repo root (the standard pytest
# invocation for this repo).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tools.election_events_honesty.__main__ import build_honesty_report  # noqa: E402


def test_catalogue_complete_rows_have_per_event_files_on_disk() -> None:
    """For every catalogue event with `data_status: "complete"`, both
    `candidacies.csv` and `summary.csv` MUST exist under the canonical
    `datasets/elections/...` per-event directory.

    A catalogue row that claims `complete` without the per-event files
    triggers a 404 on the frontend firehose and renders an amber "error"
    badge to the citizen. The fix is structural (CLAUDE.md §5 / §10):
    flip the catalogue row to "pending_upstream" (operator runs
    `python -m tools.election_events_honesty`) so the frontend renders a
    calm "Pending" affordance instead.

    If THIS test fails, the operator must either:

      (a) Run `python -m tools.election_events_honesty` to flip false
          "complete" rows to "pending_upstream" based on on-disk truth,
          OR

      (b) Ingest the missing per-event files in the same PR.

    The check is the same one the operator tool uses (via
    `build_honesty_report`), so the two surfaces stay in lockstep.
    """
    report = build_honesty_report(_REPO_ROOT)
    to_flip = report["flipped"] + report["no_pattern_flipped"]
    if not to_flip:
        return
    # Surface up to 20 violations so the operator can triage in one run.
    sample = to_flip[:20]
    lines = [
        "Catalogue declares data_status='complete' for events whose per-event "
        "files are not on disk. Run `python -m tools.election_events_honesty` "
        "to flip these rows to 'pending_upstream', OR ingest the missing "
        "files in the same PR.",
        "",
        f"Total honesty violations: {len(to_flip)}",
        f"First {len(sample)}:",
    ]
    for row in sample:
        lines.append(
            f"  state={row['state_code']} kind={row['kind']:<14} "
            f"event_id={row['event_id']}"
        )
    pytest.fail("\n".join(lines))


def test_honesty_tool_is_idempotent_against_committed_catalogue() -> None:
    """Sanity gate: running the honesty tool against the on-disk
    catalogue must report zero pending flips (the tool's dry-run is a
    no-op). This is the symmetric oracle of the test above: the
    catalogue MUST always be in agreement with the on-disk truth when
    main is green.
    """
    report = build_honesty_report(_REPO_ROOT)
    assert report["to_flip_count"] == 0, (
        f"Honesty tool would flip {report['to_flip_count']} rows. "
        "Run `python -m tools.election_events_honesty` to bring the "
        "catalogue back into agreement with on-disk truth."
    )
