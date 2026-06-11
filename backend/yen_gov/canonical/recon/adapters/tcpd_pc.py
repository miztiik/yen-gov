"""TCPD All-States GE per-PC parity adapter (PR-PC-LS2024).

Reads ``datasets/ephemeral/All_States_GE.csv`` (the Trivedi Centre for
Political Data per-PC parliament compilation; one row per
(state, year, constituency, candidate) tuple, ~91k rows total) and
filters to the operator-supplied year. For each PC in the filtered set,
the adapter picks the ``Position == 1`` row as the winner and emits
one shape-A row per PC.

Per Q1 fact-class authority (plan section 0.3): TCPD is NOT
authoritative on winner_party_id (ECI wins per Holy Law #9; yen-gov
canonical is the second oracle since yen-gov derives from ECI). TCPD's
per-PC role here is corroboration: when TCPD's compilation covers the
year (1962 - 2019 only as of the 2021 cutoff; LS-2024 is NOT covered),
TCPD acts as a third oracle that promotes verified PCs to ``VERIFIED``
status and surfaces DISPUTED rows for the curator.

**Important known limitation (PR-PC-LS2024 discovery)**: the on-disk
TCPD All_States_GE.csv compilation cutoff is 2019 (per the 2021 file
edition pin). When the adapter is invoked with year=2024, it returns
an EMPTY shape-A row list (logged via stderr) and the parity
degrades to 2-way (yen-gov vs bhukyavenkatamahesh). This is the
expected fallback per the PR-PC-LS2024 brief's stop conditions:
"If bhukyavenkatamahesh source returns 404 or has materially
different shape - STOP and surface; the 2-way (yen-gov vs TCPD-PC)
parity is the minimum-viable fallback." The reciprocal also holds:
when TCPD lacks coverage but bhukyavenkatamahesh has it, the
2-way (yen-gov vs bhukyavenkatamahesh) parity is the minimum-viable
fallback. The adapter is year-aware + future-proof for PR-PC-LS2019
(LS-2019 is well within the TCPD compilation window).

The vintage pin is ``2021`` per ADR-0042 (publisher edition - the
TCPD compilation file name carries the cutoff).
"""

from __future__ import annotations

import csv
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from yen_gov.canonical.recon.shape_a import ShapeARow

#: Where the TCPD All-States GE compilation lives on disk.
#: Operator-managed ephemeral source (gitignored).
DEFAULT_TCPD_GE_CSV: Final[Path] = Path(
    "datasets/ephemeral/All_States_GE.csv"
)

#: TCPD compilation publisher edition pin per ADR-0042.
TCPD_GE_VINTAGE: Final[str] = "2021"

#: Adapter source-id used as the ShapeARow.external_scope on emitted rows.
TCPD_PC_SCOPE: Final[str] = "tcpd-pc"

#: TCPD compilation cutoff year - any year > this returns empty.
#: When the file is re-snapshotted with a later cutoff, bump this and
#: bump TCPD_GE_VINTAGE in lockstep.
TCPD_GE_LAST_COVERED_YEAR: Final[int] = 2019

#: TCPD State_Name -> yen-gov state slug remap. TCPD uses underscores
#: (e.g. "Andaman_&_Nicobar_Islands"); the remap normalises punctuation
#: + casing before the state_codes.csv lookup. The 4 ampersand /
#: legacy spellings below need an explicit slug because the simple
#: underscore-to-space + lower pipeline does not produce the canonical
#: slug.
_TCPD_STATE_SLUG_REMAP: Final[dict[str, str]] = {
    "ANDAMAN_&_NICOBAR_ISLANDS": "andaman-and-nicobar-islands",
    "JAMMU_&_KASHMIR": "jammu-and-kashmir",
    "DADRA_&_NAGAR_HAVELI": "dadra-and-nagar-haveli-and-daman-and-diu",
    "DAMAN_&_DIU": "dadra-and-nagar-haveli-and-daman-and-diu",
    "DADAR_NAGAR_HAVELI": "dadra-and-nagar-haveli-and-daman-and-diu",
    "DELHI": "delhi",
    "NCT_OF_DELHI": "delhi",
    "PONDICHERRY": "puducherry",
    "ORISSA": "odisha",
    "UTTARANCHAL": "uttarakhand",
}


