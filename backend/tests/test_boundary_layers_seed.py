"""Tier-A unit tests for ``yen_gov.canonical.boundary_layers_seed``.

Per CLAUDE.md §15: ``tmp_path`` fixtures only, no real on-disk corpus.
Per CLAUDE.md §10: provenance-as-code is a ``derive_source_id`` triple
hash; tests assert determinism (re-running with same triple gives the
same source_id, byte-for-byte).

T.0d contract surface (chunk 1 of 6): this module defines the
``BoundaryLayerRow`` shape + the 4 hard-coded boundary
``SourceRow`` seeds + an ``upsert_boundary_sources`` helper that
mirrors the office_holdings_seed UPSERT pattern. The full
``compile_to_parquet`` pipeline lands in chunk 2 alongside the
snapshot.py rewrite; the additional 3 compile-tier tests
(happy-path round-trip, denominator-mismatch reject, byte-stable
re-emit) land in that commit's same fused atomic.
"""

from __future__ import annotations

import duckdb
import pytest
from pydantic import ValidationError

from yen_gov.canonical.boundary_layers_seed import (
    BOUNDARY_LAYERS_ROW_SCHEMA_VERSION,
    BOUNDARY_SOURCE_ID_BY_NICKNAME,
    BOUNDARY_SOURCES,
    SOURCE_NICKNAMES,
    BoundaryLayerRow,
    compile_to_parquet,
    upsert_boundary_sources,
)
from yen_gov.canonical.citation import derive_source_id


# ---------------------------------------------------------------------------
# BoundaryLayerRow — Pydantic shape
# ---------------------------------------------------------------------------


def _minimal_row_kwargs(**overrides) -> dict:
    """Default valid kwargs for a minimum-viable BoundaryLayerRow.

    All 10 required fields populated; the 7 nullables default to None.
    Overrides merge in on top so tests can vary one field at a time.
    """
    base = {
        "layer_id": "boundaries.in.states",
        "level": "state",
        "partition_path": "boundaries/in/states/all.geojson",
        "format": "geojson",
        "crs": "EPSG:4326",
        "original_feature_count": 37,
        "retained_feature_count": 37,
        "unkeyed_count": 0,
        "size_bytes": 123456,
        "source_id": BOUNDARY_SOURCE_ID_BY_NICKNAME["datameet"],
    }
    base.update(overrides)
    return base


def test_boundary_layer_row_happy_path():
    row = BoundaryLayerRow(**_minimal_row_kwargs())
    assert row.layer_id == "boundaries.in.states"
    assert row.level == "state"
    assert row.entity_state is None  # nullable default
    assert row.notes is None
    assert row.source_id.startswith("src-")
    assert len(row.source_id) == 16  # "src-" + 12-hex


def test_boundary_layer_row_with_all_nullables_populated():
    row = BoundaryLayerRow(
        **_minimal_row_kwargs(
            layer_id="boundaries.in.villages.state=in_s22.district=603",
            level="village",
            partition_path="boundaries/in/villages/state=in_s22/district=603/all.geojson",
            entity_state="S22",
            entity_district="603",
            simplification_algorithm="douglas-peucker",
            simplification_tolerance_deg=0.0001,
            unkeyed_keys_json='["UNKNOWN_VILLAGE_A","UNKNOWN_VILLAGE_B"]',
            unkeyed_count=2,
            original_feature_count=1234,
            retained_feature_count=1232,
            notes="LGD-keyed; 2 features dropped (no LGD code).",
        )
    )
    assert row.entity_state == "S22"
    assert row.entity_district == "603"
    assert row.simplification_algorithm == "douglas-peucker"
    assert row.simplification_tolerance_deg == 0.0001
    assert row.notes is not None


def test_boundary_layer_row_extra_forbidden():
    """Schema is additionalProperties:false; Pydantic must match (else a
    typo on a column name silently drops to NULL at parquet emit)."""
    with pytest.raises(ValidationError) as exc:
        BoundaryLayerRow(**_minimal_row_kwargs(unknown_column="x"))
    assert "unknown_column" in str(exc.value) or "Extra inputs" in str(exc.value)


