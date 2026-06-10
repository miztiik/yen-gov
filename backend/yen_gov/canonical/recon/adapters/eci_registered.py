"""ECI registered-parties parity adapter (PR-W-2).

Reads ``datasets/ephemeral/eci-registered-parties/2024/registered.csv``
(operator-committed snapshot of the Election Commission of India's Apr
2024 published "List of Political Parties & Symbol main Notification";
see the README in the same directory for full provenance + re-snapshot
policy) and projects each ECI row into a ``ShapeARow`` pair:

  1. One row with ``external_scope = "eci-registered"`` carrying ECI's
     proposed alignment / enrichment / mint-new action.
  2. One synthetic row with ``external_scope = "yen-gov-canonical"`` when
     ECI's party resolves to an existing canonical ``party_id``. This
     dual-emit mirrors PR-W-1's TCPD adapter — for PR-W-2 the second
     oracle is the canonical roster itself, so any ECI row that aligns
     with canonical is auto-promotable to ``VERIFIED`` per the Fowler
     n_oracles>=2 rule (plan section 0.5 ESCALATE #2 machine rule).
     Pure mint-new rows (no canonical match) emit only the ECI row →
     ``UNVERIFIED`` → curator-hand-mint via the Q7 + Hans-catalogue
     pathway.

Per Q1 fact-class authority (plan section 0.3):

  - **ECI wins on ``eci_codes``** (numeric or string registration code
    per vintage; e.g. 1 for BJP, 6 for INC, 12 for BSP).
  - **ECI wins on ``recognition_scope``** (the ``national`` / ``state``
    / ``unrecognised_registered`` / ``defunct`` enum).
  - **ECI wins on ``home_state_codes``** (pipe-list of ISO 3166-2 IN-XX
    codes for state-recognised parties).

The adapter's ``proposed_action == enrich`` body only touches Q1-owned
fields; never overwrites TCPD-owned (full_name / short / aliases /
lineage) or Wikipedia-owned (brand_colour / symbol_asset / wikipedia
URL / name_native_script) cells.

Per CLAUDE.md section 10 ("auto-correct BANNED on publisher
disagreement"): the adapter NEVER mutates parties.csv. It only proposes
shape-A rows. The curator script
(``tools/recon_curate_eci_registered``) applies VERIFIED enrichments +
``alias-add`` and surfaces DISPUTED rows for hand-curation.
``mint-new`` rows are surfaced as a deferred list; only the Q7-trio
mints (AIADMK_OPS, SHS_UBT) + the 6 known 2024 recognition flips per
Hans section 9 are hand-applied in this PR via the
``tools.recon_curate_eci_registered.hans_mints`` script.

Source provenance: ECI Apr 2024 publication snapshot;
``external_vintage = "2024"`` per ADR-0042 (operator snapshot window).
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

#: Where the ECI snapshot lives on disk. Per the brief's source preference
#: order: option (a) operator drops a direct ECI CSV (or hand-authored
#: snapshot from Wikipedia's mirror per option (b)) at this path. The
#: file IS committed to git as an audit-trail per Q3 commit policy
#: (unlike TCPD which is a multi-MB compilation kept ephemeral).
DEFAULT_ECI_CSV: Final[Path] = Path(
    "datasets/ephemeral/eci-registered-parties/2024/registered.csv"
)

#: ECI snapshot vintage. Per ADR-0042 (publisher edition anchor),
#: this is the operator's snapshot pin of the ECI publication date.
ECI_VINTAGE: Final[str] = "2024"

#: Adapter source-id used as the ShapeARow.external_scope on emitted rows.
ECI_SCOPE: Final[str] = "eci-registered"

#: Synthetic scope used for the second (canonical) oracle when an ECI
#: row matches an existing parties.csv row. The aggregator counts
#: distinct external_scope values as distinct oracles for the
#: n_oracles_present rule (recon/aggregator.py docstring + plan section
#: 0.5 ESCALATE #2). Same scope string PR-W-1 used so the Compare-
#: Aggregator's grouping is consistent across Stream W PRs.
CANONICAL_SCOPE: Final[str] = "yen-gov-canonical"

#: Generic stopwords stripped from the shared-significant-words guard
#: (``_share_significant_words``). Lifted from PR-W-1's TCPD adapter
#: with the same minimal set — over-aggressive stopwords empty most
#: party names of all signal and over-fires the collision guard.
_STOPWORDS: Final[frozenset[str]] = frozenset({
    "PARTY",
    "PARTIES",
    "FRONT",
})


def _normalise_full_name(full: str) -> str:
    """Normalise a full party name for fuzzy-equal matching across publishers.

    Same strategy as PR-W-1: uppercase + collapse internal whitespace
    + strip non-alphanumeric (parentheses, hyphens, dots). Collapses
    "All India Anna Dravida Munnetra Kazhagam" and "All India Anna
    Dravida Munnetra Kazhagam (M)" to the same key for the alias-add
    leg. Per Q1, ECI's full_name is NOT authoritative (TCPD wins on
    full_name); this normalisation is purely for the match-to-canonical
    bridge.
    """
    s = re.sub(r"[^A-Za-z0-9]+", " ", (full or "").upper()).strip()
    return re.sub(r"\s+", " ", s)


def _significant_words(full: str) -> set[str]:
    """Project a full-name string to its set of >=4-char content words.

    Used by ``_share_significant_words`` for the abbreviation-collision
    guard (lifted from PR-W-1). Removes punctuation and filters out
    short connectives and over-common party-name stopwords. Filters to
    party-identifying lexicon (e.g. for AAM AADMI PARTY: just {"AADMI"}
    after PARTY and AAM<4 are dropped).
    """
    s = re.sub(r"[^A-Za-z0-9]+", " ", (full or "").upper())
    return {w for w in s.split() if len(w) >= 4 and w not in _STOPWORDS}


def _share_significant_words(
    eci_full: str, canonical_full: str, canonical_short: str
) -> bool:
    """True iff ECI and canonical full names share a >=4-char content word.

    Defence against abbreviation collisions where two unrelated parties
    share a short. Returns ``True`` when canonical's full is "sparse"
    (full == short after normalisation) since sparse canonical provides
    no signal for word-overlap detection so by_alias is the strongest
    signal available. The guard only fires when canonical has a
    DISTINCT real full name AND zero significant words overlap with ECI.

    Lifted from PR-W-1; same semantics.
    """
    full_norm = _normalise_full_name(canonical_full)
    short_norm = _normalise_full_name(canonical_short)
    if full_norm == short_norm:
        return True
    canonical_words = _significant_words(canonical_full)
    if not canonical_words:
        return True
    return bool(_significant_words(eci_full) & canonical_words)


def _make_slug(abbrev: str) -> str:
    """Build a ``parties.IN.<SLUG>`` id from an ECI abbreviation.

    Sanitises to ``[A-Z0-9_]+`` per the parties.csv ``party_id`` regex
    (PR-0 schema). Replaces ``(``, ``)``, ``-``, ``.``, space with
    ``_``. Collapses multi-underscore runs. Same shape as PR-W-1's
    TCPD slug builder.
    """
    s = re.sub(r"[^A-Za-z0-9]+", "_", (abbrev or "").upper()).strip("_")
    s = re.sub(r"_+", "_", s)
    return f"parties.IN.{s}" if s else "parties.IN.UNK"


@dataclass(frozen=True, slots=True)
class _EciRecord:
    """In-memory projection of one row from the ECI snapshot CSV."""

    eci_code: str
    short: str
    full: str
    recognition_scope: str
    home_state_codes: str
    gained_year: str
    notes: str


def _read_eci_snapshot(path: Path) -> list[_EciRecord]:
    """Read the snapshot CSV into ``_EciRecord``s.

    Pure I/O; no normalisation beyond ``.strip()`` on each cell. The
    snapshot is hand-authored / operator-committed so the schema is
    fixed (see README in the same directory).
    """
    out: list[_EciRecord] = []
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            out.append(
                _EciRecord(
                    eci_code=(row.get("eci_code") or "").strip(),
                    short=(row.get("short") or "").strip(),
                    full=(row.get("full") or "").strip(),
                    recognition_scope=(row.get("recognition_scope") or "").strip(),
                    home_state_codes=(row.get("home_state_codes") or "").strip(),
                    gained_year=(row.get("gained_year") or "").strip(),
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
    """Build a canonical-side alias / full-name index from parties.csv.

    Lifted from PR-W-1's TCPD adapter; same shape. Aliases come from the
    resolver (short + pipe-split aliases column, UPPER). Full-name
    index is normalised for fuzzy-equal matching across publishers.
    Rows are kept for the enrich-leg comparisons (recognition_scope
    empty on canonical -> ECI can fill per Q1).
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
    rec: _EciRecord, ix: _CanonicalIndex
) -> tuple[str | None, bool]:
    """Match an ECI record to a canonical ``party_id``.

    Match priority (lifted from PR-W-1):

      1. **Normalised full-name match** against canonical's full column.
         Highest-confidence signal; runs first to avoid abbreviation
         variants mis-matching a different canonical party.
      2. **short (abbreviation)** UPPER lookup in canonical aliases.

    Returns ``(party_id, hit_via_full_name)`` so the caller can apply
    the shared-significant-words conflict guard only to by_alias hits.
    """
    full_key = _normalise_full_name(rec.full)
    if full_key:
        hit = ix.by_full.get(full_key)
        if hit is not None:
            return hit, True
    short_key = rec.short.upper().strip()
    if short_key:
        hit = ix.by_alias.get(short_key)
        if hit is not None:
            return hit, False
    return None, False


