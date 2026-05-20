"""Hive-partitioned fact-table emit tests (Phase 0 closeout, TODO §0e.10 lock B).

The canonical writer registers ``elections`` in ``FAMILY_FACT_PARTITION_BY``
with a single ``state`` partition column. These tests pin:

  * one file per distinct ``entity_id`` state-prefix lands on disk under
    ``state=<val>/election_results.parquet``;
  * the partition value grammar is ``in_<two-char-lower>`` (country-prefixed,
    lowercase, underscore-separated) — locked grammar from TODO §0e.10 lock A;
  * non-partitioned families (default) keep their single-file layout;
  * the regenerated manifest emits one entry per partitioned table with
    ``partition_columns: ["state"]`` and per-file ``partition_values``;
  * a write_batch that lands on a pre-existing monolith sweeps it away
    after the partition files write successfully (migration safety).

Per CLAUDE.md §15: tmp_path fixtures only, no mocks, no real-corpus walk.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb

from yen_gov.canonical import (
    BatchEnvelope,
    ObservationRow,
    ReplacementSemantics,
    SourceRow,
    write_batch,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
ENTITIES_FIXTURE = REPO_ROOT / "datasets" / "taxonomy" / "entities.json"


def _seed_taxonomy(datasets_root: Path) -> None:
    (datasets_root / "taxonomy").mkdir(parents=True, exist_ok=True)
    shutil.copy(ENTITIES_FIXTURE, datasets_root / "taxonomy" / "entities.json")


def _src(source_id: str = "src-test0001") -> SourceRow:
    return SourceRow(
        source_id=source_id,
        url="https://example.gov.in/test",
        content_hash="",
        producer="yen-gov",
        first_fetched_at="2026-05-18T00:00:00Z",
        last_seen_at="2026-05-18T00:00:00Z",
        license="internal",
        confidence_tier="gold",
        is_issuing_authority=False,
    )


def _obs(
    entity_id: str,
    *,
    year: int = 2024,
    period_label: str = "AcGenMay2024",
    period_seq: int = 1,
    indicator_id: str = "election-test-votes-total-int",
    value_numeric: float = 1.0,
    source_id: str = "src-test0001",
) -> ObservationRow:
    return ObservationRow(
        entity_id=entity_id,
        year=year,
        period_label=period_label,
        period_seq=period_seq,
        indicator_id=indicator_id,
        value_numeric=value_numeric,
        source_id=source_id,
    )


def _elections_envelope(observations: list[ObservationRow]) -> BatchEnvelope:
    return BatchEnvelope(
        target_family="elections",
        source_rows=[_src()],
        observation_rows=observations,
        replacement_semantics=ReplacementSemantics.upsert,
    )


# ---------------------------------------------------------------------------
# Partition path layout
# ---------------------------------------------------------------------------


def test_elections_writes_one_parquet_per_state(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    env = _elections_envelope([
        _obs("IN-S22", indicator_id="election-test-a"),
        _obs("IN-S22-AC-2024-001", indicator_id="election-test-b"),
        _obs("IN-S08", indicator_id="election-test-c"),
        _obs("IN-U05-AC-2024-001", indicator_id="election-test-d"),
    ])

    write_batch(env, tmp_path)

    elections_dir = tmp_path / "elections"
    partition_files = sorted(elections_dir.glob("state=*/election_results.parquet"))
    rels = sorted(p.relative_to(elections_dir).as_posix() for p in partition_files)
    assert rels == [
        "state=in_s08/election_results.parquet",
        "state=in_s22/election_results.parquet",
        "state=in_u05/election_results.parquet",
    ]
    # No monolith leaks into the family dir.
    assert not (elections_dir / "election_results.parquet").exists()


def test_partition_grammar_is_in_underscore_lowercase(tmp_path: Path) -> None:
    """Locked grammar (TODO §0e.10 lock A): partition value = ``in_<two-char-lower>``.

    Rules: country prefix preserved (``in_``, not bare ``s22``); ASCII
    lower case; ``-`` swapped for ``_`` so Hive parsers don't choke."""
    _seed_taxonomy(tmp_path)
    env = _elections_envelope([
        _obs("IN-S22-AC-2024-001"),
        _obs("IN-U05"),
    ])

    write_batch(env, tmp_path)

    files = sorted(
        p.relative_to(tmp_path / "elections").as_posix()
        for p in (tmp_path / "elections").glob("state=*/election_results.parquet")
    )
    # All-lowercase, underscore separator, country-prefixed.
    for rel in files:
        seg = rel.split("/", 1)[0]
        assert seg.startswith("state=in_"), rel
        # Two-char-lower state code follows the prefix.
        partition_val = seg.split("=", 1)[1]
        assert partition_val.startswith("in_")
        assert partition_val == partition_val.lower()
        assert "-" not in partition_val


