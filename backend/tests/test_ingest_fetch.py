"""Fetch-engine unit tests (Row 5): dedup, the 3-try retry, operator_staged.

No live network: the httpx path is driven through ``httpx.MockTransport`` and the
operator-staged path reads ``tmp_path`` fixtures (test-policy carve-out a). The
retry ``sleeper`` is a no-op so the suite never actually sleeps.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from yen_gov.canonical.ingest.fetch import (
    CACHE_DIR_REL,
    CacheKey,
    FetchError,
    FetchedCache,
    dedup_cache_units,
    fetch_unit,
)


def _noop_sleep(_attempt: int) -> None:
    return None


def _auto_key(year: int = 2020) -> CacheKey:
    return CacheKey(
        adapter_slug="demo-src",
        unit_id=f"demo-src:demo:{year}",
        year=year,
        staging_filename=f"demo-{year}.csv",
        url=f"https://example.test/demo-{year}.csv",
        mode="auto",
    )


def _staged_key(year: int = 2020) -> CacheKey:
    return CacheKey(
        adapter_slug="demo-src",
        unit_id=f"demo-src:demo:{year}",
        year=year,
        staging_filename=f"demo-{year}.csv",
        url=f"https://example.test/demo-{year}.csv",
        mode="operator_staged",
    )


def _counting_transport(statuses: list[int], body: bytes = b"PAYLOAD"):
    """A MockTransport returning ``statuses[i]`` on call i; counts the calls."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        i = calls["n"]
        calls["n"] += 1
        status = statuses[min(i, len(statuses) - 1)]
        content = body if 200 <= status < 300 else b"upstream error"
        return httpx.Response(status, content=content)

    return httpx.MockTransport(handler), calls


# --------------------------------------------------------------------------- #
# dedup: two indicators sharing a unit collapse to one
# --------------------------------------------------------------------------- #


class TestDedup:
    def test_equal_keys_collapse_preserving_order(self):
        k2019 = _staged_key(2019)
        k2020 = _staged_key(2020)
        # the same unit handed back for two indicators is the SAME key.
        assert dedup_cache_units([k2019, k2019, k2020, k2020]) == [k2019, k2020]

    def test_two_indicators_sharing_a_unit_are_equal(self):
        # an indicator-agnostic unit_id is what makes the two indicators' keys
        # equal, so the cache fetches the shared per-year file once.
        a = _staged_key(2021)
        b = _staged_key(2021)
        assert a == b
        assert hash(a) == hash(b)


# --------------------------------------------------------------------------- #
# operator_staged: the no-network path
# --------------------------------------------------------------------------- #


class TestOperatorStaged:
    def test_reads_the_staged_payload(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "demo-2020.csv").write_bytes(b"state,v\nKerala,1\n")
        fetched = fetch_unit(
            _staged_key(2020),
            cache_dir=tmp_path / Path(CACHE_DIR_REL),
            staging_dir=staging,
        )
        assert fetched.raw_bytes == b"state,v\nKerala,1\n"
        assert fetched.cache_key.year == 2020

    def test_missing_staged_file_raises(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        with pytest.raises(FileNotFoundError):
            fetch_unit(
                _staged_key(2020),
                cache_dir=tmp_path / Path(CACHE_DIR_REL),
                staging_dir=staging,
            )

    def test_no_staging_dir_raises(self, tmp_path):
        with pytest.raises(FetchError):
            fetch_unit(
                _staged_key(2020),
                cache_dir=tmp_path / Path(CACHE_DIR_REL),
                staging_dir=None,
            )


# --------------------------------------------------------------------------- #
# auto: bounded 3-try retry over httpx (no tenacity)
# --------------------------------------------------------------------------- #


class TestHttpxRetry:
    def test_succeeds_on_third_attempt(self, tmp_path):
        transport, calls = _counting_transport([503, 503, 200])
        fetched = fetch_unit(
            _auto_key(2020),
            cache_dir=tmp_path / Path(CACHE_DIR_REL),
            transport=transport,
            sleeper=_noop_sleep,
        )
        assert calls["n"] == 3  # tried thrice, third succeeded
        assert fetched.raw_bytes == b"PAYLOAD"

    def test_exhausts_three_attempts_then_raises(self, tmp_path):
        transport, calls = _counting_transport([503])  # always 503
        with pytest.raises(FetchError):
            fetch_unit(
                _auto_key(2020),
                cache_dir=tmp_path / Path(CACHE_DIR_REL),
                staging_dir=None,
                transport=transport,
                sleeper=_noop_sleep,
            )
        assert calls["n"] == 3  # bounded at exactly 3 (no infinite retry)

    def test_transport_error_is_retried(self, tmp_path):
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            raise httpx.ConnectError("simulated TLS/connection failure")

        with pytest.raises(FetchError):
            fetch_unit(
                _auto_key(2020),
                cache_dir=tmp_path / Path(CACHE_DIR_REL),
                staging_dir=None,
                transport=httpx.MockTransport(handler),
                sleeper=_noop_sleep,
            )
        assert calls["n"] == 3  # the except httpx.HTTPError branch retried

    def test_falls_back_to_staged_on_exhaustion(self, tmp_path):
        # flaky-TLS source: the network fails but the operator staged a copy.
        staging = tmp_path / "staging"
        staging.mkdir()
        (staging / "demo-2020.csv").write_bytes(b"STAGED")
        transport, _ = _counting_transport([503])
        fetched = fetch_unit(
            _auto_key(2020),
            cache_dir=tmp_path / Path(CACHE_DIR_REL),
            staging_dir=staging,
            transport=transport,
            sleeper=_noop_sleep,
        )
        assert fetched.raw_bytes == b"STAGED"

    def test_success_writes_raw_bytes_to_gitignored_cache(self, tmp_path):
        transport, _ = _counting_transport([200])
        fetched = fetch_unit(
            _auto_key(2020),
            cache_dir=tmp_path / Path(CACHE_DIR_REL),
            transport=transport,
            sleeper=_noop_sleep,
        )
        cache_file = tmp_path / Path(CACHE_DIR_REL) / "demo-src" / "demo-2020.csv"
        assert cache_file.is_file()
        assert cache_file.read_bytes() == b"PAYLOAD"
        assert fetched.raw_path == cache_file
        # the cache lives under .runtime/ (gitignored), never the committed tree.
        assert ".runtime/cache/ingest" in cache_file.as_posix()


# --------------------------------------------------------------------------- #
# FetchedCache: each distinct unit is fetched once
# --------------------------------------------------------------------------- #


class TestFetchedCache:
    def test_repeated_key_fetches_once(self, tmp_path):
        transport, calls = _counting_transport([200])
        cache = FetchedCache(
            repo_root=tmp_path,
            staging_dir=None,
            transport=transport,
            sleeper=_noop_sleep,
        )
        key = _auto_key(2020)
        first = cache.get_or_fetch(key)
        second = cache.get_or_fetch(key)
        assert first is second  # cache hit, not re-fetched
        assert cache.fetch_count == 1
        assert calls["n"] == 1

    def test_distinct_keys_each_fetch(self, tmp_path):
        transport, calls = _counting_transport([200])
        cache = FetchedCache(
            repo_root=tmp_path,
            staging_dir=None,
            transport=transport,
            sleeper=_noop_sleep,
        )
        cache.get_or_fetch(_auto_key(2019))
        cache.get_or_fetch(_auto_key(2020))
        assert cache.fetch_count == 2
        assert calls["n"] == 2
