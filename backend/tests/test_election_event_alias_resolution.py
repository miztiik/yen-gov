"""PR-W2a G6 oracle: every period_label in the canonical electoral CSVs
resolves through the strangler alias index.

For each row in datasets/data/datapoints/electoral/*.csv, the period_label
value MUST be present in the union {event_id} U {event_id_aliases} across
every event row in datasets/taxonomy/election_events.json.

This is the load-bearing assertion that the citizen-facing event_id rename
(PR-W2a, 2026-06-10) does not break the backend-written cohort period_label
values on disk. Old `LsGenJun2024` / `AcGenMay2026` literals resolve via
the alias array to the renamed `general-2024` / `assembly-2026` ids.

When this red-fails, the unresolved label is the bug -- either the alias
array on the corresponding event row is missing the cohort id (most likely),
or the CSV contains a label that belongs to no known event (rare; would
indicate an upstream ingest bug, in which case xfail with a citation back
to the W1c parity-oracle finding).
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
EVENTS_JSON = REPO / "datasets" / "taxonomy" / "election_events.json"
ELECTORAL_GLOB = REPO / "datasets" / "data" / "datapoints" / "electoral"


@pytest.mark.skipif(not EVENTS_JSON.is_file(), reason="catalogue absent")
@pytest.mark.skipif(not ELECTORAL_GLOB.is_dir(), reason="electoral CSV dir absent")
def test_electoral_csv_period_labels_resolve_via_alias_index():
    """Every period_label in every electoral CSV resolves via event_id or alias."""
    catalogue = json.loads(EVENTS_JSON.read_text(encoding="utf-8"))

    # Build a flat set: each event row contributes its event_id plus every alias.
    known: set[str] = set()
    for entries in catalogue["states"].values():
        for entry in entries:
            known.add(str(entry["event_id"]))
            for alias in entry.get("event_id_aliases", []):
                known.add(str(alias))

    unresolved: dict[str, set[str]] = {}  # label -> set of CSV stems that carry it
    csv_paths = sorted(ELECTORAL_GLOB.glob("*_election_results.csv"))
    # Defensive: the test is only meaningful when there are CSVs to walk.
    assert csv_paths, (
        f"No electoral CSVs found under {ELECTORAL_GLOB} -- the strangler "
        "test has nothing to bind. If this is a fresh worktree without "
        "data, skip via fixture."
    )
    for csv_path in csv_paths:
        with csv_path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                label = (row.get("period_label") or row.get("event_id") or "").strip()
                if label and label not in known:
                    unresolved.setdefault(label, set()).add(csv_path.stem)

    if unresolved:
        # Render a deterministic, citable failure message.
        rendered = sorted(
            (label, sorted(stems)) for label, stems in unresolved.items()
        )
        pytest.fail(
            "PR-W2a strangler-fig oracle: the following period_label values in "
            "datasets/data/datapoints/electoral/*.csv resolve to NO event row "
            "in datasets/taxonomy/election_events.json (neither event_id nor "
            "event_id_aliases). Add the cohort id to the matching row's "
            f"event_id_aliases array. Unresolved: {rendered}"
        )