def test_rows_partition_correctly_by_entity_state_prefix(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    env = _elections_envelope([
        _obs("IN-S22", value_numeric=22.0),
        _obs("IN-S22-AC-2024-001", value_numeric=22.1),
        _obs("IN-S08", value_numeric=8.0),
    ])
    write_batch(env, tmp_path)

    con = duckdb.connect(":memory:")
    s22_rows = con.execute(
        "SELECT entity_id, value_numeric FROM read_parquet(?) ORDER BY entity_id",
        [(tmp_path / "elections" / "state=in_s22" / "election_results.parquet").as_posix()],
    ).fetchall()
    s08_rows = con.execute(
        "SELECT entity_id, value_numeric FROM read_parquet(?) ORDER BY entity_id",
        [(tmp_path / "elections" / "state=in_s08" / "election_results.parquet").as_posix()],
    ).fetchall()
    assert s22_rows == [("IN-S22", 22.0), ("IN-S22-AC-2024-001", 22.1)]
    assert s08_rows == [("IN-S08", 8.0)]


def test_partition_parquet_omits_synthesized_state_column(tmp_path: Path) -> None:
    """The ``state`` value lives in the Hive path segment, not as a row
    field in the parquet file. (DuckDB's ``read_parquet`` will SYNTHESIZE
    a virtual ``state`` column on read because of Hive auto-discovery,
    so we explicitly disable that to check the physical schema.)

    Why this matters: keeping ``state`` out of the file means the
    canonical writer can re-derive it from ``entity_id`` deterministically
    on every emit. Persisting it as a row field would create a redundant
    representation that could drift if ``entity_id`` is renamed without
    re-deriving."""
    _seed_taxonomy(tmp_path)
    env = _elections_envelope([_obs("IN-S22")])
    write_batch(env, tmp_path)
    file = tmp_path / "elections" / "state=in_s22" / "election_results.parquet"
    cols = duckdb.connect(":memory:").execute(
        f"DESCRIBE SELECT * FROM read_parquet('{file.as_posix()}', hive_partitioning=false)"
    ).fetchall()
    col_names = [r[0] for r in cols]
    assert "state" not in col_names
    assert col_names == [
        "observation_id", "entity_id", "year", "period_label", "period_seq",
        "indicator_id", "value_numeric", "value_text", "source_id", "derivation",
    ]


# ---------------------------------------------------------------------------
# Non-partitioned families are unaffected (regression guard)
# ---------------------------------------------------------------------------


def test_non_partitioned_family_still_writes_single_file(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    env = BatchEnvelope(
        target_family="test",  # not in FAMILY_FACT_PARTITION_BY
        source_rows=[_src()],
        observation_rows=[_obs("IN-S22", indicator_id="state-test-dummy-int")],
        replacement_semantics=ReplacementSemantics.upsert,
    )
    result = write_batch(env, tmp_path)
    # Single monolith at default location; no partitioned dirs.
    assert result.observations_path == tmp_path / "test" / "observations.parquet"
    assert result.observations_path.is_file()
    assert not list((tmp_path / "test").glob("state=*"))


# ---------------------------------------------------------------------------
# Manifest entry shape
# ---------------------------------------------------------------------------


def test_manifest_lists_partitioned_table_with_per_file_values(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    env = _elections_envelope([
        _obs("IN-S22"),
        _obs("IN-S08"),
        _obs("IN-U05"),
    ])
    write_batch(env, tmp_path)

    manifest = json.loads((tmp_path / "manifest.json").read_text("utf-8"))
    elections_tables = [t for t in manifest["tables"] if t["family"] == "elections"]
    assert len(elections_tables) == 1
    t = elections_tables[0]
    assert t["table_id"] == "elections.election_results"
    assert t["partition_columns"] == ["state"]
    assert t["kind"] == "observations"

    files_by_pv = {f["partition_values"]["state"]: f for f in t["files"]}
    assert set(files_by_pv) == {"in_s22", "in_s08", "in_u05"}
    for pv, f in files_by_pv.items():
        assert f["path"] == f"elections/state={pv}/election_results.parquet"
        assert f["row_count"] == 1
        assert f["size_bytes"] > 0

    assert t["row_count_total"] == 3


# ---------------------------------------------------------------------------
# Migration: pre-existing monolith is swept on first partitioned write
# ---------------------------------------------------------------------------


def test_pre_existing_monolith_swept_after_partitioned_emit(tmp_path: Path) -> None:
    """A stale ``elections/election_results.parquet`` left over from the
    pre-partition era must NOT survive a subsequent ``write_batch`` —
    keeping it would double-count rows on the next ``_load_existing``."""
    _seed_taxonomy(tmp_path)
    # Step 1: write a single-row monolith by simulating pre-partition state.
    # We do this by writing an envelope, then moving the partitioned file
    # back to the monolith location.
    env_seed = _elections_envelope([_obs("IN-S22", value_numeric=99.0)])
    write_batch(env_seed, tmp_path)
    elections_dir = tmp_path / "elections"
    src_partition = elections_dir / "state=in_s22" / "election_results.parquet"
    monolith = elections_dir / "election_results.parquet"
    shutil.copy(src_partition, monolith)
    shutil.rmtree(elections_dir / "state=in_s22")
    assert monolith.is_file()
    assert not list(elections_dir.glob("state=*"))

    # Step 2: a fresh write_batch with an additive observation.
    env_add = _elections_envelope([_obs("IN-S08", value_numeric=8.0)])
    write_batch(env_add, tmp_path)

    # Monolith is gone; both partition files present; UPSERT preserved the
    # original row.
    assert not monolith.exists()
    rels = sorted(
        p.relative_to(elections_dir).as_posix()
        for p in elections_dir.glob("state=*/election_results.parquet")
    )
    assert rels == [
        "state=in_s08/election_results.parquet",
        "state=in_s22/election_results.parquet",
    ]
    con = duckdb.connect(":memory:")
    s22 = con.execute(
        f"SELECT value_numeric FROM read_parquet('{(elections_dir / 'state=in_s22' / 'election_results.parquet').as_posix()}')"
    ).fetchall()
    assert s22 == [(99.0,)]


# ---------------------------------------------------------------------------
# Re-emit on existing partitioned corpus is UPSERT-safe (idempotency)
# ---------------------------------------------------------------------------


def test_partitioned_writes_are_idempotent_on_reemit(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    env = _elections_envelope([_obs("IN-S22"), _obs("IN-S08")])

    write_batch(env, tmp_path)
    rels_first = sorted(
        p.relative_to(tmp_path / "elections").as_posix()
        for p in (tmp_path / "elections").glob("state=*/election_results.parquet")
    )
    elections_dir = tmp_path / "elections"
    bytes_first = {
        rel: (elections_dir / rel).read_bytes()
        for rel in rels_first
    }

    # Second emit with identical envelope must produce byte-identical
    # partition files (writer is deterministic per ADR-0030 §8.3).
    write_batch(env, tmp_path)
    bytes_second = {
        rel: (elections_dir / rel).read_bytes()
        for rel in rels_first
    }
    assert bytes_second == bytes_first
