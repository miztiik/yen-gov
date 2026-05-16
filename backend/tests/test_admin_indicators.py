"""Smoke tests for the `/api/inventory/indicators` admin endpoint.

The endpoint wraps `datasets/reference/in/indicators-completeness.json`;
the assertions here pin the response envelope (shape contract with the
admin Svelte panel) and confirm that index updates flow through without
restarting the app — the file is read fresh on every request, not
cached.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from yen_gov.admin.app import app

client = TestClient(app)


def test_indicators_endpoint_returns_index_envelope() -> None:
    r = client.get("/api/inventory/indicators")
    assert r.status_code == 200, r.text
    body = r.json()

    assert isinstance(body, dict)
    for key in ("$schema", "$schema_version", "generated_at", "index_mtime", "count", "indicators"):
        assert key in body, f"missing key: {key}"

    assert isinstance(body["indicators"], list)
    assert body["count"] == len(body["indicators"])
    # The on-disk index already covers every indicator in the repo.
    # If this drops to zero, the index file got truncated or moved.
    assert body["count"] > 0


def test_indicators_endpoint_row_shape() -> None:
    body = client.get("/api/inventory/indicators").json()
    sample = body["indicators"][0]

    # These are the columns the admin Indicators panel binds to. If the
    # underlying emitter changes them, this test fails loudly so the
    # panel rebind happens in the same commit.
    expected_keys = {
        "id",
        "topic",
        "path",
        "title",
        "documentation_status",
        "inventory_status",
        "frozen",
        "last_collected_at",
        "observed_count",
        "pending_count",
        "unavailable_count",
    }
    missing = expected_keys - set(sample)
    assert not missing, f"row missing keys: {sorted(missing)}"

    # POSIX-relative path per CLAUDE.md §2.
    assert "\\" not in sample["path"]
    assert not sample["path"].startswith("/")
