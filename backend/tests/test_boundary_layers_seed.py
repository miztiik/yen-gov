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


def test_boundary_sources_count_is_seven():
    """7 boundary producers seeded today (datameet, htl, shijithpk J&K AC,
    shijithpk PC 2024, ramseraph, yashveeeeeeer, datagovin_post_pincode_polygons_2025).
    Was 6 before the postal polygons ingest landed (Phase A.2) -- the
    7th row is India Post (Department of Posts, Government of India)
    via the data.gov.in OGD KMZ catalogue, the FIRST issuing-authority
    boundary source (others all republish ECI/SoI/LGD upstream). The
    second shijithpk row exists because the J&K AC layer and the India
    PC layer are DIFFERENT publications by the same producer with
    distinct (producer, title, vintage) triples; collapsing them onto
    one source_id would lose per-document citation precision (ADR-0032
    Rejected A). Adding an 8th producer requires a co-bumped
    citizen-facing change AND addition to SOURCE_NICKNAMES +
    _BOUNDARY_SOURCE_TRIPLES + by_nickname in the same commit."""
    assert len(BOUNDARY_SOURCES) == 7
    assert len(SOURCE_NICKNAMES) == 7
    assert len(BOUNDARY_SOURCE_ID_BY_NICKNAME) == 7


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


def test_boundary_sources_republisher_split():
    """Post Phase A.2 (postal polygons), 6 of 7 boundary seeds are
    republishers (ECI / SoI / LGD are the upstream-upstream authorities)
    and exactly 1 is an issuing-authority seed: India Post (Department
    of Posts, Government of India) via the data.gov.in OGD catalogue.
    India Post IS the upstream authority for pincode definitions; no
    other party publishes the canonical pincode-to-polygon mapping. If
    a future PR seeds a second issuing-authority source (e.g. ECI raw
    shapefile), the count below shifts accordingly."""
    issuing_rows = [r for r in BOUNDARY_SOURCES if r.is_issuing_authority]
    republisher_rows = [r for r in BOUNDARY_SOURCES if not r.is_issuing_authority]
    assert len(issuing_rows) == 1, (
        f"expected exactly 1 issuing-authority boundary source today; "
        f"got {[r.source_id for r in issuing_rows]}"
    )
    assert len(republisher_rows) == 6
    # The one issuing-authority row is India Post (Phase A.2 pincode polygons)
    only_issuing = issuing_rows[0]
    assert "post" in only_issuing.producer.lower(), (
        f"the issuing-authority seed should be India Post; got {only_issuing.producer!r}"
    )


def test_boundary_sources_postal_seed_is_india_post():
    """Post Phase A.2: the postal/pincode source row is seeded by
    Department of Posts via data.gov.in OGD. Catches accidental
    drift (e.g. someone removing the postal seed, or a future
    PR adding a second postal source without bumping this test)."""
    postal_rows = [
        row
        for row in BOUNDARY_SOURCES
        if "postal" in (row.producer + " " + row.title).lower()
        or "pincode" in (row.producer + " " + row.title).lower()
        or "post" in row.producer.lower()
    ]
    assert len(postal_rows) == 1, (
        f"expected exactly one postal/pincode boundary seed today; got {len(postal_rows)}"
    )
    row = postal_rows[0]
    assert "Department of Posts" in row.producer
    assert row.is_issuing_authority is True
    assert row.license == "OGL-IN-1.0"
    assert row.verification_method == "transcribed"


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


def test_upsert_boundary_sources_inserts_seven_rows(_sources_con):
    n = upsert_boundary_sources(_sources_con)
    assert n == 7
    [(count,)] = _sources_con.execute("SELECT COUNT(*) FROM sources").fetchall()
    assert count == 7


def test_upsert_boundary_sources_is_idempotent(_sources_con):
    """Re-running MUST NOT duplicate rows (PK on source_id; INSERT OR REPLACE)."""
    upsert_boundary_sources(_sources_con)
    upsert_boundary_sources(_sources_con)
    [(count,)] = _sources_con.execute("SELECT COUNT(*) FROM sources").fetchall()
    assert count == 7


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
    assert n_sources == 7  # all 7 BOUNDARY_SOURCES upserted regardless of which are referenced
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
    with pytest.raises(ValueError, match="not one of the 7 BOUNDARY_SOURCES"):
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
    assert n_sources == 7
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


# ---------------------------------------------------------------------------
# PC layer + delimitation_vintage partitioning (PR-1 contract)
# ---------------------------------------------------------------------------


