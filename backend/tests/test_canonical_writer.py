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
    assert kv.get("schema_version") == schema_version("observation.schema.json")
    assert kv.get("row_schema_id") == "./observation.schema.json"
    assert "writer_version" in kv
    assert json.loads(kv["sort_columns"]) == [
        "indicator_id", "entity_id", "year", "period_seq"
    ]


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
    # Post-B3 (2026-06-06): taxonomy.sources retired in X1b (#814);
    # the manifest no longer emits an entry for it.
    assert "taxonomy.sources" not in table_ids

    test_table = next(t for t in manifest["tables"] if t["table_id"] == "test.observations")
    assert test_table["family"] == "test"
    assert test_table["format"] == "parquet"
    assert test_table["schema_version"] == schema_version("observation.schema.json")
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

    Post-B3 (2026-06-06): use the surviving taxonomy/entities.parquet as
    the witness because taxonomy/sources.parquet was retired in X1b
    (#814). entities.parquet still exists on disk (entities_seed.py
    survives) and the seeded fixture corpus carries it via the test
    helper's pre-seeded entities.json.
    """
    _seed_taxonomy(tmp_path)
    # Manually compile entities.parquet so the manifest can pick it up.
    from yen_gov.canonical.entities_seed import compile_to_parquet as _compile_entities
    _compile_entities(
        tmp_path / "taxonomy" / "entities.json",
        tmp_path / "taxonomy" / "entities.parquet",
    )
    write_batch(_envelope([_obs()]), tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    entities_table = next(t for t in manifest["tables"] if t["table_id"] == "taxonomy.entities")
    assert entities_table["family"] == "taxonomy"
    assert entities_table["table_name"] == "entities"
    assert entities_table["kind"] == "taxonomy"


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
    # so the partition value is "tamil-nadu".
    assert result.observations_path.name == "election_results.parquet"
    partition_file = tmp_path / "elections" / "state=tamil-nadu" / "election_results.parquet"
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
    assert files[0]["path"] == "elections/state=tamil-nadu/election_results.parquet"
    assert files[0]["partition_values"] == {"state": "tamil-nadu"}


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
#
# Post-B3 (2026-06-06): dim_persons / dim_acs / dim_pcs / dim_parties +
# elections_candidacies parquets retired in X1b (#814); the writer paths
# for them were deleted alongside this test refactor. Only the
# dim_party_alliances dim survives (CSV emit still TBD per a future X1b
# follow-up). The Pydantic row models (PartyDimRow, AcDimRow, PcDimRow,
# PersonDimRow, CandidacyRow) stay on envelope.py because the legacy
# ECI adapters in canonical/adapters/eci* import them; B4 retires the
# adapters + the unused models.


from yen_gov.canonical.envelope import PartyAllianceDimRow


def _party_alliance_dim(period: str = "AcGenApr2021", alliance: str | None = "UPA") -> PartyAllianceDimRow:
    return PartyAllianceDimRow(
        party_id="parties.IN.DMK",
        short_name="DMK",
        period_label=period,
        alliance=alliance,
        source_id="src-test00000001",
    )


def _alliance_envelope(family: str = "elections") -> BatchEnvelope:
    return BatchEnvelope(
        target_family=family,
        source_rows=[_src()],
        observation_rows=[_obs(entity_id="IN-S22-AC-2008-167-AcGenApr2021-C01",
                               indicator_id="candidate-votes-polled",
                               year=2021, period_label="AcGenApr2021")],
        party_alliance_dim_rows=[_party_alliance_dim()],
    )


def test_dim_party_alliances_composite_pk_upserts(tmp_path: Path) -> None:
    """Composite PK (party_id, period_label): two events for the same party
    coexist, and re-emitting the same key overwrites in place."""
    _seed_taxonomy(tmp_path)
    env = _alliance_envelope()
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


def test_dim_party_alliances_appear_in_manifest(tmp_path: Path) -> None:
    _seed_taxonomy(tmp_path)
    write_batch(_alliance_envelope(), tmp_path)
    manifest = __import__("json").loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    table_ids = {t["table_id"] for t in manifest["tables"]}
    assert "elections.dim_party_alliances" in table_ids
    row = next(t for t in manifest["tables"] if t["table_id"] == "elections.dim_party_alliances")
    assert row["format"] == "parquet"
    assert row["table_name"] == "dim_party_alliances"
    assert row["kind"] == "dim"
    assert row["row_count_total"] == 1
