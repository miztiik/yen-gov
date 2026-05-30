import json
from pathlib import Path

import pytest

from yen_gov.core.schema_registry import schema_version
from yen_gov.validate import (
    ENERGY_INDICATOR_DIR,
    LEGACY_BOUNDARY_SIDECARS_ALLOWLIST,
    LEGACY_INDICATOR_SHARDS_ALLOWLIST,
    LEGACY_INDICATOR_SHARDS_DIR,
    MEADOW_PRODUCER_REGISTRY,
    load_schemas,
    run,
    tier_a,
    tier_b,
    tier_b_legacy_boundary_sidecars,
    tier_b_meadow_shard_contract,
    tier_b_meadow_vintage_matches_source_id,
    tier_b_no_new_sub_fuel_shards,
)

REPO = Path(__file__).resolve().parents[2]


# Note: these Tier-A validator tests use `entity.schema.json` as a
# representative fixture (any well-formed schema with x-version /
# x-changelog would do). The original fixture was `state.schema.json`;
# repointed in Phase C of the strangler-fig closeout for
# `datasets/reference/in/states.json` when state.schema.json was deleted.


def test_tier_a_rejects_three_part_version(tmp_path: Path):
    src = json.loads((REPO / "datasets/schemas/entity.schema.json").read_text(encoding="utf-8"))
    src["x-version"] = "1.0.0"
    schemas_dir = tmp_path / "datasets/schemas"
    schemas_dir.mkdir(parents=True)
    (schemas_dir / "entity.schema.json").write_text(json.dumps(src), encoding="utf-8")
    schemas, parse_fails = load_schemas(schemas_dir)
    fails = parse_fails + tier_a(schemas)
    assert any("major.minor" in f.message for f in fails), fails


def test_tier_a_rejects_changelog_tail_mismatch(tmp_path: Path):
    src = json.loads((REPO / "datasets/schemas/entity.schema.json").read_text(encoding="utf-8"))
    src["x-changelog"][-1]["version"] = "9.9"
    schemas_dir = tmp_path / "datasets/schemas"
    schemas_dir.mkdir(parents=True)
    (schemas_dir / "entity.schema.json").write_text(json.dumps(src), encoding="utf-8")
    schemas, parse_fails = load_schemas(schemas_dir)
    fails = parse_fails + tier_a(schemas)
    assert any("tail version" in f.message for f in fails), fails


def test_load_schemas_reports_malformed_json(tmp_path: Path):
    schemas_dir = tmp_path / "datasets/schemas"
    schemas_dir.mkdir(parents=True)
    (schemas_dir / "broken.schema.json").write_text("{ not valid json", encoding="utf-8")
    schemas, parse_fails = load_schemas(schemas_dir)
    assert "broken.schema.json" not in schemas
    assert any("invalid JSON" in f.message and f.tier == "A" for f in parse_fails), parse_fails


def _seed_repo(tmp_path: Path) -> Path:
    """Copy real schemas into a tmp 'repo' so Tier B can resolve them."""
    schemas_dir = tmp_path / "datasets/schemas"
    schemas_dir.mkdir(parents=True)
    for src in (REPO / "datasets/schemas").glob("*.schema.json"):
        (schemas_dir / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    return schemas_dir


def _processing_config(version: str, *, include_results: bool = True) -> dict:
    body = {
        "$schema": "https://yen-gov.github.io/schemas/processing.schema.json",
        "$schema_version": version,
        "sources": [],
        "fetch": {
            "concurrency": 1, "retry_attempts": 0,
            "timeout_seconds": 1.0, "user_agent": "x",
        },
    }
    if include_results:
        body["results"] = {"top_n_candidates": 1, "collapse_others": False}
    return body


def _write_schema_compatibility(tmp_path: Path, overrides: list[dict]) -> None:
    registry_path = tmp_path / "datasets" / "schema-compatibility.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps({
        "$schema": "./schemas/schema-compatibility.schema.json",
        "$schema_version": schema_version("schema-compatibility.schema.json"),
        "defaults": [
            {
                "surface": "json-corpus",
                "policy": "current_schema_only",
                "validation": "current_schema",
                "applies_to": ["datasets/**/*.json", "config/**/*.json"],
                "rationale": "Test fixture default keeps JSON corpus current-only unless overrides name additive minors.",
            }
        ],
        "overrides": overrides,
    }), encoding="utf-8")


def _processing_override(accepted_versions: list[str]) -> dict:
    return {
        "surface": "json-corpus",
        "schema": "processing.schema.json",
        "accepted_versions": accepted_versions,
        "validation": "current_schema",
        "rationale": "Test fixture override for additive processing schema minors validated by the current schema.",
    }


def test_tier_b_rejects_wrong_schema_version(tmp_path: Path):
    schemas_dir = _seed_repo(tmp_path)
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "processing.json").write_text(json.dumps({
        "$schema": "https://yen-gov.github.io/schemas/processing.schema.json",
        "$schema_version": "9.9",
        "sources": [],
        "fetch": {
            "concurrency": 1, "retry_attempts": 0,
            "timeout_seconds": 1.0, "user_agent": "x",
        },
        "results": {"top_n_candidates": 1, "collapse_others": False},
    }), encoding="utf-8")
    schemas, _ = load_schemas(schemas_dir)
    fails = tier_b(schemas, tmp_path)
    assert any("$schema_version" in f.message for f in fails), fails


