"""HTTP fetcher: httpx + tenacity, persists raw to .runtime/raw/<source>/...

Per ADR-0003 there is NO cache. Every Fetcher.fetch hits the network. The on-disk
copy at .runtime/raw/ is a debugging artifact (so a parser bug can be diagnosed
without re-fetching), not a cache. Re-fetches overwrite.

Per docs/architecture/backend/core.md (intermediate raw-file path derivation) the on-disk path is
derived from the URL's path component, not
its hostname or a hash, so filenames are human-readable and grep-able.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, urlsplit

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


@dataclass(frozen=True)
class FetchResult:
    """Bytes fetched + when. fetched_at feeds straight into Source for provenance."""

    url: str
    content: bytes
    fetched_at: datetime
    raw_path: Path  # where the bytes were persisted under .runtime/raw/<source>/...
    status_code: int


class Fetcher:
    """One Fetcher per pipeline run, configured from processing.json's fetch block.

    Args:
        source: logical source name (e.g. "eci", "wikipedia"). Determines the
            top-level directory under .runtime/raw/. NOT inferred from URL host
            (see docs/architecture/backend/core.md).
        runtime_root: parent of .runtime/. Defaults to repo root (cwd).
        timeout_seconds, retry_attempts, retry_backoff_seconds, user_agent:
            mirror the fields under fetch in config/processing.json.
    """

    def __init__(
        self,
        *,
        source: str,
        runtime_root: Path,
        timeout_seconds: float,
        retry_attempts: int,
        retry_backoff_seconds: float,
        user_agent: str,
    ) -> None:
        if not source or "/" in source or "\\" in source:
            raise ValueError(f"source must be a single path segment, got {source!r}")
        self._source = source
        self._raw_dir = runtime_root / ".runtime" / "raw" / source
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout_seconds,
            follow_redirects=True,
        )
        self._retry_attempts = retry_attempts
        self._retry_backoff = retry_backoff_seconds

    def __enter__(self) -> Fetcher:
        return self

    def __exit__(self, *exc: Any) -> None:
        self._client.close()

    def close(self) -> None:
        self._client.close()

    def fetch(self, url: str) -> FetchResult:
        response = self._fetch_with_retry(url)
        response.raise_for_status()
        fetched_at = datetime.now(timezone.utc).replace(microsecond=0)
        raw_path = self._persist(url, response.content)
        return FetchResult(
            url=url,
            content=response.content,
            fetched_at=fetched_at,
            raw_path=raw_path,
            status_code=response.status_code,
        )

    def _fetch_with_retry(self, url: str) -> httpx.Response:
        retrying = Retrying(
            stop=stop_after_attempt(max(1, self._retry_attempts + 1)),
            wait=wait_exponential(multiplier=self._retry_backoff, max=30),
            retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
            reraise=True,
        )
        for attempt in retrying:
            with attempt:
                response = self._client.get(url)
                # Treat 5xx as retry-worthy, 4xx as terminal.
                if 500 <= response.status_code < 600:
                    response.raise_for_status()
                return response
        raise RuntimeError("unreachable")  # pragma: no cover

    def _persist(self, url: str, content: bytes) -> Path:
        rel = url_to_relative_raw_path(url)
        target = self._raw_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target


def url_to_relative_raw_path(url: str) -> Path:
    """Derive the on-disk relative path for a fetched URL per docs/architecture/backend/core.md.

    Returns a Path relative to .runtime/raw/<source>/. Caller joins.
    Rejects path-traversal attempts.
    """
    parts = urlsplit(url)
    if not parts.scheme.startswith("http"):
        raise ValueError(f"only http(s) URLs are supported, got {url!r}")
    path = parts.path.lstrip("/")
    if not path:
        path = "_root"
    if parts.query:
        path = f"{path}?{parts.query}"

    posix = PurePosixPath(path)
    if any(p == ".." for p in posix.parts):
        raise ValueError(f"path traversal in URL not allowed: {url!r}")

    # Percent-encode reserved chars per platform. On Windows '?' '*' ':' etc.
    # are illegal in filenames; quote them defensively. The result is still
    # round-trippable to a URL via urllib.parse.unquote.
    import os
    if os.name == "nt":
        encoded_parts = [quote(p, safe="") for p in posix.parts]
        return Path(*encoded_parts) if encoded_parts else Path()
    return Path(*posix.parts)