def test_two_shijithpk_sources_have_distinct_ids():
    """ADR-0032 Rejected A: same producer + different title/vintage =
    different source_id. The J&K AC layer and the India PC 2024 layer
    are TWO distinct shijithpk publications; collapsing them would
    lose per-document citation precision."""
    jk_id = BOUNDARY_SOURCE_ID_BY_NICKNAME["shijithpk"]
    pc_id = BOUNDARY_SOURCE_ID_BY_NICKNAME["shijithpk_pc_2024"]
    assert jk_id != pc_id, (
        "shijithpk J&K AC and shijithpk PC 2024 share a source_id; "
        "the citation triple should disambiguate them"
    )
    # Both come from same producer string
    by_id = {row.source_id: row for row in BOUNDARY_SOURCES}
    assert by_id[jk_id].producer == by_id[pc_id].producer == "shijithpk"
    # But titles differ (vintages happen to both be '2024' here -- the
    # disambiguator that gives them distinct source_ids is the title)
    assert by_id[jk_id].title != by_id[pc_id].title


def test_shijithpk_pc_2024_v2_field_profile():
    """The PC 2024 row's classification reflects what was actually
    verified: public-domain (Unlicense, equivalent to a dedication),
    bronze (a single individual's georeferencing of an ECI bitmap,
    not the ECI authoritative shapefile), transcribed (not a
    live-fetched authoritative feed), is_issuing_authority=False
    (ECI is the upstream-upstream authority, shijithpk is republisher).
    A future PR that ingests ECI's authoritative shapefile would add
    a DIFFERENT row with is_issuing_authority=True; this row stays
    as-is."""
    by_id = {row.source_id: row for row in BOUNDARY_SOURCES}
    row = by_id[BOUNDARY_SOURCE_ID_BY_NICKNAME["shijithpk_pc_2024"]]
    assert row.license == "public-domain"
    assert row.confidence_tier == "bronze"
    assert row.verification_method == "transcribed"
    assert row.is_issuing_authority is False
    assert row.url_main == "https://github.com/shijithpk/2024_maps_supplement"


def test_pc_layer_row_delim_partition_via_compile(tmp_path):
    """End-to-end: write + read parquet, confirm delimitation_vintage
    column round-trips for the PC row."""
    import duckdb

    pc_src = BOUNDARY_SOURCE_ID_BY_NICKNAME["shijithpk_pc_2024"]
    row = BoundaryLayerRow(
        layer_id="boundaries.in.pc.delim=2024",
        level="pc",
        partition_path="boundaries/in/pc/delim=2024/all.geojson",
        format="geojson",
        crs="EPSG:4326",
        original_feature_count=545,
        retained_feature_count=545,
        unkeyed_count=0,
        size_bytes=8769142,
        source_id=pc_src,
        delimitation_vintage="2024",
    )
    n_layers, _ = compile_to_parquet([row], tmp_path)
    assert n_layers == 1

    con = duckdb.connect()
    try:
        result = con.execute(
            f"SELECT layer_id, level, delimitation_vintage FROM read_parquet("
            f"'{(tmp_path / 'boundaries' / 'boundary_layers.parquet').as_posix()}'"
            f") WHERE level='pc'"
        ).fetchall()
    finally:
        con.close()
    assert result == [("boundaries.in.pc.delim=2024", "pc", "2024")]


def test_delim_vintage_pattern_enforced():
    """Pydantic regex on delimitation_vintage: must be 4 digits or None.
    Catches accidental empty string, ISO date, or free-form vintage text."""
    pc_src = BOUNDARY_SOURCE_ID_BY_NICKNAME["shijithpk_pc_2024"]
    base = dict(
        layer_id="boundaries.in.pc.delim=2024",
        level="pc",
        partition_path="boundaries/in/pc/delim=2024/all.geojson",
        format="geojson",
        crs="EPSG:4326",
        original_feature_count=1,
        retained_feature_count=1,
        unkeyed_count=0,
        size_bytes=1,
        source_id=pc_src,
    )
    # None is the documented default (e.g. for non-delimited bodies like states)
    BoundaryLayerRow(**base, delimitation_vintage=None)
    # Empty string violates the ^[0-9]{4}$ pattern
    with pytest.raises(ValidationError):
        BoundaryLayerRow(**base, delimitation_vintage="")
    # ISO date violates
    with pytest.raises(ValidationError):
        BoundaryLayerRow(**base, delimitation_vintage="2024-05-01")
    # Free-form text violates
    with pytest.raises(ValidationError):
        BoundaryLayerRow(**base, delimitation_vintage="post-2024")

