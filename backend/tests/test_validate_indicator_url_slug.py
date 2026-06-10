"""Unit tests for ``tier_b_indicator_url_slug_unique`` (v3.0).

Per Deferral 2 of ``TODO/20260609-url-prefix-drop-phase0-plan.md`` (Hans +
Max + Gregor unanimous verdict 2026-06-10), the canonical-catalogue
``url_slug`` + ``url_slug_history[]`` entries form a global ledger that
MUST be unique across the catalogue -- a retired slug may NEVER be
reused for a different indicator (forever-redirect contract).

Mirrors the cross-row + cross-history collision throw in
``buildIndicatorCatalogueIndex`` (frontend/src/lib/indicator-catalogue.ts
v3.0). The Tier-B check surfaces the same violation pre-publish so the
operator never has to wait for a browser load failure.
"""

from __future__ import annotations

import json
from pathlib import Path

import yen_gov.validate as v
from yen_gov.validate import run


def _write_indicator_catalogue(root: Path, rows: list[dict]) -> None:
    (root / "datasets" / "taxonomy").mkdir(parents=True, exist_ok=True)
    payload = {
        "$schema": "../schemas/indicator-catalogue.schema.json",
        "$schema_version": "3.0",
        "indicators": rows,
    }
    (root / "datasets" / "taxonomy" / "indicators.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_no_failures_when_all_url_slugs_distinct(tmp_path: Path):
    rows = [
        {
            "indicator_id": "candidate-votes-polled",
            "url_slug": "candidate-votes-polled",
        },
        {
            "indicator_id": "candidate-vote-share-pct",
            "url_slug": "candidate-vote-share-pct",
        },
    ]
    _write_indicator_catalogue(tmp_path, rows)

    failures = v.tier_b_indicator_url_slug_unique(tmp_path)
    assert failures == [], failures


def test_reports_current_url_slug_collision_across_rows(tmp_path: Path):
    rows = [
        {
            "indicator_id": "candidate-votes-polled",
            "url_slug": "shared-slug",
        },
        {
            "indicator_id": "candidate-vote-share-pct",
            "url_slug": "shared-slug",
        },
    ]
    _write_indicator_catalogue(tmp_path, rows)

    failures = v.tier_b_indicator_url_slug_unique(tmp_path)
    assert len(failures) == 1, failures
    msg = failures[0].message
    assert "shared-slug" in msg
    assert "candidate-vote-share-pct" in msg
    assert "candidate-votes-polled" in msg
    assert failures[0].tier == "B"
    assert failures[0].file == "datasets/taxonomy/indicators.json"


def test_reports_current_vs_historical_collision(tmp_path: Path):
    # Row A retired "old-slug" into its url_slug_history; row B then
    # mints "old-slug" as its CURRENT url_slug -- forever-redirect
    # ledger now ambiguous, MUST fail.
    rows = [
        {
            "indicator_id": "candidate-votes-polled",
            "url_slug": "candidate-votes",
            "url_slug_history": ["old-slug"],
        },
        {
            "indicator_id": "candidate-vote-share-pct",
            "url_slug": "old-slug",
        },
    ]
    _write_indicator_catalogue(tmp_path, rows)

    failures = v.tier_b_indicator_url_slug_unique(tmp_path)
    assert len(failures) == 1, failures
    assert "old-slug" in failures[0].message


def test_reports_shared_history_entry(tmp_path: Path):
    # Two rows both list the same slug in url_slug_history --
    # equally ambiguous for the redirect ledger.
    rows = [
        {
            "indicator_id": "candidate-votes-polled",
            "url_slug": "a-current",
            "url_slug_history": ["shared-old"],
        },
        {
            "indicator_id": "candidate-vote-share-pct",
            "url_slug": "b-current",
            "url_slug_history": ["shared-old"],
        },
    ]
    _write_indicator_catalogue(tmp_path, rows)

    failures = v.tier_b_indicator_url_slug_unique(tmp_path)
    assert len(failures) == 1, failures
    assert "shared-old" in failures[0].message


def test_check_is_noop_when_catalogue_absent(tmp_path: Path):
    failures = v.tier_b_indicator_url_slug_unique(tmp_path)
    assert failures == []


def test_check_is_noop_when_catalogue_is_invalid_json(tmp_path: Path):
    (tmp_path / "datasets" / "taxonomy").mkdir(parents=True)
    (tmp_path / "datasets" / "taxonomy" / "indicators.json").write_text(
        "{ not valid json", encoding="utf-8"
    )
    failures = v.tier_b_indicator_url_slug_unique(tmp_path)
    assert failures == []


def test_check_chained_into_run(tmp_path: Path):
    """Regression guard: tier_b_indicator_url_slug_unique must be called
    by run(). Without this chain the v3.0 contract would silently pass
    on any catalogue that re-used a retired slug."""
    # Seed the real schemas dir so run() can resolve them.
    schemas_dir = tmp_path / "datasets" / "schemas"
    schemas_dir.mkdir(parents=True)
    repo = Path(__file__).resolve().parents[2]
    for src in (repo / "datasets" / "schemas").glob("*.schema.json"):
        (schemas_dir / src.name).write_text(
            src.read_text(encoding="utf-8"), encoding="utf-8"
        )

    rows = [
        {
            "indicator_id": "candidate-votes-polled",
            "url_slug": "shared-slug",
        },
        {
            "indicator_id": "candidate-vote-share-pct",
            "url_slug": "shared-slug",
        },
    ]
    _write_indicator_catalogue(tmp_path, rows)

    failures = run(tmp_path)
    slug_failures = [
        f
        for f in failures
        if "url_slug or url_slug_history entry 'shared-slug'" in f.message
    ]
    assert len(slug_failures) == 1, (
        f"run() must chain tier_b_indicator_url_slug_unique, got: {failures}"
    )
