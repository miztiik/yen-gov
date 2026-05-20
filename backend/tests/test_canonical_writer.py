"""Contract tests for the canonical writer (Phase 0.10).

Per CLAUDE.md §15 + THE PLAN §6 step 0.10: tmp_path fixtures only, no
mocks, no corpus walk. Each test builds a tiny synthetic envelope, asks
the writer to emit, then asserts a contract: column types, sort order,
FK gate, idempotency, KV metadata stamp, manifest regen.

Why this file is single-purpose: these tests pin the writer's emit
contract. A future change to `backend/yen_gov/canonical/writer.py` that
breaks any assertion here is breaking the producer/consumer binding
defined in `docs/architecture/data/canonical-store.md` §11–§12, and
should be reviewed at that doc's seam first.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb
import pytest

from yen_gov.canonical import (
    BatchEnvelope,
    ObservationRow,
    ReplacementSemantics,
    SourceRow,
    write_batch,
)
from yen_gov.canonical.writer import WriterError
from yen_gov.core.schema_registry import schema_version


REPO_ROOT = Path(__file__).resolve().parents[2]
ENTITIES_FIXTURE = REPO_ROOT / "datasets" / "taxonomy" / "entities.json"


def _seed_taxonomy(datasets_root: Path) -> None:
    """Copy the entity catalogue into a tmp datasets root so FK gate has
    something to check. We do NOT copy indicators.json — Phase 0.9
    deliberately runs the writer with indicator FK skipped + warned."""
    (datasets_root / "taxonomy").mkdir(parents=True, exist_ok=True)
    shutil.copy(ENTITIES_FIXTURE, datasets_root / "taxonomy" / "entities.json")


def _src(source_id: str = "src-test00000001") -> SourceRow:
    return SourceRow(
        source_id=source_id,
        producer="yen-gov",
        title="Test Source",
        vintage="2026",
        license="internal",
        confidence_tier="gold",
        is_issuing_authority=False,
        verification_method="editorial",
    )


def _obs(
    entity_id: str = "IN-S22",
    year: int = 2025,
    period_label: str = "FY 2024-25",
    period_seq: int = 1,
    indicator_id: str = "state-test-dummy-int",
    value_numeric: float | None = 42.0,
    value_text: str | None = None,
    source_id: str = "src-test00000001",
) -> ObservationRow:
    return ObservationRow(
        entity_id=entity_id,
        year=year,
        period_label=period_label,
        period_seq=period_seq,
        indicator_id=indicator_id,
        value_numeric=value_numeric,
        value_text=value_text,
        source_id=source_id,
    )


def _envelope(observations: list[ObservationRow], sources: list[SourceRow] | None = None,
              family: str = "test", semantics: ReplacementSemantics = ReplacementSemantics.upsert) -> BatchEnvelope:
    return BatchEnvelope(
        target_family=family,
        source_rows=sources if sources is not None else [_src()],
        observation_rows=observations,
        replacement_semantics=semantics,
    )


# ---------------------------------------------------------------------------
# Column shape + types
# ---------------------------------------------------------------------------


def test_observations_parquet_has_canonical_columns_and_types(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    result = write_batch(_envelope([_obs()]), tmp_path)

    con = duckdb.connect(":memory:")
    schema = con.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{result.observations_path.as_posix()}')"
    ).fetchall()
    cols = {row[0]: row[1] for row in schema}

    assert list(cols.keys()) == [
        "observation_id", "entity_id", "year", "period_label", "period_seq",
        "indicator_id", "value_numeric", "value_text", "source_id", "derivation",
    ]
    assert cols["year"] == "INTEGER"
    assert cols["period_seq"] == "INTEGER"
    assert cols["value_numeric"] == "DOUBLE"
    assert cols["value_text"] == "VARCHAR"
    assert cols["entity_id"] == "VARCHAR"
    assert cols["derivation"] == "VARCHAR"


def test_value_text_and_value_numeric_are_both_nullable(tmp_path: Path) -> None:
    """R17 split: 'Nil'/'N.A.' goes to value_text; numeric reading goes to
    value_numeric; the unused side is null."""
    _seed_taxonomy(tmp_path)
    env = _envelope([
        _obs(value_numeric=10.0, value_text=None, indicator_id="state-test-a"),
        _obs(value_numeric=None, value_text="Nil", indicator_id="state-test-b"),
    ])
    result = write_batch(env, tmp_path)
    con = duckdb.connect(":memory:")
    rows = con.execute(
        f"SELECT indicator_id, value_numeric, value_text "
        f"FROM read_parquet('{result.observations_path.as_posix()}') "
        f"ORDER BY indicator_id"
    ).fetchall()
    assert rows == [("state-test-a", 10.0, None), ("state-test-b", None, "Nil")]


# ---------------------------------------------------------------------------
# Sort order (D7)
# ---------------------------------------------------------------------------


def test_observations_emit_sorted_by_indicator_entity_year_period_seq(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    # Insert deliberately out of order.
    env = _envelope([
        _obs(indicator_id="state-test-b", entity_id="IN-S22", year=2024, period_seq=2,
             period_label="Q2", value_numeric=2.0),
        _obs(indicator_id="state-test-a", entity_id="IN-S22", year=2025, period_seq=1,
             period_label="Q1", value_numeric=1.0),
        _obs(indicator_id="state-test-b", entity_id="IN-S22", year=2024, period_seq=1,
             period_label="Q1", value_numeric=3.0),
        _obs(indicator_id="state-test-a", entity_id="IN-S08", year=2025, period_seq=1,
             period_label="Q1", value_numeric=4.0),
    ])
    result = write_batch(env, tmp_path)
    con = duckdb.connect(":memory:")
    rows = con.execute(
        f"SELECT indicator_id, entity_id, year, period_seq "
        f"FROM read_parquet('{result.observations_path.as_posix()}')"
    ).fetchall()
    assert rows == [
        ("state-test-a", "IN-S08", 2025, 1),
        ("state-test-a", "IN-S22", 2025, 1),
        ("state-test-b", "IN-S22", 2024, 1),
        ("state-test-b", "IN-S22", 2024, 2),
    ]


# ---------------------------------------------------------------------------
# FK gate (D22)
# ---------------------------------------------------------------------------


def test_dangling_source_id_aborts_write(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    env = BatchEnvelope(
        target_family="test",
        source_rows=[_src("src-aaaaaaaaaaaa")],
        observation_rows=[_obs(source_id="src-zzzzzzzzzzzz")],  # not in envelope or store
    )
    with pytest.raises(WriterError, match="dangling source_id"):
        write_batch(env, tmp_path)
    # No file should have been emitted.
    assert not (tmp_path / "test" / "observations.parquet").exists()


def test_dangling_entity_id_aborts_write(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    env = _envelope([_obs(entity_id="IN-S99")])  # not a real state code
    with pytest.raises(WriterError, match="dangling entity_id"):
        write_batch(env, tmp_path)
    assert not (tmp_path / "test" / "observations.parquet").exists()


def test_indicator_fk_skipped_with_warning_when_taxonomy_missing(tmp_path: Path) -> None:
    """Phase 0.9 transitional: indicators.json not seeded yet, so indicator
    FK gate warns + skips rather than failing every write."""
    _seed_taxonomy(tmp_path)
    result = write_batch(_envelope([_obs()]), tmp_path)
    assert any("indicators.json" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Exactly-one-of(value_numeric, value_text)
# ---------------------------------------------------------------------------


def test_both_value_fields_populated_rejected(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    env = _envelope([_obs(value_numeric=1.0, value_text="oops")])
    with pytest.raises(WriterError, match="exactly one of value_numeric"):
        write_batch(env, tmp_path)


def test_neither_value_field_populated_rejected(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    env = _envelope([_obs(value_numeric=None, value_text=None)])
    with pytest.raises(WriterError, match="exactly one of value_numeric"):
        write_batch(env, tmp_path)


# ---------------------------------------------------------------------------
# UPSERT semantics (D7, R16)
# ---------------------------------------------------------------------------


def test_rerun_with_identical_envelope_is_byte_identical(tmp_path: Path) -> None:
    """Idempotency: same upstream -> same Parquet bytes. Sort + UPSERT
    on logical key guarantee this."""
    _seed_taxonomy(tmp_path)
    env = _envelope([_obs(), _obs(indicator_id="state-test-other", value_numeric=99.0)])
    r1 = write_batch(env, tmp_path)
    bytes1 = r1.observations_path.read_bytes()

    r2 = write_batch(env, tmp_path)
    bytes2 = r2.observations_path.read_bytes()
    assert bytes1 == bytes2, "re-run with identical envelope produced different Parquet bytes"


def test_corrected_value_with_new_source_id_keeps_logical_row(tmp_path: Path) -> None:
    """R16: source_id is row-attribute, not identity. Two envelopes with
    same logical key but different source_id -> one row, latest source_id."""
    _seed_taxonomy(tmp_path)
    env1 = _envelope([_obs(value_numeric=10.0, source_id="src-aaaaaaaaaaaa")],
                     sources=[_src("src-aaaaaaaaaaaa")])
    write_batch(env1, tmp_path)

    env2 = _envelope([_obs(value_numeric=11.0, source_id="src-bbbbbbbbbbbb")],
                     sources=[_src("src-bbbbbbbbbbbb")])
    r2 = write_batch(env2, tmp_path)

    con = duckdb.connect(":memory:")
    rows = con.execute(
        f"SELECT value_numeric, source_id FROM read_parquet('{r2.observations_path.as_posix()}')"
    ).fetchall()
    assert rows == [(11.0, "src-bbbbbbbbbbbb")]


def test_replace_partition_clears_existing_rows_for_indicator(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    initial = _envelope([
        _obs(indicator_id="state-test-x", value_numeric=1.0, entity_id="IN-S22"),
        _obs(indicator_id="state-test-x", value_numeric=2.0, entity_id="IN-S08"),
        _obs(indicator_id="state-test-y", value_numeric=3.0, entity_id="IN-S22"),
    ])
    write_batch(initial, tmp_path)

    replacement = _envelope(
        [_obs(indicator_id="state-test-x", value_numeric=99.0, entity_id="IN-S22")],
        semantics=ReplacementSemantics.replace_partition,
    )
    r2 = write_batch(replacement, tmp_path)

    con = duckdb.connect(":memory:")
    rows = con.execute(
        f"SELECT indicator_id, entity_id, value_numeric "
        f"FROM read_parquet('{r2.observations_path.as_posix()}') "
        f"ORDER BY indicator_id, entity_id"
    ).fetchall()
    # state-test-x kept only the one replacement row; state-test-y untouched.
    assert rows == [
        ("state-test-x", "IN-S22", 99.0),
        ("state-test-y", "IN-S22", 3.0),
    ]


# ---------------------------------------------------------------------------
# Parquet KV metadata stamp (§11.1)
# ---------------------------------------------------------------------------


def test_parquet_kv_metadata_carries_writer_contract_keys(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    result = write_batch(_envelope([_obs()]), tmp_path)
    con = duckdb.connect(":memory:")
    kv_raw = con.execute(
        f"SELECT key, value FROM parquet_kv_metadata('{result.observations_path.as_posix()}')"
    ).fetchall()
    kv = {(k.decode() if isinstance(k, bytes) else k):
          (v.decode() if isinstance(v, bytes) else v)
          for k, v in kv_raw}
    assert kv.get("table_id") == "test.observations"
    assert kv.get("schema_version") == "1.1"
    assert kv.get("row_schema_id") == "./observation.schema.json"
    assert "writer_version" in kv
    assert json.loads(kv["sort_columns"]) == [
        "indicator_id", "entity_id", "year", "period_seq"
    ]


def test_sources_parquet_kv_metadata(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    result = write_batch(_envelope([_obs()]), tmp_path)
    con = duckdb.connect(":memory:")
    kv_raw = con.execute(
        f"SELECT key, value FROM parquet_kv_metadata('{result.sources_path.as_posix()}')"
    ).fetchall()
    kv = {(k.decode() if isinstance(k, bytes) else k):
          (v.decode() if isinstance(v, bytes) else v)
          for k, v in kv_raw}
    assert kv.get("table_id") == "taxonomy.sources"
    assert kv.get("schema_version") == "2.0"


# ---------------------------------------------------------------------------
# Manifest regeneration (§12.3)
# ---------------------------------------------------------------------------


def test_manifest_regenerates_with_correct_table_entries(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    write_batch(_envelope([_obs()]), tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["$schema"] == "./schemas/manifest.schema.json"
    assert manifest["manifest_version"] == "1.0"
    table_ids = {t["table_id"] for t in manifest["tables"]}
    assert "test.observations" in table_ids
    assert "taxonomy.sources" in table_ids

    test_table = next(t for t in manifest["tables"] if t["table_id"] == "test.observations")
    assert test_table["family"] == "test"
    assert test_table["format"] == "parquet"
    assert test_table["schema_version"] == "1.1"
    assert test_table["table_name"] == "observations"
    assert test_table["kind"] == "observations"
    assert test_table["files"][0]["path"] == "test/observations.parquet"
    assert test_table["files"][0]["row_count"] == 1
    assert test_table["row_count_total"] == 1


def test_manifest_schema_version_is_current(tmp_path: Path) -> None:
    """manifest.json must declare $schema_version equal to manifest.schema.json's
    current x-version (CLAUDE.md §11 strict equality — the validator rejects
    any drift). Sourcing through schema_registry catches hand-typed literal
    drift in the writer (see lessons.md 2026-05-16 ¶“Schema enum extension”).
    """
    _seed_taxonomy(tmp_path)
    write_batch(_envelope([_obs()]), tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["$schema_version"] == schema_version("manifest.schema.json")
    assert manifest["$schema_version"] == "1.3"


def test_manifest_carries_known_deprecations(tmp_path: Path) -> None:
    """Writer stamps the ``_DEPRECATIONS`` ledger into ``manifest.json`` under
    the ``deprecations[]`` array introduced in ``manifest.schema.json`` v1.2
    (PR-O.2-minimal). The frontend loader (``frontend/src/lib/duckdb.ts``)
    and ``datasets/CHANGELOG.md`` are the human-readable surfaces; this test
    guards the machine-readable surface so an accidental drop of the field
    from the writer fails Tier-A instead of silently shipping.
    """
    _seed_taxonomy(tmp_path)
    write_batch(_envelope([_obs()]), tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    deprecations = manifest.get("deprecations", [])
    assert any(
        d.get("old_path") == "elections/observations.parquet"
        and d.get("new_path") == "elections/election_results.parquet"
        and d.get("deprecated_at") == "2026-05-18"
        for d in deprecations
    ), f"expected elections rename entry in deprecations[], got {deprecations!r}"


def test_manifest_kind_for_taxonomy_table(tmp_path: Path) -> None:
    """taxonomy/*.parquet entries carry kind="taxonomy" regardless of stem —
    the family wins (canonical-store.md §2a: taxonomy exception, flat names).
    """
    _seed_taxonomy(tmp_path)
    write_batch(_envelope([_obs()]), tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    sources_table = next(t for t in manifest["tables"] if t["table_id"] == "taxonomy.sources")
    assert sources_table["family"] == "taxonomy"
    assert sources_table["table_name"] == "sources"
    assert sources_table["kind"] == "taxonomy"


def test_elections_family_uses_election_results_stem(tmp_path: Path) -> None:
    """PR-O.1 (TODO row 1.8b-i): the elections family writes its fact-table
    to ``election_results.parquet`` (citizen-honest stem) and registers in
    the manifest as ``elections.election_results`` with
    ``kind="observations"``. The default ``observations`` stem is the
    correct fallback for families NOT listed in ``FAMILY_FACT_TABLE_STEM``
    (asserted by the ``test.observations`` table elsewhere in this file).

    Phase 0 closeout (TODO §0e.10 lock B): ``elections`` is also registered
    in ``FAMILY_FACT_PARTITION_BY = {"elections": ["state"]}``, so the
    fact-table is emitted as one parquet per Hive partition
    (``state=<val>/election_results.parquet``), not a single monolith.
    The per-family stem still applies, just inside each partition dir.
    """
    _seed_taxonomy(tmp_path)
    env = _envelope([_obs()])
    env = env.model_copy(update={"target_family": "elections"})
    result = write_batch(env, tmp_path)
    # File-on-disk uses the per-family stem, but lives inside a Hive
    # partition directory now. The default _obs() entity_id is "IN-S22",
    # so the partition value is "in_s22".
    assert result.observations_path.name == "election_results.parquet"
    partition_file = tmp_path / "elections" / "state=in_s22" / "election_results.parquet"
    assert partition_file.is_file()
    # Monolith and legacy names both absent.
    assert not (tmp_path / "elections" / "election_results.parquet").exists()
    assert not (tmp_path / "elections" / "observations.parquet").exists()
    # Manifest entry uses the per-family stem and declares partition_columns.
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    elections_table = next(t for t in manifest["tables"]
                           if t["table_id"] == "elections.election_results")
    assert elections_table["family"] == "elections"
    assert elections_table["table_name"] == "election_results"
    assert elections_table["kind"] == "observations"
    assert elections_table["partition_columns"] == ["state"]
    files = elections_table["files"]
    assert len(files) == 1
    assert files[0]["path"] == "elections/state=in_s22/election_results.parquet"
    assert files[0]["partition_values"] == {"state": "in_s22"}


def test_manifest_path_is_posix_no_backslashes(tmp_path: Path) -> None:
    """CLAUDE.md §2: paths leaving the process are POSIX-only."""
    _seed_taxonomy(tmp_path)
    write_batch(_envelope([_obs()]), tmp_path)
    manifest_text = (tmp_path / "manifest.json").read_text(encoding="utf-8")
    assert "\\\\" not in manifest_text
    assert "\\/" not in manifest_text
    manifest = json.loads(manifest_text)
    for table in manifest["tables"]:
        for f in table["files"]:
            assert "\\" not in f["path"], f"backslash in manifest path: {f['path']}"


# ---------------------------------------------------------------------------
# Dimension tables (Phase 1.2b)
# ---------------------------------------------------------------------------


from yen_gov.canonical.envelope import AcDimRow, CandidateDimRow, PartyAllianceDimRow, PartyDimRow


def _cand_dim(cid: str = "IN-S22-AC-2008-167-AcGenApr2021-C01",
              party_id: str = "parties.IN.DMK", rank: int = 1) -> CandidateDimRow:
    return CandidateDimRow(
        candidate_id=cid,
        ac_id="IN-S22-AC-2008-167",
        period_label="AcGenApr2021",
        ballot_serial=rank,
        name="A. Alpha",
        party_id=party_id,
        rank=rank,
        source_id="src-test00000001",
    )


def _ac_dim() -> AcDimRow:
    return AcDimRow(
        ac_id="IN-S22-AC-2008-167",
        state_code="S22",
        delim_year=2008,
        eci_no=167,
        name="Mylapore",
        source_id="src-test00000001",
    )


def _party_dim() -> PartyDimRow:
    return PartyDimRow(
        party_id="parties.IN.DMK",
        eci_code="1234",
        short_name="DMK",
        full_name="Dravida Munnetra Kazhagam",
        recognition="state",
        source_id="src-test00000001",
    )


def _party_alliance_dim(period: str = "AcGenApr2021", alliance: str | None = "UPA") -> PartyAllianceDimRow:
    return PartyAllianceDimRow(
        party_id="parties.IN.DMK",
        short_name="DMK",
        period_label=period,
        alliance=alliance,
        source_id="src-test00000001",
    )


def _dim_envelope(family: str = "elections") -> BatchEnvelope:
    return BatchEnvelope(
        target_family=family,
        source_rows=[_src()],
        observation_rows=[_obs(entity_id="IN-S22-AC-2008-167-AcGenApr2021-C01",
                               indicator_id="candidate-votes-polled",
                               year=2021, period_label="AcGenApr2021")],
        candidate_dim_rows=[_cand_dim()],
        ac_dim_rows=[_ac_dim()],
        party_dim_rows=[_party_dim()],
        party_alliance_dim_rows=[_party_alliance_dim()],
    )


def test_dimension_parquets_emit_under_family_dir(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    write_batch(_dim_envelope(), tmp_path)
    family_dir = tmp_path / "elections"
    assert (family_dir / "dim_candidates.parquet").is_file()
    assert (family_dir / "dim_acs.parquet").is_file()
    assert (family_dir / "dim_parties.parquet").is_file()
    assert (family_dir / "dim_party_alliances.parquet").is_file()


def test_dim_party_alliances_composite_pk_upserts(tmp_path: Path) -> None:
    """Composite PK (party_id, period_label): two events for the same party
    coexist, and re-emitting the same key overwrites in place."""
    _seed_taxonomy(tmp_path)
    env = _dim_envelope()
    env = env.model_copy(update={
        "party_alliance_dim_rows": [
            _party_alliance_dim(period="AcGenApr2021", alliance="UPA"),
            _party_alliance_dim(period="AcGenMay2026", alliance="SPA"),
        ]
    })
    write_batch(env, tmp_path)

    con = duckdb.connect(":memory:")
    rows = con.execute(
        f"SELECT party_id, period_label, alliance FROM read_parquet('"
        f"{(tmp_path / 'elections' / 'dim_party_alliances.parquet').as_posix()}') "
        f"ORDER BY period_label"
    ).fetchall()
    assert rows == [
        ("parties.IN.DMK", "AcGenApr2021", "UPA"),
        ("parties.IN.DMK", "AcGenMay2026", "SPA"),
    ]

    # Re-emit with one PK overwritten; the other untouched.
    env2 = env.model_copy(update={
        "party_alliance_dim_rows": [
            _party_alliance_dim(period="AcGenMay2026", alliance="SPA-corrected"),
        ]
    })
    write_batch(env2, tmp_path)
    rows2 = con.execute(
        f"SELECT party_id, period_label, alliance FROM read_parquet('"
        f"{(tmp_path / 'elections' / 'dim_party_alliances.parquet').as_posix()}') "
        f"ORDER BY period_label"
    ).fetchall()
    assert rows2 == [
        ("parties.IN.DMK", "AcGenApr2021", "UPA"),
        ("parties.IN.DMK", "AcGenMay2026", "SPA-corrected"),
    ]


def test_dim_candidates_pk_join_reconstructs_observation_entity(tmp_path: Path) -> None:
    """The JOIN that unblocks the route swap (PR-E) must hold byte-equal PKs.

    With Phase 0 closeout partitioning, the elections fact-table now lives
    at ``state=<val>/election_results.parquet``; the JOIN reads it via a
    Hive glob (DuckDB stitches partitions transparently)."""
    _seed_taxonomy(tmp_path)
    write_batch(_dim_envelope(), tmp_path)
    con = duckdb.connect(":memory:")
    rows = con.execute(
        f"""
        SELECT c.name, o.value_numeric
        FROM read_parquet('{(tmp_path / "elections" / "state=*" / "election_results.parquet").as_posix()}') o
        JOIN read_parquet('{(tmp_path / "elections" / "dim_candidates.parquet").as_posix()}') c
          ON c.candidate_id = o.entity_id
        WHERE o.indicator_id = 'candidate-votes-polled'
        """
    ).fetchall()
    assert rows == [("A. Alpha", 42.0)]


def test_dim_upsert_overwrites_pk_on_rerun(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    write_batch(_dim_envelope(), tmp_path)

    updated = _cand_dim()
    updated = updated.model_copy(update={"name": "A. Alpha (corrected)"})
    env2 = BatchEnvelope(
        target_family="elections",
        source_rows=[_src()],
        observation_rows=[_obs(entity_id="IN-S22-AC-2008-167-AcGenApr2021-C01",
                               indicator_id="candidate-votes-polled",
                               year=2021, period_label="AcGenApr2021")],
        candidate_dim_rows=[updated],
    )
    write_batch(env2, tmp_path)

    con = duckdb.connect(":memory:")
    [(name,)] = con.execute(
        f"SELECT name FROM read_parquet('"
        f"{(tmp_path / 'elections' / 'dim_candidates.parquet').as_posix()}')"
    ).fetchall()
    assert name == "A. Alpha (corrected)"


def test_empty_dim_lists_do_not_touch_existing_dim_files(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    write_batch(_dim_envelope(), tmp_path)
    dim_path = tmp_path / "elections" / "dim_candidates.parquet"
    bytes_before = dim_path.read_bytes()

    env2 = BatchEnvelope(
        target_family="elections",
        source_rows=[_src()],
        observation_rows=[_obs(entity_id="IN-S22-AC-2008-167-AcGenApr2021-C01",
                               indicator_id="candidate-votes-polled",
                               year=2021, period_label="AcGenApr2021")],
    )
    write_batch(env2, tmp_path)
    assert dim_path.read_bytes() == bytes_before


def test_dim_candidates_party_short_raw_roundtrips(tmp_path: Path) -> None:
    """v1.1 additive: dim_candidates carries party_short_raw, the verbatim
    upstream ECI party_short string. Used by the UI as a fallback display
    when party_id == 'parties.IN.UNK' so the chip never shows the literal
    sentinel for long-tail fringe parties not yet in taxonomy/parties.json.

    This is the structural fix for PR-R.2 (no-UNK-regression). Even with
    a richer canonical taxonomy, new shorts will surface forever; the
    column ensures the citizen-visible chip always carries an honest label.
    """
    _seed_taxonomy(tmp_path)
    unk_cand = CandidateDimRow(
        candidate_id="IN-S22-AC-2008-167-AcGenApr2021-C02",
        ac_id="IN-S22-AC-2008-167",
        period_label="AcGenApr2021",
        ballot_serial=2,
        name="X. Unknown",
        party_id="parties.IN.UNK",
        rank=2,
        source_id="src-test00000001",
        party_short_raw="FRINGE",
    )
    env = BatchEnvelope(
        target_family="elections",
        source_rows=[_src()],
        observation_rows=[_obs(entity_id="IN-S22-AC-2008-167-AcGenApr2021-C02",
                               indicator_id="candidate-votes-polled",
                               year=2021, period_label="AcGenApr2021")],
        candidate_dim_rows=[unk_cand],
    )
    write_batch(env, tmp_path)

    con = duckdb.connect(":memory:")
    rows = con.execute(
        f"SELECT candidate_id, party_id, party_short_raw FROM read_parquet('"
        f"{(tmp_path / 'elections' / 'dim_candidates.parquet').as_posix()}') "
        f"ORDER BY candidate_id"
    ).fetchall()
    assert rows == [
        ("IN-S22-AC-2008-167-AcGenApr2021-C02", "parties.IN.UNK", "FRINGE"),
    ]


def test_dim_candidates_upsert_by_name_fills_legacy_rows_with_null(tmp_path: Path) -> None:
    """Additive-column safety: an existing v1.0 Parquet (no party_short_raw)
    plus a v1.1 envelope must coexist after UPSERT. The legacy rows carry
    NULL for the new column; the new rows carry their value. INSERT BY NAME
    keeps the writer migrate-friendly for additive bumps."""
    _seed_taxonomy(tmp_path)
    # First write: v1.1-shaped row but with party_short_raw=None (simulating
    # a row carried over from v1.0 when the field didn't exist).
    legacy = _cand_dim(cid="IN-S22-AC-2008-167-AcGenApr2021-C01", rank=1)
    env1 = BatchEnvelope(
        target_family="elections",
        source_rows=[_src()],
        observation_rows=[_obs(entity_id="IN-S22-AC-2008-167-AcGenApr2021-C01",
                               indicator_id="candidate-votes-polled",
                               year=2021, period_label="AcGenApr2021")],
        candidate_dim_rows=[legacy],
    )
    write_batch(env1, tmp_path)

    # Second write: adds a new row with party_short_raw populated.
    new = CandidateDimRow(
        candidate_id="IN-S22-AC-2008-167-AcGenApr2021-C03",
        ac_id="IN-S22-AC-2008-167",
        period_label="AcGenApr2021",
        ballot_serial=3,
        name="Y. Newcomer",
        party_id="parties.IN.UNK",
        rank=3,
        source_id="src-test00000001",
        party_short_raw="UPNEW",
    )
    env2 = BatchEnvelope(
        target_family="elections",
        source_rows=[_src()],
        observation_rows=[_obs(entity_id="IN-S22-AC-2008-167-AcGenApr2021-C03",
                               indicator_id="candidate-votes-polled",
                               year=2021, period_label="AcGenApr2021")],
        candidate_dim_rows=[new],
    )
    write_batch(env2, tmp_path)

    con = duckdb.connect(":memory:")
    rows = con.execute(
        f"SELECT candidate_id, party_short_raw FROM read_parquet('"
        f"{(tmp_path / 'elections' / 'dim_candidates.parquet').as_posix()}') "
        f"ORDER BY candidate_id"
    ).fetchall()
    assert rows == [
        ("IN-S22-AC-2008-167-AcGenApr2021-C01", None),
        ("IN-S22-AC-2008-167-AcGenApr2021-C03", "UPNEW"),
    ]


def test_dim_tables_appear_in_manifest(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    write_batch(_dim_envelope(), tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    table_ids = {t["table_id"] for t in manifest["tables"]}
    assert {"elections.dim_candidates", "elections.dim_acs",
            "elections.dim_parties", "elections.dim_party_alliances"}.issubset(table_ids)
    cand = next(t for t in manifest["tables"]
                if t["table_id"] == "elections.dim_candidates")
    assert cand["format"] == "parquet"
    # schema_version is derived from dim-candidates.schema.json's x-version
    # via writer._regenerate_manifest -> schema_version(); bumps here when
    # the schema bumps. v1.2 (PR-S.1) added 6 bio columns.
    assert cand["schema_version"] == "1.2"
    assert cand["table_name"] == "dim_candidates"
    assert cand["kind"] == "dim"
    assert cand["row_count_total"] == 1


def test_dim_candidates_bio_fields_roundtrip(tmp_path: Path) -> None:
    """v1.2 additive (PR-S.1): dim_candidates carries six biographic fields
    (sex, age, education, profession, constituency_type, party_type) lifted
    from the per-candidate JSON sidecars formerly under
    ``datasets/people/<event>/<ac>/<slug>.json``. Each field is nullable;
    enums copied verbatim from people.entity.schema.json v1.0.

    This test pins the round-trip so any future enum drift between the two
    schemas (or a forgotten Pydantic widening) surfaces as a hard failure.
    """
    _seed_taxonomy(tmp_path)
    with_bio = CandidateDimRow(
        candidate_id="IN-S22-AC-2008-167-AcGenApr2021-C01",
        ac_id="IN-S22-AC-2008-167",
        period_label="AcGenApr2021",
        ballot_serial=1,
        name="A. Alpha",
        party_id="parties.IN.DMK",
        rank=1,
        source_id="src-test00000001",
        sex="Female",
        age=42,
        education="Graduate Professional",
        profession="Liberal Profession or Professional",
        constituency_type="GEN",
        party_type="STATE",
    )
    env = BatchEnvelope(
        target_family="elections",
        source_rows=[_src()],
        observation_rows=[_obs(entity_id="IN-S22-AC-2008-167-AcGenApr2021-C01",
                               indicator_id="candidate-votes-polled",
                               year=2021, period_label="AcGenApr2021")],
        candidate_dim_rows=[with_bio],
    )
    write_batch(env, tmp_path)

    con = duckdb.connect(":memory:")
    rows = con.execute(
        f"SELECT candidate_id, sex, age, education, profession, constituency_type, party_type "
        f"FROM read_parquet('"
        f"{(tmp_path / 'elections' / 'dim_candidates.parquet').as_posix()}') "
        f"ORDER BY candidate_id"
    ).fetchall()
    assert rows == [
        (
            "IN-S22-AC-2008-167-AcGenApr2021-C01",
            "Female",
            42,
            "Graduate Professional",
            "Liberal Profession or Professional",
            "GEN",
            "STATE",
        ),
    ]


def test_dim_candidates_bio_fields_nullable_and_age_bounds(tmp_path: Path) -> None:
    """All six v1.2 bio columns are nullable; age has explicit 18-120 bounds
    (Art. 173(b) constitutional minimum). A row that omits every bio field
    round-trips with NULLs in every bio column; an out-of-range age raises
    at Pydantic validation time."""
    _seed_taxonomy(tmp_path)
    write_batch(_dim_envelope(), tmp_path)
    con = duckdb.connect(":memory:")
    rows = con.execute(
        f"SELECT sex, age, education, profession, constituency_type, party_type "
        f"FROM read_parquet('"
        f"{(tmp_path / 'elections' / 'dim_candidates.parquet').as_posix()}') "
        f"ORDER BY candidate_id"
    ).fetchall()
    # _cand_dim() does not set any bio field -> all NULL.
    assert rows == [(None, None, None, None, None, None)]

    # Age bounds: 17 rejected (below constitutional minimum), 121 rejected.
    import pytest as _pytest
    with _pytest.raises(Exception):
        CandidateDimRow(
            candidate_id="IN-S22-AC-2008-167-AcGenApr2021-C09",
            ac_id="IN-S22-AC-2008-167",
            period_label="AcGenApr2021",
            ballot_serial=9,
            name="Q. Underage",
            party_id="parties.IN.DMK",
            rank=9,
            source_id="src-test00000001",
            age=17,
        )
    with _pytest.raises(Exception):
        CandidateDimRow(
            candidate_id="IN-S22-AC-2008-167-AcGenApr2021-C10",
            ac_id="IN-S22-AC-2008-167",
            period_label="AcGenApr2021",
            ballot_serial=10,
            name="R. Overage",
            party_id="parties.IN.DMK",
            rank=10,
            source_id="src-test00000001",
            age=121,
        )
