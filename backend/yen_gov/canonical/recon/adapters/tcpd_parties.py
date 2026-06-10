"""TCPD-PoliticalPartiesIndia_1962_2021 parity adapter (PR-W-1).

Reads ``datasets/ephemeral/TCPD-PoliticalPartiesIndia_1962_2021.csv`` (the
Trivedi Centre for Political Data 1962-2021 compilation; per-row shape is
one row per (Assembly, State, Party_ID) tuple, ~10k rows over ~3k
distinct TCPD Party_IDs) and projects each DISTINCT TCPD party into a
``ShapeARow`` pair:

  1. One row with ``external_scope = "tcpd-parties"`` carrying TCPD's
     proposed alignment / enrichment / mint-new action.
  2. One synthetic row with ``external_scope = "yen-gov-canonical"`` when
     TCPD's party resolves to an existing canonical ``party_id``. This
     dual-emit is the PR-W-1 brief's machine-rule extension to the Fowler
     VERIFIED-iff-n_oracles>=2 contract — for PR-W-1 the only upstream
     oracle is TCPD, so the canonical roster (parties.csv) IS the second
     effective oracle and any TCPD row that aligns with canonical is
     auto-promotable to ``VERIFIED``. Pure mint-new rows (no canonical
     match) emit only the TCPD row → ``UNVERIFIED`` → hand-curate.

Per Q1 fact-class authority (plan section 0.3): TCPD wins on
``full_name``, ``short``, ``aliases``, and lineage. PR-W-2 (ECI) covers
``eci_codes`` + ``recognition_scope``; PR-W-3 (Wikipedia) covers
``brand_colour`` / ``symbol_asset`` / ``wikipedia`` URL. PR-W-1's
``proposed_action == enrich`` body only touches Q1-owned fields.

Per CLAUDE.md section 10 ("auto-correct BANNED on publisher
disagreement"): the adapter NEVER mutates parties.csv. It only proposes
shape-A rows. The curator script (``tools/recon_curate_tcpd_parties.py``)
applies VERIFIED enrichments + ``alias-add`` and surfaces DISPUTED rows
for hand-curation. ``mint-new`` rows are surfaced as a deferred list;
only the Hans 33-case catalogue entries (TVK, JNP standalone, etc.) are
hand-minted in this PR.

Source provenance: TCPD compilation cutoff is 2021 (per the file name);
``external_vintage = "2021"`` per ADR-0042 (publisher edition pin).
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

#: Where the TCPD file lives on disk (CLAUDE.md section 3 ephemeral tier).
#: Operator drops the upstream file at this path; not committed to git.
DEFAULT_TCPD_CSV: Final[Path] = Path(
    "datasets/ephemeral/TCPD-PoliticalPartiesIndia_1962_2021.csv"
)

#: TCPD compilation cutoff year. Per ADR-0042 (publisher edition anchor),
#: this is the operator's snapshot pin of the upstream catalogue.
TCPD_VINTAGE: Final[str] = "2021"

#: Adapter source-id used as the ShapeARow.external_scope on emitted rows.
TCPD_SCOPE: Final[str] = "tcpd-parties"

#: Synthetic scope used for the second (canonical) oracle when a TCPD
#: row matches an existing parties.csv row. The aggregator counts distinct
#: external_scope values as distinct oracles for the n_oracles_present rule
#: (recon/aggregator.py docstring + plan section 0.5 ESCALATE #2).
CANONICAL_SCOPE: Final[str] = "yen-gov-canonical"

#: TCPD ``Party_Type`` -> parties.csv ``recognition_scope`` enum (plan
#: section 3 PR-0 brief). Anything outside this map is left empty so the
#: curator can fill it manually rather than silently default.
_PARTY_TYPE_TO_RECOGNITION: Final[dict[str, str]] = {
    "National Party": "national",
    "State-based Party": "state",
}

#: TCPD ``Party_Name`` values that signal dirty / placeholder rows in the
#: upstream compilation. These are skipped at group time (no shape-A row
#: emitted) so the verdict CSV is not polluted with NA-row false positives.
#: Source-evidence: ~20 rows in the 2021 compilation carry ``Party_Name``
#: "NA's" with valid Party_IDs but no usable identity metadata; these
#: collide with real canonical rows when their abbreviation is non-empty
#: (e.g. TCPD 24588 AIADMk / NA's mistakenly enriches parties.IN.AIADMK).
_DIRTY_FULL_NAMES: Final[frozenset[str]] = frozenset({
    "NA's",
    "NA",
    "N/A",
    "",
})

#: Generic stopwords stripped from the shared-significant-words guard
#: (``_share_significant_words``). Without this filter, almost every two
#: parties would "share" the word PARTY (or INDIA / NATIONAL / ALL etc.)
#: and the guard would never fire — letting abbreviation collisions silently
#: enrich the wrong canonical row (e.g. TCPD "awami aamjan party" matching
#: canonical AAM AADMI PARTY via the "AAP" short — verdict.csv row 12 in
#: the pre-fix PR-W-1 dry run). Kept INTENTIONALLY MINIMAL — only truly
#: generic suffix words. Words like BHARATIYA / JANATA / RASHTRIYA / DAL
#: are distinguishing in real Indian party names and stay in (excluding
#: them empties most party names of all signal and over-fires the guard).
_STOPWORDS: Final[frozenset[str]] = frozenset({
    "PARTY",
    "PARTIES",
    "FRONT",
})


def _normalise_full_name(full: str) -> str:
    """Normalise a full party name for fuzzy-equal matching across publishers.

    Strategy: uppercase + collapse internal whitespace + strip non-
    alphanumeric (parentheses, hyphens, dots). This collapses
    "All India Anna Dravida Munnetra Kazhagam" and "All India Anna
    Dravida Munnetra Kazhagam (M)" to the same key for the alias-add
    leg of the adapter. Per Q1, TCPD's full_name wins; canonical's
    full_name is only used as a fallback bridge when TCPD's
    abbreviations all miss the resolver.
    """
    s = re.sub(r"[^A-Za-z0-9]+", " ", (full or "").upper()).strip()
    return re.sub(r"\s+", " ", s)


def _significant_words(full: str) -> set[str]:
    """Project a full-name string to its set of >=4-char content words.

    Used by ``_share_significant_words`` for the abbreviation-collision
    guard. Removes punctuation (already done by ``_normalise_full_name``
    callers, but defensive here) and filters out short connectives and
    over-common party-name stopwords (``_STOPWORDS``). What's left is the
    party-identifying lexicon (e.g. for AAM AADMI PARTY: just {"AADMI"}
    after PARTY and AAM<4 are dropped).
    """
    s = re.sub(r"[^A-Za-z0-9]+", " ", (full or "").upper())
    return {w for w in s.split() if len(w) >= 4 and w not in _STOPWORDS}


def _share_significant_words(
    tcpd_full: str, canonical_full: str, canonical_short: str
) -> bool:
    """True iff TCPD and canonical full names share a >=4-char content word.

    Defence against abbreviation collisions where two unrelated parties
    share a short (e.g. TCPD's "awami aamjan party" and canonical's
    "Aam Aadmi Party" both abbreviated AAP). When the by_alias match
    fires but the full names share no significant words, the adapter
    surfaces the row as ``conflict`` rather than silently enriching the
    wrong canonical row.

    Returns ``True`` (trust the alias hit) when canonical's full is
    "sparse" — specifically when ``canonical_full == canonical_short``
    after normalisation. Sparse canonical is the X1a-fu2 transcode
    default where the parties.csv ``full`` cell was never authored
    beyond the slug-tail (~85% of the 619 pre-PR-W-1 rows); these rows
    provide no signal for word-overlap detection so by_alias is the
    strongest signal we have. The guard only fires when canonical has a
    DISTINCT real full name AND zero significant words overlap with TCPD.
    """
    full_norm = _normalise_full_name(canonical_full)
    short_norm = _normalise_full_name(canonical_short)
    if full_norm == short_norm:
        return True
    canonical_words = _significant_words(canonical_full)
    if not canonical_words:
        return True
    return bool(_significant_words(tcpd_full) & canonical_words)


def _make_slug(abbrev: str) -> str:
    """Build a ``parties.IN.<SLUG>`` id from a TCPD abbreviation.

    Sanitises to ``[A-Z0-9_]+`` (the parties.csv ``party_id`` regex per
    PR-0 schema). Replaces ``(``, ``)``, ``-``, ``.``, space with ``_``.
    Collapses multi-underscore runs. The resulting slug is the
    ``proposed_party_id`` for ``mint-new`` rows; if it collides with an
    existing canonical row, the aggregator escalates to ``conflict`` per
    the action-precedence rule in ``recon/aggregator.py``.
    """
    s = re.sub(r"[^A-Za-z0-9]+", "_", (abbrev or "").upper()).strip("_")
    s = re.sub(r"_+", "_", s)
    return f"parties.IN.{s}" if s else "parties.IN.UNK"


@dataclass(frozen=True, slots=True)
class _TcpdParty:
    """In-memory projection of one distinct TCPD Party_ID across all rows."""

    party_id: str  # TCPD numeric Party_ID, as string
    full_name: str  # Party_Name from the most-recent row
    frequent_abbrev: str  # Frequent_Abbreviation from the most-recent row
    last_abbrev: str  # Last_Abbreviation from the most-recent row
    all_abbrevs: tuple[str, ...]  # union of Abbreviations across all rows
    start_year: int  # min(Start_Year) across all rows
    last_year: int  # max(Last_Year) across all rows
    party_type: str  # Party_Type from the most-recent row


def _group_tcpd_rows_by_party_id(rows: Iterable[dict[str, str]]) -> list[_TcpdParty]:
    """Collapse the per-(Assembly, State, Party_ID) CSV into one row per Party_ID.

    Picks the row with max Last_Year (ties broken by max Start_Year,
    then by Assembly == "Lok_Sabha" being preferred for `Party_Type`
    consistency) as the representative for full_name + frequent_abbrev
    + last_abbrev + party_type. Aliases are unioned across all rows;
    start_year is the min seen; last_year is the max seen.

    Pure function for testability; no I/O, no clock.
    """
    by_pid: dict[str, list[dict[str, str]]] = {}
    for r in rows:
        pid = (r.get("Party_ID") or "").strip()
        if not pid:
            continue
        # Skip rows where Party_Name is the TCPD compilation's placeholder
        # for unparseable upstream entries ("NA's" / "NA" / empty). These
        # rows carry a valid Party_ID but no identity metadata; if the
        # row's Frequent_Abbreviation happens to UPPER-match a real
        # canonical short, the synthetic-oracle pair would silently
        # validate a garbage record (e.g. TCPD 24588 AIADMk "NA's" -> a
        # false-positive enrich of parties.IN.AIADMK).
        full_name = (r.get("Party_Name") or "").strip()
        if full_name in _DIRTY_FULL_NAMES:
            continue
        by_pid.setdefault(pid, []).append(r)

    out: list[_TcpdParty] = []
    for pid, grp in by_pid.items():
        # Pick representative row for "current name" fields. Prefer max
        # Last_Year so we describe the party as TCPD last saw it; ties
        # broken by max Start_Year, then by Lok_Sabha rows over state
        # rows (LS rows tend to carry the all-states aggregate party
        # type label).
        def _rep_key(r: dict[str, str]) -> tuple[int, int, int]:
            try:
                last = int(r.get("Last_Year") or 0)
            except ValueError:
                last = 0
            try:
                start = int(r.get("Start_Year") or 0)
            except ValueError:
                start = 0
            ls_pref = 1 if (r.get("Assembly") or "") == "Lok_Sabha" else 0
            return (last, start, ls_pref)

        rep = max(grp, key=_rep_key)

        all_abbrevs: set[str] = set()
        for r in grp:
            for fld in ("Frequent_Abbreviation", "Last_Abbreviation"):
                v = (r.get(fld) or "").strip()
                if v:
                    all_abbrevs.add(v)
            for v in (r.get("Abbreviations") or "").split("|"):
                v = v.strip()
                if v:
                    all_abbrevs.add(v)

        starts = []
        lasts = []
        for r in grp:
            try:
                starts.append(int(r.get("Start_Year") or 0))
            except ValueError:
                pass
            try:
                lasts.append(int(r.get("Last_Year") or 0))
            except ValueError:
                pass

        out.append(
            _TcpdParty(
                party_id=pid,
                full_name=(rep.get("Party_Name") or "").strip(),
                frequent_abbrev=(rep.get("Frequent_Abbreviation") or "").strip(),
                last_abbrev=(rep.get("Last_Abbreviation") or "").strip(),
                all_abbrevs=tuple(sorted(all_abbrevs)),
                start_year=min(starts) if starts else 0,
                last_year=max(lasts) if lasts else 0,
                party_type=(rep.get("Party_Type") or "").strip(),
            )
        )
    return out


@dataclass(frozen=True, slots=True)
class _CanonicalIndex:
    """Lightweight index over parties.csv for adapter-side matching."""

    by_alias: dict[str, str] = field(default_factory=dict)
    by_full: dict[str, str] = field(default_factory=dict)  # normalised full -> party_id
    rows_by_pid: dict[str, dict[str, str]] = field(default_factory=dict)


def _load_canonical_index(parties_csv: Path) -> _CanonicalIndex:
    """Build a canonical-side alias / full-name index from parties.csv.

    Aliases come from the resolver (short + pipe-split aliases column,
    UPPER). Full-name index is normalised (alphanumeric only, UPPER) so
    "All India Anna Dravida Munnetra Kazhagam" matches across publishers.
    Rows are kept for the enrich-leg comparisons (founded_year empty
    on canonical -> TCPD can fill).
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
    tcpd: _TcpdParty, ix: _CanonicalIndex
) -> tuple[str | None, bool]:
    """Match a TCPD party to a canonical ``party_id``.

    Match priority (most specific to least specific):

      1. **Normalised full-name match** against canonical's full column.
         Most specific signal — "All India Anna Dravida Munnetra Kazhagam"
         can only mean one party. This must run FIRST or TCPD abbreviation
         variants will mis-match a different canonical party that happens
         to share one of the variants (e.g. TCPD AIADMK's ``ADK``
         abbreviation would mis-match canonical ``parties.IN.ADK``).

      2. **Frequent_Abbreviation** UPPER lookup in canonical aliases.
         TCPD's primary short for the party.

      3. **Last_Abbreviation** UPPER lookup in canonical aliases.
         TCPD's most-recent short for the party.

      4. **Other Abbreviations** UPPER lookup in canonical aliases
         (sorted for determinism). Historical / regional variants.

    Returns ``(party_id, hit_via_full_name)`` — ``hit_via_full_name``
    distinguishes the high-confidence full-name match from the lower-
    confidence by_alias match (caller uses the flag to decide whether to
    apply the shared-significant-words conflict guard).
    """
    full_key = _normalise_full_name(tcpd.full_name)
    if full_key:
        hit = ix.by_full.get(full_key)
        if hit is not None:
            return hit, True
    seen: set[str] = set()
    candidates: list[str] = []
    if tcpd.frequent_abbrev:
        candidates.append(tcpd.frequent_abbrev)
    if tcpd.last_abbrev:
        candidates.append(tcpd.last_abbrev)
    candidates.extend(tcpd.all_abbrevs)
    for abbrev in candidates:
        key = (abbrev or "").upper().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        hit = ix.by_alias.get(key)
        if hit is not None:
            return hit, False
    return None, False


