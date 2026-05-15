"""Unit tests for tools.boundaries.snapshot.apply_state_filter — Phase 1b commit 2.

Per CLAUDE.md §15 + Holy Law #7: real fixtures, no mocks. The fixtures are
hand-built feature dicts so this suite has no py7zr dependency (the heavier
geojsonl_7z integration test depends on py7zr separately).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "boundaries"))

import snapshot  # noqa: E402  (after sys.path manipulation)


def _feat(state_lgd: int, dist_lgd: int) -> dict:
    return {
        "type": "Feature",
        "properties": {"state_lgd": state_lgd, "dist_lgd": dist_lgd},
        "geometry": {"type": "Point", "coordinates": [80.0, 13.0]},
    }


@pytest.fixture
def mixed_states() -> list[dict]:
    # 3 TN (state_lgd=33), 2 KL (state_lgd=32), 1 KA (state_lgd=29).
    return [
        _feat(33, 603),
        _feat(33, 532),
        _feat(33, 561),
        _feat(32, 580),
        _feat(32, 581),
        _feat(29, 593),
    ]


def test_equals_keeps_only_matching(mixed_states: list[dict]) -> None:
    kept, dropped = snapshot.apply_state_filter(
        mixed_states, {"property": "state_lgd", "equals": 33}
    )
    assert len(kept) == 3
    assert len(dropped) == 3
    assert all(f["properties"]["state_lgd"] == 33 for f in kept)
    assert all(f["properties"]["state_lgd"] != 33 for f in dropped)


def test_one_of_keeps_union(mixed_states: list[dict]) -> None:
    kept, dropped = snapshot.apply_state_filter(
        mixed_states, {"property": "state_lgd", "one_of": [33, 32]}
    )
    assert len(kept) == 5
    assert len(dropped) == 1
    assert dropped[0]["properties"]["state_lgd"] == 29


def test_empty_kept_fails_loud(mixed_states: list[dict]) -> None:
    """Fowler v5 nit: a state_filter that matches zero features is a config
    error (wrong property name or wrong value), not a legitimate empty
    state. Don't emit an empty FeatureCollection silently."""
    with pytest.raises(ValueError, match="matched zero features"):
        snapshot.apply_state_filter(
            mixed_states, {"property": "state_lgd", "equals": 999}
        )


def test_missing_property_treated_as_no_match() -> None:
    features = [
        {"type": "Feature", "properties": {"name": "no-lgd-here"}, "geometry": None},
        _feat(33, 603),
    ]
    kept, dropped = snapshot.apply_state_filter(
        features, {"property": "state_lgd", "equals": 33}
    )
    assert len(kept) == 1
    assert len(dropped) == 1


def test_requires_equals_or_one_of(mixed_states: list[dict]) -> None:
    with pytest.raises(ValueError, match="requires `equals` or `one_of`"):
        snapshot.apply_state_filter(mixed_states, {"property": "state_lgd"})
