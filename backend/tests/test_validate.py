import json
from pathlib import Path

import pytest

from yen_gov.validate import load_schemas, run, tier_a, tier_b

REPO = Path(__file__).resolve().parents[2]


def test_repo_passes_validation():
    failures = run(REPO)
    assert failures == [], "\n".join(f"[{f.tier}] {f.file}: {f.message}" for f in failures)


def test_tier_a_rejects_three_part_version(tmp_path: Path):
    src = json.loads((REPO / "datasets/schemas/state.schema.json").read_text(encoding="utf-8"))
    src["x-version"] = "1.0.0"
    schemas_dir = tmp_path / "datasets/schemas"
    schemas_dir.mkdir(parents=True)
    (schemas_dir / "state.schema.json").write_text(json.dumps(src), encoding="utf-8")
    schemas, parse_fails = load_schemas(schemas_dir)
    fails = parse_fails + tier_a(schemas)
    assert any("major.minor" in f.message for f in fails), fails


def test_tier_a_rejects_changelog_tail_mismatch(tmp_path: Path):
    src = json.loads((REPO / "datasets/schemas/state.schema.json").read_text(encoding="utf-8"))
    src["x-changelog"][-1]["version"] = "9.9"
    schemas_dir = tmp_path / "datasets/schemas"
    schemas_dir.mkdir(parents=True)
    (schemas_dir / "state.schema.json").write_text(json.dumps(src), encoding="utf-8")
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
        "$schema_version": "3.0",
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
