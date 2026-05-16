"""Smoke tests for the admin Schemas endpoint.

Exercise the endpoint LOGIC (response shape, per-schema metadata,
summary math) against a tiny ``tmp_path`` corpus, not the real
``datasets/**`` tree. Walking the live repo here would re-introduce
the corpus-conformance check we descoped from pytest on 2026-05-16 —
see docs/architecture/backend/validator.md for the rationale.

The endpoint reads its root from ``YEN_GOV_REPO_ROOT`` when set, so
each test points it at a controlled fixture corpus and asserts the
endpoint's behaviour without depending on which datasets happen to be
on disk.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")  # noqa: F841
from fastapi.testclient import TestClient

from yen_gov.admin import app


client = TestClient(app)


# A minimal yen-gov-shaped schema: meta-schema clean, x-version /
# x-changelog tail aligned. Body accepts an object with required
# ``name``. We don't model §12 sources[] here because this fixture
# exists to test the endpoint's response-assembly logic, not the
# real-repo provenance contract.
_FIXTURE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://example.test/schemas/foo.schema.json",
    "title": "Foo",
    "description": "Test fixture schema.",
    "x-version": "1.0",
    "x-changelog": [
        {"version": "1.0", "date": "2026-05-16", "description": "Initial."}
    ],
    "type": "object",
    "properties": {
        "$schema": {"type": "string"},
        "$schema_version": {"type": "string"},
        "name": {"type": "string"},
    },
    "required": ["$schema", "$schema_version", "name"],
}


def _write_fixture_corpus(root: Path, *, with_failing: bool = False) -> None:
    """Build a tiny repo skeleton: one schema + one passing data file.

    When ``with_failing`` is set, also drop a data file missing the
    required ``name`` field so Tier-B exercises the failure-grouping
    branch.
    """
    schemas_dir = root / "datasets" / "schemas"
    schemas_dir.mkdir(parents=True)
    (schemas_dir / "foo.schema.json").write_text(
        json.dumps(_FIXTURE_SCHEMA), encoding="utf-8"
    )

    data_dir = root / "datasets" / "foos"
    data_dir.mkdir(parents=True)
    (data_dir / "ok.json").write_text(
        json.dumps(
            {
                "$schema": "https://example.test/schemas/foo.schema.json",
                "$schema_version": "1.0",
                "name": "alpha",
            }
        ),
        encoding="utf-8",
    )
    if with_failing:
        (data_dir / "broken.json").write_text(
            json.dumps(
                {
                    "$schema": "https://example.test/schemas/foo.schema.json",
                    "$schema_version": "1.0",
                    # missing 'name' -> Tier-B failure
                }
            ),
            encoding="utf-8",
        )


@pytest.fixture
def fixture_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _write_fixture_corpus(tmp_path)
    monkeypatch.setenv("YEN_GOV_REPO_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def fixture_corpus_with_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    _write_fixture_corpus(tmp_path, with_failing=True)
    monkeypatch.setenv("YEN_GOV_REPO_ROOT", str(tmp_path))
    return tmp_path


def test_schemas_shape(fixture_corpus: Path):
    r = client.get("/api/schemas")
    assert r.status_code == 200
    body = r.json()
    assert {"schemas", "orphan_failures", "summary"}.issubset(body.keys())
    assert {"total_schemas", "meta_failing", "data_failing_files", "orphan_files"} == set(
        body["summary"].keys()
    )
    assert body["summary"]["total_schemas"] == 1
    assert body["summary"]["meta_failing"] == 0
    assert body["summary"]["data_failing_files"] == 0
    assert body["summary"]["orphan_files"] == 0
    foo = body["schemas"][0]
    assert foo["id"] == "foo.schema.json"
    assert foo["data_files"] == 1


def test_each_schema_has_version_and_changelog(fixture_corpus: Path):
    body = client.get("/api/schemas").json()
    for s in body["schemas"]:
        assert s["x_version"], s
        assert s["last_changelog"] is not None, s
        # Tail entry version equals current x-version (validator invariant).
        assert s["last_changelog"]["version"] == s["x_version"], s


def test_endpoint_groups_data_failures_under_owning_schema(
    fixture_corpus_with_failure: Path,
):
    """A Tier-B failure attributable to a schema lands in that schema's
    ``data_failures`` bucket, not in the global orphan list."""
    body = client.get("/api/schemas").json()
    assert body["summary"]["data_failing_files"] == 1
    assert body["summary"]["orphan_files"] == 0
    foo = body["schemas"][0]
    assert foo["data_failing_files"] == 1
    assert len(foo["data_failures"]) == 1
    assert "name" in foo["data_failures"][0]["message"]