def _slugify(s: str) -> str:
    """TCPD state-name -> yen-gov slug (helper used after the remap).

    TCPD uses underscores instead of spaces (its CSV is space-free for
    cell-quoting reasons); this helper undoes the underscores then
    falls through to the conventional slug pipeline.
    """
    s = re.sub(r"_+", " ", s or "")
    s = re.sub(r"&", "and", s)
    s = re.sub(r"[^A-Za-z0-9 ]+", " ", s).strip()
    s = re.sub(r"\s+", "-", s).lower()
    return s


@dataclass(frozen=True, slots=True)
class _StateIndex:
    """Lightweight index over state_codes.csv for adapter-side matching.

    Same shape as the bhukyavenkatamahesh adapter's _StateIndex
    (lifted for consistency; kept local to avoid an inter-adapter
    coupling that would force a refactor when one adapter's lookup
    needs change). Indexes lgd_name (UPPER) + iso + aliases (UPPER) +
    slug.
    """

    by_upper_name: dict[str, str]
    by_iso: dict[str, str]
    by_alias: dict[str, str]
    by_slug: set[str]


def _load_state_index(state_codes_csv: Path) -> _StateIndex:
    """Build the state-name -> slug index from state_codes.csv."""
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


def _resolve_state_slug(
    tcpd_state: str, ix: _StateIndex
) -> str | None:
    """Resolve TCPD's underscored state name to a yen-gov slug.

    Priority: remap UPPER -> by_upper_name (after underscore-to-space)
    -> by_alias -> by_slug -> _slugify -> None.
    """
    if not tcpd_state:
        return None
    upper_raw = tcpd_state.upper()
    hit = _TCPD_STATE_SLUG_REMAP.get(upper_raw)
    if hit:
        return hit
    spaced = re.sub(r"_+", " ", tcpd_state).upper()
    hit = ix.by_upper_name.get(spaced)
    if hit:
        return hit
    hit = ix.by_alias.get(spaced)
    if hit:
        return hit
    candidate = _slugify(tcpd_state)
    if candidate in ix.by_slug:
        return candidate
    return None


