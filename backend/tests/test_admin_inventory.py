"""Smoke tests for the admin Inventory endpoint.

These talk to the FastAPI app in-process (TestClient — no uvicorn,
no port). They assume the repo's `datasets/elections/` is the live
one (the inventory module resolves the repo root via __file__) so
the assertions are loose: shape only, plus presence of the May 2026
states we know are in the repo today.
"""

from __future__ import annotations

import pytest

# Skip the whole module gracefully if FastAPI/admin extras aren't installed.
fastapi = pytest.importorskip("fastapi")  # noqa: F841
from fastapi.testclient import TestClient

from yen_gov.admin import app


client = TestClient(app)


def test_health_ok():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_inventory_shape():
    r = client.get("/api/inventory")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"events", "states", "cells"}
    assert isinstance(body["events"], list)
    assert isinstance(body["cells"], list)
    assert isinstance(body["states"], dict)


def test_inventory_includes_known_2026_event():
    body = client.get("/api/inventory").json()
    assert "AcGenMay2026" in body["events"], body["events"]
    # At least one state cell with a non-zero ac_results.found
    assert any(
        c["event"] == "AcGenMay2026" and c["ac_results"]["found"] > 0
        for c in body["cells"]
    )


def test_inventory_resolves_state_names():
    body = client.get("/api/inventory").json()
    # If S22 is present in the inventory, its display name must resolve via
    # datasets/reference/in/states.json (this is the bug class the user
    # called out: codes leaking into UI).
    if "S22" in body["states"]:
        assert body["states"]["S22"] == "Tamil Nadu"
