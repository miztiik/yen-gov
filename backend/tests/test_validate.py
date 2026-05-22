import json
from pathlib import Path

import pytest

from yen_gov.validate import (
    LEGACY_INDICATOR_SHARDS_ALLOWLIST,
    LEGACY_INDICATOR_SHARDS_DIR,
    load_schemas,
    run,
    tier_a,
    tier_b,
    tier_b_legacy_folded_indicator_shards,
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


def test_tier_b_rejects_missing_required_field(tmp_path: Path):
    schemas_dir = _seed_repo(tmp_path)
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "processing.json").write_text(json.dumps({
        "$schema": "https://yen-gov.github.io/schemas/processing.schema.json",
        "$schema_version": "3.1",
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
    fails = tier_b_legacy_folded_indicator_shards(tmp_path)
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
    fails = tier_b_legacy_folded_indicator_shards(tmp_path)
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
    fails = tier_b_legacy_folded_indicator_shards(tmp_path)
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
    fails = tier_b_legacy_folded_indicator_shards(tmp_path)
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
    fails = tier_b_legacy_folded_indicator_shards(tmp_path)
    missing = [f for f in fails if "missing allowlist file" in f.message]
    assert len(missing) == 1, f"expected one missing-allowlist failure, got: {fails}"
    assert missing[0].file == LEGACY_INDICATOR_SHARDS_ALLOWLIST.as_posix()
    assert missing[0].tier == "B"


def test_legacy_shards_check_chained_into_run(tmp_path: Path):
    """Regression guard: tier_b_legacy_folded_indicator_shards must be
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
        f"run() must chain tier_b_legacy_folded_indicator_shards, got: {fails}"



