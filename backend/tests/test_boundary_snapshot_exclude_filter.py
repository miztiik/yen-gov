"""Unit tests for tools.boundaries.snapshot.apply_exclude_filter — Phase D.2.

Per CLAUDE.md §15 + Holy Law #7: real fixtures, no mocks. The fixtures are
hand-built feature dicts so this suite has no py7zr dependency.

The `apply_exclude_filter` directive was added in Phase D.2 (AC consolidation
promote) so `pipeline.json` entries can drop features whose property value
matches a sentinel (e.g. `status == "Pre delimitation"` on ramSeraph LGD
AC release per the D.1 recon note in `notes/2026-05-25-d1-ac-consolidation-recon.md`).
Unlike `state_filter`, an empty `kept` list is a valid outcome — the caller
explicitly authorised the drop.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "boundaries"))

import snapshot  # noqa: E402  (after sys.path manipulation)


def _feat(status: str | None, ac_id: str) -> dict:
    props: dict = {"AC_ID": ac_id}
    if status is not None:
        props["status"] = status
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Point", "coordinates": [80.0, 13.0]},
    }


@pytest.fixture
def mixed_status() -> list[dict]:
    # 4 current (status=' '), 2 pre-delim, 1 missing-status.
    return [
        _feat(" ", "10001"),
        _feat(" ", "10002"),
        _feat("Pre delimitation", "10003"),
        _feat(" ", "10004"),
        _feat("Pre delimitation", "10005"),
        _feat(" ", "10006"),
        _feat(None, "10007"),
    ]


def test_equals_drops_matching_keeps_rest(mixed_status: list[dict]) -> None:
    kept, dropped = snapshot.apply_exclude_filter(
        mixed_status, {"property": "status", "equals": "Pre delimitation"}
    )
    assert len(kept) == 5  # 4 current + 1 missing-status
    assert len(dropped) == 2
    assert all(f["properties"].get("status") != "Pre delimitation" for f in kept)
    assert all(f["properties"]["status"] == "Pre delimitation" for f in dropped)


def test_one_of_drops_union(mixed_status: list[dict]) -> None:
    kept, dropped = snapshot.apply_exclude_filter(
        mixed_status, {"property": "status", "one_of": ["Pre delimitation", " "]}
    )
    # Drops both " " (current) AND "Pre delimitation"; keeps only missing-status row.
    assert len(kept) == 1
    assert len(dropped) == 6
    assert kept[0]["properties"]["AC_ID"] == "10007"


def test_no_match_is_noop(mixed_status: list[dict]) -> None:
    """An exclude_filter that matches zero features is a valid no-op — common
    when filtering for a vintage tag that some upstream slices don't carry."""
    kept, dropped = snapshot.apply_exclude_filter(
        mixed_status, {"property": "status", "equals": "Never appears"}
    )
    assert len(kept) == len(mixed_status)
    assert len(dropped) == 0


def test_empty_kept_is_valid() -> None:
    """Unlike state_filter, exclude_filter may legitimately drop everything;
    the caller explicitly authorised the drop. No exception."""
    features = [_feat("Pre delimitation", "10001"), _feat("Pre delimitation", "10002")]
    kept, dropped = snapshot.apply_exclude_filter(
        features, {"property": "status", "equals": "Pre delimitation"}
    )
    assert kept == []
    assert len(dropped) == 2


def test_missing_property_treated_as_no_match(mixed_status: list[dict]) -> None:
    """Features that lack the property entirely are NOT dropped (the exclude
    targets a specific value; absence is not equality)."""
    kept, dropped = snapshot.apply_exclude_filter(
        mixed_status, {"property": "status", "equals": "Pre delimitation"}
    )
    missing_row = next(f for f in kept if f["properties"]["AC_ID"] == "10007")
    assert "status" not in missing_row["properties"]


def test_requires_equals_or_one_of(mixed_status: list[dict]) -> None:
    with pytest.raises(ValueError, match="requires `equals` or `one_of`"):
        snapshot.apply_exclude_filter(mixed_status, {"property": "status"})