def test_tier_b_accepts_supported_old_additive_minor_from_json_corpus_registry(tmp_path: Path):
    schemas_dir = _seed_repo(tmp_path)
    _write_schema_compatibility(tmp_path, [_processing_override(["3.0", "3.1"])])
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "processing.json").write_text(
        json.dumps(_processing_config("3.0")), encoding="utf-8"
    )
    schemas, _ = load_schemas(schemas_dir)
    fails = tier_b(schemas, tmp_path)
    assert not [f for f in fails if f.file == "config/processing.json"], fails


def test_tier_b_rejects_future_version_even_if_registry_lists_it(tmp_path: Path):
    schemas_dir = _seed_repo(tmp_path)
    _write_schema_compatibility(tmp_path, [_processing_override(["3.1", "3.9"])])
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "processing.json").write_text(
        json.dumps(_processing_config("3.9")), encoding="utf-8"
    )
    schemas, _ = load_schemas(schemas_dir)
    fails = tier_b(schemas, tmp_path)
    assert any(
        f.file == "config/processing.json" and "$schema_version '3.9' is not accepted" in f.message
        for f in fails
    ), fails


def test_tier_b_rejects_old_major_even_if_registry_lists_it(tmp_path: Path):
    schemas_dir = _seed_repo(tmp_path)
    _write_schema_compatibility(tmp_path, [_processing_override(["2.0", "3.1"])])
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "processing.json").write_text(
        json.dumps(_processing_config("2.0")), encoding="utf-8"
    )
    schemas, _ = load_schemas(schemas_dir)
    fails = tier_b(schemas, tmp_path)
    assert any(
        f.file == "config/processing.json" and "$schema_version '2.0' is not accepted" in f.message
        for f in fails
    ), fails


def test_tier_b_rejects_supported_old_minor_with_current_schema_shape_error(tmp_path: Path):
    schemas_dir = _seed_repo(tmp_path)
    _write_schema_compatibility(tmp_path, [_processing_override(["3.0", "3.1"])])
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "processing.json").write_text(
        json.dumps(_processing_config("3.0", include_results=False)), encoding="utf-8"
    )
    schemas, _ = load_schemas(schemas_dir)
    fails = tier_b(schemas, tmp_path)
    assert any(
        f.file == "config/processing.json" and "'results'" in f.message
        for f in fails
    ), fails


def test_tier_b_rejects_missing_required_field(tmp_path: Path):
    schemas_dir = _seed_repo(tmp_path)
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "processing.json").write_text(json.dumps({
        "$schema": "https://yen-gov.github.io/schemas/processing.schema.json",
        "$schema_version": schema_version("processing.schema.json"),
        "sources": [],
        "fetch": {
            "concurrency": 1, "retry_attempts": 0,
            "timeout_seconds": 1.0, "user_agent": "x",
        },
    }), encoding="utf-8")
    schemas, _ = load_schemas(schemas_dir)
    fails = tier_b(schemas, tmp_path)
    assert any("'results'" in f.message for f in fails), fails


def test_tier_b_rejects_unknown_schema(tmp_path: Path):
    schemas_dir = _seed_repo(tmp_path)
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "processing.json").write_text(json.dumps({
        "$schema": "https://example.com/nope.schema.json",
        "$schema_version": "3.0",
    }), encoding="utf-8")
    schemas, _ = load_schemas(schemas_dir)
    fails = tier_b(schemas, tmp_path)
    assert any("unknown schema" in f.message for f in fails), fails


def test_tier_b_does_not_silently_skip_unknown_underscore_dirs(tmp_path: Path):
    """Underscore-prefix is NOT an auto-exemption escape hatch. The only
    permanent exempt segment is `ephemeral` (gitignored operator scratch);
    any other underscore-prefixed dir under `datasets/` MUST raise Tier-B
    loudly so accidental contract drift is caught at validation time. Per
    Fowler review 2026-05-17. Previously paired with a `_test/` exemption;
    that subtree was deleted by T.1 (TODO/20260517 §0e.7) — cross-language
    fixtures now live under `backend/tests/fixtures/`.
    """
    schemas_dir = _seed_repo(tmp_path)
    # Scratch sibling under an underscore-prefixed dir that is NOT in the
    # exclusion set. Must raise Tier-B failure (no $schema declared).
    scratch_dir = tmp_path / "datasets/_scratch"
    scratch_dir.mkdir(parents=True)
    (scratch_dir / "stray.json").write_text(json.dumps({"hello": "world"}), encoding="utf-8")
    schemas, _ = load_schemas(schemas_dir)
    fails = tier_b(schemas, tmp_path)
    paths = [f.file for f in fails]
    assert any("_scratch" in p for p in paths), \
        f"datasets/_scratch/ must NOT be silently skipped, got: {paths}"


