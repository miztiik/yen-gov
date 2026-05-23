"""Tier-A tests for ``yen_gov.validate.tier_b_indicator_alias_window``.

Per CLAUDE.md §15 + §10 anti-patterns: operates on ``tmp_path``, never
walks the real corpus. Asserts the 60-day expiry window contract on the
v1.1 indicator-catalogue id_aliases / deprecated_in fields.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from yen_gov.validate import (
    INDICATOR_ALIAS_WINDOW_DAYS,
    INDICATOR_CATALOGUE_JSON,
    run,
    tier_b_indicator_alias_window,
)


_MIN_PARENT_ROW = {
    "indicator_id": "candidate-votes-polled",
    "label_short": "Candidate votes",
    "label_long": "Votes polled by each candidate in an AC contest",
    "description_short": "Votes polled by each candidate in an AC contest.",
    "unit": "votes",
    "cadence": "ad_hoc",
    "family": "elections",
    "pillar": "politics",
    "value_kind": "count",
    "direction": "neutral",
    "attribution_geography": "where_resident",
    "comparability": "directional_only",
    "parent_indicator_id": None,
}


def _write_catalogue(root: Path, rows: list[dict]) -> None:
    """Write a minimal indicators.json under the catalogue path."""
    catalogue_path = root / INDICATOR_CATALOGUE_JSON
    catalogue_path.parent.mkdir(parents=True, exist_ok=True)
    catalogue_path.write_text(
        json.dumps(
            {
                "$schema": "./indicator-catalogue.schema.json",
                "$schema_version": "1.1",
                "indicators": rows,
            }
        ),
        encoding="utf-8",
    )


# -- No-op + happy-path cases ------------------------------------------------


def test_noop_when_catalogue_missing(tmp_path):
    """No-op when datasets/taxonomy/indicators.json does not exist."""
    failures = tier_b_indicator_alias_window(tmp_path)
    assert failures == []


def test_passes_when_no_rows_have_aliases(tmp_path):
    """Rows without id_aliases never trip the expiry window."""
    _write_catalogue(tmp_path, [_MIN_PARENT_ROW])
    failures = tier_b_indicator_alias_window(tmp_path)
    assert failures == []


def test_passes_when_alias_anchor_within_window(tmp_path):
    """deprecated_in within 60 days of today: passes."""
    today = date(2026, 5, 22)
    row = {
        **_MIN_PARENT_ROW,
        "id_aliases": ["elections/candidate_votes"],
        "deprecated_in": (today - timedelta(days=10)).isoformat(),
    }
    _write_catalogue(tmp_path, [row])
    failures = tier_b_indicator_alias_window(tmp_path, today=today)
    assert failures == []


def test_passes_at_exact_window_boundary(tmp_path):
    """deprecated_in exactly 60 days ago: still passes (window is inclusive)."""
    today = date(2026, 5, 22)
    row = {
        **_MIN_PARENT_ROW,
        "id_aliases": ["elections/candidate_votes"],
        "deprecated_in": (today - timedelta(days=60)).isoformat(),
    }
    _write_catalogue(tmp_path, [row])
    failures = tier_b_indicator_alias_window(tmp_path, today=today)
    assert failures == []


def test_passes_when_deprecated_in_set_but_no_aliases(tmp_path):
    """Reverse pairing (deprecated_in set, id_aliases empty) is legal."""
    row = {**_MIN_PARENT_ROW, "deprecated_in": "2026-05-22"}
    _write_catalogue(tmp_path, [row])
    failures = tier_b_indicator_alias_window(tmp_path)
    assert failures == []


# -- Failure cases ------------------------------------------------------------


def test_fails_when_alias_older_than_window(tmp_path):
    """deprecated_in older than 60 days: rejected with cleanup message."""
    today = date(2026, 5, 22)
    row = {
        **_MIN_PARENT_ROW,
        "id_aliases": ["elections/candidate_votes"],
        "deprecated_in": (today - timedelta(days=61)).isoformat(),
    }
    _write_catalogue(tmp_path, [row])
    failures = tier_b_indicator_alias_window(tmp_path, today=today)
    assert len(failures) == 1
    msg = failures[0].message
    assert "id_aliases expired" in msg
    assert "61 days old" in msg
    assert "60 days" in msg


def test_fails_far_beyond_window(tmp_path):
    """deprecated_in very old (180 days): rejected with correct age."""
    today = date(2026, 5, 22)
    row = {
        **_MIN_PARENT_ROW,
        "id_aliases": ["elections/candidate_votes"],
        "deprecated_in": (today - timedelta(days=180)).isoformat(),
    }
    _write_catalogue(tmp_path, [row])
    failures = tier_b_indicator_alias_window(tmp_path, today=today)
    assert len(failures) == 1
    assert "180 days old" in failures[0].message


def test_fails_when_id_aliases_set_but_deprecated_in_null(tmp_path):
    """Paired-semantic violation: id_aliases non-empty REQUIRES deprecated_in."""
    row = {**_MIN_PARENT_ROW, "id_aliases": ["elections/candidate_votes"]}
    _write_catalogue(tmp_path, [row])
    failures = tier_b_indicator_alias_window(tmp_path)
    assert len(failures) == 1
    msg = failures[0].message
    assert "id_aliases set but deprecated_in is null" in msg
    assert "paired" in msg


def test_fails_when_id_aliases_set_but_deprecated_in_empty_string(tmp_path):
    """Empty-string deprecated_in is treated the same as null."""
    row = {
        **_MIN_PARENT_ROW,
        "id_aliases": ["elections/candidate_votes"],
        "deprecated_in": "",
    }
    _write_catalogue(tmp_path, [row])
    failures = tier_b_indicator_alias_window(tmp_path)
    assert len(failures) == 1
    assert "null" in failures[0].message


def test_fails_on_malformed_deprecated_in(tmp_path):
    """Malformed ISO date (day-first) is rejected with a parse-error message."""
    row = {
        **_MIN_PARENT_ROW,
        "id_aliases": ["elections/candidate_votes"],
        "deprecated_in": "22-05-2026",
    }
    _write_catalogue(tmp_path, [row])
    failures = tier_b_indicator_alias_window(tmp_path)
    assert len(failures) == 1
    assert "not a valid ISO" in failures[0].message


def test_reports_all_violations_independently(tmp_path):
    """Two rows with two different violation kinds: both reported."""
    today = date(2026, 5, 22)
    row_a = {
        **_MIN_PARENT_ROW,
        "indicator_id": "ac-votes-polled",
        "label_short": "AC votes polled",
        "label_long": "Total votes polled in an AC contest",
        "description_short": "Total votes polled in an AC contest.",
        "id_aliases": ["elections/ac_votes"],
        "deprecated_in": (today - timedelta(days=100)).isoformat(),
    }
    row_b = {
        **_MIN_PARENT_ROW,
        "indicator_id": "ac-turnout-pct",
        "label_short": "AC turnout",
        "label_long": "AC turnout as a percent of total electors",
        "description_short": "AC turnout percentage of total electors.",
        "id_aliases": ["elections/ac_turnout"],
    }
    _write_catalogue(tmp_path, [row_a, row_b])
    failures = tier_b_indicator_alias_window(tmp_path, today=today)
    assert len(failures) == 2
    messages = [f.message for f in failures]
    assert any("ac-votes-polled" in m and "expired" in m for m in messages)
    assert any("ac-turnout-pct" in m and "null" in m for m in messages)


# -- Constants + integration --------------------------------------------------


def test_window_constant_is_60_days():
    """Lock the user-direction-Q3 60-day window into a test."""
    assert INDICATOR_ALIAS_WINDOW_DAYS == 60


def test_chained_into_run(tmp_path):
    """run() must invoke tier_b_indicator_alias_window.

    Regression guard: without this, someone could remove the call from
    run() and only the unit tests above would catch it. Sets up an
    expired-alias row so the failure surfaces in run()'s aggregate list.
    """
    # Minimal schemas/ dir so load_schemas doesn't error.
    schemas_dir = tmp_path / "datasets" / "schemas"
    schemas_dir.mkdir(parents=True)
    today = date.today()
    row = {
        **_MIN_PARENT_ROW,
        "id_aliases": ["elections/candidate_votes"],
        "deprecated_in": (today - timedelta(days=200)).isoformat(),
    }
    _write_catalogue(tmp_path, [row])
    failures = run(tmp_path)
    alias_failures = [f for f in failures if "id_aliases expired" in f.message]
    assert len(alias_failures) == 1
