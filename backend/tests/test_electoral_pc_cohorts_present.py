"""Regression test pinning electoral.csv PC cohort presence per
TODO/20260613-party-deferred-followups-plan.md PR-5 (collapsed-with-receipt).

The pre-1999 LS history ingest plan-doc (Max Q1.1c) anticipated a missing
1967 cohort would need seeding. Orchestrator pre-flight on origin/main
HEAD 284b0581a discovered all 4 PC cohorts already present on disk with
the expected row counts. This test locks them so any regression that drops
the cohort surfaces immediately.

Expected cohort sizes derived from the actual on-disk counts at the time
of PR-5; tolerance of +/-25 rows allows for legitimate (PR-9+) entity
register edits without breaking this test."""

import csv
import re
from collections import Counter
from pathlib import Path


def test_electoral_pc_cohorts_present_with_expected_sizes():
    """4 PC cohorts (1962/1967/1976/2008) must be present on disk with
    row counts within +/-25 of the orchestrator-verified baseline."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    electoral = repo_root / "datasets" / "data" / "entities" / "electoral.csv"
    assert electoral.exists(), f"electoral.csv missing at {electoral}"

    csv.field_size_limit(10 ** 7)
    delim_count: Counter[str] = Counter()
    with electoral.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["entity_kind"] == "pc":
                delim_count[r["delim_year"]] += 1

    # Expected per PR-5 receipt (orchestrator pre-flight 2026-06-13).
    EXPECTED = {
        "1962": 427,
        "1967": 493,
        "1976": 574,
        "2008": 544,
    }
    TOLERANCE = 25  # allow legitimate entity register edits

    for delim, expected in EXPECTED.items():
        actual = delim_count.get(delim, 0)
        assert abs(actual - expected) <= TOLERANCE, (
            f"PC cohort delim_year={delim} drifted: expected ~{expected} "
            f"(+/-{TOLERANCE}), got {actual}. If intentional, update PR-5's "
            f"receipt in TODO/20260613-party-deferred-followups-plan.md."
        )


def test_electoral_pc_cohort_grammar_uniformity():
    """All PC entity_ids must match the IN-PC-<delim>-<slug>-<num|eci<n>>
    grammar. Catches accidental shape drift."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    electoral = repo_root / "datasets" / "data" / "entities" / "electoral.csv"

    csv.field_size_limit(10 ** 7)
    pat = re.compile(r"^IN-PC-(\d{4})-([a-z0-9-]+)-([0-9]+|eci\d+)$")

    bad = []
    with electoral.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["entity_kind"] == "pc":
                if not pat.match(r["entity_id"]):
                    bad.append(r["entity_id"])

    assert not bad, f"PC entity_ids violated grammar (first 5): {bad[:5]}"
