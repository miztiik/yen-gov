"""IndiaVotes party catalogue parity adapter (UNK-enrichment).

Reads the operator-committed snapshot at
``datasets/ephemeral/indiavotes-parties/2026-06/registered.csv`` (one row
per distinct IndiaVotes party catalogue entry; sourced via the listing
page + per-slug detail probes per
``tools/scrape_indiavotes_parties/__main__.py``) and projects each row
into a ``ShapeARow`` pair following the PR-W-1 / W-2 / W-3 cohort
convention:

  1. One row with ``external_scope = "indiavotes-parties"`` carrying
     IndiaVotes's proposed alignment / alias-add / mint-new action.
  2. One synthetic row with ``external_scope = "yen-gov-canonical"`` when
     IndiaVotes's party resolves to an existing canonical ``party_id``.
     This dual-emit mirrors the Stream W cohort - canonical is the second
     effective oracle, so any IndiaVotes row that aligns with canonical
     is auto-promotable to ``VERIFIED`` per the Fowler
     ``n_oracles_present >= 2`` machine rule (recon/aggregator.py
     docstring). Pure mint-new rows (no canonical match) emit only the
     IndiaVotes row -> ``UNVERIFIED`` -> curator-hand-mint via
     ``tools/recon_curate_indiavotes_parties``.

User signoff (2026-06-11, "A - fix all UNK and rajasthan") promoted
IndiaVotes from Q1 secondary-lane-only (fact-class table for state-event
parity oracles, PR-S-* cohort) to a NEW enrichment source for
parties.csv aliases + mint-new rows. The Q1 fact-class table is
UNCHANGED for the existing tables (TCPD still wins on full_name / short
/ aliases / lineage; ECI still wins on eci_codes / recognition_scope /
home_state_codes; Wikipedia still wins on brand_colour / symbol_asset /
wikipedia URL / native script). IndiaVotes's role on the
parties.csv-enrichment seam is restricted to:

  - **Add aliases**: when IndiaVotes's full_name uniquely matches one
    canonical row by short / aliases / full, and the IndiaVotes
    publisher abbreviation is NOT yet in that row's aliases pipe-list.
    Auto-applies in the curator (alias-add is the lowest-impact
    enrichment; the canonical's existing aliases are preserved
    byte-identically).
  - **Mint-new rows**: when no canonical match exists, the curator
    auto-mints a new ``parties.IN.<SLUG>`` row using IndiaVotes's
    full_name + slug + recognition_scope (mapped from IV's ``iv_type``
    column) + home_state_codes (left empty -- IV does not publish a
    state-code column; ECI's next list refresh is the authoritative
    fill). The mint is dispatched in the curator, not auto-applied
    here; this adapter only emits the shape-A row that signals
    ``mint-new`` to the aggregator.

The adapter NEVER mutates parties.csv (CLAUDE.md section 10
"auto-correct BANNED"). It only emits shape-A rows. The curator script
applies the verdict.

Source provenance: IndiaVotes 2026-06 snapshot
(``external_vintage = "2026-06"`` per ADR-0042 operator snapshot window
anchor).
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

#: Where the IndiaVotes snapshot lives on disk (CLAUDE.md section 3
#: ephemeral tier; committed per Q3 audit-trail convention).
DEFAULT_INDIAVOTES_CSV: Final[Path] = Path(
    "datasets/ephemeral/indiavotes-parties/2026-06/registered.csv"
)

#: IndiaVotes snapshot vintage. Per ADR-0042 (operator snapshot anchor),
#: this is the YYYY-MM pin of when the snapshot was authored.
INDIAVOTES_VINTAGE: Final[str] = "2026-06"

#: Adapter source-id used as the ShapeARow.external_scope on emitted rows.
INDIAVOTES_SCOPE: Final[str] = "indiavotes-parties"

#: Synthetic scope used for the second (canonical) oracle when an IV row
#: matches an existing parties.csv row. Same scope string PR-W-1 + W-2 +
#: W-3 use so the Compare-Aggregator's distinct-oracle counting stays
#: consistent across Stream W PRs (the aggregator treats distinct
#: external_scope values as distinct oracles for n_oracles_present, plan
#: section 0.5 ESCALATE #2 machine rule).
CANONICAL_SCOPE: Final[str] = "yen-gov-canonical"

#: IV ``iv_type`` -> parties.csv ``recognition_scope`` enum.
#: Anything outside this map is left empty so the curator can fill it
#: manually rather than silently default.
_IV_TYPE_TO_RECOGNITION: Final[dict[str, str]] = {
    "national": "national",
    "state": "state",
    "state-recognised": "state",
    "state-based": "state",
    "unrecognised": "unrecognised_registered",
    "unrecognized": "unrecognised_registered",
    "registered": "unrecognised_registered",
    "registered_unrecognised": "unrecognised_registered",
    "registered-unrecognised": "unrecognised_registered",
}

#: IV ``iv_type`` values that signal a non-party sentinel row in the
#: catalogue (IV publishes "Independent" as a "party" row in the
#: listing). These are skipped entirely; canonical's parties.IN.IND
#: sentinel covers the independent case and minting a second IND-like
#: row would corrupt FK closure.
_DIRTY_TYPES: Final[frozenset[str]] = frozenset({"independent"})

#: Generic stopwords stripped from the shared-significant-words guard
#: (``_share_significant_words``). Lifted from PR-W-1 + W-2 + W-3 with
#: the same minimal set - over-aggressive stopwords empty most party
#: names of all signal and over-fires the collision guard.
_STOPWORDS: Final[frozenset[str]] = frozenset({
    "PARTY",
    "PARTIES",
    "FRONT",
})

#: Current year used to decide whether IV's active-period upper bound
#: signals a real dissolution or just IV's data-current-year sentinel.
#: Per Hans no-silent-demotion: we set dissolved_year ONLY when the
#: upper bound is STRICTLY LESS than this constant.
_DATA_CURRENT_YEAR: Final[int] = 2026


def _normalise_full_name(full: str) -> str:
    """Normalise a full party name for fuzzy-equal matching across publishers.

    Same strategy as PR-W-1 + W-2 + W-3: uppercase + collapse internal
    whitespace + strip non-alphanumeric (parentheses, hyphens, dots).
    Collapses "All India Anna Dravida Munnetra Kazhagam" and "All India
    Anna Dravida Munnetra Kazhagam (M)" to the same key. Per Q1,
    IndiaVotes's ``full_name`` is NOT authoritative for cell overwrites
    (TCPD still wins on full_name); this normalisation is purely for
    the match-to-canonical bridge.
    """
    s = re.sub(r"[^A-Za-z0-9]+", " ", (full or "").upper()).strip()
    return re.sub(r"\s+", " ", s)


def _significant_words(full: str) -> set[str]:
    """Project a full-name string to its set of >=4-char content words.

    Used by ``_share_significant_words`` for the abbreviation-collision
    guard (lifted verbatim from PR-W-1 + W-2 + W-3).
    """
    s = re.sub(r"[^A-Za-z0-9]+", " ", (full or "").upper())
    return {w for w in s.split() if len(w) >= 4 and w not in _STOPWORDS}


def _share_significant_words(
    iv_full: str, canonical_full: str, canonical_short: str
) -> bool:
    """True iff IndiaVotes and canonical full names share a >=4-char content word.

    Defence against abbreviation collisions where two unrelated parties
    share a short. Returns ``True`` when canonical's full is "sparse"
    (full == short after normalisation) since sparse canonical provides
    no signal for word-overlap detection so by_alias is the strongest
    signal available. The guard only fires when canonical has a
    DISTINCT real full name AND zero significant words overlap with IV.

    Lifted verbatim from PR-W-1 + W-2 + W-3.
    """
    full_norm = _normalise_full_name(canonical_full)
    short_norm = _normalise_full_name(canonical_short)
    if full_norm == short_norm:
        return True
    canonical_words = _significant_words(canonical_full)
    if not canonical_words:
        return True
    return bool(_significant_words(iv_full) & canonical_words)


def _make_slug(abbrev: str) -> str:
    """Build a ``parties.IN.<SLUG>`` id from an IndiaVotes abbreviation.

    Sanitises to ``[A-Z0-9_]+`` per the parties.csv ``party_id`` regex
    (PR-0 schema). Replaces ``(``, ``)``, ``-``, ``.``, space with
    ``_``. Collapses multi-underscore runs. Same shape as PR-W-1 + W-2
    + W-3 slug builders.
    """
    s = re.sub(r"[^A-Za-z0-9]+", "_", (abbrev or "").upper()).strip("_")
    s = re.sub(r"_+", "_", s)
    return f"parties.IN.{s}" if s else "parties.IN.UNK"


@dataclass(frozen=True, slots=True)
class _IvRecord:
    """In-memory projection of one row from the IndiaVotes snapshot CSV."""

    abbrev: str
    full: str
    slug: str
    iv_type: str
    iv_url: str
    active_from: str
    active_to: str
    source_lane: str  # "listing" | "probe" -- curator-readable origin
    notes: str


def _read_indiavotes_snapshot(path: Path) -> list[_IvRecord]:
    """Read the snapshot CSV into ``_IvRecord``s.

    Pure I/O; no normalisation beyond ``.strip()`` on each cell. The
    snapshot is operator-committed so the schema is fixed (see the
    README in the same directory).

    Rows with ``iv_type == 'independent'`` are skipped (canonical's
    parties.IN.IND sentinel covers the independent case; minting a
    parallel IND-like row would corrupt FK closure).
    """
    out: list[_IvRecord] = []
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            iv_type = (row.get("iv_type") or "").strip().lower()
            if iv_type in _DIRTY_TYPES:
                continue
            abbrev = (row.get("party_abbreviation") or "").strip()
            full = (row.get("party_full_name") or "").strip()
            if not abbrev or not full:
                continue
            out.append(
                _IvRecord(
                    abbrev=abbrev,
                    full=full,
                    slug=(row.get("slug") or "").strip(),
                    iv_type=iv_type,
                    iv_url=(row.get("iv_url") or "").strip(),
                    active_from=(row.get("active_period_from") or "").strip(),
                    active_to=(row.get("active_period_to") or "").strip(),
                    source_lane=(row.get("source_lane") or "").strip(),
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

    Lifted from PR-W-1 + W-2 + W-3; same shape. ``rows_by_pid`` is the
    direct-id index used when the snapshot's slug deterministically
    matches an existing canonical id.
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
    rec: _IvRecord, ix: _CanonicalIndex
) -> tuple[str | None, bool]:
    """Match an IndiaVotes record to a canonical ``party_id``.

    Match priority (lifted from PR-W-1 + W-2 + W-3):

      1. **Normalised full-name match** against canonical's full column.
         Highest-confidence signal; runs first to avoid abbreviation
         variants mis-matching a different canonical party.
      2. **abbreviation** UPPER lookup in canonical aliases.

    Returns ``(party_id, hit_via_full_name)`` so the caller can apply
    the shared-significant-words conflict guard only to by_alias hits.
    """
    full_key = _normalise_full_name(rec.full)
    if full_key:
        hit = ix.by_full.get(full_key)
        if hit is not None:
            return hit, True
    short_key = rec.abbrev.upper().strip()
    if short_key:
        hit = ix.by_alias.get(short_key)
        if hit is not None:
            return hit, False
    return None, False


def _has_new_aliases(rec: _IvRecord, canonical_row: dict[str, str]) -> bool:
    """True if IV's abbrev is NOT already in canonical aliases / short."""
    short = rec.abbrev.upper().strip()
    if not short:
        return False
    canonical_short = (canonical_row.get("short") or "").upper().strip()
    if short == canonical_short:
        return False
    aliases_raw = (canonical_row.get("aliases") or "").strip()
    canonical_aliases: set[str] = set()
    if aliases_raw:
        for a in aliases_raw.split("|"):
            v = a.strip().upper()
            if v:
                canonical_aliases.add(v)
    return short not in canonical_aliases