def _has_new_aliases(tcpd: _TcpdParty, canonical_row: dict[str, str]) -> bool:
    """True if TCPD has at least one abbreviation NOT in canonical aliases."""
    canonical_short = (canonical_row.get("short") or "").upper().strip()
    aliases_raw = (canonical_row.get("aliases") or "").strip()
    canonical_aliases = {canonical_short} if canonical_short else set()
    if aliases_raw:
        for a in aliases_raw.split("|"):
            v = a.strip().upper()
            if v:
                canonical_aliases.add(v)
    for abbrev in tcpd.all_abbrevs:
        if abbrev.upper().strip() and abbrev.upper().strip() not in canonical_aliases:
            return True
    return False


def _has_enrichable_fields(tcpd: _TcpdParty, canonical_row: dict[str, str]) -> bool:
    """True if TCPD adds non-empty data to a Q1-owned field canonical lacks.

    Q1 fact-class for TCPD: full_name / short / aliases / lineage. PR-W-1
    additionally fills founded_year + recognition_scope when the canonical
    cell is empty — these are not Q1 fact-class fields for TCPD (ECI wins
    on recognition_scope per Q1) but TCPD's data is non-conflicting when
    canonical is empty and the enrich leg is a strict "fill empty cells
    only" operation. Real disagreement (TCPD says national, canonical says
    state) surfaces as DISPUTED via the curator workflow, never auto-applied.
    """
    if tcpd.start_year and not (canonical_row.get("founded_year") or "").strip():
        return True
    rec = _PARTY_TYPE_TO_RECOGNITION.get(tcpd.party_type)
    if rec and not (canonical_row.get("recognition_scope") or "").strip():
        return True
    return False