def test_tier_b_skips_ephemeral_subtree(tmp_path: Path):
    """`datasets/ephemeral/...` is exempt — the whole subtree is
    gitignored (`.gitignore = *`), same rationale as `.runtime/` per
    CLAUDE.md §2. Holds raw XLSX/PDF dumps, restored legacy-corpus
    snapshots, and operator inventory sidecars (e.g.
    `_ingest_inventory.json`) that are NOT contract surfaces. Other
    non-exempt operator-prefixed dirs (e.g. `notes/`) are not under
    DATA_ROOTS so are skipped anyway; this test pins the explicit
    exclusion.
    """
    schemas_dir = _seed_repo(tmp_path)
    ephemeral_dir = tmp_path / "datasets/ephemeral"
    ephemeral_dir.mkdir(parents=True)
    # Operator inventory sidecar without `$schema` — the real-world bug.
    (ephemeral_dir / "_ingest_inventory.json").write_text(
        json.dumps({"ingested_at": "2026-05-20", "files": []}),
        encoding="utf-8",
    )
    # Nested operator scratchpad — recursion must skip too.
    nested = ephemeral_dir / "legacy-corpus" / "tn"
    nested.mkdir(parents=True)
    (nested / "raw.json").write_text(json.dumps({"dump": True}), encoding="utf-8")
    schemas, _ = load_schemas(schemas_dir)
    fails = tier_b(schemas, tmp_path)
    paths = [f.file for f in fails]
    assert not any("ephemeral" in p for p in paths), \
        f"datasets/ephemeral/ subtree must be skipped, got: {paths}"


# ---------------------------------------------------------------------------
# Tier-B: forbid new folded-indicator shards (CLAUDE.md §10, Gregor PR1)
# ---------------------------------------------------------------------------

def _seed_indicator_tree(
    tmp_path: Path,
    *,
    shards: list[str] | None = None,
    allowlist_entries: list[str] | None = None,
    write_allowlist: bool = True,
) -> None:
    """Seed a tmp repo with optional indicators/in/ shards and an allowlist.

    `shards`: list of relative paths (e.g. ["datasets/indicators/in/foo/bar.json"])
              to create on disk under tmp_path. Each file gets a stub JSON body.
    `allowlist_entries`: list of relative paths to write into the allowlist
              (one per line). If None, the allowlist mirrors `shards`.
    `write_allowlist`: if False, skip writing the allowlist file even when
              the indicators directory exists (tests the missing-allowlist branch).
    """
    if shards is not None:
        for rel in shards:
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps({"stub": True}), encoding="utf-8")
    if write_allowlist:
        allow_path = tmp_path / LEGACY_INDICATOR_SHARDS_ALLOWLIST
        allow_path.parent.mkdir(parents=True, exist_ok=True)
        entries = allowlist_entries if allowlist_entries is not None else (shards or [])
        body = "# Test fixture allowlist\n\n" + "\n".join(entries) + "\n"
        allow_path.write_text(body, encoding="utf-8")


def test_legacy_shards_check_passes_when_allowlisted(tmp_path: Path):
    """Files on disk under datasets/indicators/in/ that ARE in the allowlist
    must not be flagged. This is the steady-state behaviour: every legacy
    shard is listed; nothing fails."""
    shards = [
        "datasets/indicators/in/economy/foo.json",
        "datasets/indicators/in/energy/bar.json",
    ]
    _seed_indicator_tree(tmp_path, shards=shards)
    fails = tier_b_meadow_shard_contract(tmp_path)
    assert fails == [], f"expected no failures, got: {fails}"


def test_legacy_shards_check_rejects_new_shard(tmp_path: Path):
    """A *.json file under datasets/indicators/in/ that is NOT in the
    allowlist must be reported as 'forbidden new indicator shard'. This is
    the doctrine enforcement — the whole point of the check."""
    _seed_indicator_tree(
        tmp_path,
        shards=[
            "datasets/indicators/in/economy/known.json",
            "datasets/indicators/in/economy/sneaky_new.json",
        ],
        allowlist_entries=["datasets/indicators/in/economy/known.json"],
    )
    fails = tier_b_meadow_shard_contract(tmp_path)
    forbidden = [f for f in fails if "forbidden new indicator shard" in f.message]
    assert len(forbidden) == 1, f"expected one forbidden-new failure, got: {fails}"
    assert forbidden[0].file == "datasets/indicators/in/economy/sneaky_new.json"
    assert forbidden[0].tier == "B"


def test_legacy_shards_check_rejects_orphan_allowlist_entry(tmp_path: Path):
    """An allowlist entry whose file no longer exists on disk must surface
    as an orphan failure pointing at the allowlist file. Prevents the
    allowlist from drifting out of sync after a P.* retirement PR."""
    _seed_indicator_tree(
        tmp_path,
        shards=[],
        allowlist_entries=["datasets/indicators/in/economy/gone.json"],
    )
    # Need at least one *.json under datasets/indicators/in/ for the dir
    # to exist; seed an allowlisted one that also exists on disk.
    (tmp_path / "datasets/indicators/in/economy").mkdir(parents=True, exist_ok=True)
    (tmp_path / "datasets/indicators/in/economy/here.json").write_text(
        json.dumps({"stub": True}), encoding="utf-8"
    )
    # Rewrite allowlist to include both the existing and the orphan.
    allow_path = tmp_path / LEGACY_INDICATOR_SHARDS_ALLOWLIST
    allow_path.write_text(
        "# fixture\ndatasets/indicators/in/economy/here.json\n"
        "datasets/indicators/in/economy/gone.json\n",
        encoding="utf-8",
    )
    fails = tier_b_meadow_shard_contract(tmp_path)
    orphans = [f for f in fails if "orphan allowlist entry" in f.message]
    assert len(orphans) == 1, f"expected one orphan failure, got: {fails}"
    assert orphans[0].file == LEGACY_INDICATOR_SHARDS_ALLOWLIST.as_posix()
    assert "gone.json" in orphans[0].message


