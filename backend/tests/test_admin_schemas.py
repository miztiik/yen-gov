"""Smoke tests for the admin Schemas endpoint."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")  # noqa: F841
from fastapi.testclient import TestClient

from yen_gov.admin import app


client = TestClient(app)


def test_schemas_shape():
    r = client.get("/api/schemas")
    assert r.status_code == 200
    body = r.json()
    assert {"schemas", "orphan_failures", "summary"}.issubset(body.keys())
    assert {"total_schemas", "meta_failing", "data_failing_files", "orphan_files"} == set(
        body["summary"].keys()
    )


def test_repo_schemas_are_clean():
    """The committed repo must satisfy the same validator CI runs."""
    body = client.get("/api/schemas").json()
    assert body["summary"]["meta_failing"] == 0, body["summary"]
    assert body["summary"]["data_failing_files"] == 0, body["summary"]
    assert body["summary"]["orphan_files"] == 0, body["summary"]


def test_each_schema_has_version_and_changelog():
    body = client.get("/api/schemas").json()
    for s in body["schemas"]:
        assert s["x_version"], s
        assert s["last_changelog"] is not None, s
        # Tail entry version equals current x-version (validator invariant).
        assert s["last_changelog"]["version"] == s["x_version"], s
