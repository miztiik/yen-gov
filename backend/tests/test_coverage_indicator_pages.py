"""Tests for the per-indicator docs generator (Phase 1).

Two tiers per CLAUDE.md §15:
- Unit: pure ``render_page`` against a hand-built minimal artifact dict;
  asserts required sections present AND that omitted optional fields do
  NOT produce empty headings.
- Integration: ``write_pages`` against the real ``datasets/indicators/in/``
  tree; asserts every topic on disk gets at least one page, every page
  starts with the auto-gen banner, ``index.md`` lists every artifact id.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yen_gov.coverage_indicator_pages import (
    INDICATORS_REL,
    INDICATOR_DOCS_REL,
    IndicatorArtifact,
    iter_indicator_artifacts,
    render_page,
    write_pages,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _minimal_artifact(**overrides) -> IndicatorArtifact:
    doc = {
        "$schema": "https://yen-gov.github.io/schemas/indicator.schema.json",
        "$schema_version": "1.4",
        "sources": [
            {"url": "https://example.gov.in/data.csv", "fetched_at": "2026-05-15T00:00:00Z"}
        ],
        "coverage": {
            "spatial": "India (states)",
            "temporal": "2010-04..2024-04",
            "admin_level": "state",
        },
        "license": {
            "id": "GoI-OpenData",
            "name": "Government of India Open Data License",
            "url": "https://www.data.gov.in/government-open-data-license-india",
            "redistributable": True,
        },
        "indicator": {
            "id": "energy/test_indicator",
            "title": "Test indicator title",
            "description": "First sentence of the definition. Second sentence with more detail.",
            "entity_kind": "state",
            "time_grain": "fiscal_year",
            "value_kind": "raw",
            "unit": "Mt",
            "direction": "neutral",
            "comparability": "comparable_with_normalisation",
        },
        "rows": [
            {"entity_id": "S01", "time": "2010-04", "value": 1.0},
            {"entity_id": "S02", "time": "2010-04", "value": 2.0},
            {"entity_id": "S01", "time": "2011-04", "value": 1.5},
        ],
    }
    doc.update(overrides)
    return IndicatorArtifact(
        path_rel="datasets/indicators/in/energy/test_indicator.json",
        topic="energy",
        basename="test_indicator",
        doc=doc,
    )


def test_render_page_includes_required_sections() -> None:
    out = render_page(_minimal_artifact())
    # H1
    assert out.startswith("# `energy/test_indicator`")
    # Auto-gen banner
    assert "AUTO-GENERATED" in out
    # Definition section + content
    assert "## Definition" in out
    assert "First sentence of the definition." in out
    # Signature table row
    assert "## Signature" in out
    assert "| Entity kind | `state` |" in out
    # Coverage line
    assert "## Coverage" in out
    assert "**Temporal**: 2010-04..2024-04 (2 periods)" in out
    assert "**Spatial**: India (states) (2 entities)" in out
    assert "**Rows on disk**: 3" in out
    # Sources bullet with the URL
    assert "## Sources" in out
    assert "https://example.gov.in/data.csv" in out
    # License
    assert "## License" in out
    assert "Government of India Open Data License" in out
    # Citation block
    assert "## Citation" in out
    assert "schema v1.4" in out
    # Schema footer
    assert "## Schema" in out


def test_render_page_omits_empty_sections_for_missing_fields() -> None:
    """Anti-empty-section invariant — the bug a future maintainer will introduce."""
    art = _minimal_artifact()
    # Strip optional fields entirely
    art.doc["indicator"].pop("methodology_vintage", None)
    art.doc.pop("series_breaks", None)
    art.doc["indicator"].pop("notes", None)
    out = render_page(art)
    # None of these headings may appear when their data is absent
    assert "## Methodology vintage" not in out
    assert "## Series breaks" not in out
    assert "## Notes" not in out
    # No two consecutive blank H2 headings (defence-in-depth)
    assert "##  ##" not in out


def test_render_page_includes_methodology_and_breaks_when_present() -> None:
    art = _minimal_artifact()
    art.doc["indicator"]["methodology_vintage"] = "Source X, Table 7. Aggregated by SUM."
    art.doc["series_breaks"] = [
        {"at_time": "2014-04", "kind": "definition_change", "note": "Coverage broadened."}
    ]
    out = render_page(art)
    assert "## Methodology vintage" in out
    assert "Source X, Table 7" in out
    assert "## Series breaks" in out
    assert "| `2014-04` | `definition_change` | Coverage broadened. |" in out
    assert "Renderer guard" in out


def test_iter_artifacts_skips_notes_sidecars(tmp_path: Path) -> None:
    base = tmp_path / "datasets" / "indicators" / "in" / "energy"
    base.mkdir(parents=True)
    (base / "real.json").write_text(
        json.dumps(
            {
                "indicator": {"id": "energy/real"},
                "coverage": {"temporal": "2020"},
                "rows": [],
            }
        ),
        encoding="utf-8",
    )
    (base / "real.notes.json").write_text(json.dumps({"related": []}), encoding="utf-8")
    found = list(iter_indicator_artifacts(tmp_path))
    assert len(found) == 1
    assert found[0].basename == "real"


def test_write_pages_against_real_datasets() -> None:
    """Integration: emit the full tree from the live datasets/ tree."""
    written = write_pages(REPO_ROOT)
    assert len(written) >= 2  # at least one page + index

    docs_root = REPO_ROOT / INDICATOR_DOCS_REL
    index_path = docs_root / "index.md"
    assert index_path.exists()
    index_body = index_path.read_text(encoding="utf-8")
    assert "AUTO-GENERATED" in index_body

    # Every topic dir on disk under indicators/in must produce at least one page
    indicators_root = REPO_ROOT / INDICATORS_REL
    topic_dirs = [p.name for p in indicators_root.iterdir() if p.is_dir()]
    for topic in topic_dirs:
        topic_pages = list((docs_root / topic).glob("*.md"))
        assert topic_pages, f"no pages emitted for topic {topic!r}"

    # Every emitted page begins with H1 + auto-gen banner
    for p in written:
        if p.name == "index.md":
            continue
        body = p.read_text(encoding="utf-8")
        assert body.startswith("# `"), f"missing H1 in {p}"
        assert "AUTO-GENERATED" in body, f"missing banner in {p}"

    # Every artifact id appears in index.md
    for art in iter_indicator_artifacts(REPO_ROOT):
        ind_id = (art.doc.get("indicator") or {}).get("id") or f"{art.topic}/{art.basename}"
        assert f"`{ind_id}`" in index_body, f"index.md missing id {ind_id}"