def test_legacy_shards_check_is_noop_when_indicators_dir_absent(tmp_path: Path):
    """If datasets/indicators/in/ does not exist (final P.* PR has shipped),
    the check is a no-op and does NOT require the allowlist file. This is
    the retirement contract — the directory, the allowlist, and the check
    all disappear together; the check must not fail mid-retirement."""
    # No indicators dir, no allowlist — both absent.
    fails = tier_b_meadow_shard_contract(tmp_path)
    assert fails == [], f"expected no failures when indicators dir absent, got: {fails}"


def test_legacy_shards_check_requires_allowlist_when_indicators_dir_present(tmp_path: Path):
    """If datasets/indicators/in/ exists but the allowlist file is missing,
    the check must fail loudly. Prevents silent passes from accidental
    deletion of the allowlist while the legacy tree is still in place."""
    _seed_indicator_tree(
        tmp_path,
        shards=["datasets/indicators/in/economy/foo.json"],
        write_allowlist=False,
    )
    fails = tier_b_meadow_shard_contract(tmp_path)
    missing = [f for f in fails if "missing allowlist file" in f.message]
    assert len(missing) == 1, f"expected one missing-allowlist failure, got: {fails}"
    assert missing[0].file == LEGACY_INDICATOR_SHARDS_ALLOWLIST.as_posix()
    assert missing[0].tier == "B"


def test_legacy_shards_check_chained_into_run(tmp_path: Path):
    """Regression guard: tier_b_meadow_shard_contract must be
    called by run(). Without this, a future refactor could remove the
    chain and silently re-allow new shards. Seeds a real schemas dir
    (run() loads them) plus a forbidden new shard, then asserts run()
    surfaces the failure."""
    _seed_repo(tmp_path)  # populates datasets/schemas/
    _seed_indicator_tree(
        tmp_path,
        shards=["datasets/indicators/in/economy/forbidden_new.json"],
        allowlist_entries=[],  # empty allowlist
    )
    fails = run(tmp_path)
    forbidden = [
        f for f in fails
        if "forbidden new indicator shard" in f.message
        and f.file == "datasets/indicators/in/economy/forbidden_new.json"
    ]
    assert len(forbidden) == 1, \
        f"run() must chain tier_b_meadow_shard_contract, got: {fails}"


# ---------------------------------------------------------------------------
# Tier-B: forbid legacy boundary sidecars (ADR-0031 Amendment 2026-05-22, T.0d)
# ---------------------------------------------------------------------------

def _seed_boundary_tree(
    tmp_path: Path,
    *,
    files: list[str] | None = None,
    allowlist_entries: list[str] | None = None,
    write_allowlist: bool = True,
) -> None:
    """Seed a tmp repo with files under datasets/boundaries/ and an allowlist.

    `files`: relative paths under tmp_path (typically *.sources.json /
             *.unkeyed.json / *.metadata.json / *-index.json /
             *.geojson). All get a stub body.
    """
    if files is not None:
        for rel in files:
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if rel.endswith(".geojson"):
                p.write_text(
                    json.dumps({"type": "FeatureCollection", "features": []}),
                    encoding="utf-8",
                )
            else:
                p.write_text(json.dumps({"stub": True}), encoding="utf-8")
    if write_allowlist:
        allow_path = tmp_path / LEGACY_BOUNDARY_SIDECARS_ALLOWLIST
        allow_path.parent.mkdir(parents=True, exist_ok=True)
        entries = allowlist_entries if allowlist_entries is not None else []
        body = "# Test fixture allowlist\n" + "\n".join(entries) + "\n"
        allow_path.write_text(body, encoding="utf-8")


def test_legacy_boundary_sidecars_check_passes_when_only_geojson(tmp_path: Path):
    """Steady state post-T.0d: boundaries/ contains only *.geojson + the
    parquet ledger; no sidecars; the check returns zero failures."""
    _seed_boundary_tree(
        tmp_path,
        files=["datasets/boundaries/in/states/all.geojson"],
    )
    fails = tier_b_legacy_boundary_sidecars(tmp_path)
    assert fails == [], f"expected no failures, got: {fails}"


