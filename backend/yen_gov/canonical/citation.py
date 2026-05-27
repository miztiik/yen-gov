"""Citation-ledger helpers for the canonical sources table.

Single source of truth for:

- ``derive_source_id(producer, title, vintage)`` — the deterministic 12-char
  ``src-<hash>`` ID used everywhere a ``SourceRow`` is constructed.
- ``render_citation(producer, title, vintage, citation_full=None)`` —
  default human-readable citation when the row has no ``citation_full``.
- ``verification_method_rank(method)`` — trust ordering used by Compare /
  per-AC viewers when two sources disagree.
- Enum constants (``VERIFICATION_METHODS``, ``CONFIDENCE_TIERS``, ``LICENSES``)
  that mirror the schema's locked enums so callers don't drift.

This module is stdlib-only. No third-party imports — keeps the citation
contract independent of pydantic / duckdb / httpx and importable from
adapters, the writer, tests, and tooling alike.

Per ADR-0032 (sources v2.0 citation ledger) — see
``docs/architecture/decisions/0032-sources-citation-ledger.md`` for the
rejected-design archive (notably: NOT a UUID, NOT a content-hash, NOT an
autoincrement integer — must be deterministic across cold starts so the
same citation triple yields the same ID anywhere in the codebase).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final, Literal

VerificationMethod = Literal["live-fetch", "archived-snapshot", "transcribed", "editorial"]
ConfidenceTier = Literal["gold", "silver", "bronze"]
License = Literal["OGL-IN-1.0", "CC-BY-4.0", "CC0-1.0", "public-domain", "unknown-public", "internal"]

# Enum-mirror tuples — kept in declaration order so callers can index them
# when (rare) ordering-sensitive display logic is needed. The Literal types
# above are the type-checked surface; these tuples are the runtime surface.
VERIFICATION_METHODS: Final[tuple[VerificationMethod, ...]] = (
    "live-fetch",
    "archived-snapshot",
    "transcribed",
    "editorial",
)
CONFIDENCE_TIERS: Final[tuple[ConfidenceTier, ...]] = ("gold", "silver", "bronze")
LICENSES: Final[tuple[License, ...]] = (
    "OGL-IN-1.0",
    "CC-BY-4.0",
    "CC0-1.0",
    "public-domain",
    "unknown-public",
    "internal",
)

# Trust ordering for verification_method. Higher = stronger evidence that
# yen-gov holds the upstream bytes faithfully. Used by Compare / per-AC
# viewers and reconciliation tooling when two sources disagree on a value:
# the higher-ranked source wins by default, with the lower-ranked source
# surfaced as a caveat (NOT silently discarded). 4-3-2-1 instead of
# 1-2-3-4 so the rank order matches the schema declaration order while
# still being intuitive ("higher number = more trustworthy").
_VERIFICATION_METHOD_RANK: Final[dict[VerificationMethod, int]] = {
    "live-fetch": 4,
    "archived-snapshot": 3,
    "transcribed": 2,
    "editorial": 1,
}


def derive_source_id(producer: str, title: str, vintage: str) -> str:
    """Deterministic 12-char ``src-`` id from the citation identity triple.

    Identity = ``(producer, title, vintage)`` joined by ``|``. The same
    triple anywhere in the codebase (adapter, test, tooling) yields the
    same ID — that is the citation-ledger invariant (ADR-0032): two
    observations that cite the same upstream report carry the same
    ``source_id``, regardless of which fetch session populated them.

    ``vintage`` is the strongest period anchor available per ADR-0042 —
    publisher edition when the upstream publishes one (RBI Handbook
    ``"2024-25"``, NFHS ``"NFHS-5"``), operator snapshot window when the
    publisher publishes no edition tag (ICED API ``"2024-25"`` meaning
    "the operator snapshotted this in FY 2024-25"). Empty ``vintage`` is
    accepted by the signature but rejected by the schema (v3.0 sets
    ``minLength: 1``); callers MUST supply a non-empty period label so
    the meadow-tier path discipline of ADR-0041 §non-negotiable #4 holds.
    Triples that differ only in whitespace produce distinct IDs by
    design; callers MUST pass the publisher's verbatim strings (no
    normalisation).

    Returns: ``"src-" + sha256(triple).hexdigest()[:12]``. 12 chars =
    48 bits = ~10^14 collision floor across the whole table, which sits
    comfortably above the corpus ceiling (low thousands of citations
    even at full coverage).
    """
    if not producer:
        raise ValueError("producer must be non-empty")
    if not title:
        raise ValueError("title must be non-empty")
    # vintage is required-string with minLength=1 per schema v3.0 (ADR-0042);
    # the signature still accepts empty strings (for tests that construct
    # rejected fixtures), but production callers must supply the publisher
    # edition or the operator snapshot window so the meadow-path FK closes.
    payload = f"{producer}|{title}|{vintage}".encode("utf-8")
    return "src-" + hashlib.sha256(payload).hexdigest()[:12]


def lookup_source_id(
    producer: str,
    title: str,
    vintage: str,
    *,
    sources_path: Path,
) -> str:
    """Data-driven counterpart to :func:`derive_source_id` (PR-A6).

    Reads ``sources_path`` (a ``datasets/taxonomy/sources.parquet``-shaped
    parquet) and returns the ``source_id`` of the row whose
    ``(producer, title, vintage)`` triple matches the arguments exactly.

    Use this from observation-stamping call sites that want to verify
    against the citation ledger rather than re-hash from hand-typed
    triples. ``derive_source_id`` remains the writer-side primitive for
    seed modules that populate the ledger itself (chicken-and-egg
    bootstrap); ``lookup_source_id`` is for downstream readers.

    Raises:
        FileNotFoundError: ``sources_path`` does not exist.
        LookupError: no row in the parquet matches the triple. The
            error message lists the triple so the operator can either
            (a) fix the hand-typed value in the adapter, or (b) add the
            missing row to the sources seed.

    duckdb is imported lazily so the module-level import surface stays
    stdlib-only (per the module docstring's contract — keeps
    ``citation`` importable from any layer without third-party deps).
    """
    if not producer:
        raise ValueError("producer must be non-empty")
    if not title:
        raise ValueError("title must be non-empty")
    if not vintage:
        raise ValueError("vintage must be non-empty")
    if not sources_path.exists():
        raise FileNotFoundError(
            f"sources parquet not found at {sources_path}; "
            "run the sources seed first"
        )
    import duckdb  # lazy: preserve module-level stdlib-only surface

    con = duckdb.connect(":memory:")
    try:
        row = con.execute(
            "SELECT source_id FROM read_parquet(?) "
            "WHERE producer = ? AND title = ? AND vintage = ?",
            [str(sources_path), producer, title, vintage],
        ).fetchone()
    finally:
        con.close()
    if row is None:
        raise LookupError(
            f"no sources row for (producer={producer!r}, "
            f"title={title!r}, vintage={vintage!r}) in {sources_path}"
        )
    return row[0]


def render_citation(
    producer: str,
    title: str,
    vintage: str,
    *,
    citation_full: str | None = None,
) -> str:
    """Default citation rendering for a citation-ledger row.

    Precedence: an explicit ``citation_full`` (from the SourceRow) always
    wins — adapters and hand-authored rows that carry a bibliographically
    precise citation should set ``citation_full`` and not depend on this
    helper. When ``citation_full`` is ``None`` (the common case), this
    composes a short human-readable form:

      - With vintage: ``"<producer>. <title> (<vintage>)."``
      - Without vintage: ``"<producer>. <title>."`` (legacy v2.0 path —
        v3.0 ``minLength: 1`` makes this branch unreachable from valid
        SourceRow instances, but the fallback survives for backstop and
        for tests that construct rejected fixtures).

    Used by the renderer when a citizen-facing source chip needs a
    fallback string. The citation chip is supposed to ALWAYS resolve to
    something readable — no row should ever surface as just a bare
    ``source_id``.
    """
    if citation_full is not None and citation_full.strip():
        return citation_full
    if vintage:
        return f"{producer}. {title} ({vintage})."
    return f"{producer}. {title}."


def verification_method_rank(method: VerificationMethod) -> int:
    """Trust rank for a verification_method value. Higher = stronger.

    ``live-fetch`` (4) > ``archived-snapshot`` (3) > ``transcribed`` (2)
    > ``editorial`` (1). See module docstring for the use-case (Compare
    / reconciliation tooling picks the higher-ranked source when two
    citations report differently).

    Raises ``KeyError`` on unknown method — callers should be reading
    method values from a ``SourceRow`` (pydantic-validated against the
    Literal type) so an unknown value here means a contract drift, not
    a runtime input bug. Fail loud per CLAUDE.md §1 Holy Law #5.
    """
    return _VERIFICATION_METHOD_RANK[method]