def _has_new_aliases(rec: _EciRecord, canonical_row: dict[str, str]) -> bool:
    """True if ECI's short is NOT in canonical aliases or canonical.short."""
    short = rec.short.upper().strip()
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


def _has_enrichable_fields(rec: _EciRecord, canonical_row: dict[str, str]) -> bool:
    """True if ECI adds non-empty data to a Q1-owned field canonical lacks.

    Q1 fact-class for ECI: ``eci_codes`` (numeric registration code),
    ``recognition_scope``, ``home_state_codes``. The enrich leg is a
    strict "fill empty cells only" operation — real disagreement (ECI
    says national, canonical says state) is surfaced as the curator's
    job, not auto-applied (CLAUDE.md section 10).
    """
    if rec.eci_code and not (canonical_row.get("eci_codes") or "").strip():
        return True
    if rec.recognition_scope and not (canonical_row.get("recognition_scope") or "").strip():
        return True
    if rec.home_state_codes and not (canonical_row.get("home_state_codes") or "").strip():
        return True
    return False


def _notes_for(rec: _EciRecord) -> str:
    """Compact provenance note carried on every emitted shape-A row.

    Combines ECI code + recognition_scope + home_state_codes + gained_year
    + the snapshot's free-text notes for curator review.
    """
    parts: list[str] = []
    if rec.eci_code:
        parts.append(f"eci_code={rec.eci_code}")
    if rec.recognition_scope:
        parts.append(f"scope={rec.recognition_scope}")
    if rec.home_state_codes:
        parts.append(f"states={rec.home_state_codes}")
    if rec.gained_year:
        parts.append(f"gained={rec.gained_year}")
    if rec.notes:
        parts.append(rec.notes)
    return "; ".join(parts)