def test_boundary_layer_row_frozen():
    row = BoundaryLayerRow(**_minimal_row_kwargs())
    with pytest.raises(ValidationError):
        row.layer_id = "boundaries.in.something_else"  # type: ignore[misc]


def test_boundary_layer_row_invalid_layer_id_pattern():
    """layer_id must match the dot-separated handle regex."""
    with pytest.raises(ValidationError):
        BoundaryLayerRow(**_minimal_row_kwargs(layer_id="invalid id with spaces"))
    with pytest.raises(ValidationError):
        BoundaryLayerRow(**_minimal_row_kwargs(layer_id="boundaries/in/states"))  # slashes not allowed


def test_boundary_layer_row_invalid_partition_path():
    """partition_path must start with ``boundaries/in/``."""
    with pytest.raises(ValidationError):
        BoundaryLayerRow(
            **_minimal_row_kwargs(partition_path="elections/in/results.parquet")
        )


def test_boundary_layer_row_invalid_level_enum():
    with pytest.raises(ValidationError):
        BoundaryLayerRow(**_minimal_row_kwargs(level="continent"))


def test_boundary_layer_row_invalid_source_id_pattern():
    """source_id must match the ``src-<12hex>`` pattern."""
    with pytest.raises(ValidationError):
        BoundaryLayerRow(**_minimal_row_kwargs(source_id="src-NOT_HEX_XX!"))
    with pytest.raises(ValidationError):
        BoundaryLayerRow(**_minimal_row_kwargs(source_id="random-id"))


def test_boundary_layer_row_negative_counts_rejected():
    with pytest.raises(ValidationError):
        BoundaryLayerRow(**_minimal_row_kwargs(original_feature_count=-1))
    with pytest.raises(ValidationError):
        BoundaryLayerRow(**_minimal_row_kwargs(unkeyed_count=-1))
    with pytest.raises(ValidationError):
        BoundaryLayerRow(**_minimal_row_kwargs(size_bytes=-1))


# ---------------------------------------------------------------------------
# BOUNDARY_SOURCES — 4 hard-coded citation rows
# ---------------------------------------------------------------------------


def test_boundary_sources_count_is_five():
    """Per spec §2 + 2026-05-22 chunk-1 correction: 5 boundary producers
    seeded today (datameet, htl, shijithpk, ramseraph, yashveeeeeeer).
    The spec text said '4' but missed yashveeeeeeer/india-geodata (SoI
    national silhouette) which is already on disk via the
    `kind: country` entry. Postal/India Post still NOT seeded —
    pincode geojson doesn't exist yet. Adding a 6th producer requires
    a co-bumped citizen-facing change AND addition to SOURCE_NICKNAMES."""
    assert len(BOUNDARY_SOURCES) == 5
    assert len(SOURCE_NICKNAMES) == 5
    assert len(BOUNDARY_SOURCE_ID_BY_NICKNAME) == 5


def test_boundary_sources_have_deterministic_ids():
    """source_id is sha256(producer|title|vintage)[:12] — re-deriving from
    the same triple MUST produce byte-identical IDs across runs and
    machines. Catches accidental reordering of triple fields."""
    expected_ids = {
        nickname: row.source_id for nickname, row in zip(SOURCE_NICKNAMES, BOUNDARY_SOURCES, strict=True)
    }
    for nickname, row in zip(SOURCE_NICKNAMES, BOUNDARY_SOURCES, strict=True):
        # Re-derive from row's own triple; MUST equal the seed value.
        rederived = derive_source_id(row.producer, row.title, row.vintage)
        assert rederived == row.source_id, (
            f"source_id drift for {nickname}: row has {row.source_id}, "
            f"derive_source_id({row.producer!r}, {row.title!r}, {row.vintage!r}) returns {rederived}"
        )
        assert expected_ids[nickname] == row.source_id


def test_boundary_sources_all_have_required_v2_fields():
    """Per ADR-0032 §12 v2.0: 8 required + 3 optional. Every seed row
    must populate the 8 required fields (producer, title, vintage,
    license, confidence_tier, is_issuing_authority, verification_method,
    source_id). url_main / citation_full / notes are optional."""
    for row in BOUNDARY_SOURCES:
        assert row.producer
        assert row.title
        # vintage MAY be empty string (datameet is rolling) but must be a str
        assert isinstance(row.vintage, str)
        assert row.license
        assert row.confidence_tier
        assert isinstance(row.is_issuing_authority, bool)
        assert row.verification_method
        assert row.source_id.startswith("src-") and len(row.source_id) == 16


