"""Smoke tests for the admin Pipeline endpoints.

Covers the operator-console HTTP contract: run listing shape, command
allowlist, confirm-required guard, and 404 on unknown run ids. Does
NOT exercise long-running commands end-to-end — corpus validation is a
local-only concern per docs/architecture/backend/validator.md, so
spawning ``yen_gov validate`` from a test would be 60-180s of overhead
testing nothing this layer owns.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")  # noqa: F841
from fastapi.testclient import TestClient

from yen_gov.admin import app


client = TestClient(app)


def test_list_runs_shape():
    r = client.get("/api/pipeline/runs")
    assert r.status_code == 200
    body = r.json()
    assert {"runs", "total", "active", "allowed_commands"}.issubset(body.keys())
    assert "validate" in body["allowed_commands"]
    assert "run" in body["allowed_commands"]


def test_trigger_requires_confirm():
    r = client.post(
        "/api/pipeline/runs",
        json={"command": "validate", "args": [], "confirm": False},
    )
    assert r.status_code == 400


def test_trigger_rejects_unknown_command():
    r = client.post(
        "/api/pipeline/runs",
        json={"command": "rm-rf", "args": [], "confirm": True},
    )
    # pydantic Literal rejects this at validation → 422
    assert r.status_code == 422


def test_get_run_404():
    r = client.get("/api/pipeline/runs/does-not-exist")
    assert r.status_code == 404