def _emit_shape_a_for_eci_record(
    rec: _EciRecord, ix: _CanonicalIndex
) -> list[ShapeARow]:
    """Emit one (or two) shape-A rows for a single ECI record.

    Decision tree (mirrors PR-W-1's TCPD adapter):

      - canonical match found:
          * action = ``enrich`` if ECI adds non-empty Q1-owned data
            (eci_codes / recognition_scope / home_state_codes).
          * action = ``alias-add`` if ECI's short is not in canonical's
            aliases.
          * action = ``match`` otherwise (canonical already has it all).
          Emits the eci-registered row + the synthetic yen-gov-canonical
          row (second oracle for the VERIFIED leg).
      - no canonical match: action = ``mint-new``. proposed_party_id =
        slug from ECI's short. Only the eci-registered row is emitted
        (no canonical to pair with → UNVERIFIED).
      - abbreviation-collision detected (by_alias hit but full-name
        words don't overlap): action = ``conflict`` for both legs so
        the curator must disambiguate.
    """
    matched_pid, matched_via_full = _resolve_via_index(rec, ix)
    notes = _notes_for(rec)

    if matched_pid is None:
        slug_source = rec.short or _normalise_full_name(rec.full).replace(" ", "_")[:32]
        slug = _make_slug(slug_source)
        return [
            ShapeARow(
                external_key=rec.short or rec.full[:32],
                external_short=rec.short,
                external_full=rec.full,
                external_scope=ECI_SCOPE,
                external_vintage=ECI_VINTAGE,
                proposed_party_id=slug,
                proposed_action="mint-new",
                notes=notes,
            ),
        ]

    canonical_row = ix.rows_by_pid.get(matched_pid, {})

    # Abbreviation-collision guard: when by_alias hits but the full names
    # share no significant content word, treat as conflict. Lifted from
    # PR-W-1's TCPD adapter; same semantics.
    if not matched_via_full:
        canonical_full = (canonical_row.get("full") or "").strip()
        canonical_short = (canonical_row.get("short") or "").strip()
        if not _share_significant_words(rec.full, canonical_full, canonical_short):
            return [
                ShapeARow(
                    external_key=rec.short or rec.full[:32],
                    external_short=rec.short,
                    external_full=rec.full,
                    external_scope=ECI_SCOPE,
                    external_vintage=ECI_VINTAGE,
                    proposed_party_id=matched_pid,
                    proposed_action="conflict",
                    notes=(
                        f"abbreviation collision: ECI '{rec.full}' shares no "
                        f"significant word with canonical '{canonical_full}' "
                        f"under {matched_pid}; curator: mint different slug "
                        f"for ECI party."
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

    has_enrich = _has_enrichable_fields(rec, canonical_row)
    has_alias = _has_new_aliases(rec, canonical_row)

    # Action precedence: enrich dominates alias-add when both apply (the
    # curator script's enrich leg also applies the alias-add). Mirrors
    # PR-W-1's TCPD adapter precedence.
    action: str
    if has_enrich:
        action = "enrich"
    elif has_alias:
        action = "alias-add"
    else:
        action = "match"

    return [
        ShapeARow(
            external_key=rec.short or rec.full[:32],
            external_short=rec.short,
            external_full=rec.full,
            external_scope=ECI_SCOPE,
            external_vintage=ECI_VINTAGE,
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
class EciRegisteredAdapter:
    """The PR-W-2 adapter; registered against
    ``recon.adapters.REGISTRY['eci-registered']`` at module import time.

    Signature matches ``ParityAdapter`` Protocol (recon/adapters/__init__.py).
    The state / event / kind kwargs are accepted and ignored; ECI's
    notification is a global snapshot covering every recognised + the
    well-known unrecognised_registered cohort in one file.
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
        del state, event, kind  # unused: ECI snapshot is global.
        if vintage and vintage != ECI_VINTAGE:
            raise ValueError(
                f"eci-registered adapter only supports vintage "
                f"{ECI_VINTAGE!r}; got {vintage!r}. Drop a fresh "
                f"snapshot at {DEFAULT_ECI_CSV.as_posix()!r} and update "
                f"ECI_VINTAGE in {__name__!r}."
            )
        eci_csv = root / DEFAULT_ECI_CSV
        if not eci_csv.exists():
            raise FileNotFoundError(
                f"ECI registered-parties snapshot not found at "
                f"{eci_csv.as_posix()!r}; see the README in the same "
                f"directory for provenance + re-snapshot policy."
            )
        parties_csv = root / "datasets" / "data" / "entities" / "parties.csv"
        ix = _load_canonical_index(parties_csv)
        records = _read_eci_snapshot(eci_csv)
        out: list[ShapeARow] = []
        # Stable sort by short for reproducibility across runs.
        for rec in sorted(records, key=lambda r: (r.short, r.full)):
            out.extend(_emit_shape_a_for_eci_record(rec, ix))
        return out


#: Adapter instance auto-registered at import time (see __init__.py).
ADAPTER: Final[EciRegisteredAdapter] = EciRegisteredAdapter()


__all__ = [
    "ADAPTER",
    "EciRegisteredAdapter",
    "DEFAULT_ECI_CSV",
    "ECI_VINTAGE",
    "ECI_SCOPE",
    "CANONICAL_SCOPE",
]
