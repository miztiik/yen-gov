"""bhukyavenkatamahesh per-PC parity adapter (PR-PC-LS2024 + PR-PC-LS2019).

Reads ``datasets/ephemeral/bhukyavenkatamahesh-pc/<year>/results.csv``
(one-off snapshot of source #6 / source #5 from the PR-PC-LS2024 +
PR-PC-LS2019 briefs:

  - 2024: ``https://github.com/bhukyavenkatamahesh/election-viz/blob/
    main/Data/results/results_2024.csv``
  - 2019: ``https://github.com/bhukyavenkatamahesh/election-viz/blob/
    main/Data/results/results_2019.csv``

and emits ONE per-PC shape-A row per parliamentary constituency
(the winner row, derived as the per-PC modal candidate by Votes /
total_votes depending on vintage schema).

The 2024 CSV is semicolon-delimited with columns
``State;Constituency;Party;Candidate;Votes;State ID;Constituency ID``.
The 2019 CSV is comma-delimited with a DIFFERENT column schema
(``province_id, province_name, constituency_id, constituency_name,
type, osn, candidate_name, party_name, evm_votes, postal_votes,
total_votes, vote_share``) - the publisher refactored the file format
between vintages. PR-PC-LS2019 dispatches per-year to the right reader
(see ``_read_bhuky_winners`` vs ``_read_bhuky_2019_winners``); the
2024 callers remain on the BHUKY_VINTAGE pin + DEFAULT_BHUKY_CSV path
unchanged.

The 2024 publisher carries 8902 candidate rows across 543 PCs; the
2019 publisher carries 8568 candidate rows across 542 PCs (Vellore
2019 was postponed). The adapter groups by
``(publisher_state, publisher_constituency)`` (textual; the
``(State ID, Constituency ID)`` tuple is NOT unique across states -
the publisher's per-state CIDs only run 1..9 max) and picks the
max-vote-count row per group as the winner.

Per Q1 fact-class authority (plan section 0.3): bhukyavenkatamahesh
is NOT authoritative on any fact-class - it is a corroboration
oracle for the per-PC winner_party_id parity check. ECI / yen-gov
canonical wins per Holy Law #9; bhuky's role is to surface
DISPUTED rows for the curator (CLAUDE.md section 10:
auto-correct BANNED on publisher disagreement).

The vintage pin is the publisher's stated edition year per ADR-0042:
``BHUKY_VINTAGE = "2024"`` / ``BHUKY_VINTAGE_2019 = "2019"`` (the
file path itself is ``results_2024.csv`` / ``results_2019.csv``).

Source provenance: 2024 file snapshotted from the
raw.githubusercontent.com URL on 2026-06-11 by the PR-PC-LS2024 ship
session; 2019 file snapshotted on 2026-06-11 by the PR-PC-LS2019
ship session. Both files are committed to git as audit trails per
Q3 commit policy (matching PR-W-2's ECI snapshot which is also
hand-snapshotted + committed).
"""

from __future__ import annotations

import csv
import html
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from yen_gov.canonical.recon.shape_a import ShapeARow

#: Where the bhukyavenkatamahesh 2024 snapshot lives on disk. Per Q3
#: commit policy this file IS committed (operator-snapshotted, not
#: auto-fetched).
DEFAULT_BHUKY_CSV: Final[Path] = Path(
    "datasets/ephemeral/bhukyavenkatamahesh-pc/2024/results.csv"
)

#: Where the bhukyavenkatamahesh 2019 snapshot lives on disk
#: (PR-PC-LS2019 of the 2026-06-10 plan). Per Q3 commit policy this
#: file IS committed (operator-snapshotted on 2026-06-11 from
#: ``raw.githubusercontent.com/bhukyavenkatamahesh/election-viz/main/
#: Data/results/results_2019.csv``). The 2019 file is comma-delimited
#: with a DIFFERENT column schema vs the 2024 file (the publisher
#: refactored the CSV between vintages); see _read_bhuky_2019_winners.
DEFAULT_BHUKY_CSV_2019: Final[Path] = Path(
    "datasets/ephemeral/bhukyavenkatamahesh-pc/2019/results.csv"
)

