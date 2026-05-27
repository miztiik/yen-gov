"""PR-A5a: deterministic ``fetched_at`` in ``IcedClient.get``.

Proves the wall-clock ``datetime.now()`` was replaced by
(a) the upstream ``Last-Modified`` header when present, else
(b) the raw snapshot file's mtime — both stable across re-fetches of
byte-identical bodies. See CLAUDE.md §10 anti-pattern on
``datetime.now()`` in data-row content.
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from email.message import Message
from unittest import mock

import pytest

from yen_gov.sources.iced_common.client import IcedClient, _parse_last_modified


def _fake_response(body: bytes, *, last_modified: str | None = None):
    msg = Message()
    if last_modified is not None:
        msg["Last-Modified"] = last_modified
    fake = mock.MagicMock()
    fake.__enter__.return_value = fake
    fake.__exit__.return_value = False
    fake.read.return_value = body
    fake.headers = msg
    return fake


def test_parse_last_modified_handles_rfc7231_and_missing():
    dt = _parse_last_modified("Wed, 21 Oct 2015 07:28:00 GMT")
    assert dt == datetime(2015, 10, 21, 7, 28, 0, tzinfo=timezone.utc)
    assert _parse_last_modified(None) is None
    assert _parse_last_modified("not a date") is None


def test_get_uses_last_modified_header_when_present(tmp_path):
    client = IcedClient(runtime_root=tmp_path, polite_delay=0.0)
    body = json.dumps({"hello": "world"}).encode("utf-8")
    fake = _fake_response(body, last_modified="Wed, 21 Oct 2015 07:28:00 GMT")
    with mock.patch("urllib.request.urlopen", return_value=fake):
        resp = client.get("/some/endpoint", decrypt=False)
    assert resp.fetched_at == datetime(2015, 10, 21, 7, 28, 0, tzinfo=timezone.utc)
    assert resp.decrypted == {"hello": "world"}


def test_get_falls_back_to_raw_snapshot_mtime_when_header_absent(tmp_path):
    client = IcedClient(runtime_root=tmp_path, polite_delay=0.0)
    body = b'"plain"'
    fake = _fake_response(body, last_modified=None)
    with mock.patch("urllib.request.urlopen", return_value=fake):
        resp = client.get("/no/header", decrypt=False)
    expected = datetime.fromtimestamp(
        resp.raw_path.stat().st_mtime, tz=timezone.utc
    ).replace(microsecond=0)
    assert resp.fetched_at == expected
    # Re-fetching the same byte-identical body yields a deterministic
    # timestamp tied to the on-disk snapshot, NOT a wall-clock ``now()``.
    fake2 = _fake_response(body, last_modified=None)
    with mock.patch("urllib.request.urlopen", return_value=fake2):
        resp2 = client.get("/no/header", decrypt=False)
    assert resp2.fetched_at == datetime.fromtimestamp(
        resp2.raw_path.stat().st_mtime, tz=timezone.utc
    ).replace(microsecond=0)