def test_legacy_boundary_sidecars_check_rejects_sources_json(tmp_path: Path):
    """A *.sources.json sidecar surviving under boundaries/ must fail."""
    _seed_boundary_tree(
        tmp_path,
        files=[
            "datasets/boundaries/in/states/all.geojson",
            "datasets/boundaries/in/states/all.geojson.sources.json",
        ],
    )
    fails = tier_b_legacy_boundary_sidecars(tmp_path)
    forbidden = [f for f in fails if "forbidden legacy boundary sidecar" in f.message]
    assert len(forbidden) == 1, f"expected one forbidden failure, got: {fails}"
    assert forbidden[0].file == "datasets/boundaries/in/states/all.geojson.sources.json"
    assert forbidden[0].tier == "B"


def test_legacy_boundary_sidecars_check_rejects_metadata_and_unkeyed(tmp_path: Path):
    """*.metadata.json and *.unkeyed.json patterns are both gated."""
    _seed_boundary_tree(
        tmp_path,
        files=[
            "datasets/boundaries/in/districts/all.geojson.metadata.json",
            "datasets/boundaries/in/districts/all.geojson.unkeyed.json",
        ],
    )
    fails = tier_b_legacy_boundary_sidecars(tmp_path)
    paths = sorted(f.file for f in fails if "forbidden legacy boundary sidecar" in f.message)
    assert paths == [
        "datasets/boundaries/in/districts/all.geojson.metadata.json",
        "datasets/boundaries/in/districts/all.geojson.unkeyed.json",
    ], f"got: {paths}"


def test_legacy_boundary_sidecars_check_rejects_per_state_index_manifest(tmp_path: Path):
    """The per-state `<eci>-villages-index.json` family is gated via the
    `*-index.json` pattern."""
    _seed_boundary_tree(
        tmp_path,
        files=["datasets/boundaries/in/villages/state=in_s22/S22-villages-index.json"],
    )
    fails = tier_b_legacy_boundary_sidecars(tmp_path)
    forbidden = [f for f in fails if "forbidden legacy boundary sidecar" in f.message]
    assert len(forbidden) == 1
    assert "S22-villages-index.json" in forbidden[0].file


def test_legacy_boundary_sidecars_check_honours_allowlist(tmp_path: Path):
    """An allowlisted sidecar is permitted (short-lived override path)."""
    _seed_boundary_tree(
        tmp_path,
        files=["datasets/boundaries/in/states/all.geojson.sources.json"],
        allowlist_entries=["datasets/boundaries/in/states/all.geojson.sources.json"],
    )
    fails = tier_b_legacy_boundary_sidecars(tmp_path)
    assert fails == [], f"expected no failures, got: {fails}"


def test_legacy_boundary_sidecars_check_flags_orphan_allowlist_entry(tmp_path: Path):
    """An allowlist entry whose file is absent must surface as an orphan."""
    _seed_boundary_tree(
        tmp_path,
        files=["datasets/boundaries/in/states/all.geojson"],
        allowlist_entries=["datasets/boundaries/in/states/gone.geojson.sources.json"],
    )
    fails = tier_b_legacy_boundary_sidecars(tmp_path)
    orphans = [f for f in fails if "orphan allowlist entry" in f.message]
    assert len(orphans) == 1, f"expected one orphan failure, got: {fails}"
    assert orphans[0].file == LEGACY_BOUNDARY_SIDECARS_ALLOWLIST.as_posix()


def test_legacy_boundary_sidecars_check_is_noop_when_dir_absent(tmp_path: Path):
    """If datasets/boundaries/ does not exist, the check is a no-op and
    does NOT require the allowlist file."""
    fails = tier_b_legacy_boundary_sidecars(tmp_path)
    assert fails == [], f"expected no failures when boundaries dir absent, got: {fails}"


def test_legacy_boundary_sidecars_check_requires_allowlist_when_dir_present(tmp_path: Path):
    """If boundaries/ exists but the allowlist file is missing, fail loudly."""
    _seed_boundary_tree(
        tmp_path,
        files=["datasets/boundaries/in/states/all.geojson"],
        write_allowlist=False,
    )
    fails = tier_b_legacy_boundary_sidecars(tmp_path)
    missing = [f for f in fails if "missing allowlist file" in f.message]
    assert len(missing) == 1
    assert missing[0].file == LEGACY_BOUNDARY_SIDECARS_ALLOWLIST.as_posix()


def test_legacy_boundary_sidecars_check_chained_into_run(tmp_path: Path):
    """Regression guard: tier_b_legacy_boundary_sidecars must be called by
    run(). Without this, a future refactor could remove the chain and
    silently re-allow boundary sidecars."""
    _seed_repo(tmp_path)  # populates datasets/schemas/
    _seed_boundary_tree(
        tmp_path,
        files=["datasets/boundaries/in/states/all.geojson.sources.json"],
        allowlist_entries=[],
    )
    fails = run(tmp_path)
    forbidden = [
        f for f in fails
        if "forbidden legacy boundary sidecar" in f.message
        and f.file == "datasets/boundaries/in/states/all.geojson.sources.json"
    ]
    assert len(forbidden) == 1, \
        f"run() must chain tier_b_legacy_boundary_sidecars, got: {fails}"