#: bhukyavenkatamahesh publisher edition pin. Per ADR-0042 (publisher
#: edition anchor) this is the file's stated cutoff. Back-compat name
#: for the 2024 vintage; PR-PC-LS2019 adds the parallel
#: BHUKY_VINTAGE_2019 constant rather than renaming.
BHUKY_VINTAGE: Final[str] = "2024"

#: bhukyavenkatamahesh 2019 publisher edition pin (PR-PC-LS2019).
BHUKY_VINTAGE_2019: Final[str] = "2019"

#: Adapter source-id used as the ShapeARow.external_scope on emitted rows.
BHUKY_SCOPE: Final[str] = "bhukyavenkatamahesh-pc"


#: bhukyavenkatamahesh publisher state name -> yen-gov state slug remaps
#: where the lookup against ``state_codes.csv`` would not match
#: (publisher's "NCT OF Delhi" vs canonical "Delhi"; "Dadra & Nagar
#: Haveli and Daman & Diu" with ampersands; etc.). All other state
#: names match via the case-insensitive ``state_codes.csv`` lookup.
_BHUKY_STATE_SLUG_REMAP: Final[dict[str, str]] = {
    "NCT OF DELHI": "delhi",
    "DADRA & NAGAR HAVELI AND DAMAN & DIU": "dadra-and-nagar-haveli-and-daman-and-diu",
    "ANDAMAN & NICOBAR ISLANDS": "andaman-and-nicobar-islands",
    "JAMMU AND KASHMIR": "jammu-and-kashmir",
}


#: bhukyavenkatamahesh publisher constituency name -> yen-gov canonical
#: name spelling fixes for the 2024 vintage (4 known cases per the
#: 2026-06-11 join-audit). Applied to UPPER-cased input; output is
#: also UPPER. Empty when not present in this map (fall through to
#: direct UPPER match). Canonical 2024 spellings reflect post-2024
#: ECI / TCPD spellings: PALAMU (was PALAMAU pre-2024), ARAMBAG
#: (was ARAMBAGH pre-2024), JAYNAGAR (was JOYNAGAR pre-2024),
#: SREERAMPUR (was SRERAMPUR pre-2024).
_BHUKY_CONSTITUENCY_NAME_REMAP: Final[dict[tuple[str, str], str]] = {
    ("jharkhand", "PALAMAU"): "PALAMU",
    ("west-bengal", "ARAMBAGH"): "ARAMBAG",
    ("west-bengal", "JOYNAGAR"): "JAYNAGAR",
    ("west-bengal", "SRERAMPUR"): "SREERAMPUR",
}

#: bhukyavenkatamahesh publisher constituency name -> yen-gov canonical
#: name spelling fixes for the 2019 vintage (PR-PC-LS2019). 2 known
#: cases per the 2026-06-11 join-audit (424 of 426 canonical 2019 PCs
#: matched directly on UPPER name; the remaining 2 needed remap):
#: bhuky 'SAMASTIPUR (SC)' carries the reservation suffix that
#: canonical 2019 drops; bhuky 'JOYNAGAR' was renamed JAYNAGAR
#: post-2024 but canonical 2019 also already uses JAYNAGAR. The
#: per-year split is necessary because canonical 2019 keeps several
#: pre-2024 spellings (ARAMBAGH / PALAMAU / SRERAMPUR / etc.) that
#: the 2024 remap above explicitly rewrites - applying the 2024
#: remap to 2019 would BREAK the join. See _read_bhuky_2019_winners.
_BHUKY_CONSTITUENCY_NAME_REMAP_2019: Final[dict[tuple[str, str], str]] = {
    ("bihar", "SAMASTIPUR (SC)"): "SAMASTIPUR",
    ("west-bengal", "JOYNAGAR"): "JAYNAGAR",
}


#: Non-numeric placeholders the publisher uses in the ``Votes`` cell.
#: Mapped to None per shape-A v1.1 ``winner_votes`` schema (the
#: 'Unopposed' reservation - e.g. Surat LS-2024). The PR-PC-LS2024
#: snapshot ships ONE such row: S06 (Gujarat) CID 2 = SURAT with the
#: truncated 'Unconteste' literal in the Votes cell. Reservation
#: preserved here to be tolerant of future snapshots that may use
#: variant spellings.
_VOTES_PLACEHOLDERS: Final[frozenset[str]] = frozenset({
    "Unconteste",
    "Uncontested",
    "-",
    "--",
    "NA",
    "N/A",
    "",
})