def _notes_for(tcpd: _TcpdParty) -> str:
    """Compact provenance note carried on every emitted shape-A row.

    Combines the TCPD active-window + party-type for curator review.
    Empty fields are elided so the note stays terse.
    """
    parts: list[str] = []
    if tcpd.start_year and tcpd.last_year:
        parts.append(f"TCPD active {tcpd.start_year}-{tcpd.last_year}")
    elif tcpd.start_year:
        parts.append(f"TCPD start {tcpd.start_year}")
    if tcpd.party_type:
        parts.append(f"type={tcpd.party_type}")
    if tcpd.all_abbrevs:
        parts.append(f"abbrevs={'|'.join(tcpd.all_abbrevs)}")
    return "; ".join(parts)


def _emit_shape_a_for_tcpd_party(
    tcpd: _TcpdParty, ix: _CanonicalIndex
) -> list[ShapeARow]:
    """Emit one (or two) shape-A rows for a single TCPD party.

    Decision tree:
      - canonical match found:
          * action = ``enrich`` if TCPD adds non-empty Q1-owned data and
            also has new aliases (covers both legs in one row).
          * action = ``enrich`` if TCPD adds non-empty Q1-owned data.
          * action = ``alias-add`` if TCPD has abbreviations not in
            canonical's aliases column.
          * action = ``match`` otherwise (canonical already has it all).
          Emits the tcpd-parties row + the synthetic yen-gov-canonical
          row (second oracle for the VERIFIED leg).
      - no canonical match: action = ``mint-new``. proposed_party_id =
        slug from TCPD's Frequent_Abbreviation. Only the tcpd-parties
        row is emitted (no canonical to pair with → UNVERIFIED).
    """
    matched_pid, matched_via_full = _resolve_via_index(tcpd, ix)
    notes = _notes_for(tcpd)

    if matched_pid is None:
        # Slug source: prefer Frequent_Abbreviation (TCPD's primary short),
        # fall back to Last_Abbreviation, then to a slug derived from the
        # full name (lossy but deterministic). Empty-on-all-three should
        # have been filtered by ``_group_tcpd_rows_by_party_id`` via the
        # _DIRTY_FULL_NAMES skip; if a row still leaks through we slug it
        # to the first 32 chars of the normalised full so the verdict CSV
        # doesn't carry a collision-bait ``parties.IN.UNK`` row.
        slug_source = (
            tcpd.frequent_abbrev
            or tcpd.last_abbrev
            or _normalise_full_name(tcpd.full_name).replace(" ", "_")[:32]
            or tcpd.party_id
        )
        slug = _make_slug(slug_source)
        return [
            ShapeARow(
                external_key=tcpd.party_id,
                external_short=tcpd.frequent_abbrev or tcpd.last_abbrev,
                external_full=tcpd.full_name,
                external_scope=TCPD_SCOPE,
                external_vintage=TCPD_VINTAGE,
                proposed_party_id=slug,
                proposed_action="mint-new",
                notes=notes,
            ),
        ]

    canonical_row = ix.rows_by_pid.get(matched_pid, {})

    # Abbreviation-collision guard: when by_alias hits but the full names
    # share no significant content word, treat as conflict (curator must
    # disambiguate; TCPD's row likely needs a fresh slug instead of
    # silently enriching the colliding canonical row).
    if not matched_via_full:
        canonical_full = (canonical_row.get("full") or "").strip()
        canonical_short = (canonical_row.get("short") or "").strip()
        if not _share_significant_words(
            tcpd.full_name, canonical_full, canonical_short
        ):
            return [
                ShapeARow(
                    external_key=tcpd.party_id,
                    external_short=tcpd.frequent_abbrev or tcpd.last_abbrev,
                    external_full=tcpd.full_name,
                    external_scope=TCPD_SCOPE,
                    external_vintage=TCPD_VINTAGE,
                    proposed_party_id=matched_pid,
                    proposed_action="conflict",
                    notes=(
                        f"abbreviation collision: TCPD '{tcpd.full_name}' "
                        f"shares no significant word with canonical "
                        f"'{canonical_full}' under {matched_pid}; "
                        f"curator: mint different slug for TCPD party."
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

    has_enrich = _has_enrichable_fields(tcpd, canonical_row)
    has_alias = _has_new_aliases(tcpd, canonical_row)

    # Action precedence: enrich dominates alias-add when both apply
    # (enrich's curator leg applies the alias-add and also fills the
    # empty Q1 cell). alias-add when only new aliases. match otherwise.
    action: str
    if has_enrich:
        action = "enrich"
    elif has_alias:
        action = "alias-add"
    else:
        action = "match"

    return [
        ShapeARow(
            external_key=tcpd.party_id,
            external_short=tcpd.frequent_abbrev or tcpd.last_abbrev,
            external_full=tcpd.full_name,
            external_scope=TCPD_SCOPE,
            external_vintage=TCPD_VINTAGE,
            proposed_party_id=matched_pid,
            proposed_action=action,  # type: ignore[arg-type]
            notes=notes,
        ),
        # Second oracle: the canonical roster itself. Same proposed_party_id
        # so the Compare-Aggregator groups them together and counts
        # n_oracles_present == 2 -> VERIFIED.
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
class TcpdPartiesAdapter:
    """The PR-W-1 adapter; registered against
    ``recon.adapters.REGISTRY['tcpd-parties']`` at module import time.

    Signature matches ``ParityAdapter`` Protocol (recon/adapters/__init__.py).
    The state / event / kind kwargs are accepted and ignored; TCPD covers
    every party / every state / every assembly+parliament in one file.
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
        del state, event, kind  # unused: TCPD compilation is global.
        if vintage and vintage != TCPD_VINTAGE:
            # The compilation cutoff is hardcoded into the file's name +
            # contents; refuse to claim a different vintage to avoid
            # publisher-edition spoofing.
            raise ValueError(
                f"tcpd-parties adapter only supports vintage "
                f"{TCPD_VINTAGE!r}; got {vintage!r}"
            )
        tcpd_csv = root / DEFAULT_TCPD_CSV
        if not tcpd_csv.exists():
            raise FileNotFoundError(
                f"TCPD parties CSV not found at {tcpd_csv.as_posix()!r}; "
                f"operator drops the upstream file (gitignored ephemeral)."
            )
        parties_csv = root / "datasets" / "data" / "entities" / "parties.csv"
        ix = _load_canonical_index(parties_csv)
        with tcpd_csv.open(encoding="utf-8", newline="") as fh:
            tcpd_rows = list(csv.DictReader(fh))
        tcpd_parties = _group_tcpd_rows_by_party_id(tcpd_rows)
        out: list[ShapeARow] = []
        for tp in sorted(tcpd_parties, key=lambda t: t.party_id):
            out.extend(_emit_shape_a_for_tcpd_party(tp, ix))
        return out


#: Adapter instance auto-registered at import time (see __init__.py).
ADAPTER: Final[TcpdPartiesAdapter] = TcpdPartiesAdapter()


__all__ = [
    "ADAPTER",
    "TcpdPartiesAdapter",
    "DEFAULT_TCPD_CSV",
    "TCPD_VINTAGE",
    "TCPD_SCOPE",
    "CANONICAL_SCOPE",
]
