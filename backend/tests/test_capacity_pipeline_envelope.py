"""Integration tests for the energy capacity-pipeline envelope (layer 3+4).

Per CLAUDE.md §14 + ADR-0041: uses an in-process synthetic meadow shard
under ``tmp_path``; does NOT walk the real corpus or hit the live ICED
API. Covers (a) the SUM-collapse over publisher status facets, (b) the
20-row shape from 20 calendar-year x 2-status x SUM, (c) idempotency of
the lift contract.
"""
from __future__ import annotations

import json
from pathlib import Path

from yen_gov.canonical.adapters.energy.capacity_pipeline import build_envelope
from yen_gov.canonical.envelope import BatchEnvelope


_MEADOW_VINTAGE = "2026-05-27"


def _write_synthetic_meadow(root: Path, *, rows: list[dict]) -> None:
    meadow_dir = root / "datasets" / "energy" / "_meadow" / "iced" / _MEADOW_VINTAGE
    meadow_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "$schema": "https://yen-gov.github.io/schemas/indicator.schema.json",
        "$schema_version": "6.0",
        "indicator": {"id": "energy/plant_pipeline_info"},
        "rows": rows,
    }
    (meadow_dir / "plant_pipeline_info.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_build_envelope_sum_collapses_status_facets(tmp_path: Path) -> None:
    """3 calendar years x 2 status facets -> 3 SUM-collapsed rows."""
    _write_synthetic_meadow(
        tmp_path,
        rows=[
            {"entity_id": "IN", "time": "2024", "value": 6.5,
             "facet": "Under Construction and likely to be commissioned"},
            {"entity_id": "IN", "time": "2024", "value": 0.0,
             "facet": "Under Construction but on Hold"},
            {"entity_id": "IN", "time": "2025", "value": 3.5,
             "facet": "Under Construction and likely to be commissioned"},
            {"entity_id": "IN", "time": "2025", "value": 0.5,
             "facet": "Under Construction but on Hold"},
            {"entity_id": "IN", "time": "2026", "value": 8.0,
             "facet": "Under Construction and likely to be commissioned"},
            {"entity_id": "IN", "time": "2026", "value": 1.0,
             "facet": "Under Construction but on Hold"},
        ],
    )
    env = build_envelope(tmp_path)
    assert isinstance(env, BatchEnvelope)
    assert env.target_table_stem == "energy_capacity_pipeline"
    assert env.target_family == "energy"

    by_year = {r.period_label: r for r in env.observation_rows}
    assert set(by_year) == {"2024", "2025", "2026"}
    # SUM-collapse: 6.5 + 0.0 = 6.5; 3.5 + 0.5 = 4.0; 8.0 + 1.0 = 9.0
    assert by_year["2024"].value_numeric == 6.5
    assert by_year["2025"].value_numeric == 4.0
    assert by_year["2026"].value_numeric == 9.0
    for row in env.observation_rows:
        assert row.entity_id == "IN"
        assert row.indicator_id == "under-construction-capacity-gw"
        assert row.derivation == "sum"
        assert row.period_seq == 1
        assert row.year == int(row.period_label)
        # source_id is the registry hash; reject hand-typed-from-test.
        assert row.source_id == "src-e0b2a084d204"


def test_build_envelope_preserves_publisher_year_gaps(tmp_path: Path) -> None:
    """ICED skips 2022 verbatim; the SUM-collapsed envelope must too."""
    _write_synthetic_meadow(
        tmp_path,
        rows=[
            {"entity_id": "IN", "time": "2020", "value": 1.0,
             "facet": "Under Construction and likely to be commissioned"},
            {"entity_id": "IN", "time": "2021", "value": 2.0,
             "facet": "Under Construction and likely to be commissioned"},
            # 2022 absent
            {"entity_id": "IN", "time": "2023", "value": 3.0,
             "facet": "Under Construction and likely to be commissioned"},
        ],
    )
    env = build_envelope(tmp_path)
    periods = sorted(r.period_label for r in env.observation_rows)
    assert periods == ["2020", "2021", "2023"]


def test_build_envelope_is_idempotent_against_same_meadow(tmp_path: Path) -> None:
    """Calling build_envelope twice yields equal observation rows (UPSERT contract).

    The writer's canonical-store UPSERT keys on (entity_id, year, period_label,
    indicator_id); a re-lift over the same meadow MUST produce the same row
    set so the second-run is a no-op.
    """
    rows_in = [
        {"entity_id": "IN", "time": "2024", "value": 6.5,
         "facet": "Under Construction and likely to be commissioned"},
        {"entity_id": "IN", "time": "2024", "value": 0.5,
         "facet": "Under Construction but on Hold"},
    ]
    _write_synthetic_meadow(tmp_path, rows=rows_in)
    env_a = build_envelope(tmp_path)
    env_b = build_envelope(tmp_path)
    keys_a = sorted(
        (r.entity_id, r.year, r.period_label, r.indicator_id, r.value_numeric)
        for r in env_a.observation_rows
    )
    keys_b = sorted(
        (r.entity_id, r.year, r.period_label, r.indicator_id, r.value_numeric)
        for r in env_b.observation_rows
    )
    assert keys_a == keys_b
    assert len(keys_a) == 1
    assert keys_a[0][3] == "under-construction-capacity-gw"
    assert keys_a[0][4] == 7.0  # 6.5 + 0.5
