"""Tests for core.http.Fetcher.

Per Holy Law #7 (no mocks unless asked), these spin up a real local HTTP server.
"""

from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from yen_gov.core.http import Fetcher, url_to_relative_raw_path


# --- local HTTP server fixture ---------------------------------------------

class _FlakyHandler(BaseHTTPRequestHandler):
    """Returns the body registered for the path, with optional N-failures-first."""

    # mutable class state — reset per test via the fixture
    routes: dict[str, bytes] = {}
    fail_first_n: dict[str, int] = {}
    hits: dict[str, int] = {}

    def log_message(self, *args, **kwargs):  # silence stderr
        return

    def do_GET(self):
        path = self.path
        _FlakyHandler.hits[path] = _FlakyHandler.hits.get(path, 0) + 1
        remaining = _FlakyHandler.fail_first_n.get(path, 0)
        if remaining > 0:
            _FlakyHandler.fail_first_n[path] = remaining - 1
            self.send_response(503)
            self.end_headers()
            self.wfile.write(b"flake")
            return
        if path not in _FlakyHandler.routes:
            self.send_response(404)
            self.end_headers()
            return
        body = _FlakyHandler.routes[path]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def http_server():
    _FlakyHandler.routes = {}
    _FlakyHandler.fail_first_n = {}
    _FlakyHandler.hits = {}
    server = HTTPServer(("127.0.0.1", 0), _FlakyHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, _FlakyHandler
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


# --- url_to_relative_raw_path ----------------------------------------------

def test_url_to_path_simple():
    p = url_to_relative_raw_path("https://results.eci.gov.in/ResultAcGenMay2026/partywiseresult-S22.htm")
    assert p.parts[0] == "ResultAcGenMay2026"
    assert p.parts[-1].startswith("partywiseresult-S22.htm") or "partywiseresult-S22.htm" in p.parts[-1]


def test_url_to_path_root():
    p = url_to_relative_raw_path("https://example.com/")
    assert p == Path("_root")


def test_url_to_path_with_query():
    p = url_to_relative_raw_path("https://en.wikipedia.org/w/index.php?title=Foo&oldid=123")
    last = p.parts[-1]
    # On Linux the '?' is preserved literally; on Windows it's percent-encoded.
    if os.name == "nt":
        assert "%3F" in last and "title%3DFoo" in last
    else:
        assert "?title=Foo&oldid=123" in last


def test_url_to_path_rejects_non_http():
    with pytest.raises(ValueError, match="http"):
        url_to_relative_raw_path("ftp://example.com/x")


def test_url_to_path_rejects_traversal():
    with pytest.raises(ValueError, match="traversal"):
        url_to_relative_raw_path("https://example.com/../../etc/passwd")


# --- Fetcher round-trip ----------------------------------------------------

def _fetcher(tmp_path: Path, **overrides) -> Fetcher:
    defaults = dict(
        source="testsrc",
        runtime_root=tmp_path,
        timeout_seconds=5.0,
        retry_attempts=2,
        retry_backoff_seconds=0.01,
        user_agent="yen-gov-test/0.0",
    )
    defaults.update(overrides)
    return Fetcher(**defaults)


def test_fetch_persists_to_raw_and_returns_metadata(tmp_path: Path, http_server):
    server, handler = http_server
    handler.routes["/eci/page1.htm"] = b"<html>hi</html>"
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/eci/page1.htm"

    with _fetcher(tmp_path) as fetcher:
        result = fetcher.fetch(url)

    assert result.url == url
    assert result.content == b"<html>hi</html>"
    assert result.status_code == 200
    assert result.fetched_at.tzinfo is not None
    assert result.raw_path.exists()
    assert result.raw_path.read_bytes() == b"<html>hi</html>"
    # Path should land under .runtime/raw/testsrc/eci/page1.htm
    rel = result.raw_path.relative_to(tmp_path / ".runtime" / "raw" / "testsrc")
    assert rel.parts == ("eci", "page1.htm")


def test_fetch_retries_on_transient_5xx(tmp_path: Path, http_server):
    server, handler = http_server
    handler.routes["/p"] = b"ok"
    handler.fail_first_n["/p"] = 2  # fail twice with 503, then succeed
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/p"

    with _fetcher(tmp_path, retry_attempts=3) as fetcher:
        result = fetcher.fetch(url)

    assert result.content == b"ok"
    assert handler.hits["/p"] == 3  # 2 failures + 1 success


def test_fetch_does_not_retry_on_404(tmp_path: Path, http_server):
    server, handler = http_server
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/nope"

    import httpx
    with _fetcher(tmp_path) as fetcher:
        with pytest.raises(httpx.HTTPStatusError):
            fetcher.fetch(url)
    # Single attempt — 4xx is terminal
    assert handler.hits.get("/nope", 0) == 1


def test_fetcher_rejects_bad_source_name(tmp_path: Path):
    with pytest.raises(ValueError, match="single path segment"):
        _fetcher(tmp_path, source="eci/sub")