def _slugify(s: str) -> str:
    """Lowercase + ASCII-only + collapse whitespace to hyphens.

    Used to derive a candidate state slug from the publisher's free-text
    State cell when no remap or alias hits. Mirrors the simple slug
    convention used across yen-gov entity slugs (no transliteration of
    non-ASCII; the bhukyavenkatamahesh file is ASCII).
    """
    s = re.sub(r"&", "and", s)
    s = re.sub(r"[^A-Za-z0-9 ]+", " ", s).strip()
    s = re.sub(r"\s+", "-", s).lower()
    return s


@dataclass(frozen=True, slots=True)
class _StateIndex:
    """Lightweight index over state_codes.csv for adapter-side matching."""

    by_upper_name: dict[str, str]  # UPPER(lgd_name) -> slug
    by_iso: dict[str, str]  # iso_3166_2 -> slug
    by_alias: dict[str, str]  # UPPER(alias) -> slug
    by_slug: set[str]  # set of all slugs


def _load_state_index(state_codes_csv: Path) -> _StateIndex:
    """Build the state-name -> slug index from state_codes.csv.

    Indexes lgd_name (UPPER) + iso_3166_2 + aliases (pipe-split, UPPER)
    + slug. Caller looks up in priority order:
      1. UPPER remap (publisher-name special case).
      2. UPPER(publisher-name) against ``by_upper_name``.
      3. UPPER(publisher-name) against ``by_alias``.
      4. ``by_slug`` to validate a slug-shaped name.
      5. ``_slugify(publisher-name)`` against ``by_slug``.
    """
    by_upper_name: dict[str, str] = {}
    by_iso: dict[str, str] = {}
    by_alias: dict[str, str] = {}
    by_slug: set[str] = set()
    if not state_codes_csv.exists():
        return _StateIndex(
            by_upper_name=by_upper_name,
            by_iso=by_iso,
            by_alias=by_alias,
            by_slug=by_slug,
        )
    with state_codes_csv.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            slug_v = (row.get("slug") or "").strip()
            if not slug_v:
                continue
            by_slug.add(slug_v)
            name_upper = (row.get("lgd_name") or "").strip().upper()
            if name_upper:
                by_upper_name[name_upper] = slug_v
            iso = (row.get("iso_3166_2") or "").strip()
            if iso:
                by_iso[iso] = slug_v
            aliases_raw = (row.get("aliases") or "").strip()
            if aliases_raw:
                for alias in aliases_raw.split("|"):
                    a_upper = alias.strip().upper()
                    if a_upper:
                        by_alias[a_upper] = slug_v
    return _StateIndex(
        by_upper_name=by_upper_name,
        by_iso=by_iso,
        by_alias=by_alias,
        by_slug=by_slug,
    )


def _resolve_state_slug(publisher_state: str, ix: _StateIndex) -> str | None:
    """Resolve the publisher's free-text State cell to a yen-gov slug.

    Priority: remap -> by_upper_name -> by_alias -> by_slug ->
    _slugify -> None. Returns ``None`` on miss; caller (the adapter
    main loop) MAY skip the row + log + carry on (the verdict.csv
    will simply lack a row for that constituency, which is a citizen-
    surfaceable signal that yen-gov has no slug for the publisher's
    state spelling - typically an indicator the operator should
    extend the remap dict).
    """
    upper = publisher_state.strip().upper()
    if not upper:
        return None
    hit = _BHUKY_STATE_SLUG_REMAP.get(upper)
    if hit:
        return hit
    hit = ix.by_upper_name.get(upper)
    if hit:
        return hit
    hit = ix.by_alias.get(upper)
    if hit:
        return hit
    candidate = _slugify(publisher_state)
    if candidate in ix.by_slug:
        return candidate
    return None


