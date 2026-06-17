"""Unit tests for tools/iced_stage.py (the ICED feed staging helper).

The tool is standalone (no backend imports); loaded via importlib like the
RBI staging-tool test. The one external boundary -- the network GET -- is
injected (``fetch=``), so no test touches the network (CLAUDE.md mock
carve-out for an untestable boundary).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = REPO_ROOT / "tools" / "iced_stage.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("iced_stage", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fake_fetch(body: bytes):
    def _fetch(url, *, retries, retry_delay_seconds, timeout_seconds):
        return body

    return _fetch


def test_feed_url_joins_host_and_path() -> None:
    tool = _load_tool()
    cap = tool.FEEDS_BY_NAME["capacity_metatable"]
    assert tool.feed_url(cap) == "https://icedapi.niti.gov.in/v1/capacity-metatable-data"
    sol = tool.FEEDS_BY_NAME["solar_potential"]
    assert tool.feed_url(sol) == "https://icedapi.niti.gov.in/energy/fuel-sources/solar/potential"


def test_looks_like_json_body_accepts_json_and_aes_envelope() -> None:
    tool = _load_tool()
    assert tool.looks_like_json_body(b'{"a":1}') is True
    assert tool.looks_like_json_body(b"[1,2]") is True
    assert tool.looks_like_json_body(b'"U2FsdGVkX1+abc=="') is True  # AES envelope
    assert tool.looks_like_json_body(b"  \n[1]") is True  # leading whitespace
    assert tool.looks_like_json_body(b"<!DOCTYPE html>") is False
    assert tool.looks_like_json_body(b"") is False


def test_manifest_integrity() -> None:
    tool = _load_tool()
    names = [f.name for f in tool.FEEDS]
    assert len(names) == len(set(names)), "feed names must be unique"
    # The 5 agreed NEW targets are present...
    new = {f.name for f in tool.FEEDS if f.category == "new"}
    assert {
        "solar_potential", "wind_potential", "bio_energy_potential",
        "ice_ev_vahan", "captive_power_industry",
        "transmission_substation_list", "aq_coal_plant_impact",
    } <= new
    # ...and the dropped daily-peak-demand feed is NOT present.
    assert not any("daily" in n or "last30" in n.lower() for n in names)
    # Every new feed has no adapter yet; the live ones name a CLI.
    for f in tool.FEEDS:
        if f.category == "new":
            assert f.backend_ingest is None
    assert tool.FEEDS_BY_NAME["capacity_metatable"].backend_ingest == "ingest-iced-capacity"


def test_stage_feed_writes_and_records(tmp_path: Path) -> None:
    tool = _load_tool()
    feed = tool.FEEDS_BY_NAME["capacity_metatable"]
    body = b'[{"state":"Tamil Nadu"}]'

    rec = tool.stage_feed(
        feed, staging_root=tmp_path, force=False,
        retries=1, retry_delay_seconds=0, timeout_seconds=1,
        fetch=_fake_fetch(body),
    )

    out = tmp_path / feed.filename
    assert out.read_bytes() == body
    assert rec["status"] == "staged"
    assert rec["bytes"] == len(body)
    assert rec["encrypted"] is False
    assert not (tmp_path / f"{feed.filename}.partial").exists()  # atomic, no leftover


def test_stage_feed_skips_when_present_and_not_forced(tmp_path: Path) -> None:
    tool = _load_tool()
    feed = tool.FEEDS_BY_NAME["solar_potential"]
    (tmp_path / feed.filename).write_bytes(b'"U2FsdGVkX1=="')

    def _boom(*a, **k):  # fetch must NOT be called when skipping
        raise AssertionError("fetch called on skip")

    rec = tool.stage_feed(
        feed, staging_root=tmp_path, force=False,
        retries=1, retry_delay_seconds=0, timeout_seconds=1, fetch=_boom,
    )
    assert rec["status"] == "skipped"


def test_stage_feed_rejects_html_body(tmp_path: Path) -> None:
    tool = _load_tool()
    feed = tool.FEEDS_BY_NAME["retired_capacity_plants"]
    with pytest.raises(RuntimeError):
        tool.stage_feed(
            feed, staging_root=tmp_path, force=True,
            retries=1, retry_delay_seconds=0, timeout_seconds=1,
            fetch=_fake_fetch(b"<!DOCTYPE html>error"),
        )


def test_write_run_log_merges_by_feed(tmp_path: Path) -> None:
    tool = _load_tool()
    tool.write_run_log(tmp_path, [{"feed": "a", "status": "staged"}])
    tool.write_run_log(tmp_path, [{"feed": "b", "status": "staged"}])
    log = json.loads((tmp_path / tool.RUN_LOG_NAME).read_text(encoding="utf-8"))
    assert set(log) == {"a", "b"}


def test_select_feeds_filters_and_rejects_unknown() -> None:
    tool = _load_tool()
    assert {f.name for f in tool.select_feeds(["solar_potential"], None)} == {"solar_potential"}
    assert all(f.category == "new" for f in tool.select_feeds(None, "new"))
    with pytest.raises(SystemExit):
        tool.select_feeds(["does_not_exist"], None)


def test_main_list_is_offline_and_zero_exit(capsys) -> None:
    tool = _load_tool()
    assert tool.main(["--list"]) == 0
    out = capsys.readouterr().out
    assert "capacity_metatable" in out