def _notes_for(rec: _IvRecord) -> str:
    """Compact provenance note carried on every emitted shape-A row.

    Combines IV type + slug + active period + source lane + URL so the
    curator can audit each row without re-reading the snapshot.
    """
    parts: list[str] = []
    if rec.iv_type:
        parts.append(f"iv_type={rec.iv_type}")
    if rec.slug:
        parts.append(f"slug={rec.slug}")
    if rec.active_from or rec.active_to:
        parts.append(f"active={rec.active_from}-{rec.active_to}")
    if rec.source_lane:
        parts.append(f"lane={rec.source_lane}")
    if rec.iv_url:
        parts.append(f"url={rec.iv_url}")
    if rec.notes:
        parts.append(rec.notes)
    return "; ".join(parts)


def _emit_shape_a_for_iv_record(
    rec: _IvRecord, ix: _CanonicalIndex
) -> list[ShapeARow]:
    """Emit one (or two) shape-A rows for a single IndiaVotes record.

    Decision tree (mirrors PR-W-1 + W-2 + W-3):

      - canonical match found:
          * action = ``alias-add`` if IV's abbreviation is NOT in
            canonical's aliases pipe-list (the dominant case -- IV's
            publisher labels are exactly what citizens emit when
            looking at IV-derived data; adding them to the canonical
            row's aliases collapses the UNK rate on the same publisher
            labels in candidacies.csv).
          * action = ``match`` otherwise (canonical already lists this
            abbreviation; no enrichment needed).
          Emits the indiavotes-parties row + the synthetic
          yen-gov-canonical row (second oracle for the VERIFIED leg).
      - no canonical match: action = ``mint-new``. proposed_party_id =
        slug derived from IV's abbreviation. Only the
        indiavotes-parties row is emitted (no canonical to pair with
        -> UNVERIFIED).
      - abbreviation-collision detected (by_alias hit but full-name
        words don't overlap): action = ``conflict`` for both legs so
        the curator must disambiguate.

    NOTE: IV is NOT Q1-authoritative on full_name / recognition_scope /
    home_state_codes, so the ``enrich`` leg from PR-W-2 (ECI) is not
    emitted here. The mint-new leg DOES propagate IV's recognition_scope
    + active period via the ``notes`` field; the curator script reads
    those for the mint payload.
    """
    matched_pid, matched_via_full = _resolve_via_index(rec, ix)
    notes = _notes_for(rec)

    if matched_pid is None:
        slug = _make_slug(rec.abbrev)
        return [
            ShapeARow(
                external_key=rec.abbrev,
                external_short=rec.abbrev,
                external_full=rec.full,
                external_scope=INDIAVOTES_SCOPE,
                external_vintage=INDIAVOTES_VINTAGE,
                proposed_party_id=slug,
                proposed_action="mint-new",
                notes=notes,
            ),
        ]

    canonical_row = ix.rows_by_pid.get(matched_pid, {})

    # Abbreviation-collision guard: when by_alias hits but the full
    # names share no significant content word, treat as conflict.
    # Lifted verbatim from PR-W-1 + W-2 + W-3.
    if not matched_via_full:
        canonical_full = (canonical_row.get("full") or "").strip()
        canonical_short = (canonical_row.get("short") or "").strip()
        if not _share_significant_words(rec.full, canonical_full, canonical_short):
            return [
                ShapeARow(
                    external_key=rec.abbrev,
                    external_short=rec.abbrev,
                    external_full=rec.full,
                    external_scope=INDIAVOTES_SCOPE,
                    external_vintage=INDIAVOTES_VINTAGE,
                    proposed_party_id=matched_pid,
                    proposed_action="conflict",
                    notes=(
                        f"abbreviation collision: IndiaVotes '{rec.full}' "
                        f"shares no significant word with canonical "
                        f"'{canonical_full}' under {matched_pid}; curator: "
                        f"mint different slug for IndiaVotes party. "
                        f"{notes}"
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

    action: str
    if _has_new_aliases(rec, canonical_row):
        action = "alias-add"
    else:
        action = "match"

    return [
        ShapeARow(
            external_key=rec.abbrev,
            external_short=rec.abbrev,
            external_full=rec.full,
            external_scope=INDIAVOTES_SCOPE,
            external_vintage=INDIAVOTES_VINTAGE,
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


def recognition_from_iv_type(iv_type: str) -> str:
    """Map IV's ``iv_type`` to parties.csv ``recognition_scope`` enum.

    Returns "" when IV publishes an unrecognised type token; the
    curator leaves the recognition_scope empty so ECI's next list
    refresh is the authoritative fill (Q1 ECI wins on
    recognition_scope).
    """
    return _IV_TYPE_TO_RECOGNITION.get((iv_type or "").strip().lower(), "")


def dissolved_year_from_active_to(active_to: str) -> str:
    """Return a 4-digit dissolved_year when active_to < current year.

    IV's listing carries an "Active" column like "1952 - 2026". The
    trailing "2026" is IV's data-current-year sentinel; treating it as
    dissolved=2026 would falsely retire every currently-active party.
    Only set dissolved_year when the upper bound is STRICTLY LESS than
    ``_DATA_CURRENT_YEAR``.

    Returns the year as a STRING (the curator's writer also writes
    strings; parties.csv stores integer-shaped values as quoted CSV
    cells). Empty on parse failure or sentinel year.
    """
    if not active_to:
        return ""
    try:
        end = int(active_to)
    except ValueError:
        return ""
    if end < _DATA_CURRENT_YEAR:
        return str(end)
    return ""


@dataclass(frozen=True, slots=True)
class IndiaVotesPartiesAdapter:
    """The IndiaVotes parties adapter; registered against
    ``recon.adapters.REGISTRY['indiavotes-parties']`` at module import time.

    Signature matches ``ParityAdapter`` Protocol (recon/adapters/__init__.py).
    The state / event / kind kwargs are accepted and ignored; the
    IndiaVotes snapshot is a global view (top ~60 listing rows + per-slug
    probes for the long-tail UNK labels).
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
        del state, event, kind  # unused: IndiaVotes snapshot is global.
        if vintage and vintage != INDIAVOTES_VINTAGE:
            raise ValueError(
                f"indiavotes-parties adapter only supports vintage "
                f"{INDIAVOTES_VINTAGE!r}; got {vintage!r}. Drop a fresh "
                f"snapshot at {DEFAULT_INDIAVOTES_CSV.as_posix()!r} and "
                f"update INDIAVOTES_VINTAGE in {__name__!r}."
            )
        iv_csv = root / DEFAULT_INDIAVOTES_CSV
        if not iv_csv.exists():
            raise FileNotFoundError(
                f"IndiaVotes parties snapshot not found at "
                f"{iv_csv.as_posix()!r}; see the README in the same "
                f"directory for provenance + re-snapshot policy."
            )
        parties_csv = root / "datasets" / "data" / "entities" / "parties.csv"
        ix = _load_canonical_index(parties_csv)
        records = _read_indiavotes_snapshot(iv_csv)
        out: list[ShapeARow] = []
        # Stable sort by abbrev for reproducibility across runs.
        for rec in sorted(records, key=lambda r: (r.abbrev, r.full)):
            out.extend(_emit_shape_a_for_iv_record(rec, ix))
        return out


#: Adapter instance auto-registered at import time (see __init__.py).
ADAPTER: Final[IndiaVotesPartiesAdapter] = IndiaVotesPartiesAdapter()


__all__ = [
    "ADAPTER",
    "IndiaVotesPartiesAdapter",
    "DEFAULT_INDIAVOTES_CSV",
    "INDIAVOTES_VINTAGE",
    "INDIAVOTES_SCOPE",
    "CANONICAL_SCOPE",
    "recognition_from_iv_type",
    "dissolved_year_from_active_to",
]