def _parse_votes(raw: str) -> int | None:
    """Parse the publisher's ``Votes`` cell to int or None.

    None reserved for ECI 'Unopposed' rows where vote count is not
    reported (PR-PC-LS2024 snapshot: Surat LS-2024 Mukesh Dalal
    declared elected unopposed). Per shape-A v1.1 the field is
    nullable integer; the per-PC aggregator's verdict logic operates
    on winner_party_id, NOT vote count, so None is safe.
    """
    s = (raw or "").strip()
    if s in _VOTES_PLACEHOLDERS:
        return None
    try:
        return int(s)
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class _PartiesIndex:
    """Index over parties.csv for adapter-side full-name + alias matching.

    bhukyavenkatamahesh uses FULL party names (e.g. "Bharatiya Janata
    Party" / "Yuvajana Sramika Rythu Congress Party"). The canonical
    resolver only indexes ``short`` + ``aliases`` + ECI codes; full
    names are NOT in the resolver's by_alias map. So this adapter
    builds its own ``by_full_upper`` index over parties.csv full
    column, and falls back to the resolver's by_alias on a full-name
    miss (the resolver carries the publisher's short via the
    aliases column for the parties.csv rows PR-W-1 enriched).
    """

    by_full_upper: dict[str, str]
    by_alias_upper: dict[str, str]
    by_party_id: set[str]


def _load_parties_index(parties_csv: Path) -> _PartiesIndex:
    """Build the party full-name + alias index from parties.csv.

    The full-name index folds parenthesised qualifiers (e.g.
    "Communist Party of India  (Marxist)" -> "COMMUNIST PARTY OF
    INDIA MARXIST") so the publisher's variant spellings hit the
    canonical row. The alias index lifts every short + every
    pipe-split alias UPPER.
    """
    by_full_upper: dict[str, str] = {}
    by_alias_upper: dict[str, str] = {}
    by_party_id: set[str] = set()
    if not parties_csv.exists():
        return _PartiesIndex(
            by_full_upper=by_full_upper,
            by_alias_upper=by_alias_upper,
            by_party_id=by_party_id,
        )
    with parties_csv.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            pid = (row.get("party_id") or "").strip()
            if not pid:
                continue
            by_party_id.add(pid)
            full = (row.get("full") or "").strip()
            if full:
                key = _normalise_party_name(full)
                if key:
                    by_full_upper.setdefault(key, pid)
            short = (row.get("short") or "").strip().upper()
            if short:
                by_alias_upper.setdefault(short, pid)
            aliases_raw = (row.get("aliases") or "").strip()
            if aliases_raw:
                for alias in aliases_raw.split("|"):
                    a = alias.strip().upper()
                    if a:
                        by_alias_upper.setdefault(a, pid)
    return _PartiesIndex(
        by_full_upper=by_full_upper,
        by_alias_upper=by_alias_upper,
        by_party_id=by_party_id,
    )


def _normalise_party_name(s: str) -> str:
    """Normalise a party full-name for cross-publisher matching.

    UPPER + strip non-alphanumeric (parens, hyphens, dots) + collapse
    whitespace. Matches the same normalisation strategy PR-W-1 +
    PR-W-3 use (see ``recon/adapters/tcpd_parties.py::_normalise_full_name``).
    Keeps "Communist Party of India (Marxist)" matchable to
    "COMMUNIST PARTY OF INDIA M" + a future variant via the canonical
    aliases column.
    """
    s = re.sub(r"[^A-Za-z0-9]+", " ", (s or "").upper()).strip()
    return re.sub(r"\s+", " ", s)


#: Bhukyavenkatamahesh publisher party-name strings that the adapter
#: MUST recognise as NOTA / Independent regardless of canonical alias
#: hits. Kept tiny + explicit per CLAUDE.md section 6 "no hardcoding":
#: this is publisher-string-resolution logic, NOT canonical taxonomy.
_BHUKY_NOTA_NAMES: Final[frozenset[str]] = frozenset({"NONE OF THE ABOVE", "NOTA"})
_BHUKY_IND_NAMES: Final[frozenset[str]] = frozenset({"INDEPENDENT"})