def test_boundary_sources_all_are_republishers():
    """All 5 current boundary seeds are republishers (ECI / SoI / LGD are
    the upstream-upstream authorities). If a future PR seeds a
    direct-from-issuing-authority source (e.g. ECI raw shapefile),
    that row's is_issuing_authority will be True and this assertion
    will need updating in the same PR."""
    for row in BOUNDARY_SOURCES:
        assert row.is_issuing_authority is False, (
            f"{row.source_id} ({row.producer}) marked as issuing authority; "
            "boundary seeds are all republishers today"
        )


def test_boundary_sources_have_no_postal_seed():
    """Per spec §2 (locked 2026-05-22): no pincode geojson exists on disk
    today; postal subtree is forward-looking only. If the first postal
    layer ingests in a future PR, that PR adds the 5th source row in
    the same atomic commit as the geometry file + boundary_layers row."""
    for row in BOUNDARY_SOURCES:
        lowered = (row.producer + " " + row.title).lower()
        assert "postal" not in lowered and "pincode" not in lowered, (
            f"{row.source_id} appears postal-related; check spec §2"
        )


# ---------------------------------------------------------------------------
# upsert_boundary_sources — DuckDB UPSERT helper
# ---------------------------------------------------------------------------


@pytest.fixture
def _sources_con() -> duckdb.DuckDBPyConnection:
    """Fresh DuckDB in-memory connection with an empty sources table
    matching the production DDL in canonical/writer.py:_load_existing_sources."""
    con = duckdb.connect()
    con.execute(
        """
        CREATE TABLE sources (
            source_id VARCHAR PRIMARY KEY,
            producer VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            vintage VARCHAR NOT NULL,
            license VARCHAR NOT NULL,
            confidence_tier VARCHAR NOT NULL,
            is_issuing_authority BOOLEAN NOT NULL,
            verification_method VARCHAR NOT NULL,
            url_main VARCHAR,
            citation_full VARCHAR,
            notes VARCHAR
        )
        """
    )
    try:
        yield con
    finally:
        con.close()


def test_upsert_boundary_sources_inserts_five_rows(_sources_con):
    n = upsert_boundary_sources(_sources_con)
    assert n == 5
    [(count,)] = _sources_con.execute("SELECT COUNT(*) FROM sources").fetchall()
    assert count == 5


def test_upsert_boundary_sources_is_idempotent(_sources_con):
    """Re-running MUST NOT duplicate rows (PK on source_id; INSERT OR REPLACE)."""
    upsert_boundary_sources(_sources_con)
    upsert_boundary_sources(_sources_con)
    [(count,)] = _sources_con.execute("SELECT COUNT(*) FROM sources").fetchall()
    assert count == 5


def test_upsert_boundary_sources_populates_expected_ids(_sources_con):
    upsert_boundary_sources(_sources_con)
    rows = _sources_con.execute("SELECT source_id, producer FROM sources ORDER BY source_id").fetchall()
    on_disk_ids = {sid for sid, _ in rows}
    expected_ids = {row.source_id for row in BOUNDARY_SOURCES}
    assert on_disk_ids == expected_ids


# ---------------------------------------------------------------------------
# Schema metadata sourced via registry (not hand-typed)
# ---------------------------------------------------------------------------


def test_schema_version_matches_registry():
    """Per CLAUDE.md §11: code never hand-types schema-version literals.
    The seed module exposes a version constant sourced via
    core.schema_registry; this test asserts non-emptiness + format."""
    assert BOUNDARY_LAYERS_ROW_SCHEMA_VERSION
    parts = BOUNDARY_LAYERS_ROW_SCHEMA_VERSION.split(".")
    assert len(parts) == 2 and all(p.isdigit() for p in parts), (
        f"BOUNDARY_LAYERS_ROW_SCHEMA_VERSION must be 'X.Y' format; got {BOUNDARY_LAYERS_ROW_SCHEMA_VERSION!r}"
    )


