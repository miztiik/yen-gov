"""Automated Fetch + the cache-unit primitives (Row 5, plan D1 + section 3).

This is the source-agnostic Fetch engine the orchestrator drives. It does two
jobs and nothing else:

* **Fetch one cache unit.** :func:`fetch_unit` pulls a single upstream artifact
  with a bounded 3-try retry over ``httpx`` (no ``tenacity`` -- it was deleted
  in the rip; the retry is a small hand-rolled loop). A ``fetch_mode`` of
  ``"operator_staged"`` reads a locally-staged raw payload instead of the
  network -- the flaky-TLS fallback the plan mandates, and the path tests use so
  no test ever touches the live network (test-policy carve-out a).
* **Dedup cache units.** :func:`cache_units_for`-style adapters return a TUPLE of
  :class:`CacheKey` (an indicator may span >1 unit). :class:`FetchedCache`
  fetches each DISTINCT key exactly once, so two indicators that share one unit
  fetch once (the Row-5 dedup gate).

Design rulings (Gregor = contracts, Fowler = craft), baked here so a later row
does not re-litigate them:

* **Raw bytes land in ``.runtime/cache/ingest/`` (gitignored), not ``_meadow/``.**
  The delta CONTRACT is the committed checkpoint's ``raw_sha256`` (Row 2); the
  raw bytes are re-fetched and re-hashed every run, so this cache is a
  within-run claim-check that need not outlive a run. CLAUDE.md section 2 ("state
  that outlives a run belongs in datasets//config//docs/") + the retiring
  ``_meadow`` tier both route the cache to ``.runtime/``; Row 12's ``clean``
  (which refuses targets outside ``.runtime/``) then sweeps it for free.
* **httpx is imported LAZILY** (function-local in the auto path). Importing
  :class:`CacheKey` / :class:`FetchedUnit` / :func:`dedup_cache_units` must not
  pull ``httpx`` into ``ingest --help`` or an ``operator_staged`` run -- only an
  actual network fetch loads it. Mirrors the Row-4 openpyxl lazy-import ethos.
* **CacheKey is opaque for dedup but carries ``year``.** The orchestrator dedups
  purely by ``CacheKey`` equality (it never introspects the other fields); it
  DOES read ``year`` because the committed checkpoint is year-addressed
  (ingest-state.schema.json: "year (the natural cache unit of every single-series
  source)").
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from yen_gov.core.events import (
    FetchCompleted,
    FetchFailed,
    FetchRetried,
    FetchStarted,
    emit,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterable

    import httpx

    from yen_gov.core.logging import StructuredLogger

#: How a cache unit is pulled. ``auto`` = httpx with a bounded retry;
#: ``operator_staged`` = read a locally-staged raw payload (flaky-TLS sources +
#: tests). ``auto`` falls back to a staged payload if the network exhausts its
#: retries and a staged file exists.
FetchMode = Literal["auto", "operator_staged"]

#: Repo-relative home of the gitignored raw-bytes cache (POSIX, CLAUDE.md sec 2).
CACHE_DIR_REL = ".runtime/cache/ingest"

#: Bounded retry budget for an ``auto`` fetch (no tenacity; hand-rolled loop).
DEFAULT_MAX_ATTEMPTS = 3


class FetchError(RuntimeError):
    """An ``auto`` fetch exhausted its retries with no staged fallback."""


class CacheKey(BaseModel):
    """One fetchable cache unit -- the natural Fetch + delta grain.

    Opaque to the orchestrator's dedup (it compares whole-:class:`CacheKey`
    equality and passes the key back unchanged), but it carries ``year`` because
    the committed year-checkpoint is year-addressed. Two indicators that draw
    from the SAME upstream artifact for the same year return EQUAL keys (every
    field identical), so :class:`FetchedCache` fetches that artifact once.

    Frozen so it is hashable (used as a dict key in :class:`FetchedCache`) and
    cannot drift after an adapter hands it to the engine.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter_slug: str = Field(pattern=r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")
    unit_id: str = Field(min_length=1)
    year: int = Field(ge=1850, le=2100)
    staging_filename: str = Field(min_length=1)
    url: str = ""
    mode: FetchMode = "operator_staged"


class FetchedUnit(BaseModel):
    """The result of fetching one :class:`CacheKey` -- a claim-check.

    ``raw_bytes`` is the payload the delta engine hashes (Row 2
    ``hash_payload``) and the adapter slices per indicator; ``raw_path`` points
    at where the bytes live on disk (the gitignored cache for an ``auto`` fetch,
    or the operator-staged file for ``operator_staged``).
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    cache_key: CacheKey
    raw_bytes: bytes
    raw_path: Path | None = None


def dedup_cache_units(cache_keys: "Iterable[CacheKey]") -> list[CacheKey]:
    """Return ``cache_keys`` with duplicates removed, first-seen order kept.

    The pure heart of the dedup gate: two indicators whose ``cache_units_for``
    overlap collapse to one unit here, so the caller fetches each distinct unit
    once. Order-preserving so a run's fetch order is deterministic.
    """
    seen: set[CacheKey] = set()
    out: list[CacheKey] = []
    for key in cache_keys:
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _cache_path(cache_dir: Path, cache_key: CacheKey) -> Path:
    """Return the on-disk cache path for an ``auto``-fetched unit's raw bytes."""
    return cache_dir / cache_key.adapter_slug / cache_key.staging_filename


def _read_operator_staged(
    cache_key: CacheKey,
    *,
    staging_dir: Path | None,
    logger: "StructuredLogger | None",
    repo_root: Path | None,
) -> FetchedUnit:
    """Read a locally-staged raw payload (the no-network path)."""
    if staging_dir is None:
        raise FetchError(
            f"operator_staged fetch for {cache_key.staging_filename!r} needs a "
            "staging dir (pass --staging-dir / config.staging_dir)"
        )
    path = staging_dir / cache_key.staging_filename
    if not path.is_file():
        raise FileNotFoundError(
            f"{cache_key.adapter_slug}: staged payload not found at "
            f"{path.name} under the staging dir (no network fetch for this unit)"
        )
    raw = path.read_bytes()
    if logger is not None:
        emit(
            logger,
            FetchStarted(url=cache_key.url, source="operator_staged"),
            repo_root=repo_root,
            stage="fetch",
        )
        # raw_path is omitted from the event: a staged file can legitimately sit
        # outside repo_root, and the path-emit seam fails fast on an escape. The
        # byte count + url carry the signal; FetchedUnit still keeps the path.
        emit(
            logger,
            FetchCompleted(url=cache_key.url, status_code=0, bytes=len(raw)),
            repo_root=repo_root,
            stage="fetch",
        )
    return FetchedUnit(cache_key=cache_key, raw_bytes=raw, raw_path=path)


def fetch_unit(
    cache_key: CacheKey,
    *,
    cache_dir: Path,
    staging_dir: Path | None = None,
    logger: "StructuredLogger | None" = None,
    repo_root: Path | None = None,
    transport: "httpx.BaseTransport | None" = None,
    sleeper: Callable[[int], None] | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> FetchedUnit:
    """Fetch one cache unit's raw bytes; return a :class:`FetchedUnit`.

    ``operator_staged`` reads ``staging_dir / cache_key.staging_filename``.
    ``auto`` GETs ``cache_key.url`` with a bounded ``max_attempts`` retry loop
    (a 2xx returns the body, written to the gitignored cache; a non-2xx or an
    ``httpx`` error retries up to the budget). On exhaustion it falls back to a
    staged payload when one exists (flaky-TLS sources), else raises
    :class:`FetchError`.

    Args:
        cache_key: the unit to fetch.
        cache_dir: gitignored cache root (``<repo>/.runtime/cache/ingest``); the
            raw bytes of an ``auto`` fetch are written under it.
        staging_dir: operator-staged-file dir (required for ``operator_staged``;
            the fallback source for ``auto``).
        logger: optional stage-tagged logger; fetch lifecycle events are emitted
            through it when present.
        repo_root: repo root, forwarded to the path-emit seam so a logged path
            is repo-relative POSIX.
        transport: optional ``httpx`` transport (tests inject a ``MockTransport``
            so no live network is hit).
        sleeper: optional ``sleeper(attempt)`` back-off hook (tests pass a no-op;
            default is a short bounded sleep).
        max_attempts: retry budget for ``auto`` (default 3).
    """
    if cache_key.mode == "operator_staged":
        return _read_operator_staged(
            cache_key, staging_dir=staging_dir, logger=logger, repo_root=repo_root
        )

    # --- auto: httpx with a bounded hand-rolled retry (no tenacity) ---
    import httpx  # lazy: keep CacheKey/operator_staged/--help free of httpx

    sleeper = sleeper if sleeper is not None else _default_sleeper
    if logger is not None:
        emit(
            logger,
            FetchStarted(url=cache_key.url, source=cache_key.adapter_slug),
            repo_root=repo_root,
            stage="fetch",
        )

    last_error = ""
    client_kwargs: dict[str, object] = {"timeout": 30.0}
    if transport is not None:
        client_kwargs["transport"] = transport
    with httpx.Client(**client_kwargs) as client:  # type: ignore[arg-type]
        for attempt in range(1, max_attempts + 1):
            try:
                response = client.get(cache_key.url)
                if 200 <= response.status_code < 300:
                    raw = response.content
                    cache_path = _cache_path(cache_dir, cache_key)
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_bytes(raw)
                    if logger is not None:
                        emit(
                            logger,
                            FetchCompleted(
                                url=cache_key.url,
                                status_code=response.status_code,
                                raw_path=cache_path,
                                bytes=len(raw),
                            ),
                            repo_root=repo_root,
                            stage="fetch",
                        )
                    return FetchedUnit(
                        cache_key=cache_key, raw_bytes=raw, raw_path=cache_path
                    )
                last_error = f"HTTP {response.status_code}"
            except httpx.HTTPError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            if attempt < max_attempts:
                if logger is not None:
                    emit(
                        logger,
                        FetchRetried(
                            url=cache_key.url, attempt=attempt, error=last_error
                        ),
                        repo_root=repo_root,
                        stage="fetch",
                    )
                sleeper(attempt)

    if logger is not None:
        emit(
            logger,
            FetchFailed(url=cache_key.url, error=last_error),
            repo_root=repo_root,
            stage="fetch",
        )
    if staging_dir is not None and (staging_dir / cache_key.staging_filename).is_file():
        # flaky-TLS fallback: the network failed but the operator staged a copy.
        return _read_operator_staged(
            cache_key, staging_dir=staging_dir, logger=logger, repo_root=repo_root
        )
    raise FetchError(
        f"fetch failed for {cache_key.url!r} after {max_attempts} attempts "
        f"({last_error}); no staged fallback for {cache_key.staging_filename!r}"
    )


def _default_sleeper(attempt: int) -> None:
    """Short bounded linear back-off between auto-fetch retries."""
    import time

    time.sleep(min(attempt, DEFAULT_MAX_ATTEMPTS) * 0.5)


class FetchedCache:
    """Run-scoped cache that fetches each distinct :class:`CacheKey` once.

    Lives for the duration of one orchestrate call. Two indicators (or two
    years' loops) that resolve to the same cache unit hit the cache the second
    time, so the underlying artifact is fetched once -- the Row-5 dedup gate.
    ``fetch_count`` records the number of REAL fetches (cache misses) so a test
    can assert "two indicators sharing a unit fetch once".
    """

    def __init__(
        self,
        *,
        repo_root: Path,
        staging_dir: Path | None,
        logger: "StructuredLogger | None" = None,
        transport: "httpx.BaseTransport | None" = None,
        sleeper: Callable[[int], None] | None = None,
    ) -> None:
        self._cache: dict[CacheKey, FetchedUnit] = {}
        self._repo_root = repo_root
        self._staging_dir = staging_dir
        self._cache_dir = repo_root / Path(CACHE_DIR_REL)
        self._logger = logger
        self._transport = transport
        self._sleeper = sleeper
        self.fetch_count = 0

    def get_or_fetch(self, cache_key: CacheKey) -> FetchedUnit:
        """Return the cached unit for ``cache_key`` or fetch + cache it once.

        The FETCH-stage primitive. Beyond the in-memory run-scoped dedup it
        LANDS the raw payload on disk at the claim-check path
        (``.runtime/cache/ingest/<adapter_slug>/<staging_filename>``) for EVERY
        fetch mode -- an ``auto`` fetch already writes there and an
        ``operator_staged`` read is mirrored there too -- so a later
        ``--from enrich`` stage window (:meth:`get_cached`) can re-enrich +
        publish from that payload WITHOUT re-fetching. The on-disk claim-check
        is the FETCH -> ENRICH stage boundary (plan section 4); Row 12's
        ``clean`` sweeps it (it lives under ``.runtime/``).
        """
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        fetched = fetch_unit(
            cache_key,
            cache_dir=self._cache_dir,
            staging_dir=self._staging_dir,
            logger=self._logger,
            repo_root=self._repo_root,
            transport=self._transport,
            sleeper=self._sleeper,
        )
        self._persist(cache_key, fetched.raw_bytes)
        self._cache[cache_key] = fetched
        self.fetch_count += 1
        return fetched

    def get_cached(self, cache_key: CacheKey) -> FetchedUnit:
        """Return the claim-check a prior FETCH landed, or FAIL LOUD.

        The ENRICH-from-cache primitive for the ``--from enrich`` stage window:
        it reads the raw bytes a prior FETCH persisted at the claim-check path
        and NEVER touches the network or the staging dir. If no prior fetch
        landed the unit it raises :class:`FetchError` ("no cached raw ...; run
        fetch first") rather than silently re-fetching -- skipping FETCH means
        the operator asserts the cache is already warm, so a cold cache is an
        error, not a fallback.
        """
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        cache_path = _cache_path(self._cache_dir, cache_key)
        if not cache_path.is_file():
            rel = (
                f"{CACHE_DIR_REL}/{cache_key.adapter_slug}/"
                f"{cache_key.staging_filename}"
            )
            raise FetchError(
                f"no cached raw for {cache_key.unit_id!r}; run fetch first "
                f"(expected {rel})"
            )
        fetched = FetchedUnit(
            cache_key=cache_key,
            raw_bytes=cache_path.read_bytes(),
            raw_path=cache_path,
        )
        self._cache[cache_key] = fetched
        return fetched

    def _persist(self, cache_key: CacheKey, raw: bytes) -> None:
        """Mirror a fetched unit's raw bytes to the claim-check cache path.

        Idempotent: an ``auto`` ``fetch_unit`` already wrote this exact path, so
        the re-write is a no-op-equivalent; an ``operator_staged`` read did not,
        so this is what lands it. Either way FETCH leaves a uniform claim-check
        the ENRICH-from-cache window reads.
        """
        cache_path = _cache_path(self._cache_dir, cache_key)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(raw)


__all__ = [
    "CACHE_DIR_REL",
    "CacheKey",
    "FetchError",
    "FetchMode",
    "FetchedCache",
    "FetchedUnit",
    "dedup_cache_units",
    "fetch_unit",
]