def _resolve_party_id(
    publisher_party_full: str, ix: _PartiesIndex
) -> str:
    """Resolve a publisher's full party name to a canonical party_id.

    Returns ``parties.IN.UNK`` on miss per the lenient-resolution
    contract (CLAUDE.md section 10 "no silent demotion"). The per-PC
    aggregator surfaces UNK winner_party_id rows in the verdict.csv
    as DISPUTED so the curator knows to add an alias to parties.csv.

    Priority:
      1. Sentinel match (NOTA / Independent special cases).
      2. UPPER normalised by_full_upper.
      3. UPPER raw against by_alias_upper.
      4. ``parties.IN.UNK`` fallback.
    """
    raw = (publisher_party_full or "").strip()
    if not raw:
        return "parties.IN.UNK"
    upper_raw = raw.upper()
    if upper_raw in _BHUKY_NOTA_NAMES:
        return "parties.IN.NOTA"
    if upper_raw in _BHUKY_IND_NAMES:
        return "parties.IN.IND"
    full_key = _normalise_party_name(raw)
    if full_key:
        hit = ix.by_full_upper.get(full_key)
        if hit is not None:
            return hit
    # Bhuky carries full names not abbreviations, but a defensive
    # alias-lookup helps when the publisher used a short (e.g. for
    # smaller parties their CSV sometimes carries acronyms).
    hit = ix.by_alias_upper.get(upper_raw)
    if hit is not None:
        return hit
    return "parties.IN.UNK"


@dataclass(frozen=True, slots=True)
class _BhukyPcWinner:
    """In-memory projection of one PC's winner from the bhuky snapshot."""

    publisher_state: str
    publisher_constituency: str
    state_slug: str
    constituency_name_upper: str
    party_full: str
    candidate: str
    votes: int | None


def _read_bhuky_winners(
    bhuky_csv: Path, state_ix: _StateIndex
) -> list[_BhukyPcWinner]:
    """Read the bhuky 2024 CSV + derive the max-Votes winner per (state, PC).

    The 2024 snapshot has one row per candidate; the winner is the
    max-Votes row per ``(publisher_state, publisher_constituency)``
    group. Constituencies whose state cannot be resolved to a slug are
    skipped (caller may inspect the returned list count vs the
    snapshot's 543-PC universe to detect a regression).

    2024-only: the CSV is semicolon-delimited with columns
    ``State;Constituency;Party;Candidate;Votes;State ID;Constituency ID``.
    For the 2019 vintage see ``_read_bhuky_2019_winners`` (the publisher
    refactored the CSV between vintages; PR-PC-LS2019 adds the parallel
    reader rather than overloading this one).
    """
    rows: list[dict[str, str]] = []
    with bhuky_csv.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh, delimiter=";"):
            rows.append(r)

    by_pc: dict[tuple[str, str], list[dict[str, str]]] = {}
    for r in rows:
        st = (r.get("State") or "").strip()
        cn = (r.get("Constituency") or "").strip()
        if not st or not cn:
            continue
        by_pc.setdefault((st, cn), []).append(r)

    winners: list[_BhukyPcWinner] = []
    for (st_pub, cn_pub), grp in by_pc.items():
        # Pick max-Votes row; "Uncontested" / placeholder rows fall to
        # the end because their parsed votes is -1 (the placeholder
        # sentinel). The Surat row is one such case: only one candidate
        # row, Votes='Unconteste'; the group still has a deterministic
        # winner.
        def _votes_for_sort(row: dict[str, str]) -> int:
            v = _parse_votes(row.get("Votes") or "")
            return v if v is not None else -1

        winner_row = max(grp, key=_votes_for_sort)
        slug = _resolve_state_slug(st_pub, state_ix)
        if slug is None:
            # State unresolvable to a yen-gov slug; skip + log via the
            # caller's return count delta. No exception (the snapshot
            # is hand-curated; a missing state is a remap-extension
            # signal, not a fatal data event).
            continue
        # Apply the constituency-name spelling remap (4 known cases).
        cn_upper_raw = cn_pub.upper()
        cn_upper = _BHUKY_CONSTITUENCY_NAME_REMAP.get(
            (slug, cn_upper_raw), cn_upper_raw
        )
        winners.append(
            _BhukyPcWinner(
                publisher_state=st_pub,
                publisher_constituency=cn_pub,
                state_slug=slug,
                constituency_name_upper=cn_upper,
                party_full=(winner_row.get("Party") or "").strip(),
                candidate=(winner_row.get("Candidate") or "").strip(),
                votes=_parse_votes(winner_row.get("Votes") or ""),
            )
        )
    return winners


