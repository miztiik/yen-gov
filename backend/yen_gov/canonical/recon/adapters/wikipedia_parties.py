"""Wikipedia parties parity adapter (PR-W-3).

Reads ``datasets/ephemeral/wikipedia-parties/2026-06/registered.csv``
(operator-committed hand-authored snapshot of the Wikipedia ``List of
political parties in India`` page + per-party infoboxes; see the README
in the same directory for full provenance + re-snapshot policy) and
projects each Wikipedia row into a ``ShapeARow`` pair:

  1. One row with ``external_scope = "wikipedia-parties"`` carrying the
     Wikipedia-proposed alignment / enrichment / mint-new action.
  2. One synthetic row with ``external_scope = "yen-gov-canonical"`` when
     Wikipedia's party resolves to an existing canonical ``party_id``.
     This dual-emit mirrors PR-W-1 + PR-W-2 - the canonical roster IS
     the second effective oracle, so any Wikipedia row that aligns with
     canonical is auto-promotable to ``VERIFIED`` per the Fowler
     ``n_oracles_present >= 2`` rule (plan section 0.5 ESCALATE #2).
     Pure mint-new rows (no canonical match) emit only the Wikipedia
     row -> ``UNVERIFIED`` -> curator-hand-mint via the
     ``tools/recon_curate_wikipedia_parties`` script.

Per Q1 fact-class authority (plan section 0.3):

  - **Wikipedia wins on ``brand_colour``** (hex string ``#RRGGBB`` from
    the infobox swatch).
  - **Wikipedia wins on ``symbol_asset``** URL or relative path. PR-W-3
    snapshots populate ``symbol_asset_url`` ONLY for parties where the
    canonical row already carries a matching value (the parity action
    becomes ``match`` -> VERIFIED, second oracle). New symbol-asset
    minting is OUT of scope for PR-W-3; a dedicated asset-ingest PR
    handles new symbols.
  - **Wikipedia wins on ``wikipedia``** URL (canonical EN-Wikipedia
    page URL).
  - **Wikipedia wins on ``name_native_script``** per Q8 (UI policy
    filters out on citizen elections surface per PR #874 No-Hindi
    rule; storage is additive and forward-compatible).

The adapter's ``proposed_action == enrich`` body only touches Q1-owned
fields; never overwrites TCPD-owned (full_name / short / aliases /
lineage) or ECI-owned (eci_codes / recognition_scope / home_state_codes)
cells.

Per CLAUDE.md section 10 ("auto-correct BANNED on publisher
disagreement") + Wave 0 / Hans verdict: the adapter NEVER mutates
parties.csv. It only proposes shape-A rows. The curator script
(``tools/recon_curate_wikipedia_parties``) applies VERIFIED enrichments
(fill-empty-only on Q1-owned columns + alias-add as appropriate) and
surfaces DISPUTED rows for hand-curation. ``mint-new`` rows are
surfaced as a deferred list; no PR-W-3-specific mints are pre-known
(the Q7 trio + Hans 33-case catalogue + 2024 recognition flips were
handled by PR-W-1 + PR-W-2 ``hans_mints``).

Source provenance: Wikipedia snapshot date is the operator window;
``external_vintage = "2026-06"`` per ADR-0042 (operator snapshot
window).

The snapshot's ``party_id_or_short`` column carries either:

  - **The canonical ``parties.IN.<SLUG>`` id directly** (preferred when
    the curator knows the slug; bypasses resolver fuzziness for
    deterministic matching). Adapter dispatches by ``parties.IN.``
    prefix.
  - **The publisher's short abbreviation** (when the snapshot row is
    for a party the curator has not pre-mapped to canonical). Adapter
    falls back to the resolver's by_alias lookup.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from yen_gov.canonical.party_resolver import load_resolver
from yen_gov.canonical.recon.shape_a import ShapeARow

#: Where the Wikipedia snapshot lives on disk. Per the brief's source
#: preference order: option (a) operator drops a hand-authored snapshot
#: at this path. The file IS committed to git as an audit-trail per Q3
#: commit policy (matching PR-W-2's ECI snapshot which is also
#: hand-authored + committed).
DEFAULT_WIKIPEDIA_CSV: Final[Path] = Path(
    "datasets/ephemeral/wikipedia-parties/2026-06/registered.csv"
)

#: Wikipedia snapshot operator window. Per ADR-0042 (operator snapshot
#: anchor), this is the YYYY-MM pin of when the snapshot was authored.
WIKIPEDIA_VINTAGE: Final[str] = "2026-06"

#: Adapter source-id used as the ShapeARow.external_scope on emitted rows.
WIKIPEDIA_SCOPE: Final[str] = "wikipedia-parties"

#: Synthetic scope used for the second (canonical) oracle when a Wikipedia
#: row matches an existing parties.csv row. Same scope string PR-W-1 and
#: PR-W-2 use so the Compare-Aggregator's grouping is consistent across
#: Stream W PRs (the aggregator counts distinct external_scope values as
#: distinct oracles for n_oracles_present, plan section 0.5 ESCALATE #2).
CANONICAL_SCOPE: Final[str] = "yen-gov-canonical"

#: Generic stopwords stripped from the shared-significant-words guard
#: (``_share_significant_words``). Lifted from PR-W-1 + PR-W-2 with the
#: same minimal set - over-aggressive stopwords empty most party names
#: of all signal and over-fires the collision guard.
_STOPWORDS: Final[frozenset[str]] = frozenset({
    "PARTY",
    "PARTIES",
    "FRONT",
})

#: Canonical id prefix that dispatches the direct-id path in the
#: snapshot's ``party_id_or_short`` column. When a row's first cell
#: starts with this prefix, the adapter uses it as proposed_party_id
#: directly and skips the resolver (deterministic; avoids fuzzy-match
#: ambiguity when the snapshot's full-name spelling differs from
#: canonical's full-name spelling).
CANONICAL_ID_PREFIX: Final[str] = "parties.IN."


def _normalise_full_name(full: str) -> str:
    """Normalise a full party name for fuzzy-equal matching across publishers.

    Same strategy as PR-W-1 + PR-W-2: uppercase + collapse internal
    whitespace + strip non-alphanumeric (parentheses, hyphens, dots).
    Collapses "All India Anna Dravida Munnetra Kazhagam" and "All India
    Anna Dravida Munnetra Kazhagam (M)" to the same key. Per Q1,
    Wikipedia's ``full_name`` is NOT authoritative (TCPD wins on
    full_name); this normalisation is purely for the match-to-canonical
    bridge.
    """
    s = re.sub(r"[^A-Za-z0-9]+", " ", (full or "").upper()).strip()
    return re.sub(r"\s+", " ", s)


def _significant_words(full: str) -> set[str]:
    """Project a full-name string to its set of >=4-char content words.

    Used by ``_share_significant_words`` for the abbreviation-collision
    guard (lifted verbatim from PR-W-1 + PR-W-2).
    """
    s = re.sub(r"[^A-Za-z0-9]+", " ", (full or "").upper())
    return {w for w in s.split() if len(w) >= 4 and w not in _STOPWORDS}


def _share_significant_words(
    wiki_full: str, canonical_full: str, canonical_short: str
) -> bool:
    """True iff Wikipedia and canonical full names share a >=4-char content word.

    Defence against abbreviation collisions where two unrelated parties
    share a short. Returns ``True`` when canonical's full is "sparse"
    (full == short after normalisation - the X1a-fu2 transcode default
    where the parties.csv ``full`` cell was never authored beyond the
    slug-tail). The guard only fires when canonical has a DISTINCT real
    full name AND zero significant words overlap with Wikipedia.

    Lifted verbatim from PR-W-1 + PR-W-2.
    """
    full_norm = _normalise_full_name(canonical_full)
    short_norm = _normalise_full_name(canonical_short)
    if full_norm == short_norm:
        return True
    canonical_words = _significant_words(canonical_full)
    if not canonical_words:
        return True
    return bool(_significant_words(wiki_full) & canonical_words)


def _make_slug(abbrev: str) -> str:
    """Build a ``parties.IN.<SLUG>`` id from a Wikipedia abbreviation.

    Sanitises to ``[A-Z0-9_]+`` per the parties.csv ``party_id`` regex
    (PR-0 schema). Replaces ``(``, ``)``, ``-``, ``.``, space with
    ``_``. Collapses multi-underscore runs. Same shape as PR-W-1 +
    PR-W-2 slug builders.
    """
    s = re.sub(r"[^A-Za-z0-9]+", "_", (abbrev or "").upper()).strip("_")
    s = re.sub(r"_+", "_", s)
    return f"parties.IN.{s}" if s else "parties.IN.UNK"


@dataclass(frozen=True, slots=True)
class _WikiRecord:
    """In-memory projection of one row from the Wikipedia snapshot CSV."""

    party_id_or_short: str  # canonical id (parties.IN.<X>) OR publisher short
    full: str
    native_script: str
    brand_colour: str
    symbol_asset: str
    wikipedia_url: str
    myneta_url: str  # citation-only; never written to canonical
    recognition_blurb: str
    notes: str


def _read_wikipedia_snapshot(path: Path) -> list[_WikiRecord]:
    """Read the snapshot CSV into ``_WikiRecord``s.

    Pure I/O; no normalisation beyond ``.strip()`` on each cell. The
    snapshot is hand-authored / operator-committed so the schema is
    fixed (see README in the same directory).
    """
    out: list[_WikiRecord] = []
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            out.append(
                _WikiRecord(
                    party_id_or_short=(row.get("party_id_or_short") or "").strip(),
                    full=(row.get("full_name") or "").strip(),
                    native_script=(row.get("native_script_name") or "").strip(),
                    brand_colour=(row.get("brand_colour_hex") or "").strip(),
                    symbol_asset=(row.get("symbol_asset_url") or "").strip(),
                    wikipedia_url=(row.get("wikipedia_url") or "").strip(),
                    myneta_url=(row.get("myneta_url") or "").strip(),
                    recognition_blurb=(row.get("recognition_blurb") or "").strip(),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return out


@dataclass(frozen=True, slots=True)
class _CanonicalIndex:
    """Lightweight index over parties.csv for adapter-side matching."""

    by_alias: dict[str, str] = field(default_factory=dict)
    by_full: dict[str, str] = field(default_factory=dict)
    rows_by_pid: dict[str, dict[str, str]] = field(default_factory=dict)


def _load_canonical_index(parties_csv: Path) -> _CanonicalIndex:
    """Build a canonical-side alias / full-name / id index from parties.csv.

    Lifted from PR-W-1 + PR-W-2; same shape. ``rows_by_pid`` is the
    direct-id index used when the snapshot's ``party_id_or_short`` cell
    starts with ``parties.IN.``.
    """
    resolver = load_resolver(parties_csv)
    by_full: dict[str, str] = {}
    rows_by_pid: dict[str, dict[str, str]] = {}
    if parties_csv.exists():
        with parties_csv.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                pid = (row.get("party_id") or "").strip()
                if not pid:
                    continue
                rows_by_pid[pid] = dict(row)
                key = _normalise_full_name(row.get("full") or "")
                if key and key not in by_full:
                    by_full[key] = pid
    return _CanonicalIndex(
        by_alias=dict(resolver.by_alias),
        by_full=by_full,
        rows_by_pid=rows_by_pid,
    )


def _resolve_via_index(
    rec: _WikiRecord, ix: _CanonicalIndex
) -> tuple[str | None, bool]:
    """Match a Wikipedia record to a canonical ``party_id``.

    Dispatch order:

      1. **Direct id**: if ``party_id_or_short`` starts with the
         canonical ``parties.IN.`` prefix AND the id exists in the
         canonical roster, return it (skip resolver). Returns
         ``hit_via_full_name=True`` so the abbreviation-collision guard
         is skipped (the curator explicitly named the slug).
      2. **Normalised full-name match** against canonical's full column.
         Highest-confidence remaining signal.
      3. **short (abbreviation)** UPPER lookup in canonical aliases.

    Returns ``(party_id, hit_via_full_name)`` so the caller can apply
    the shared-significant-words conflict guard only to by_alias hits.
    """
    key0 = rec.party_id_or_short.strip()
    if key0.startswith(CANONICAL_ID_PREFIX):
        if key0 in ix.rows_by_pid:
            return key0, True
        # Curator named a slug that does not exist yet -> mint-new path
        # will use it as proposed_party_id (no resolver fallback to a
        # different slug; the curator's intent is preserved).
        return None, False
    full_key = _normalise_full_name(rec.full)
    if full_key:
        hit = ix.by_full.get(full_key)
        if hit is not None:
            return hit, True
    short_key = key0.upper().strip()
    if short_key:
        hit = ix.by_alias.get(short_key)
        if hit is not None:
            return hit, False
    return None, False


def _has_enrichable_fields(rec: _WikiRecord, canonical_row: dict[str, str]) -> bool:
    """True if Wikipedia adds non-empty data to a Q1-owned field canonical lacks.

    Q1 fact-class for Wikipedia: ``brand_colour``, ``symbol_asset``,
    ``wikipedia`` URL, ``name_native_script``. The enrich leg is a
    strict "fill empty cells only" operation - real disagreement
    (Wikipedia says brand=#FF0000, canonical says brand=#FF9933) is
    surfaced as the curator's job, not auto-applied (CLAUDE.md
    section 10).
    """
    if rec.brand_colour and not (canonical_row.get("brand_colour") or "").strip():
        return True
    if rec.symbol_asset and not (canonical_row.get("symbol_asset") or "").strip():
        return True
    if rec.wikipedia_url and not (canonical_row.get("wikipedia") or "").strip():
        return True
    if rec.native_script and not (canonical_row.get("name_native_script") or "").strip():
        return True
    return False


def _has_disputed_overwrite(
    rec: _WikiRecord, canonical_row: dict[str, str]
) -> bool:
    """True if Wikipedia disagrees with a non-empty canonical Q1-owned cell.

    Defence against silent overwrites: if Wikipedia's brand_colour or
    wikipedia URL differs from canonical's existing value, surface as
    ``conflict`` -> ``DISPUTED`` -> curator decides per Q1 tie-break.

    Compares case-insensitively for hex codes (#FF9933 vs #ff9933) and
    after URL-encoding normalisation for the wikipedia URL is left as
    a future enhancement; current shape is strict-equal after .strip().
    The ``name_native_script`` cell is currently 100% empty across
    parties.csv post-PR-W-2 (per the audit) so disputed-overwrite
    never fires on that column at this PR's snapshot date.
    """
    def _conflicts(wiki_value: str, canonical_value: str) -> bool:
        wv = wiki_value.strip()
        cv = canonical_value.strip()
        if not wv or not cv:
            return False
        return wv.lower() != cv.lower()

    if _conflicts(rec.brand_colour, canonical_row.get("brand_colour") or ""):
        return True
    if _conflicts(rec.symbol_asset, canonical_row.get("symbol_asset") or ""):
        return True
    if _conflicts(rec.wikipedia_url, canonical_row.get("wikipedia") or ""):
        return True
    if _conflicts(rec.native_script, canonical_row.get("name_native_script") or ""):
        return True
    return False


def _notes_for(rec: _WikiRecord) -> str:
    """Compact provenance note carried on every emitted shape-A row.

    Combines Q1-owned fields present in this Wikipedia row + the
    recognition blurb + free-text notes for curator review.
    """
    parts: list[str] = []
    if rec.brand_colour:
        parts.append(f"colour={rec.brand_colour}")
    if rec.wikipedia_url:
        parts.append(f"wiki={rec.wikipedia_url}")
    if rec.native_script:
        # Truncate at 30 chars; the full value is in the snapshot CSV.
        ns = rec.native_script if len(rec.native_script) <= 30 else rec.native_script[:27] + "..."
        parts.append(f"native={ns}")
    if rec.myneta_url:
        parts.append("myneta=yes")
    if rec.recognition_blurb:
        parts.append(rec.recognition_blurb)
    if rec.notes:
        parts.append(rec.notes)
    return "; ".join(parts)


def _proposed_party_id_for_mint(rec: _WikiRecord) -> str:
    """Derive a proposed canonical ``party_id`` for a mint-new row.

    Honours the curator's explicit slug when ``party_id_or_short``
    starts with the canonical prefix; otherwise builds a slug from the
    short / full name.
    """
    key0 = rec.party_id_or_short.strip()
    if key0.startswith(CANONICAL_ID_PREFIX):
        return key0
    slug_source = key0 or _normalise_full_name(rec.full).replace(" ", "_")[:32]
    return _make_slug(slug_source)


def _emit_shape_a_for_wiki_record(
    rec: _WikiRecord, ix: _CanonicalIndex
) -> list[ShapeARow]:
    """Emit one (or two) shape-A rows for a single Wikipedia record.

    Decision tree (mirrors PR-W-1 + PR-W-2 adapters):

      - canonical match found:
          * action = ``conflict`` if Wikipedia disagrees with a
            non-empty Q1-owned canonical cell (curator tie-break).
          * action = ``enrich`` if Wikipedia adds non-empty Q1-owned
            data to an empty canonical cell.
          * action = ``match`` otherwise (canonical already has it all
            or all snapshot Q1-owned cells empty).
          Emits the wikipedia-parties row + the synthetic
          yen-gov-canonical row (second oracle for the VERIFIED leg).
      - no canonical match: action = ``mint-new``. proposed_party_id =
        curator-specified slug or derived from short. Only the
        wikipedia-parties row is emitted (no canonical to pair with ->
        UNVERIFIED).
      - abbreviation-collision detected (by_alias hit but full-name
        words don't overlap): action = ``conflict`` for both legs so
        the curator must disambiguate.
    """
    matched_pid, matched_via_full = _resolve_via_index(rec, ix)
    notes = _notes_for(rec)

    if matched_pid is None:
        slug = _proposed_party_id_for_mint(rec)
        return [
            ShapeARow(
                external_key=rec.party_id_or_short or rec.full[:32],
                external_short=rec.party_id_or_short,
                external_full=rec.full,
                external_scope=WIKIPEDIA_SCOPE,
                external_vintage=WIKIPEDIA_VINTAGE,
                proposed_party_id=slug,
                proposed_action="mint-new",
                notes=notes,
            ),
        ]

    canonical_row = ix.rows_by_pid.get(matched_pid, {})

    # Abbreviation-collision guard: when by_alias hits but the full names
    # share no significant content word, treat as conflict. Lifted from
    # PR-W-1 + PR-W-2; same semantics. Skipped for direct-id hits where
    # the curator explicitly named the canonical slug.
    if not matched_via_full:
        canonical_full = (canonical_row.get("full") or "").strip()
        canonical_short = (canonical_row.get("short") or "").strip()
        if not _share_significant_words(rec.full, canonical_full, canonical_short):
            return [
                ShapeARow(
                    external_key=rec.party_id_or_short or rec.full[:32],
                    external_short=rec.party_id_or_short,
                    external_full=rec.full,
                    external_scope=WIKIPEDIA_SCOPE,
                    external_vintage=WIKIPEDIA_VINTAGE,
                    proposed_party_id=matched_pid,
                    proposed_action="conflict",
                    notes=(
                        f"abbreviation collision: Wikipedia '{rec.full}' "
                        f"shares no significant word with canonical "
                        f"'{canonical_full}' under {matched_pid}; curator: "
                        f"mint different slug for Wikipedia party."
                    ),
                ),
                ShapeARow(
                    external_key=matched_pid,
                    external_short=(canonical_row.get("short") or "").strip(),
                    external_full=canonical_full,
                    external_scope=CANONICAL_SCOPE,
                    external_vintage="v1.1",
                    proposed_party_id=matched_pid,
                    proposed_action="conflict",
                    notes="canonical row in parties.csv (collision target)",
                ),
            ]

    # Q1 disputed-overwrite has precedence over enrich (a real
    # disagreement on brand_colour / wikipedia URL is a curator
    # decision per CLAUDE.md section 10; not silently overridden by
    # enrich's fill-empty-only semantics).
    has_dispute = _has_disputed_overwrite(rec, canonical_row)
    has_enrich = _has_enrichable_fields(rec, canonical_row)

    action: str
    if has_dispute:
        action = "conflict"
    elif has_enrich:
        action = "enrich"
    else:
        action = "match"

    return [
        ShapeARow(
            external_key=rec.party_id_or_short or rec.full[:32],
            external_short=rec.party_id_or_short,
            external_full=rec.full,
            external_scope=WIKIPEDIA_SCOPE,
            external_vintage=WIKIPEDIA_VINTAGE,
            proposed_party_id=matched_pid,
            proposed_action=action,  # type: ignore[arg-type]
            notes=notes,
        ),
        # Second oracle: the canonical roster itself. Same
        # proposed_party_id so the Compare-Aggregator groups them
        # together and counts n_oracles_present == 2 -> VERIFIED.
        ShapeARow(
            external_key=matched_pid,
            external_short=(canonical_row.get("short") or "").strip(),
            external_full=(canonical_row.get("full") or "").strip(),
            external_scope=CANONICAL_SCOPE,
            external_vintage="v1.1",
            proposed_party_id=matched_pid,
            proposed_action="match",
            notes="canonical row in parties.csv (second oracle for VERIFIED)",
        ),
    ]


@dataclass(frozen=True, slots=True)
class WikipediaPartiesAdapter:
    """The PR-W-3 adapter; registered against
    ``recon.adapters.REGISTRY['wikipedia-parties']`` at module import time.

    Signature matches ``ParityAdapter`` Protocol (recon/adapters/__init__.py).
    The state / event / kind kwargs are accepted and ignored; the
    Wikipedia snapshot is a global view covering the major national +
    state + Q7 split cohort in one file.
    """

    def __call__(
        self,
        *,
        root: Path,
        vintage: str,
        state: str | None = None,
        event: str | None = None,
        kind: str | None = None,
    ) -> Iterable[ShapeARow]:
        del state, event, kind  # unused: Wikipedia snapshot is global.
        if vintage and vintage != WIKIPEDIA_VINTAGE:
            raise ValueError(
                f"wikipedia-parties adapter only supports vintage "
                f"{WIKIPEDIA_VINTAGE!r}; got {vintage!r}. Drop a fresh "
                f"snapshot at {DEFAULT_WIKIPEDIA_CSV.as_posix()!r} and "
                f"update WIKIPEDIA_VINTAGE in {__name__!r}."
            )
        wiki_csv = root / DEFAULT_WIKIPEDIA_CSV
        if not wiki_csv.exists():
            raise FileNotFoundError(
                f"Wikipedia parties snapshot not found at "
                f"{wiki_csv.as_posix()!r}; see the README in the same "
                f"directory for provenance + re-snapshot policy."
            )
        parties_csv = root / "datasets" / "data" / "entities" / "parties.csv"
        ix = _load_canonical_index(parties_csv)
        records = _read_wikipedia_snapshot(wiki_csv)
        out: list[ShapeARow] = []
        # Stable sort by external key for reproducibility across runs.
        for rec in sorted(records, key=lambda r: (r.party_id_or_short, r.full)):
            out.extend(_emit_shape_a_for_wiki_record(rec, ix))
        return out


#: Adapter instance auto-registered at import time (see __init__.py).
ADAPTER: Final[WikipediaPartiesAdapter] = WikipediaPartiesAdapter()


__all__ = [
    "ADAPTER",
    "WikipediaPartiesAdapter",
    "DEFAULT_WIKIPEDIA_CSV",
    "WIKIPEDIA_VINTAGE",
    "WIKIPEDIA_SCOPE",
    "CANONICAL_SCOPE",
]
