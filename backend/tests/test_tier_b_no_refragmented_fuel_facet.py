"""Tier-B tests for ``tier_b_no_refragmented_fuel_facet_csv``.

CSV-era sibling of the JSON-shard fence ``tier_b_no_new_sub_fuel_shards``.
PR #1097 migrated the fuel-faceted installed-capacity measures to the faceted
``datasets/data/datapoints/geo_by_fuel/*.csv`` class, and the CEA + ICED
adapters now emit that faceted shape directly (CEA+ICED faceted-ingestion
plan, Rows 2-3). This fence forbids re-fragmenting those measures back into
per-fuel / parent-single-file files under ``datasets/data/datapoints/geo/``.

Scope (plan R-H): installed-capacity families only; the net-transfers
estimate-stage fence is owned by the RBI agent and lands separately.

Per CLAUDE.md anti-pattern (pytest never walks the real corpus) these tests
use ``tmp_path`` fixtures only.
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.validate import tier_b_no_refragmented_fuel_facet_csv


def _geo(root: Path) -> Path:
    d = root / "datasets" / "data" / "datapoints" / "geo"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _touch(root: Path, *stems: str) -> None:
    geo = _geo(root)
    for stem in stems:
        (geo / f"{stem}.csv").write_text(
            "entity_id,time,value,source_id\n", encoding="utf-8"
        )


def test_noop_when_geo_dir_absent(tmp_path):
    assert tier_b_no_refragmented_fuel_facet_csv(tmp_path) == []


def test_passes_on_allowed_single_value_files(tmp_path):
    # The publisher-split allocated files are single-value (stay in geo/); a
    # plain single-value indicator is fine.
    _touch(
        tmp_path,
        "installed-capacity-allocated-iced-mw",
        "literacy-rate-pct-total",
    )
    assert tier_b_no_refragmented_fuel_facet_csv(tmp_path) == []


def test_rejects_per_fuel_child(tmp_path):
    _touch(tmp_path, "installed-capacity-mw-coal")
    failures = tier_b_no_refragmented_fuel_facet_csv(tmp_path)
    assert len(failures) == 1
    assert "re-fragmented fuel-facet CSV" in failures[0].message
    assert "geo_by_fuel/installed-capacity-mw.csv" in failures[0].message


def test_rejects_geographical_and_snapshot_fuel_children(tmp_path):
    _touch(
        tmp_path,
        "installed-capacity-geographical-mw-renewable",
        "installed-capacity-snapshot-mw-gas",
    )
    failures = tier_b_no_refragmented_fuel_facet_csv(tmp_path)
    assert len(failures) == 2
    measures = {
        m
        for f in failures
        for m in (
            "installed-capacity-geographical-mw",
            "installed-capacity-snapshot-mw",
        )
        if m in f.message
    }
    assert measures == {
        "installed-capacity-geographical-mw",
        "installed-capacity-snapshot-mw",
    }


def test_rejects_parent_single_file_form(tmp_path):
    # The parent single-file form under geo/ is also re-fragmentation -- the
    # measure is faceted now (data lives in geo_by_fuel/).
    _touch(tmp_path, "installed-capacity-geographical-mw")
    failures = tier_b_no_refragmented_fuel_facet_csv(tmp_path)
    assert len(failures) == 1
    assert "re-fragmented fuel-facet CSV" in failures[0].message


def test_allocated_mw_not_false_positive(tmp_path):
    # The publisher-split allocated files must NOT be caught by the
    # `installed-capacity-mw` prefix rule (different measure, stays single).
    _touch(
        tmp_path,
        "installed-capacity-allocated-iced-mw",
        "installed-capacity-statewise-total-rbi-mw",
    )
    assert tier_b_no_refragmented_fuel_facet_csv(tmp_path) == []