def _emit_shape_a_for_winner(
    winner: _BhukyPcWinner,
    parties_ix: _PartiesIndex,
    constituency_no: str,
    *,
    vintage: str = BHUKY_VINTAGE,
) -> ShapeARow:
    """Emit a single per-PC shape-A row for one bhuky-derived winner.

    The proposed_party_id is resolved via the parties index (fall-back
    to ``parties.IN.UNK`` on miss). The shape-A row's external_key
    follows the convention ``<state_slug>:<constituency_no>:<UPPER_NAME>``
    so a curator inspecting the verdict.csv can trace back to the
    publisher row deterministically.

    For shape-A rows where the resolution lands on ``parties.IN.UNK``,
    proposed_action = ``mint-new`` (the publisher named a party that
    canonical does not carry; per Q1 / Wave 0 Hans verdict, the
    curator decides whether to mint or to add an alias). For all
    other resolutions, proposed_action = ``match`` (the per-PC
    aggregator's verdict is structural by oracle agreement, not by
    per-row action precedence).

    The ``vintage`` keyword is the bhukyavenkatamahesh publisher
    edition pin per ADR-0042. Defaults to ``BHUKY_VINTAGE`` (=
    ``"2024"``) for back-compat with existing 2024 callers;
    PR-PC-LS2019 passes ``BHUKY_VINTAGE_2019`` for the 2019 vintage.
    """
    pid = _resolve_party_id(winner.party_full, parties_ix)
    action = "mint-new" if pid == "parties.IN.UNK" else "match"

    return ShapeARow(
        external_key=(
            f"{winner.state_slug}:{constituency_no}:"
            f"{winner.constituency_name_upper}"
        ),
        external_short=winner.party_full[:64],  # publisher full as the short
        external_full=winner.party_full,
        external_scope=BHUKY_SCOPE,
        external_vintage=vintage,
        proposed_party_id=pid,
        proposed_action=action,  # type: ignore[arg-type]
        notes=(
            f"bhuky publisher: state={winner.publisher_state!r} "
            f"constituency={winner.publisher_constituency!r}"
        ),
        constituency_no=constituency_no,
        constituency_name=winner.constituency_name_upper,
        state_code=winner.state_slug,
        winner_candidate=winner.candidate,
        winner_votes=winner.votes,
    )


def _read_bhuky_2019_winners(
    bhuky_csv: Path, state_ix: _StateIndex
) -> list[_BhukyPcWinner]:
    """Read the bhuky 2019 CSV + derive the max-total_votes winner per PC.

    PR-PC-LS2019 parallel reader. The 2019 snapshot is comma-delimited
    with a different column schema vs the 2024 reader
    (``_read_bhuky_winners``): the publisher refactored the CSV format
    between vintages.

    2019 schema columns:
      ``province_id, province_name, constituency_id, constituency_name,
       type, osn, candidate_name, party_name, evm_votes, postal_votes,
       total_votes, vote_share``

    The winner row per PC is the max-``total_votes`` candidate (per ECI
    convention - postal + EVM totals already summed in the publisher's
    ``total_votes`` column). Constituencies whose state cannot be
    resolved to a slug are skipped.

    Two 2019-specific publisher quirks the reader handles:
      - ``province_name`` carries HTML-encoded ampersands
        (``Andaman &amp; Nicobar Islands``); the reader runs
        ``html.unescape`` before state-slug resolution so the existing
        ``_BHUKY_STATE_SLUG_REMAP`` (keyed on decoded UPPER form)
        applies cleanly. The 2024 reader doesn't need this because
        the 2024 CSV is plain ASCII.
      - the 2019 constituency-name remap dict
        ``_BHUKY_CONSTITUENCY_NAME_REMAP_2019`` is applied (NOT the
        2024 remap, which would BREAK the 2019 join - canonical 2019
        kept several pre-2024 spellings).
    """
    rows: list[dict[str, str]] = []
    with bhuky_csv.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh, delimiter=","):
            rows.append(r)

    by_pc: dict[tuple[str, str], list[dict[str, str]]] = {}
    for r in rows:
        st = html.unescape((r.get("province_name") or "").strip())
        cn = (r.get("constituency_name") or "").strip()
        if not st or not cn:
            continue
        by_pc.setdefault((st, cn), []).append(r)

    winners: list[_BhukyPcWinner] = []
    for (st_pub, cn_pub), grp in by_pc.items():
        def _votes_for_sort(row: dict[str, str]) -> int:
            v = _parse_votes(row.get("total_votes") or "")
            return v if v is not None else -1

        winner_row = max(grp, key=_votes_for_sort)
        slug = _resolve_state_slug(st_pub, state_ix)
        if slug is None:
            # State unresolvable to a yen-gov slug; skip. Operator
            # extends _BHUKY_STATE_SLUG_REMAP if this fires.
            continue
        cn_upper_raw = cn_pub.upper()
        cn_upper = _BHUKY_CONSTITUENCY_NAME_REMAP_2019.get(
            (slug, cn_upper_raw), cn_upper_raw
        )
        # html.unescape on party_name + candidate_name (mirrors the
        # province_name decode) so publisher strings like
        # 'Jammu &amp; Kashmir National Conference' resolve against
        # canonical's plain-ampersand 'Jammu & Kashmir National
        # Conference' full-name.
        winners.append(
            _BhukyPcWinner(
                publisher_state=st_pub,
                publisher_constituency=cn_pub,
                state_slug=slug,
                constituency_name_upper=cn_upper,
                party_full=html.unescape(
                    (winner_row.get("party_name") or "").strip()
                ),
                candidate=html.unescape(
                    (winner_row.get("candidate_name") or "").strip()
                ),
                votes=_parse_votes(winner_row.get("total_votes") or ""),
            )
        )
    return winners