# ---------------------------------------------------------------------------
# tier_b_no_new_sub_fuel_shards (P.1.A C4.8 2026-05-24, Hans+Max Q3 verdict
# Option B per TODO/20260524-p1a-data-reacquisition-plan.md §5). Closed
# 5-bucket fuel axis (ADR-0030 D33.8) enforced via filename regex on
# `<state_>?installed_capacity_<X>_mw.json` shards under
# `datasets/indicators/in/energy/`. Tests use tmp_path fixtures only --
# never walk the real corpus (CLAUDE.md §10).
# ---------------------------------------------------------------------------


def _seed_energy_indicator_tree(tmp_path: Path, files: list[str]) -> None:
    """Seed a tmp repo with stub JSON files under datasets/indicators/in/energy/."""
    for rel in files:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"stub": True}), encoding="utf-8")


def test_no_new_sub_fuel_shards_check_passes_on_current_fuel_set(tmp_path: Path):
    """The on-disk fuel + attribution-axis set as of 2026-05-24 (the suffixes
    pinned in _INSTALLED_CAPACITY_ALLOWED_SUFFIXES) MUST all pass cleanly.

    Failure here = the allowlist drifted out of sync with the corpus and
    real shards will start tripping the fence on the next CI run.
    """
    _seed_energy_indicator_tree(
        tmp_path,
        files=[
            # 5-bucket canonical fuels (Hans D33.8)
            "datasets/indicators/in/energy/installed_capacity_coal_mw.json",
            "datasets/indicators/in/energy/installed_capacity_gas_mw.json",
            "datasets/indicators/in/energy/installed_capacity_hydro_mw.json",
            "datasets/indicators/in/energy/installed_capacity_nuclear_mw.json",
            "datasets/indicators/in/energy/installed_capacity_renewable_mw.json",
            # Pre-D33.8 composite (legacy)
            "datasets/indicators/in/energy/installed_capacity_thermal_mw.json",
            # Aggregate markers
            "datasets/indicators/in/energy/installed_capacity_total_mw.json",
            # state-prefixed aggregate markers
            "datasets/indicators/in/energy/state_installed_capacity_by_source_mw.json",
            "datasets/indicators/in/energy/state_installed_capacity_total_mw.json",
            # state-prefixed attribution-axis variants
            "datasets/indicators/in/energy/state_installed_capacity_geographical_mw.json",
            "datasets/indicators/in/energy/state_installed_capacity_with_alloc_mw.json",
        ],
    )
    fails = tier_b_no_new_sub_fuel_shards(tmp_path)
    assert fails == [], f"expected no failures on current fuel set, got: {fails}"


def test_no_new_sub_fuel_shards_check_rejects_rooftop_solar(tmp_path: Path):
    """A new sub-fuel breakout (rooftop-solar) MUST be rejected.

    This is the canonical example called out in the C4.8 plan-doc §3:
    upstream MNRE publishes rooftop-solar separately, but the canonical
    5-bucket axis collapses it into `renewable` at lift time.
    """
    _seed_energy_indicator_tree(
        tmp_path,
        files=["datasets/indicators/in/energy/installed_capacity_rooftop_solar_mw.json"],
    )
    fails = tier_b_no_new_sub_fuel_shards(tmp_path)
    forbidden = [f for f in fails if "forbidden new sub-fuel" in f.message]
    assert len(forbidden) == 1, f"expected one forbidden failure, got: {fails}"
    assert forbidden[0].file == \
        "datasets/indicators/in/energy/installed_capacity_rooftop_solar_mw.json"
    assert forbidden[0].tier == "B"
    assert "'rooftop_solar'" in forbidden[0].message
    assert "ADR-0030 D33.8" in forbidden[0].message


def test_no_new_sub_fuel_shards_check_rejects_small_hydro_and_bio_power(tmp_path: Path):
    """Multi-shard reject: small-hydro and bio-power both collapse into
    distinct canonical buckets (hydro, renewable) at lift time per
    SUB_FUEL_TO_CANONICAL; neither is a citizen-surface indicator."""
    _seed_energy_indicator_tree(
        tmp_path,
        files=[
            "datasets/indicators/in/energy/installed_capacity_small_hydro_mw.json",
            "datasets/indicators/in/energy/installed_capacity_bio_power_mw.json",
            # state-prefixed sub-fuel variant -- regex must match both shapes
            "datasets/indicators/in/energy/state_installed_capacity_waste_to_energy_mw.json",
        ],
    )
    fails = tier_b_no_new_sub_fuel_shards(tmp_path)
    forbidden_files = sorted(f.file for f in fails if "forbidden new sub-fuel" in f.message)
    assert forbidden_files == [
        "datasets/indicators/in/energy/installed_capacity_bio_power_mw.json",
        "datasets/indicators/in/energy/installed_capacity_small_hydro_mw.json",
        "datasets/indicators/in/energy/state_installed_capacity_waste_to_energy_mw.json",
    ], f"expected three forbidden failures, got: {fails}"


