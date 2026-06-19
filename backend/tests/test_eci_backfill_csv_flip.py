"""Parity oracle for the canonical_eci_backfill flip to per-state CSV (Row 8).

Proves the backfill driver UPSERTs every observation tuple the in-memory
builder produces into the per-state electoral CSV, with no drop. Covers both
the write seam over the in-memory builder output and the full
``backfill_elections`` walk over a tmp per-AC JSON corpus.

Reuses the proven 3-AC fixture (``_emit_fixtures``) + parties roster from
``test_canonical_eci_backfill``.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import _emit_fixtures  # noqa: I001 -- sibling test helper, not a package
from test_canonical_eci_backfill import _PARTIES_ROSTER

from yen_gov.canonical.adapters.eci.identity import parse_period_label
from yen_gov.canonical.adapters.eci.state_slug import eci_to_lgd_slug
from yen_gov.canonical.adapters.eci.electoral_csv import write_electoral_results
from yen_gov.canonical.party_resolver import load_party_lookup
from yen_gov.pipeline.canonical_eci_backfill import (
    backfill_elections,
    build_slice_envelope,
)

_EVENT = "AcGenMay2026"
_STATE = "S22"


def _seed_parties(datasets_root: Path):
    taxonomy = datasets_root / "taxonomy"
    taxonomy.mkdir(parents=True, exist_ok=True)
    (taxonomy / "parties.json").write_text(
        json.dumps(_PARTIES_ROSTER, ensure_ascii=False), encoding="utf-8"
    )
    return load_party_lookup(datasets_root)


def _seed_source_csv(datasets_root: Path) -> Path:
    path = datasets_root / "data" / "entities" / "source.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("source_id,producer,title,vintage,url\n", encoding="utf-8")
    return path


def _read_electoral_dir(datasets_root: Path) -> list[dict[str, str]]:
    electoral = datasets_root / "data" / "datapoints" / "electoral"
    out: list[dict[str, str]] = []
    for path in sorted(electoral.glob("*_election_results.csv")):
        with path.open(encoding="utf-8", newline="") as fh:
            out.extend(csv.DictReader(fh))
    return out


def test_build_slice_envelope_write_seam_preserves_tuples(tmp_path: Path) -> None:
    datasets_root = tmp_path / "datasets"
    party_lookup = _seed_parties(datasets_root)
    period = parse_period_label(_EVENT)

    rows, _sources, _unresolved, _persons, _cands, _acs = build_slice_envelope(
        constituencies=_emit_fixtures.constituency_models(),
        state_code=_STATE,
        period=period,
        party_lookup=party_lookup,
    )
    before = {(r.entity_id, r.year, r.indicator_id) for r in rows}

    paths = write_electoral_results(datasets_root=datasets_root, observation_rows=rows)
    assert set(paths) == {eci_to_lgd_slug(_STATE)}

    after = {
        (d["entity_id"], int(d["year"]), d["indicator_id"])
        for d in _read_electoral_dir(datasets_root)
    }
    assert after == before


def test_backfill_elections_end_to_end_preserves_tuples(tmp_path: Path) -> None:
    datasets_root = tmp_path / "datasets"
    party_lookup = _seed_parties(datasets_root)
    _seed_source_csv(datasets_root)

    # BEFORE: the tuples the in-memory builder produces for this slice.
    period = parse_period_label(_EVENT)
    constituencies = _emit_fixtures.constituency_models()
    rows, sources, _unresolved, _persons, _cands, _acs = build_slice_envelope(
        constituencies=constituencies,
        state_code=_STATE,
        period=period,
        party_lookup=party_lookup,
    )
    before = {(r.entity_id, r.year, r.indicator_id) for r in rows}

    # Materialise the per-AC JSON corpus the disk walker consumes.
    results_dir = datasets_root / "elections" / _EVENT / _STATE / "results"
    results_dir.mkdir(parents=True)
    for cr in constituencies:
        payload = cr.body_payload()
        payload["sources"] = cr.sources_payload()
        (results_dir / f"{cr.eci_no}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    res = backfill_elections(datasets_root=datasets_root)

    assert not res.failed_slices, res.failed_slices
    assert res.observation_rows_written == len(rows)
    slug = eci_to_lgd_slug(_STATE)
    assert res.csv_paths == (
        datasets_root / "data" / "datapoints" / "electoral" / f"{slug}_election_results.csv",
    )

    after = {
        (d["entity_id"], int(d["year"]), d["indicator_id"])
        for d in _read_electoral_dir(datasets_root)
    }
    assert after == before

    # The slice's citation rows were additively appended to source.csv.
    with (datasets_root / "data" / "entities" / "source.csv").open(
        encoding="utf-8", newline=""
    ) as fh:
        source_ids = {r["source_id"] for r in csv.DictReader(fh)}
    assert {s.source_id for s in sources.values()} <= source_ids