def _yen_gov_pc_no_index(elections_root: Path, year: int) -> dict[
    tuple[str, str], str
]:
    """Build a (state_slug, constituency_name_upper) -> constituency_no map.

    Reads ``datasets/elections/parliament/election=<year>/summary.csv``
    + derives ``constituency_no`` from the ``entity_id`` column
    (format ``IN-PC-2008-<state>-<eci_no>`` per the canonical
    entity-id grammar). The publisher's free-text constituency name
    is joined to this index to derive the SAME numeric constituency_no
    yen-gov uses, so the per-PC aggregator's grouping key
    ``(state_code, constituency_no)`` is consistent across oracles.

    A bhuky winner that does not match any yen-gov PC by
    ``(state_slug, constituency_name_upper)`` is emitted with
    ``constituency_no = "?"`` so the aggregator's grouping still
    surfaces it (as a single-oracle UNVERIFIED row); operator
    inspects the verdict.csv to discover the spelling drift.
    """
    summary_csv = (
        elections_root
        / "elections"
        / "parliament"
        / f"election={year}"
        / "summary.csv"
    )
    if not summary_csv.exists():
        return {}
    by_pc: dict[tuple[str, str], str] = {}
    with summary_csv.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            state = (r.get("state") or "").strip()
            cn = (r.get("constituency_name") or "").strip().upper()
            entity_id = (r.get("entity_id") or "").strip()
            if not state or not cn or not entity_id:
                continue
            # entity_id format: IN-PC-2008-<state>-<eci_no>; final
            # token after rsplit('-', 1) is the constituency_no.
            try:
                pc_no = entity_id.rsplit("-", 1)[1]
            except IndexError:
                continue
            by_pc[(state, cn)] = pc_no
    return by_pc