def test_no_new_sub_fuel_shards_check_ignores_other_filename_shapes(tmp_path: Path):
    """The fence is scoped to `<state_>?installed_capacity_<X>_mw.json` only.

    Other energy shards (e.g. `state_rooftop_solar_capacity_mw.json`,
    `india_thermal_capacity_retired_mw.json`, generation / consumption shards)
    are governed by `tier_b_meadow_shard_contract`, NOT this fence.
    Confirms scope-boxing per the C4.8 design note.
    """
    _seed_energy_indicator_tree(
        tmp_path,
        files=[
            # Different filename family -- not matched by the regex
            "datasets/indicators/in/energy/state_rooftop_solar_capacity_mw.json",
            "datasets/indicators/in/energy/india_thermal_capacity_retired_mw.json",
            "datasets/indicators/in/energy/state_electricity_generation_by_source_gwh.json",
            "datasets/indicators/in/energy/state_peak_electricity_demand_mw.json",
        ],
    )
    fails = tier_b_no_new_sub_fuel_shards(tmp_path)
    assert fails == [], \
        f"expected no failures for non-installed_capacity_<X>_mw shapes, got: {fails}"


def test_no_new_sub_fuel_shards_check_is_noop_when_dir_absent(tmp_path: Path):
    """If `datasets/indicators/in/energy/` does not exist (the energy
    family has fully retired to canonical), the check is a no-op."""
    fails = tier_b_no_new_sub_fuel_shards(tmp_path)
    assert fails == [], f"expected no failures when energy dir absent, got: {fails}"


def test_no_new_sub_fuel_shards_check_chained_into_run(tmp_path: Path):
    """Regression guard: tier_b_no_new_sub_fuel_shards must be called by
    run(). Without this, a future refactor could remove the chain and
    silently re-allow sub-fuel shards."""
    _seed_repo(tmp_path)  # populates datasets/schemas/
    _seed_energy_indicator_tree(
        tmp_path,
        files=["datasets/indicators/in/energy/installed_capacity_rooftop_solar_mw.json"],
    )
    fails = run(tmp_path)
    forbidden = [
        f for f in fails
        if "forbidden new sub-fuel" in f.message
        and f.file == "datasets/indicators/in/energy/installed_capacity_rooftop_solar_mw.json"
    ]
    assert len(forbidden) == 1, \
        f"run() must chain tier_b_no_new_sub_fuel_shards, got: {fails}"


def test_no_new_sub_fuel_shards_constants_exported(tmp_path: Path):
    """Sanity: the module-level constants are exported and have the
    expected shape. Guards against a refactor accidentally moving them
    behind a leading-underscore private name (which would break the test
    suite's import + any downstream tooling that needs the dir path)."""
    assert ENERGY_INDICATOR_DIR.as_posix() == "datasets/indicators/in/energy"


# ---------------------------------------------------------------------------
# tier_b_meadow_vintage_matches_source_id (PR-B Commit 3 of ADR-0042;
# structurally enforces ADR-0041 §nn4 / non-negotiable #4). For every
# file under `datasets/<family>/_meadow/<source>/<vintage>/*.json`, the
# rule walks `MEADOW_PRODUCER_REGISTRY` to resolve `<source>` -> full
# producer and asserts at least one row in
# `datasets/taxonomy/sources.parquet` exists with that (producer, vintage)
# pair. Strict equality (no wildcards). Tests use tmp_path corpus only.
# ---------------------------------------------------------------------------


import duckdb  # noqa: E402 -- only needed by the meadow-vintage tests below


def _write_sources_parquet(
    tmp_path: Path, pairs: list[tuple[str, str]]
) -> Path:
    """Write a minimal `datasets/taxonomy/sources.parquet` containing
    one row per (producer, vintage) pair. Only the 4 columns the rule
    reads (`source_id`, `producer`, `vintage` + a stub for the rest)
    are populated."""
    out = tmp_path / "datasets" / "taxonomy" / "sources.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(":memory:")
    try:
        con.execute(
            "CREATE TABLE sources(source_id VARCHAR, producer VARCHAR, vintage VARCHAR)"
        )
        for i, (producer, vintage) in enumerate(pairs):
            con.execute(
                "INSERT INTO sources VALUES (?, ?, ?)",
                [f"src-stub-{i:04d}", producer, vintage],
            )
        con.execute(
            f"COPY (SELECT * FROM sources) TO '{out.as_posix()}' (FORMAT PARQUET)"
        )
    finally:
        con.close()
    return out


def _write_meadow_file(tmp_path: Path, rel: str) -> Path:
    """Write a stub meadow JSON file at `<tmp_path>/<rel>`."""
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"stub": True}), encoding="utf-8")
    return p


def test_meadow_vintage_check_passes_when_path_matches_sources_parquet(
    tmp_path: Path,
):
    """Positive: meadow file at `<source>/<vintage>/` matches an existing
    (producer, vintage) row in `sources.parquet`."""
    _write_meadow_file(
        tmp_path,
        "datasets/energy/_meadow/cea/2026-03/installed_capacity_coal_mw.json",
    )
    _write_sources_parquet(
        tmp_path, [("Central Electricity Authority", "2026-03")]
    )
    fails = tier_b_meadow_vintage_matches_source_id(tmp_path)
    assert fails == [], f"expected no failures on matching pair, got: {fails}"


