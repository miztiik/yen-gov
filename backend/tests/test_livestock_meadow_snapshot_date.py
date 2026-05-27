"""Per PR-A5b (plan-doc docs/archive/plans/20260526-grain-over-entity-and-storage-decoupling-plan.md):
the 3 livestock meadow generators MUST refuse to run without an explicit
``--snapshot-date YYYY-MM-DD`` and MUST stamp ``<date>T00:00:00Z`` (not
``datetime.now()``) into ``sources[].fetched_at`` + ``indicator.methodology_vintage``
so re-runs are byte-deterministic per CLAUDE.md s10.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "tools"

TOOL_NAMES = (
    "livestock_meadow_pashu_aadhaar",
    "livestock_meadow_owner_reg",
    "livestock_meadow_naip_iv",
)


def _load(tool_name: str):
    path = TOOLS_DIR / f"{tool_name}.py"
    spec = importlib.util.spec_from_file_location(f"_a5b_{tool_name}", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("tool_name", TOOL_NAMES)
def test_main_refuses_without_snapshot_date(monkeypatch, capsys, tool_name):
    mod = _load(tool_name)
    monkeypatch.setattr(sys, "argv", [tool_name])
    with pytest.raises(SystemExit) as exc:
        mod.main()
    # argparse exits with code 2 on missing-required.
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "--snapshot-date" in err


@pytest.mark.parametrize("tool_name", TOOL_NAMES)
def test_main_rejects_malformed_snapshot_date(monkeypatch, capsys, tool_name):
    mod = _load(tool_name)
    monkeypatch.setattr(
        sys, "argv", [tool_name, "--snapshot-date", "2024/01/15"]
    )
    with pytest.raises(SystemExit) as exc:
        mod.main()
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "YYYY-MM-DD" in err


def test_pashu_aadhaar_build_stamps_supplied_fetched_at():
    mod = _load("livestock_meadow_pashu_aadhaar")
    doc, _ = mod.build_meadow_for_species(
        ("2024-25",), 1, "cattle", "Cattle", "cattle",
        {},  # empty district_lookup -> 0 rows + unresolved skip
        "2024-04-01T00:00:00Z",
    )
    assert doc["sources"][0]["fetched_at"] == "2024-04-01T00:00:00Z"
    assert "2024-04-01T00:00:00Z" in doc["indicator"]["methodology_vintage"]


def test_owner_reg_build_stamps_supplied_fetched_at():
    mod = _load("livestock_meadow_owner_reg")
    doc, _ = mod.build_meadow_doc(
        ("2024-25",), {}, "2024-04-01T00:00:00Z",
    )
    assert doc["sources"][0]["fetched_at"] == "2024-04-01T00:00:00Z"
    assert "2024-04-01T00:00:00Z" in doc["indicator"]["methodology_vintage"]


def test_naip_iv_district_build_stamps_supplied_fetched_at():
    mod = _load("livestock_meadow_naip_iv")
    doc, _ = mod.build_district_meadow_doc(
        ("2024-25",), {}, "2024-04-01T00:00:00Z",
    )
    assert doc["sources"][0]["fetched_at"] == "2024-04-01T00:00:00Z"
    assert "2024-04-01T00:00:00Z" in doc["indicator"]["methodology_vintage"]
