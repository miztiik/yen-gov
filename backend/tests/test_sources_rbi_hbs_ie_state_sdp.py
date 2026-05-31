"""Adapter-level tests for ``yen_gov.sources.rbi_hbs_ie_state_sdp``."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path

import pytest
from openpyxl import Workbook

from yen_gov.core.schema_registry import schema_version
from yen_gov.sources.rbi_hbs_ie_state_sdp.ingest import (
    CACHE_RELDIR,
    RBIHBSIEStateSDPCacheMissing,
    ingest,
)


_CACHE_FILENAMES = (
    "T05_NSDP_Statewise_Current.xlsx",
    "T06_NSDP_Statewise_Constant.xlsx",
    "T09_PCNSDP_Statewise_Current.xlsx",
    "T10_PCNSDP_Statewise_Constant.xlsx",
)


def _build_workbook(*, andhra_values: tuple[int, int, int, int], national: bool) -> bytes:
    """Build a minimal HBS-IE state-column workbook.

    Values are ordered as:
    2004-05 base 2010-11, 2004-05 base 2011-12,
    2011-12 base 2011-12, 2011-12 base 2012-13.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "T_5"
    header = [None, "Year", "Andhra Pradesh"]
    if national:
        header.append("All-India per capita NNI")
    else:
        header.append("Telangana")
    ws.append([None])
    ws.append([None, "RBI table title"])
    ws.append(header)
    ws.append([None, "(Base Year : 2004-05)"])
    ws.append([None, "2010-11", andhra_values[0], 9000])
    ws.append([None, "2011-12", andhra_values[1], 10000])
    ws.append([None, "(Base Year : 2011-12)"])
    ws.append([None, "2011-12", andhra_values[2], 11000])
    ws.append([None, "2012-13", andhra_values[3], 12000])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _seed_cache(tmp_path: Path) -> None:
    cache = tmp_path / CACHE_RELDIR
    cache.mkdir(parents=True)
    payloads = {
        "T05_NSDP_Statewise_Current.xlsx": _build_workbook(
            andhra_values=(100, 101, 111, 112), national=False
        ),
        "T06_NSDP_Statewise_Constant.xlsx": _build_workbook(
            andhra_values=(200, 201, 211, 212), national=False
        ),
        "T09_PCNSDP_Statewise_Current.xlsx": _build_workbook(
            andhra_values=(300, 301, 311, 312), national=True
        ),
        "T10_PCNSDP_Statewise_Constant.xlsx": _build_workbook(
            andhra_values=(400, 401, 411, 412), national=True
        ),
    }
    for offset, filename in enumerate(_CACHE_FILENAMES):
        path = cache / filename
        path.write_bytes(payloads[filename])
        ts = 1_800_000_000 + offset
        os.utime(path, (ts, ts))


def test_missing_cache_raises_operator_recipe(tmp_path: Path):
    with pytest.raises(RBIHBSIEStateSDPCacheMissing) as excinfo:
        ingest(repo_root=tmp_path)
    msg = str(excinfo.value)
    assert "Handbook+of+Statistics+on+Indian+Economy" in msg
    assert ".runtime/raw/rbi/handbook_economy_2024_25" in msg
    assert "T05_NSDP_Statewise_Current.xlsx" in msg


def test_ingest_writes_current_schema_artifacts_without_removed_render_fields(tmp_path: Path):
    _seed_cache(tmp_path)

    result = ingest(repo_root=tmp_path)

    assert {item.indicator_id for item in result.indicators} == {
        "economy/nsdp_inr_crore",
        "economy/per_capita_nsdp_current_inr",
        "economy/per_capita_nsdp_constant_inr",
    }

    out_dir = tmp_path / "datasets" / "indicators" / "in" / "economy"
    assert {path.name for path in out_dir.iterdir()} == {
        "nsdp_inr_crore.json",
        "per_capita_nsdp_current_inr.json",
        "per_capita_nsdp_constant_inr.json",
    }

    nsdp = json.loads((out_dir / "nsdp_inr_crore.json").read_text(encoding="utf-8"))
    assert nsdp["$schema_version"] == schema_version("indicator.schema.json")
    assert "facet_labels" not in nsdp["indicator"]
    assert "default_mode" not in nsdp["indicator"]
    assert "renderer_rules" not in nsdp["indicator"]
    assert nsdp["indicator"]["id"] == "economy/nsdp_inr_crore"
    assert nsdp["indicator"]["unit"] == "INR (crore)"

    rows = {
        (row["entity_id"], row["time"], row["facet"]): row
        for row in nsdp["rows"]
    }
    assert rows[("S01", "2010-04", "current")]["value"] == 100
    assert rows[("S01", "2011-04", "current")]["value"] == 111
    assert rows[("S01", "2011-04", "current")]["vintage"] == "Base 2011-12"
    assert rows[("S01", "2011-04", "constant")]["value"] == 211
    assert rows[("S29", "2012-04", "constant")]["value"] == 12000

    assert len(nsdp["sources"]) == 3
    assert nsdp["sources"][0]["url"].startswith("https://rbidocs.rbi.org.in/")
    assert nsdp["sources"][-1]["url"].startswith("https://www.rbi.org.in/")


def test_per_capita_artifact_keeps_all_india_reference_and_denominator(tmp_path: Path):
    _seed_cache(tmp_path)

    ingest(repo_root=tmp_path)

    out_dir = tmp_path / "datasets" / "indicators" / "in" / "economy"
    current = json.loads(
        (out_dir / "per_capita_nsdp_current_inr.json").read_text(encoding="utf-8")
    )

    assert current["$schema_version"] == schema_version("indicator.schema.json")
    assert current["indicator"]["denominator"]["price_basis"] == "current"
    assert "facet_labels" not in current["indicator"]
    rows = {(row["entity_id"], row["time"]): row for row in current["rows"]}
    assert rows[("IN", "2011-04")]["value"] == 11000
    assert rows[("S01", "2011-04")]["value"] == 311
    assert rows[("S01", "2011-04")]["vintage"] == "Base 2011-12"