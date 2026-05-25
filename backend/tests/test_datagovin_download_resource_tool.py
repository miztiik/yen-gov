from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = REPO_ROOT / "tools" / "datagovin_download_resource.py"


def _load_tool():
    spec = importlib.util.spec_from_file_location("datagovin_download_resource", TOOL_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_url_uses_standard_resource_endpoint() -> None:
    tool = _load_tool()
    url = tool.build_url(
        resource_uuid="abc-123",
        api_key="key with spaces",
        offset=20,
        limit=10,
        response_format="csv",
    )

    assert url.startswith("https://api.data.gov.in/resource/abc-123?")
    assert "api-key=key+with+spaces" in url
    assert "offset=20" in url
    assert "limit=10" in url
    assert "format=csv" in url


def test_parse_csv_page_reads_header_and_rows() -> None:
    tool = _load_tool()

    header, rows = tool.parse_csv_page(b"a,b\n1,2\n3,4\n")

    assert header == ("a", "b")
    assert rows == [["1", "2"], ["3", "4"]]


def test_read_partial_row_count_validates_shape(tmp_path: Path) -> None:
    tool = _load_tool()
    partial = tmp_path / "resource.csv.partial"
    partial.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")

    assert tool.read_partial_row_count(partial, expected_header=("a", "b")) == 2

    bad = tmp_path / "bad.csv.partial"
    bad.write_text("a,b\n1\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="columns"):
        tool.read_partial_row_count(bad, expected_header=("a", "b"))