def test_meadow_vintage_check_rejects_wrong_vintage(tmp_path: Path):
    """Negative: meadow file declares vintage='2024-25' but sources.parquet
    only has the same producer at vintage='2026-03'. The rule MUST
    fail loudly so the operator either rotates the meadow path or adds
    the citation row."""
    _write_meadow_file(
        tmp_path,
        "datasets/energy/_meadow/cea/2024-25/installed_capacity_coal_mw.json",
    )
    _write_sources_parquet(
        tmp_path, [("Central Electricity Authority", "2026-03")]
    )
    fails = tier_b_meadow_vintage_matches_source_id(tmp_path)
    assert len(fails) == 1, f"expected one failure, got: {fails}"
    f = fails[0]
    assert f.tier == "B"
    assert f.file == (
        "datasets/energy/_meadow/cea/2024-25/installed_capacity_coal_mw.json"
    )
    assert "vintage='2024-25'" in f.message
    assert "Central Electricity Authority" in f.message
    assert "ADR-0041" in f.message
    assert "ADR-0042" in f.message


def test_meadow_vintage_check_rejects_unknown_source_segment(tmp_path: Path):
    """Negative: meadow file uses a `<source>` segment NOT in
    MEADOW_PRODUCER_REGISTRY. The rule MUST name the registry so the
    operator either renames the directory or adds the mapping."""
    _write_meadow_file(
        tmp_path,
        "datasets/energy/_meadow/xyz/2024-25/some_file.json",
    )
    _write_sources_parquet(tmp_path, [("Some Producer", "2024-25")])
    fails = tier_b_meadow_vintage_matches_source_id(tmp_path)
    assert len(fails) == 1, f"expected one failure, got: {fails}"
    f = fails[0]
    assert f.tier == "B"
    assert "unknown meadow source segment 'xyz'" in f.message
    assert "MEADOW_PRODUCER_REGISTRY" in f.message
    # All 3 registry keys named so the operator knows which to use.
    for key in MEADOW_PRODUCER_REGISTRY:
        assert key in f.message


def test_meadow_vintage_check_is_noop_when_no_meadow_dirs(tmp_path: Path):
    """If no `_meadow/` subdirectories exist under datasets/, the check
    is a no-op (even if sources.parquet is absent)."""
    (tmp_path / "datasets").mkdir()
    fails = tier_b_meadow_vintage_matches_source_id(tmp_path)
    assert fails == [], f"expected no failures when no meadow dirs, got: {fails}"


def test_meadow_vintage_check_skips_schema_files(tmp_path: Path):
    """`.schema.json` sibling files MUST be skipped (they're contract
    metadata, not staged source data)."""
    _write_meadow_file(
        tmp_path,
        "datasets/energy/_meadow/cea/2026-03/installed_capacity.schema.json",
    )
    _write_meadow_file(
        tmp_path,
        "datasets/energy/_meadow/cea/2026-03/installed_capacity_coal_mw.json",
    )
    _write_sources_parquet(
        tmp_path, [("Central Electricity Authority", "2026-03")]
    )
    fails = tier_b_meadow_vintage_matches_source_id(tmp_path)
    assert fails == [], f"expected no failures (schema file skipped), got: {fails}"


def test_meadow_vintage_check_reports_missing_sources_parquet(tmp_path: Path):
    """If meadow files exist but sources.parquet is absent, every
    meadow file is reported (the operator must run emit-taxonomy)."""
    _write_meadow_file(
        tmp_path,
        "datasets/energy/_meadow/cea/2026-03/installed_capacity_coal_mw.json",
    )
    _write_meadow_file(
        tmp_path,
        "datasets/energy/_meadow/iced/2024-25/state_capacity.json",
    )
    fails = tier_b_meadow_vintage_matches_source_id(tmp_path)
    assert len(fails) == 2, f"expected two failures, got: {fails}"
    for f in fails:
        assert f.tier == "B"
        assert "sources.parquet" in f.message
        assert "emit-taxonomy" in f.message


def test_meadow_vintage_check_chained_into_run(tmp_path: Path):
    """Regression guard: tier_b_meadow_vintage_matches_source_id MUST be
    called by run()."""
    _seed_repo(tmp_path)  # populates datasets/schemas/
    _write_meadow_file(
        tmp_path,
        "datasets/energy/_meadow/cea/2024-25/installed_capacity_coal_mw.json",
    )
    _write_sources_parquet(
        tmp_path, [("Central Electricity Authority", "2026-03")]
    )
    fails = run(tmp_path)
    mismatches = [
        f for f in fails
        if "vintage='2024-25'" in f.message
        and "Central Electricity Authority" in f.message
    ]
    assert len(mismatches) == 1, (
        f"run() must chain tier_b_meadow_vintage_matches_source_id, got: {fails}"
    )


def test_meadow_producer_registry_shape(tmp_path: Path):
    """Sanity: registry has the 3 energy producers + the 1 livestock producer,
    each mapping to the canonical full producer strings used in derive_source_id."""
    assert MEADOW_PRODUCER_REGISTRY == {
        "cea": "Central Electricity Authority",
        "iced": "NITI Aayog India Climate & Energy Dashboard",
        "rbi": "Reserve Bank of India",
        "ndlm": (
            "Department of Animal Husbandry & Dairying, "
            "Ministry of Fisheries, Animal Husbandry & Dairying, "
            "Government of India"
        ),
    }





