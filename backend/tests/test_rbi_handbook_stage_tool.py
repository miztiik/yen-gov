from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = REPO_ROOT / "tools" / "rbi_handbook_stage.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("rbi_handbook_stage", TOOL_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_staged_path_nests_under_year() -> None:
    tool = _load_tool()

    target = tool.staged_path(
        Path(".runtime/raw/rbi/handbook-states"),
        "2024-25",
        "table-birth-rate.xlsx",
    )

    assert target.as_posix() == (
        ".runtime/raw/rbi/handbook-states/2024-25/table-birth-rate.xlsx"
    )


def test_is_xlsx_bytes_distinguishes_zip_from_html() -> None:
    tool = _load_tool()

    assert tool.is_xlsx_bytes(b"PK\x03\x04rest-of-zip") is True
    assert tool.is_xlsx_bytes(b"<!DOCTYPE html><html>") is False
    assert tool.is_xlsx_bytes(b"") is False


def test_build_request_sends_browser_and_referer_headers() -> None:
    tool = _load_tool()

    request = tool.build_request(
        "https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/2T_X.XLSX",
        referer=tool.DEFAULT_REFERER,
    )

    # urllib title-cases header keys.
    assert request.get_header("User-agent") == tool.USER_AGENT
    assert request.get_header("Referer") == tool.DEFAULT_REFERER


def test_stage_table_skips_when_valid_file_present(tmp_path: Path) -> None:
    tool = _load_tool()
    target = tmp_path / "2024-25" / "table-birth-rate.xlsx"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"PK\x03\x04already-staged")

    status = tool.stage_table(
        url="https://example.invalid/should-not-be-fetched.XLSX",
        target=target,
        referer=tool.DEFAULT_REFERER,
        force=False,
        retries=1,
        retry_delay_seconds=0,
        timeout_seconds=1,
    )

    assert status == "skipped"


def test_fetch_xlsx_bytes_raises_after_exhausting_retries(monkeypatch) -> None:
    tool = _load_tool()

    def _boom(*_args, **_kwargs):
        raise OSError("server closed abruptly")

    monkeypatch.setattr(tool.urllib.request, "urlopen", _boom)

    with pytest.raises(RuntimeError, match="after 2 attempts"):
        tool.fetch_xlsx_bytes(
            "https://example.invalid/x.XLSX",
            referer=tool.DEFAULT_REFERER,
            retries=2,
            retry_delay_seconds=0,
            timeout_seconds=1,
        )
