"""Parity oracle for the eci_ls flip to per-state electoral CSV (Row 8).

Proves that flipping the Parliament-PC adapter from the retired
envelope/parquet writer to ``write_electoral_results`` preserves EVERY
``(entity_id, year, indicator_id)`` observation tuple. Drives the real TCPD
historical-GE builder (reading the committed crosswalk + party lookup) and
writes into a tmp datasets root, then reads the per-state CSV back.

Reuses the proven TCPD CSV fixture from ``test_ls_ge_tcpd``.
"""

from __future__ import annotations

import csv
from pathlib import Path

from test_ls_ge_tcpd import _row, _write_csv

from yen_gov.canonical.adapters.eci.electoral_csv import (
    upsert_source_csv,
    write_electoral_results,
)
from yen_gov.canonical.adapters.eci.state_slug import eci_to_lgd_slug
from yen_gov.canonical.adapters.eci_ls import LS_2019, build_pc_envelope_from_tcpd

DATASETS = Path(__file__).resolve().parents[2] / "datasets"


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


def test_build_pc_envelope_from_tcpd_flip_preserves_tuples(tmp_path: Path) -> None:
    rows = [
        _row(Constituency_No="1", Constituency_Name="Tiruvallur", Candidate="Winner", Votes="200"),
        _row(Constituency_No="1", Constituency_Name="Tiruvallur", Candidate="Runner", Party="DMK", Votes="100"),
        _row(Constituency_No="2", Constituency_Name="Chennai North", Candidate="Solo", Votes="150"),
    ]
    csv_path = _write_csv(tmp_path, rows)

    env, pc_count, _unresolved = build_pc_envelope_from_tcpd(
        datasets_root=DATASETS,
        csv_path=csv_path,
        year=2019,
        event=LS_2019,
        allow_unknown_parties=True,
    )
    assert pc_count == 2
    assert env.observation_rows, "adapter produced no observation rows"

    before = {(r.entity_id, r.year, r.indicator_id) for r in env.observation_rows}
    # All rows belong to one event (LsGenMay2019).
    assert {r.period_label for r in env.observation_rows} == {"LsGenMay2019"}

    datasets_root = tmp_path / "datasets"
    paths = write_electoral_results(
        datasets_root=datasets_root, observation_rows=env.observation_rows
    )
    # Single-state (Tamil Nadu) fixture -> one per-state file.
    assert set(paths) == {eci_to_lgd_slug("S22")}

    after = {
        (d["entity_id"], int(d["year"]), d["indicator_id"])
        for d in _read_electoral_dir(datasets_root)
    }
    assert after == before


def test_build_pc_envelope_from_tcpd_source_upsert_is_additive(tmp_path: Path) -> None:
    rows = [_row(Constituency_No="1", Constituency_Name="Tiruvallur", Candidate="Winner", Votes="200")]
    csv_path = _write_csv(tmp_path, rows)
    env, _pc_count, _unresolved = build_pc_envelope_from_tcpd(
        datasets_root=DATASETS,
        csv_path=csv_path,
        year=2019,
        event=LS_2019,
        allow_unknown_parties=True,
    )

    datasets_root = tmp_path / "datasets"
    source_csv = _seed_source_csv(datasets_root)
    sentinel = "src-cafecafecafe"
    with source_csv.open("a", encoding="utf-8", newline="") as fh:
        fh.write(f"{sentinel},Seed,Seed title,2000,\n")

    upsert_source_csv(datasets_root=datasets_root, source_rows=env.source_rows)

    with source_csv.open(encoding="utf-8", newline="") as fh:
        ids = {r["source_id"] for r in csv.DictReader(fh)}
    assert sentinel in ids
    assert {s.source_id for s in env.source_rows} <= ids