def _parse_votes(raw: str) -> int | None:
    """Parse TCPD's ``Votes`` cell to int or None.

    TCPD's compilation uses numeric cells throughout; empty / non-
    numeric falls through to None per shape-A v1.1 nullable schema.
    """
    s = (raw or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class _PartiesIndex:
    """Index over parties.csv for adapter-side full-name + alias matching.

    Lifted for adapter independence; same shape as the bhuky adapter
    (and same _normalise_party_name pipeline) so a future refactor
    could fold both into a shared canonical helper. Today the
    duplication is intentional - each adapter owns its own resolver
    contract.
    """

    by_full_upper: dict[str, str]
    by_alias_upper: dict[str, str]
    by_party_id: set[str]


def _normalise_party_name(s: str) -> str:
    """UPPER + strip non-alphanumeric + collapse whitespace."""
    s = re.sub(r"[^A-Za-z0-9]+", " ", (s or "").upper()).strip()
    return re.sub(r"\s+", " ", s)


def _load_parties_index(parties_csv: Path) -> _PartiesIndex:
    """Build the party full-name + alias index from parties.csv."""
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


#: TCPD Party shortcodes -> sentinel match. Same minimal set as
#: bhuky adapter; kept tiny per CLAUDE.md section 6.
_TCPD_NOTA_NAMES: Final[frozenset[str]] = frozenset({
    "NOTA", "NONE OF THE ABOVE",
})
_TCPD_IND_NAMES: Final[frozenset[str]] = frozenset({
    "IND", "INDEPENDENT",
})


def _resolve_party_id(
    tcpd_party: str, ix: _PartiesIndex
) -> str:
    """Resolve TCPD's Party short to a canonical party_id.

    TCPD's ``Party`` column carries SHORT codes (e.g. "INC", "BJP",
    "AIADMK"); a few rows carry the full name. Resolution path:
      1. Sentinel match (NOTA / IND).
      2. UPPER raw against by_alias_upper.
      3. UPPER normalised full against by_full_upper.
      4. ``parties.IN.UNK`` fallback.
    """
    raw = (tcpd_party or "").strip()
    if not raw:
        return "parties.IN.UNK"
    upper_raw = raw.upper()
    if upper_raw in _TCPD_NOTA_NAMES:
        return "parties.IN.NOTA"
    if upper_raw in _TCPD_IND_NAMES:
        return "parties.IN.IND"
    hit = ix.by_alias_upper.get(upper_raw)
    if hit is not None:
        return hit
    full_key = _normalise_party_name(raw)
    if full_key:
        hit = ix.by_full_upper.get(full_key)
        if hit is not None:
            return hit
    return "parties.IN.UNK"


@dataclass(frozen=True, slots=True)
class _TcpdPcWinner:
    """In-memory projection of one TCPD per-PC winner row."""

    state_slug: str
    constituency_no: str  # TCPD Constituency_No (numeric within state)
    constituency_name_upper: str
    party_short: str
    candidate: str
    votes: int | None


def _read_tcpd_winners(
    tcpd_csv: Path, year: int, state_ix: _StateIndex
) -> list[_TcpdPcWinner]:
    """Read TCPD All_States_GE.csv + filter to year + extract winners.

    Filter predicate: ``Year == str(year)`` AND ``Position == "1"``.
    Each surviving row is one PC's winner.
    """
    winners: list[_TcpdPcWinner] = []
    with tcpd_csv.open(encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            if (r.get("Year") or "").strip() != str(year):
                continue
            if (r.get("Position") or "").strip() != "1":
                continue
            tcpd_state = (r.get("State_Name") or "").strip()
            slug = _resolve_state_slug(tcpd_state, state_ix)
            if slug is None:
                continue
            cno = (r.get("Constituency_No") or "").strip()
            if not cno:
                continue
            cname = (r.get("Constituency_Name") or "").strip().upper()
            winners.append(
                _TcpdPcWinner(
                    state_slug=slug,
                    constituency_no=cno,
                    constituency_name_upper=cname,
                    party_short=(r.get("Party") or "").strip(),
                    candidate=(r.get("Candidate") or "").strip(),
                    votes=_parse_votes(r.get("Votes") or ""),
                )
            )
    return winners


def _emit_shape_a_for_winner(
    winner: _TcpdPcWinner, parties_ix: _PartiesIndex
) -> ShapeARow:
    """Emit a single per-PC shape-A row for one TCPD-derived winner.

    Same pattern as the bhuky adapter; external_key follows
    ``<state_slug>:<constituency_no>:<UPPER_NAME>``.
    """
    pid = _resolve_party_id(winner.party_short, parties_ix)
    action = "mint-new" if pid == "parties.IN.UNK" else "match"
    return ShapeARow(
        external_key=(
            f"{winner.state_slug}:{winner.constituency_no}:"
            f"{winner.constituency_name_upper}"
        ),
        external_short=winner.party_short[:64],
        external_full=winner.party_short,  # TCPD uses short as full
        external_scope=TCPD_PC_SCOPE,
        external_vintage=TCPD_GE_VINTAGE,
        proposed_party_id=pid,
        proposed_action=action,  # type: ignore[arg-type]
        notes=(
            f"tcpd publisher: state_slug={winner.state_slug!r} "
            f"cno={winner.constituency_no!r}"
        ),
        constituency_no=winner.constituency_no,
        constituency_name=winner.constituency_name_upper,
        state_code=winner.state_slug,
        winner_candidate=winner.candidate,
        winner_votes=winner.votes,
    )


@dataclass(frozen=True, slots=True)
class TcpdPcAdapter:
    """The PR-PC-LS2024 TCPD per-PC adapter; registered against
    ``recon.adapters.REGISTRY['tcpd-pc']`` at module import time.

    Year-aware: parses the year from the ``--event`` flag (e.g.
    'LsGenJun2024' -> 2024) and filters TCPD rows accordingly. Years
    outside the compilation window (> 2019 per TCPD_GE_LAST_COVERED_YEAR)
    return an empty shape-A list with a one-line stderr notice; the
    parity-pc CLI degrades the verdict count to 2-way per the
    PR-PC-LS2024 brief's stop conditions.
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
        del state  # unused: TCPD compilation is national.
        del vintage  # CLI passes event year (e.g. '2024'); adapter
        # always emits with its own publisher-edition pin TCPD_GE_VINTAGE.
        if kind and kind != "parliament":
            raise ValueError(
                f"tcpd-pc adapter only supports kind 'parliament'; "
                f"got {kind!r}"
            )
        year = self._parse_year_from_event(event) or int(TCPD_GE_VINTAGE)

        if year > TCPD_GE_LAST_COVERED_YEAR:
            # Out-of-window degrade: log + return empty. Parity-pc CLI
            # then runs 2-way (yen-gov vs whatever other oracles
            # remain in --sources). NOT an exception: this is the
            # documented brief fallback for LS-2024.
            sys.stderr.write(
                f"tcpd-pc: requested year {year} is beyond TCPD "
                f"compilation cutoff {TCPD_GE_LAST_COVERED_YEAR}; "
                f"returning empty shape-A row list (parity degrades "
                f"to 2-way).\n"
            )
            return []

        tcpd_csv = root / DEFAULT_TCPD_GE_CSV
        if not tcpd_csv.exists():
            raise FileNotFoundError(
                f"TCPD All-States GE CSV not found at "
                f"{tcpd_csv.as_posix()!r}; operator drops the upstream "
                f"file (gitignored ephemeral)."
            )

        parties_csv = root / "datasets" / "data" / "entities" / "parties.csv"
        state_codes_csv = (
            root / "datasets" / "data" / "entities" / "state_codes.csv"
        )

        state_ix = _load_state_index(state_codes_csv)
        parties_ix = _load_parties_index(parties_csv)

        winners = _read_tcpd_winners(tcpd_csv, year, state_ix)

        out: list[ShapeARow] = []
        for w in sorted(
            winners,
            key=lambda w: (w.state_slug, w.constituency_no, w.constituency_name_upper),
        ):
            out.append(_emit_shape_a_for_winner(w, parties_ix))
        return out

    @staticmethod
    def _parse_year_from_event(event: str | None) -> int | None:
        """Extract the 4-digit year from an event id."""
        if not event:
            return None
        m = re.search(r"(\d{4})$", event)
        if m:
            return int(m.group(1))
        return None


#: Module-level singleton; recon.adapters.__init__ registers in REGISTRY.
ADAPTER: Final[TcpdPcAdapter] = TcpdPcAdapter()


__all__ = [
    "ADAPTER",
    "DEFAULT_TCPD_GE_CSV",
    "TCPD_GE_VINTAGE",
    "TCPD_PC_SCOPE",
    "TCPD_GE_LAST_COVERED_YEAR",
    "TcpdPcAdapter",
    "_TCPD_STATE_SLUG_REMAP",
    "_PartiesIndex",
    "_StateIndex",
    "_load_parties_index",
    "_load_state_index",
    "_normalise_party_name",
    "_parse_votes",
    "_read_tcpd_winners",
    "_resolve_party_id",
    "_resolve_state_slug",
    "_slugify",
]