# ---------------------------------------------------------------------------
# compile_to_parquet — canonical emission seam (Chunk 2 contract)
# ---------------------------------------------------------------------------


def _layer_row(layer_id: str, source_id: str, **overrides) -> BoundaryLayerRow:
    """Build a minimum-valid BoundaryLayerRow with denominator-transparency
    satisfied (original = retained + unkeyed). Tests vary attributes
    via overrides."""
    base = {
        "layer_id": layer_id,
        "level": "state",
        "partition_path": f"boundaries/in/{layer_id.split('.')[-1]}/all.geojson",
        "format": "geojson",
        "crs": "EPSG:4326",
        "original_feature_count": 36,
        "retained_feature_count": 36,
        "unkeyed_count": 0,
        "size_bytes": 12345,
        "source_id": source_id,
    }
    base.update(overrides)
    return BoundaryLayerRow(**base)


def test_compile_to_parquet_emits_both_outputs(tmp_path):
    """Happy path: writes boundary_layers.parquet under boundaries/ AND
    sources.parquet under taxonomy/ in the same call. Returns
    (layer_count, source_count) for orchestrator logging."""
    from yen_gov.canonical.boundary_layers_seed import (
        BOUNDARY_SOURCE_ID_BY_NICKNAME,
        compile_to_parquet,
    )

    datameet_src = BOUNDARY_SOURCE_ID_BY_NICKNAME["datameet"]
    rows = [
        _layer_row("boundaries.in.states", datameet_src),
    ]
    n_layers, n_sources = compile_to_parquet(rows, tmp_path)
    assert n_layers == 1
    assert n_sources == 5  # all 5 BOUNDARY_SOURCES upserted regardless of which are referenced
    assert (tmp_path / "boundaries" / "boundary_layers.parquet").is_file()
    assert (tmp_path / "taxonomy" / "sources.parquet").is_file()


def test_compile_to_parquet_denominator_violation_rejects(tmp_path):
    """Citizen-trust gate: if original != retained + unkeyed for any row,
    raise ValueError BEFORE any parquet bytes hit disk."""
    from yen_gov.canonical.boundary_layers_seed import (
        BOUNDARY_SOURCE_ID_BY_NICKNAME,
        compile_to_parquet,
    )

    datameet_src = BOUNDARY_SOURCE_ID_BY_NICKNAME["datameet"]
    bad = _layer_row(
        "boundaries.in.states",
        datameet_src,
        original_feature_count=100,
        retained_feature_count=80,
        unkeyed_count=10,  # 80 + 10 = 90, not 100 → bug
    )
    with pytest.raises(ValueError, match="denominator-transparency"):
        compile_to_parquet([bad], tmp_path)
    # No bytes written on rejection
    assert not (tmp_path / "boundaries" / "boundary_layers.parquet").exists()


def test_compile_to_parquet_duplicate_layer_id_rejects(tmp_path):
    """PK uniqueness invariant: duplicate layer_id raises before emit."""
    from yen_gov.canonical.boundary_layers_seed import (
        BOUNDARY_SOURCE_ID_BY_NICKNAME,
        compile_to_parquet,
    )

    src = BOUNDARY_SOURCE_ID_BY_NICKNAME["datameet"]
    rows = [
        _layer_row("boundaries.in.states", src),
        _layer_row("boundaries.in.states", src),  # duplicate
    ]
    with pytest.raises(ValueError, match="duplicate layer_id"):
        compile_to_parquet(rows, tmp_path)


def test_compile_to_parquet_unknown_source_id_rejects(tmp_path):
    """FK pre-check: a layer pointing at a non-boundary source_id must
    be rejected (catches typos + accidental cross-adapter
    misattribution)."""
    from yen_gov.canonical.boundary_layers_seed import compile_to_parquet

    fake_src = "src-deadbeef0000"
    row = _layer_row("boundaries.in.states", fake_src)
    with pytest.raises(ValueError, match="not one of the 5 BOUNDARY_SOURCES"):
        compile_to_parquet([row], tmp_path)


