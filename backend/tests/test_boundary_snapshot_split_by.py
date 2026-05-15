"""Unit tests for tools.boundaries.snapshot — split_by + index manifest helpers.

Phase 1b commit 3. Per CLAUDE.md §15 + Holy Law #7: real fixtures, no mocks.
No py7zr dependency — these helpers operate on in-memory feature dicts and the
local filesystem. Manifest output is validated against
boundary.villages_index.schema.json so a future schema bump has to face the
test as well.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "boundaries"))

import snapshot  # noqa: E402  (after sys.path manipulation)

jsonschema = pytest.importorskip("jsonschema")


def _feat(dist_lgd: int | None, name: str = "x") -> dict:
    props: dict = {"name": name}
    if dist_lgd is not None:
        props["dist_lgd"] = dist_lgd
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Point", "coordinates": [80.0, 13.0]},
    }


# --- apply_split_by --------------------------------------------------------


def test_split_by_groups_by_property() -> None:
    features = [_feat(603, "a"), _feat(603, "b"), _feat(532, "c"), _feat(561, "d")]
    groups, dropped = snapshot.apply_split_by(features, {"property": "dist_lgd"})
    assert set(groups.keys()) == {603, 532, 561}
    assert len(groups[603]) == 2
    assert len(groups[532]) == 1
    assert dropped == []


def test_split_by_drops_features_missing_property() -> None:
    features = [_feat(603), _feat(None), _feat(532)]
    groups, dropped = snapshot.apply_split_by(features, {"property": "dist_lgd"})
    assert set(groups.keys()) == {603, 532}
    assert len(dropped) == 1


# --- emit_index_manifest ---------------------------------------------------


def _load_index_schema() -> dict:
    schema_path = REPO / "datasets" / "schemas" / "boundary.villages_index.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_emit_index_manifest_writes_valid_payload(tmp_path: Path) -> None:
    index_path = tmp_path / "S22-villages-index.json"
    snapshot.emit_index_manifest(
        index_path,
        state_lgd=33,
        group_keys=[603, 532, 561],
        schema_basename="boundary.villages_index.schema.json",
    )

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    # Schema conformance — the test would catch a future shape drift even if
    # the helper were "fixed" to silently emit something else.
    jsonschema.validate(payload, _load_index_schema())

    assert payload["state_lgd"] == "33"
    # Sorted ascending lexicographically per schema requirement.
    assert payload["district_lgd_codes"] == ["532", "561", "603"]
    assert payload["$schema_version"] == "1.0"
    assert payload["generated_at"].endswith("Z")


def test_emit_index_manifest_dedupes_keys(tmp_path: Path) -> None:
    index_path = tmp_path / "out.json"
    snapshot.emit_index_manifest(
        index_path,
        state_lgd=33,
        group_keys=[603, 603, 532],
        schema_basename="boundary.villages_index.schema.json",
    )
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["district_lgd_codes"] == ["532", "603"]


def test_emit_index_manifest_atomic_no_partial_on_existing(tmp_path: Path) -> None:
    """Pre-existing manifest is replaced atomically; no `.part` artifact remains."""
    index_path = tmp_path / "S22-villages-index.json"
    index_path.write_text('{"old":"payload"}', encoding="utf-8")

    snapshot.emit_index_manifest(
        index_path,
        state_lgd=33,
        group_keys=[603],
        schema_basename="boundary.villages_index.schema.json",
    )

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert payload["district_lgd_codes"] == ["603"]
    # Temp file MUST be cleaned up by the rename — no half-written sibling.
    assert not (tmp_path / "S22-villages-index.json.part").exists()


def test_emit_index_manifest_empty_keys_allowed(tmp_path: Path) -> None:
    """Schema permits an empty district_lgd_codes array (state with no shards
    emitted yet). The fail-loud rule lives in apply_state_filter, not here."""
    index_path = tmp_path / "empty.json"
    snapshot.emit_index_manifest(
        index_path,
        state_lgd=33,
        group_keys=[],
        schema_basename="boundary.villages_index.schema.json",
    )
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    jsonschema.validate(payload, _load_index_schema())
    assert payload["district_lgd_codes"] == []
