"""Smoke tests for the admin Pipeline endpoints.

The trigger test invokes ``yen_gov validate`` (read-only, fast) so we
don't actually fetch from the ECI site or write into datasets/. We
poll the meta until the watcher thread closes out the run.
"""

from __future__ import annotations

import time

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


def test_trigger_validate_end_to_end():
    r = client.post(
        "/api/pipeline/runs",
        json={"command": "validate", "args": [], "confirm": True},
    )
    assert r.status_code == 202, r.text
    run_id = r.json()["run_id"]
    assert run_id

    # Poll up to 60s for the watcher to write final meta.
    deadline = time.time() + 60.0
    final = None
    while time.time() < deadline:
        d = client.get(f"/api/pipeline/runs/{run_id}").json()
        if d["status"] in ("ok", "failed"):
            final = d
            break
        time.sleep(0.5)
    assert final is not None, "validate run did not finish in 60s"
    # We don't assert exit code — repo state may legitimately fail
    # validation in some branches. We DO assert the run finished and
    # produced log output.
    assert final["status"] in ("ok", "failed")
    assert final["meta"].get("argv", [])[:4] == ["python", "-m", "yen_gov", "validate"]
    assert any(line for line in final["console_tail"]), "no console output"


def test_get_run_404():
    r = client.get("/api/pipeline/runs/does-not-exist")
    assert r.status_code == 404