def test_compile_to_parquet_is_byte_stable(tmp_path):
    """Sort-stable emission: same input → byte-identical parquet."""
    from yen_gov.canonical.boundary_layers_seed import (
        BOUNDARY_SOURCE_ID_BY_NICKNAME,
        compile_to_parquet,
    )

    htl_src = BOUNDARY_SOURCE_ID_BY_NICKNAME["htl"]
    rows = [
        _layer_row(f"boundaries.in.ac.state={code}", htl_src, level="ac")
        for code in ("in_s22", "in_s11", "in_s06")  # deliberately unsorted
    ]
    compile_to_parquet(rows, tmp_path)
    first = (tmp_path / "boundaries" / "boundary_layers.parquet").read_bytes()
    compile_to_parquet(rows, tmp_path)
    second = (tmp_path / "boundaries" / "boundary_layers.parquet").read_bytes()
    assert first == second, "compile_to_parquet must be byte-stable across re-runs"


def test_compile_to_parquet_preserves_other_adapter_sources(tmp_path):
    """If sources.parquet already has rows from other adapters (e.g.
    elections, energy), compile_to_parquet must UPSERT boundary rows
    without dropping pre-existing rows. This is the cross-adapter
    co-tenancy invariant — every adapter's seed leaves the others
    intact."""
    import duckdb

    from yen_gov.canonical.boundary_layers_seed import (
        BOUNDARY_SOURCE_ID_BY_NICKNAME,
        compile_to_parquet,
    )

    # Seed an existing sources.parquet with one "other adapter" row
    sources_path = tmp_path / "taxonomy" / "sources.parquet"
    sources_path.parent.mkdir(parents=True)
    con = duckdb.connect()
    con.execute(
        """
        CREATE TABLE sources (
            source_id VARCHAR PRIMARY KEY,
            producer VARCHAR NOT NULL,
            title VARCHAR NOT NULL,
            vintage VARCHAR NOT NULL,
            license VARCHAR NOT NULL,
            confidence_tier VARCHAR NOT NULL,
            is_issuing_authority BOOLEAN NOT NULL,
            verification_method VARCHAR NOT NULL,
            url_main VARCHAR,
            citation_full VARCHAR,
            notes VARCHAR
        )
        """
    )
    con.execute(
        """
        INSERT INTO sources VALUES (
            'src-cea000000001', 'CEA', 'Monthly Generation Report', 'May-2024',
            'OGL-IN-1.0', 'gold', true, 'live-fetch',
            'https://cea.nic.in/monthly-generation-report/', NULL, NULL
        )
        """
    )
    con.execute(
        f"COPY sources TO '{sources_path.as_posix()}' (FORMAT PARQUET)"
    )
    con.close()

    # Now compile some boundary rows
    src = BOUNDARY_SOURCE_ID_BY_NICKNAME["datameet"]
    rows = [_layer_row("boundaries.in.states", src)]
    compile_to_parquet(rows, tmp_path)

    # Both adapter's sources must coexist
    con = duckdb.connect()
    try:
        result = con.execute(
            f"SELECT source_id, producer FROM read_parquet('{sources_path.as_posix()}') ORDER BY source_id"
        ).fetchall()
    finally:
        con.close()
    found_ids = {sid for sid, _ in result}
    assert "src-cea000000001" in found_ids, "pre-existing non-boundary source was dropped"
    for boundary_row in BOUNDARY_SOURCES:
        assert boundary_row.source_id in found_ids, (
            f"boundary source {boundary_row.source_id} ({boundary_row.producer}) not upserted"
        )


def test_compile_to_parquet_empty_input_writes_zero_row_table(tmp_path):
    """Edge case: empty layer_rows list writes an empty boundary_layers.parquet
    + still UPSERTs sources. Tooling that emits incrementally may pass
    [] for a stage and that must not crash."""
    from yen_gov.canonical.boundary_layers_seed import compile_to_parquet

    n_layers, n_sources = compile_to_parquet([], tmp_path)
    assert n_layers == 0
    assert n_sources == 5
    assert (tmp_path / "boundaries" / "boundary_layers.parquet").is_file()
    # Round-trip read confirms zero rows
    import duckdb

    con = duckdb.connect()
    try:
        [(count,)] = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{(tmp_path / 'boundaries' / 'boundary_layers.parquet').as_posix()}')"
        ).fetchall()
    finally:
        con.close()
    assert count == 0
