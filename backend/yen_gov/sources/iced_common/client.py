"""HTTP client for the ICED API: fetch + cache raw + decrypt + return JSON.

Keeps two responsibilities cleanly separated so future tools can pick the
slice they need:

- :class:`IcedClient` does HTTP. It fetches the raw HTTP body (a quoted
  base64 ciphertext), persists it to ``.runtime/raw/iced/v1/<path>.b64``
  for offline replay (per ADR-0003 — debug snapshot, not a cache), and
  returns the decrypted JSON via :func:`crypto.decrypt_response`.

- :class:`IcedClient.get` is the only network entry point. Polite by
  default: small inter-request sleep, exponential retry on transient
  failures, browser-style headers (the API rejects naive
  ``python-urllib`` UAs in some configs).

Why we use ``urllib`` and not ``httpx``: the existing ``iced_state_wise``
adapter (predates this module) uses ``urllib`` and proves the upstream
accepts that fingerprint when the right headers are set. We keep parity
to avoid double-vetting the WAF behaviour.
"""
from __future__ import annotations

import json
import time as _time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from .crypto import ICEDShapeError, decrypt_response


API_HOST_DEFAULT = "https://icedapi.niti.gov.in"
"""Versionless host. ``/v1`` is also valid; some endpoints live there."""

PAGE_HOST = "https://iced.niti.gov.in"
"""The dashboard the API serves. Used for ``Origin`` / ``Referer`` headers."""

CACHE_REL_DIR = ".runtime/raw/iced"
"""Per ADR-0003: raw debug snapshots, NOT a cache. Refreshed on each fetch."""


_DEFAULT_HEADERS: dict[str, str] = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": PAGE_HOST,
    "Referer": f"{PAGE_HOST}/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
    ),
}


class ICEDFetchError(RuntimeError):
    """Network-layer failure that exhausted retries."""


@dataclass(frozen=True)
class IcedResponse:
    """One decrypted ICED response + its provenance.

    ``raw_path`` is the on-disk debug snapshot of the *encrypted* HTTP
    body (a JSON-quoted base64 string). Useful when reproducing a parser
    bug offline; never published, never a contract.
    """

    url: str
    fetched_at: datetime
    decrypted: Any
    raw_body: bytes
    raw_path: Path


def _sanitize_path_for_disk(api_path: str, query: dict[str, str] | None) -> str:
    """Map an API path (+ optional query) to a POSIX-relative cache filename.

    ``"/economy-demography/key-economic-indicators/per-capita-consumption"``
    + no query → ``"economy-demography/key-economic-indicators/per-capita-consumption.b64"``.
    Query string is appended as ``__k=v__k=v`` so distinct query shapes
    don't collide.
    """
    parts = [p for p in api_path.strip("/").split("/") if p]
    base = "/".join(parts) if parts else "_root"
    if query:
        suffix = "__" + "__".join(f"{k}={v}" for k, v in sorted(query.items()))
        # Keep filenames short and filesystem-safe; no slashes leak in via values.
        suffix = suffix.replace("/", "_").replace(" ", "_")
        # Cap pathological lengths.
        if len(suffix) > 120:
            suffix = suffix[:120] + "__truncated"
        base = f"{base}{suffix}"
    return f"{base}.b64"