@dataclass(frozen=True, slots=True)
class BhukyavenkatamaheshPcAdapter:
    """The PR-PC-LS2024 adapter; registered against
    ``recon.adapters.REGISTRY['bhukyavenkatamahesh-pc']`` at module
    import time.

    Signature matches ``ParityAdapter`` Protocol (recon/adapters/
    __init__.py). The state / event / kind kwargs are accepted: state
    is None for national LS event; event is required (e.g.
    'LsGenJun2024') so the adapter can parse the year for the
    yen-gov pc-no index lookup; kind MUST be 'parliament' when set
    (defensive guard - this adapter only handles parliament data).
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
        del state  # unused: bhuky compilation is national.
        del vintage  # CLI passes event year (e.g. '2024'); adapter
        # always emits with its own publisher-edition pin
        # (BHUKY_VINTAGE or BHUKY_VINTAGE_2019).
        if kind and kind != "parliament":
            raise ValueError(
                f"bhukyavenkatamahesh-pc adapter only supports kind "
                f"'parliament'; got {kind!r}"
            )
        # Derive year from event id (e.g. LsGenJun2024 -> 2024,
        # LsGenApr2019 -> 2019) or default to the 2024 vintage pin.
        year = self._parse_year_from_event(event) or int(BHUKY_VINTAGE)

        # Per-year dispatch: 2019 has a different CSV path + a
        # different column schema (the publisher refactored the file
        # between vintages). 2024 is the default + legacy path.
        if year == 2019:
            bhuky_csv = root / DEFAULT_BHUKY_CSV_2019
            reader = _read_bhuky_2019_winners
            emit_vintage = BHUKY_VINTAGE_2019
        else:
            bhuky_csv = root / DEFAULT_BHUKY_CSV
            reader = _read_bhuky_winners
            emit_vintage = BHUKY_VINTAGE

        if not bhuky_csv.exists():
            raise FileNotFoundError(
                f"bhukyavenkatamahesh PC snapshot not found at "
                f"{bhuky_csv.as_posix()!r}; operator drops the upstream "
                f"file (committed to git per Q3 policy)."
            )

        parties_csv = root / "datasets" / "data" / "entities" / "parties.csv"
        state_codes_csv = (
            root / "datasets" / "data" / "entities" / "state_codes.csv"
        )

        state_ix = _load_state_index(state_codes_csv)
        parties_ix = _load_parties_index(parties_csv)

        winners = reader(bhuky_csv, state_ix)
        pc_no_index = _yen_gov_pc_no_index(root / "datasets", year)

        out: list[ShapeARow] = []
        for winner in sorted(
            winners,
            key=lambda w: (w.state_slug, w.constituency_name_upper),
        ):
            # Prefer canonical's cno (LGD PC code); on miss, fall back
            # to a deterministic synthetic key derived from the
            # constituency name. tcpd-pc applies the SAME fallback so
            # canonical-missing PCs (Telangana, Delhi, A&N, Chandigarh,
            # D&N+D&D, Lakshadweep, Puducherry, etc.) end up in the same
            # per-PC aggregator group as a 2-oracle (bhuky+tcpd)
            # comparison rather than collapsing into per-state '?'
            # buckets that lose row identity.
            cno = pc_no_index.get(
                (winner.state_slug, winner.constituency_name_upper)
            )
            if cno is None:
                cno = f"name-{winner.constituency_name_upper}"
            out.append(
                _emit_shape_a_for_winner(
                    winner, parties_ix, cno, vintage=emit_vintage
                )
            )
        return out

    @staticmethod
    def _parse_year_from_event(event: str | None) -> int | None:
        """Extract the 4-digit year from an event id like 'LsGenJun2024'.

        Returns None when ``event`` is None or carries no 4-digit
        suffix. The adapter's caller (the per-PC CLI) falls back to
        the vintage pin in that case.
        """
        if not event:
            return None
        m = re.search(r"(\d{4})$", event)
        if m:
            return int(m.group(1))
        return None


#: Module-level singleton; recon.adapters.__init__ registers this in REGISTRY.
ADAPTER: Final[BhukyavenkatamaheshPcAdapter] = BhukyavenkatamaheshPcAdapter()


__all__ = [
    "ADAPTER",
    "BHUKY_VINTAGE",
    "BHUKY_VINTAGE_2019",
    "BHUKY_SCOPE",
    "DEFAULT_BHUKY_CSV",
    "DEFAULT_BHUKY_CSV_2019",
    "BhukyavenkatamaheshPcAdapter",
    "_BHUKY_STATE_SLUG_REMAP",
    "_BHUKY_CONSTITUENCY_NAME_REMAP",
    "_BHUKY_CONSTITUENCY_NAME_REMAP_2019",
    "_load_state_index",
    "_load_parties_index",
    "_normalise_party_name",
    "_parse_votes",
    "_PartiesIndex",
    "_read_bhuky_winners",
    "_read_bhuky_2019_winners",
    "_resolve_party_id",
    "_resolve_state_slug",
    "_StateIndex",
    "_slugify",
    "_yen_gov_pc_no_index",
]