class IcedClient:
    """Thin per-process client over the ICED API.

    Args:
        host: API host root, default ``https://icedapi.niti.gov.in``. Pass
            ``"https://icedapi.niti.gov.in/v1"`` for endpoints under v1.
        runtime_root: parent of ``.runtime/``. Defaults to current working
            directory (the repo root when invoked from the project root).
        retries: max attempts per fetch.
        backoff_seconds: initial back-off; multiplied by attempt number on
            each retry (linear, not exponential — ICED responses are small
            and the API is unmetered).
        polite_delay: minimum seconds to sleep between successive ``get()``
            calls on the same client. Set to 0.0 for tests.
        extra_headers: merged on top of the browser-style defaults.
    """

    def __init__(
        self,
        *,
        host: str = API_HOST_DEFAULT,
        runtime_root: Path | None = None,
        retries: int = 3,
        backoff_seconds: float = 1.5,
        polite_delay: float = 0.5,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self._host = host.rstrip("/")
        self._raw_dir = (runtime_root or Path.cwd()) / CACHE_REL_DIR
        self._retries = retries
        self._backoff = backoff_seconds
        self._polite_delay = polite_delay
        self._headers = dict(_DEFAULT_HEADERS)
        if extra_headers:
            self._headers.update(extra_headers)
        self._last_call_ts: float = 0.0

    # ------------------------------------------------------------------ get
    def get(
        self,
        api_path: str,
        *,
        params: dict[str, str] | None = None,
        timeout: float = 45.0,
        decrypt: bool = True,
    ) -> IcedResponse:
        """Fetch + (optionally decrypt) one endpoint. Returns :class:`IcedResponse`.

        ``api_path`` is the API-relative path (must start with ``/``).
        ``params`` is added as a query string. The raw HTTP body is
        always written to ``.runtime/raw/iced/v1/<path>.b64`` (overwriting
        any prior copy).

        Set ``decrypt=False`` for the small set of endpoints that return
        plain JSON (no AES envelope) — observed on a handful of v1
        endpoints such as ``/v1/capacity-metatable-data`` and
        ``/v1/retired-capacity-plants``. The raw body is parsed as JSON
        directly.
        """
        if not api_path.startswith("/"):
            raise ValueError(f"api_path must start with '/', got {api_path!r}")
        self._respect_polite_delay()

        if params:
            qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
            url = f"{self._host}{api_path}?{qs}"
        else:
            url = f"{self._host}{api_path}"

        body = self._fetch_with_retry(url, timeout=timeout)
        fetched_at = datetime.now(timezone.utc)

        # Persist raw (encrypted-or-plain) body for offline replay.
        rel_disk = _sanitize_path_for_disk(api_path, params)
        raw_path = self._raw_dir / rel_disk
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(body)

        try:
            if decrypt:
                decrypted = decrypt_response(body)
            else:
                decrypted = json.loads(body.decode("utf-8"))
        except (ICEDShapeError, json.JSONDecodeError) as exc:
            raise ICEDShapeError(
                f"GET {url!r} returned a body that did not "
                f"{'decrypt' if decrypt else 'parse as JSON'}: {exc}. "
                f"Raw body persisted at {self._rel(raw_path)} for inspection."
            ) from exc

        return IcedResponse(
            url=url,
            fetched_at=fetched_at,
            decrypted=decrypted,
            raw_body=body,
            raw_path=raw_path,
        )

    # ------------------------------------------------------------- internals
    def _fetch_with_retry(self, url: str, *, timeout: float) -> bytes:
        last_err: Exception | None = None
        for attempt in range(self._retries):
            req = urllib.request.Request(url, headers=self._headers)
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    self._last_call_ts = _time.time()
                    return resp.read()
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
                last_err = exc
                if attempt + 1 < self._retries:
                    _time.sleep(self._backoff * (attempt + 1))
                    continue
        raise ICEDFetchError(
            f"GET {url!r} failed after {self._retries} attempts: {last_err!r}"
        )

    def _respect_polite_delay(self) -> None:
        if self._polite_delay <= 0 or self._last_call_ts == 0.0:
            return
        elapsed = _time.time() - self._last_call_ts
        if elapsed < self._polite_delay:
            _time.sleep(self._polite_delay - elapsed)

    @staticmethod
    def _rel(p: Path) -> str:
        """POSIX-relative-ish display string for log messages (CLAUDE.md path rules)."""
        try:
            return PurePosixPath(p.relative_to(Path.cwd())).as_posix()
        except ValueError:
            return PurePosixPath(p).as_posix()
