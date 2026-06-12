"""TCPD per-party catalogue UNK correlator (PR-Q2).

Reads ``datasets/ephemeral/TCPD-PoliticalPartiesIndia_1962_2021.csv`` (the
TCPD per-party metadata catalogue) - NOT the per-candidacy AE/GE panels
that PR #952 (``tools/correlate_unk_via_tcpd``) consumes. The catalogue
carries stronger metadata than the per-candidacy panel:

  - ``Party_Name`` (full name, sometimes parenthesized faction variants)
  - ``Party_Type`` (National Party / State-based Party / Local Party)
  - ``Frequent_Abbreviation`` (preferred short form)
  - ``Last_Abbreviation`` (most-recent ECI label)
  - ``Abbreviations`` (pipe-list of every historical variant)
  - ``State_Name`` ("All_States" for nationwide parties; else the LGD
    state name TCPD uses) - used for collision disambiguation.
  - ``Start_Year`` / ``Last_Year`` (active window 1962-2021) - used for
    collision disambiguation.

The brief at ``TODO/2026-06-12-pr-q2-tcpd-catalogue-correlator.md`` lays
out the two buckets:

  - **B1**: UNK label matches ``Party_Name`` (upper-cased) directly. The
    publisher emitted the full name verbatim.
  - **B2**: UNK label matches any of ``Frequent_Abbreviation`` /
    ``Last_Abbreviation`` / ``Abbreviations[]`` (upper-cased). The
    publisher emitted an abbreviated form.

For each match:

  1. Filter out TCPD placeholder rows (``Party_Name == "NA'S"`` or
     ``Party_Name == "EXPANDED PARTY NAME NOT RELEASED BY THE ECI"``).
     These are TCPD's sentinel rows and MUST NOT be used as the source-
     of-truth for any mint.
  2. If one candidate ``Party_ID`` remains -> singleton resolution.
  3. If multiple candidate ``Party_ID``s remain -> try collision
     disambiguation:
       a. **State-match**: every OUR state must be covered by exactly
          one candidate ``Party_ID``. ``All_States`` covers every state.
       b. **Year-match**: when multiple candidate ``Party_ID``s cover
          OUR states, the UNK row's ``election_year`` must fall in
          ``[Start_Year, Last_Year]`` for exactly one of them.
  4. Map the resolved TCPD ``Party_ID`` to a parties.csv row:
       a. Walk TCPD's preferred abbreviations (``Frequent_Abbreviation``
          first, then ``Last_Abbreviation``, then ``Abbreviations[]``).
       b. Look each up against parties.csv ``short`` / ``aliases``
          (upper-cased).
       c. If a hit exists AND the existing row's ``full`` is compatible
          with TCPD's ``Party_Name`` (case-insensitive after light
          normalisation: trim, collapse whitespace) -> ``alias-add``.
       d. If a hit exists BUT ``full`` is incompatible (genuinely
          different parties sharing an abbreviation, e.g. TCPD's
          ``ADS`` = ``APNA DAL (SAUTANTRYA)`` vs our existing
          ``parties.IN.ADS`` = ``APNA DAL (SONEYLAL)``) -> ``mint-new``
          with a disambiguated slug.
       e. If no hit exists -> ``mint-new`` with the TCPD-preferred
          abbreviation as the slug.

Output:

  - ``datasets/ephemeral/party-parity/tcpd-catalogue/<run-id>/verdict.csv``
    - one row per resolved UNK label. Schema is a SUPERSET of PR #952's
    ``correlate_unk_via_tcpd`` verdict schema so the existing apply
    tool (``tools.correlate_unk_apply``) consumes it without code
    changes. Extra columns: ``bucket`` (``B1`` / ``B2``),
    ``tcpd_state_disambiguation`` (``singleton`` / ``state-match`` /
    ``year-match``), ``tcpd_start_year``, ``tcpd_last_year``.
  - ``.../skipped.csv`` - one row per UNK label we could NOT resolve
    (extra ``skip_reason`` column). The apply tool ignores this file;
    it exists so the curator can audit unresolved labels later.

Run from the repo root:

    python -m tools.correlate_unk_via_tcpd_catalogue

This is dry-run by default (writes verdict.csv + skipped.csv but does
not mutate parties.csv). The apply step is ``tools.correlate_unk_apply``
as in PR #952. See the package ``__init__.py`` docstring for the high-
level rationale.

Disambiguated-slug convention (Step 4d above):

  - When TCPD's preferred abbreviation collides with an existing
    parties.csv ``short`` for a DIFFERENT party (``full`` incompatible),
    the mint slug is ``parties.IN.<ABBR>_<STATE_ISO>`` (where
    ``STATE_ISO`` is the ISO 3166-2 code for TCPD's ``State_Name`` when
    not ``All_States``) or ``parties.IN.<ABBR>_<START_YEAR>`` as a
    fallback. The disambiguator preserves the publisher's short form
    while keeping the canonical row distinct from the colliding
    existing row.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

from yen_gov.canonical.seed.reservation_sources import (  # noqa: E402
    TCPD_STATE_NAME_TO_SLUG,
)


# --- paths ------------------------------------------------------------------

TCPD_CATALOGUE = (
    REPO_ROOT
    / "datasets"
    / "ephemeral"
    / "TCPD-PoliticalPartiesIndia_1962_2021.csv"
)
PARTIES_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "parties.csv"
STATE_ISO_SEED = (
    REPO_ROOT / "datasets" / "data" / "entities" / "state_iso_seed.csv"
)
ASSEMBLY_ROOT = REPO_ROOT / "datasets" / "elections" / "assembly"
PARLIAMENT_ROOT = REPO_ROOT / "datasets" / "elections" / "parliament"

VERDICT_ROOT = (
    REPO_ROOT / "datasets" / "ephemeral" / "party-parity" / "tcpd-catalogue"
)

UNK_PID = "parties.IN.UNK"

# TCPD placeholder rows; the catalogue uses these in lieu of a real
# Party_Name. We never use a placeholder pid as the source-of-truth for
# a mint or alias-add.
TCPD_PLACEHOLDER_NAMES: frozenset[str] = frozenset({
    "NA'S",
    "EXPANDED PARTY NAME NOT RELEASED BY THE ECI",
})

# Special-case TCPD state name meaning "this party operates across all
# states" (e.g. national parties + parties that contest in multiple
# states without a primary home state).
TCPD_ALL_STATES = "All_States"


# --- data classes -----------------------------------------------------------


@dataclass(frozen=True)
class TcpdPartyRecord:
    """One TCPD per-party catalogue record (collapsed across assemblies).

    The catalogue carries one row per ``(Assembly, State, Party_ID)``
    triple; we collapse rows for the same ``Party_ID`` by picking the
    most-recent ``(Last_Year, Start_Year)`` row for ``party_name`` /
    ``party_type`` / ``frequent_abbrev`` / ``last_abbrev``, and union
    the ``Abbreviations`` + ``State_Name`` + year-window across all
    rows. State coverage is the set of LGD slugs the party has any row
    for (after mapping via ``TCPD_STATE_NAME_TO_SLUG``); the special
    sentinel ``"*"`` is used internally when ANY row has
    ``State_Name == "All_States"``.
    """

    party_id: str
    party_name: str  # canonical (most-recent row's Party_Name)
    party_type: str  # canonical (most-recent row's Party_Type)
    frequent_abbrev: str  # canonical (most-recent row's Frequent_Abbreviation)
    last_abbrev: str  # canonical (most-recent row's Last_Abbreviation)
    all_abbrevs: tuple[str, ...]  # union of every row's Abbreviations[]
    state_slugs: frozenset[str]  # union; "*" wildcard for All_States rows
    start_year: int | None  # min Start_Year across rows
    last_year: int | None  # max Last_Year across rows

    @property
    def is_placeholder(self) -> bool:
        """True if Party_Name is a TCPD placeholder ('NA'S' / etc.)."""
        return self.party_name.upper().strip() in TCPD_PLACEHOLDER_NAMES

    def covers_state(self, state_slug: str) -> bool:
        """True if this party has any TCPD row for ``state_slug`` (or All_States)."""
        if "*" in self.state_slugs:
            return True
        return state_slug in self.state_slugs

    def covers_year(self, year: int) -> bool:
        """True if ``year`` falls in ``[start_year, last_year]`` (inclusive).

        ``last_year == 2021`` is treated as "still active forever after"
        because the TCPD catalogue's terminal vintage is 2021; the absence
        of post-2021 rows is a catalogue artefact, not a dissolution
        signal. This mirrors the apply tool's ``dissolved_year`` rule
        (don't stamp dissolution when ``Last_Year`` equals the catalogue
        boundary).
        """
        if self.start_year is None or self.last_year is None:
            # No year info -> permissive (we won't year-disambiguate this row).
            return True
        if self.last_year >= 2021:
            return self.start_year <= year
        return self.start_year <= year <= self.last_year


@dataclass
class UnkLabel:
    """Per-label aggregate of our on-disk UNK rows."""

    label: str  # UPPER, stripped
    publisher_label: str  # original case (first occurrence)
    n_rows: int = 0
    states: set[str] = field(default_factory=set)  # lgd-slug shape
    years: set[int] = field(default_factory=set)


@dataclass
class Verdict:
    """One verdict.csv or skipped.csv row."""

    external_key: str  # UPPER label (the join key)
    party_short_raw: str  # original-case publisher label
    state: str  # pipe-delim of distinct OUR states for this label
    year: str  # year range "min-max" or single
    n_rows: int
    bucket: str  # "B1" | "B2" | "" (skipped before bucket assignment)
    tcpd_party_id: str
    tcpd_party_type: str
    tcpd_party_name: str
    tcpd_frequent_abbrev: str
    tcpd_start_year: str  # str so CSV round-trips empty
    tcpd_last_year: str
    tcpd_state_disambiguation: str  # singleton | state-match | year-match
    current_party_id: str  # always parties.IN.UNK in this PR
    proposed_party_id: str
    action: str  # alias-add | mint-new (verdict) or "" (skipped)
    oracle: str  # tcpd-catalogue-B1 | tcpd-catalogue-B2 | none
    skip_reason: str  # populated on skipped.csv rows only
    curator_note: str


VERDICT_FIELDS = [
    "external_key",
    "party_short_raw",
    "state",
    "year",
    "n_rows",
    "bucket",
    "tcpd_party_id",
    "tcpd_party_type",
    "tcpd_party_name",
    "tcpd_frequent_abbrev",
    "tcpd_start_year",
    "tcpd_last_year",
    "tcpd_state_disambiguation",
    "current_party_id",
    "proposed_party_id",
    "action",
    "oracle",
    "curator_note",
]

SKIPPED_FIELDS = VERDICT_FIELDS + ["skip_reason"]


# --- helpers ----------------------------------------------------------------


def _git_short_sha() -> str:
    """Return the short git sha of HEAD for the verdict.csv directory tag."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return out or "nogit"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "nogit"


def _slug_from_abbrev(abbrev: str) -> str:
    """Build a ``parties.IN.<SLUG>`` id from a TCPD abbreviation."""
    s = re.sub(r"[^A-Za-z0-9]+", "_", (abbrev or "").upper()).strip("_")
    s = re.sub(r"_+", "_", s)
    return f"parties.IN.{s}" if s else UNK_PID


def _normalise_full(name: str) -> str:
    """Normalise a full-party-name for case-insensitive comparison.

    Upper-cases, trims, collapses internal whitespace runs to one space.
    Used for the B1 lookup AND for the full-name compatibility check
    when deciding alias-add vs mint-new (Step 4c).
    """
    return re.sub(r"\s+", " ", (name or "").strip().upper())


def _full_compat(
    existing_full: str, existing_short: str, tcpd_full: str,
) -> bool:
    """True if an existing parties.csv row's full is compatible with TCPD's Party_Name.

    Compat = same identity for alias-add purposes. The rule is:

      - normalised equality of the two fulls,
      - either side empty (no rival),
      - existing full equals existing short (a stub row where full was
        not curated; common for PR #952-minted rows).

    This is the WEAKER compatibility check used when the abbreviation
    bridge has NOT matched (slug-coincidence fallback).
    """
    ef = _normalise_full(existing_full)
    es = _normalise_full(existing_short)
    tf = _normalise_full(tcpd_full)
    if ef == tf:
        return True
    if not ef or not tf:
        return True
    if ef == es:
        return True
    return False


def _bridge_compat(
    tcpd_freq_abbrev: str,
    existing_short: str,
    existing_full: str,
    tcpd_full: str,
) -> bool:
    """True if a bridge_keys hit should be treated as alias-add target.

    Stronger than ``_full_compat``: when TCPD's ``Frequent_Abbreviation``
    EXACTLY matches the existing canonical's ``short``, treat the bridge
    as compatible regardless of full-name mismatch. The abbreviation is
    the strongest identity signal; full-name variation is common across
    publishers (e.g. TCPD says ``CONGRESS`` but parties.csv says
    ``Indian National Congress`` for the same parties.IN.INC; the
    matching short=INC is decisive).

    Falls back to ``_full_compat`` when the abbreviations differ.
    """
    if (
        tcpd_freq_abbrev
        and existing_short
        and tcpd_freq_abbrev.upper().strip()
        == existing_short.upper().strip()
    ):
        return True
    return _full_compat(existing_full, existing_short, tcpd_full)


def _load_state_slug_to_iso() -> dict[str, str]:
    """Build ``lgd-slug -> ISO 3166-2`` map from ``state_iso_seed.csv``."""
    out: dict[str, str] = {}
    if not STATE_ISO_SEED.exists():
        return out
    with STATE_ISO_SEED.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            slug = (row.get("slug") or "").strip()
            iso = (row.get("iso_3166_2") or "").strip()
            if slug and iso:
                out[slug] = iso
    return out


# --- index builders ---------------------------------------------------------


def build_tcpd_catalogue_indexes(
    catalogue_csv: Path,
) -> tuple[
    dict[str, TcpdPartyRecord],
    dict[str, set[str]],
    dict[str, set[str]],
]:
    """Read TCPD catalogue and build 3 indexes.

    Returns ``(pid_to_record, full_to_pids, abbr_to_pids)``:

      - ``pid_to_record[party_id]``: per-party collapsed metadata.
      - ``full_to_pids[normalised(Party_Name)]``: set of party_ids
        sharing that full name (after placeholder + whitespace
        normalisation).
      - ``abbr_to_pids[upper(abbrev)]``: set of party_ids using that
        abbreviation in ANY of ``Frequent_Abbreviation`` /
        ``Last_Abbreviation`` / ``Abbreviations[]``.

    Placeholder rows (``Party_Name == "NA'S"`` etc.) are EXCLUDED from
    ``full_to_pids`` but INCLUDED in ``pid_to_record`` + ``abbr_to_pids``
    so the collision-disambiguation step can still notice them and
    prefer the non-placeholder pid.
    """
    pid_to_record: dict[str, TcpdPartyRecord] = {}
    full_to_pids: dict[str, set[str]] = defaultdict(set)
    abbr_to_pids: dict[str, set[str]] = defaultdict(set)
    if not catalogue_csv.exists():
        return pid_to_record, dict(full_to_pids), dict(abbr_to_pids)

    rows_by_pid: dict[str, list[dict[str, str]]] = defaultdict(list)
    with catalogue_csv.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            pid = (row.get("Party_ID") or "").strip()
            if pid in ("", "0"):
                continue
            rows_by_pid[pid].append(row)

    for pid, rows in rows_by_pid.items():
        def _sort_key(r: dict[str, str]) -> tuple[int, int]:
            try:
                ly = int(r.get("Last_Year") or 0)
            except ValueError:
                ly = 0
            try:
                sy = int(r.get("Start_Year") or 0)
            except ValueError:
                sy = 0
            return (ly, sy)

        canonical = max(rows, key=_sort_key)

        all_abbrevs: set[str] = set()
        for r in rows:
            for source_col in ("Frequent_Abbreviation", "Last_Abbreviation"):
                v = (r.get(source_col) or "").strip().upper()
                if v:
                    all_abbrevs.add(v)
            for token in (r.get("Abbreviations") or "").split("|"):
                v = token.strip().upper()
                if v:
                    all_abbrevs.add(v)

        state_slugs: set[str] = set()
        for r in rows:
            name = (r.get("State_Name") or "").strip()
            if name == TCPD_ALL_STATES:
                state_slugs.add("*")
                continue
            slug = TCPD_STATE_NAME_TO_SLUG.get(name)
            if slug:
                state_slugs.add(slug)

        start_year: int | None = None
        for r in rows:
            v = (r.get("Start_Year") or "").strip()
            if v.isdigit():
                y = int(v)
                if y > 0 and (start_year is None or y < start_year):
                    start_year = y
        last_year: int | None = None
        for r in rows:
            v = (r.get("Last_Year") or "").strip()
            if v.isdigit():
                y = int(v)
                if y > 0 and (last_year is None or y > last_year):
                    last_year = y

        record = TcpdPartyRecord(
            party_id=pid,
            party_name=(canonical.get("Party_Name") or "").strip(),
            party_type=(canonical.get("Party_Type") or "").strip(),
            frequent_abbrev=(
                canonical.get("Frequent_Abbreviation") or ""
            ).strip().upper(),
            last_abbrev=(canonical.get("Last_Abbreviation") or "").strip().upper(),
            all_abbrevs=tuple(sorted(all_abbrevs)),
            state_slugs=frozenset(state_slugs),
            start_year=start_year,
            last_year=last_year,
        )
        pid_to_record[pid] = record

        # Index abbreviations (always, even for placeholders - the
        # collision-disambiguation step needs to see the placeholder so
        # it can prefer the non-placeholder).
        for abbrev in all_abbrevs:
            abbr_to_pids[abbrev].add(pid)

        # Index full name only for non-placeholder rows.
        if not record.is_placeholder:
            normalised = _normalise_full(record.party_name)
            if normalised:
                full_to_pids[normalised].add(pid)

    return pid_to_record, dict(full_to_pids), dict(abbr_to_pids)


def _load_parties_csv() -> tuple[
    list[str], list[dict[str, str]], dict[str, dict[str, str]], dict[str, str]
]:
    """Return ``(fieldnames, rows, by_pid_row, claimed_aliases)``.

    - ``by_pid_row[pid]``: full row dict for the existing party.
    - ``claimed_aliases[UPPER(short|alias)]``: party_id owning that key.
    """
    with PARTIES_CSV.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    by_pid_row: dict[str, dict[str, str]] = {}
    claimed: dict[str, str] = {}
    for r in rows:
        pid = (r.get("party_id") or "").strip()
        if not pid:
            continue
        by_pid_row[pid] = r
        short = (r.get("short") or "").upper().strip()
        if short:
            claimed[short] = pid
        for a in (r.get("aliases") or "").split("|"):
            v = a.strip().upper()
            if v:
                claimed[v] = pid
    return fieldnames, rows, by_pid_row, claimed


def walk_unk_rows(
    assembly_root: Path, parliament_root: Path,
) -> dict[str, UnkLabel]:
    """Scan candidacies.csv corpus and aggregate UNK rows by UPPER(label)."""
    out: dict[str, UnkLabel] = {}
    paths = sorted(assembly_root.glob("state=*/election=*/candidacies.csv"))
    paths += sorted(parliament_root.glob("election=*/candidacies.csv"))
    for path in paths:
        with path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if (row.get("party_id") or "").strip() != UNK_PID:
                    continue
                raw = (row.get("party_short_raw") or "").strip()
                if not raw:
                    continue
                key = raw.upper()
                rec = out.get(key)
                if rec is None:
                    rec = UnkLabel(label=key, publisher_label=raw)
                    out[key] = rec
                rec.n_rows += 1
                state = (row.get("state") or "").strip()
                if state:
                    rec.states.add(state)
                year_raw = (row.get("election_year") or "").strip()
                if year_raw.isdigit():
                    rec.years.add(int(year_raw))
    return out


# --- decision engine --------------------------------------------------------


def _make_verdict_base(rec: UnkLabel) -> Verdict:
    """Build a base Verdict from an UnkLabel (action / bucket left blank)."""
    sample_states = "|".join(sorted(rec.states)) if rec.states else ""
    if rec.years:
        y_min, y_max = min(rec.years), max(rec.years)
        sample_year = str(y_min) if y_min == y_max else f"{y_min}-{y_max}"
    else:
        sample_year = ""
    return Verdict(
        external_key=rec.label,
        party_short_raw=rec.publisher_label,
        state=sample_states,
        year=sample_year,
        n_rows=rec.n_rows,
        bucket="",
        tcpd_party_id="",
        tcpd_party_type="",
        tcpd_party_name="",
        tcpd_frequent_abbrev="",
        tcpd_start_year="",
        tcpd_last_year="",
        tcpd_state_disambiguation="",
        current_party_id=UNK_PID,
        proposed_party_id="",
        action="",
        oracle="none",
        skip_reason="",
        curator_note="",
    )


def _disambiguate(
    rec: UnkLabel,
    candidate_pids: list[str],
    pid_to_record: dict[str, TcpdPartyRecord],
) -> tuple[str | None, str, str]:
    """Resolve a multi-pid collision to a single Party_ID.

    Returns ``(chosen_pid_or_None, disambiguation_kind, skip_reason)``.
    Kind is one of ``state-match`` / ``year-match`` / ``""`` (none).
    When chosen_pid is None, skip_reason carries the verdict reason.
    """
    if not rec.states:
        # No state info on our rows: state-match is impossible.
        return None, "", "tcpd-no-state-info"

    # State-match: every OUR state must be covered by EXACTLY ONE
    # candidate pid (across the candidate set). We compute, for each
    # OUR state, the set of candidate pids covering it, then take the
    # intersection.
    per_state_covers: list[set[str]] = []
    for state in sorted(rec.states):
        covers = {
            p for p in candidate_pids
            if pid_to_record[p].covers_state(state)
        }
        if not covers:
            # This OUR state is not covered by ANY candidate pid; we
            # cannot resolve via TCPD.
            return None, "", "tcpd-no-state-coverage"
        per_state_covers.append(covers)
    common = set(candidate_pids)
    for covers in per_state_covers:
        common &= covers
    if len(common) == 1:
        return next(iter(common)), "state-match", ""

    if len(common) == 0:
        # State-disambiguation contradicts itself (different states pick
        # different pids).
        return None, "", "tcpd-state-disambig-contradiction"

    # Multiple candidates still cover OUR states; try year-match.
    if not rec.years:
        return None, "", "tcpd-state-year-collision"
    per_year_covers: list[set[str]] = []
    for year in sorted(rec.years):
        covers = {p for p in common if pid_to_record[p].covers_year(year)}
        if not covers:
            return None, "", "tcpd-no-year-coverage"
        per_year_covers.append(covers)
    year_common = set(common)
    for covers in per_year_covers:
        year_common &= covers
    if len(year_common) == 1:
        return next(iter(year_common)), "year-match", ""
    return None, "", "tcpd-state-year-collision"


def decide(
    rec: UnkLabel,
    *,
    pid_to_record: dict[str, TcpdPartyRecord],
    full_to_pids: dict[str, set[str]],
    abbr_to_pids: dict[str, set[str]],
    by_pid_row: dict[str, dict[str, str]],
    claimed_aliases: dict[str, str],
    slug_to_iso: dict[str, str],
) -> Verdict:
    """Produce one Verdict per UnkLabel via the brief's decision tree."""
    base = _make_verdict_base(rec)

    # --- B1: full-name match ---------------------------------------------
    normalised = _normalise_full(rec.label)
    candidate_pids_raw = full_to_pids.get(normalised, set())
    if candidate_pids_raw:
        base.bucket = "B1"
        base.oracle = "tcpd-catalogue-B1"
    else:
        # --- B2: abbreviation match ---------------------------------------
        candidate_pids_raw = abbr_to_pids.get(rec.label, set())
        if not candidate_pids_raw:
            base.skip_reason = "not-in-tcpd-catalogue"
            base.curator_note = (
                "label not present in TCPD parties catalogue "
                "(Party_Name / Frequent_Abbreviation / Last_Abbreviation "
                "/ Abbreviations)."
            )
            return base
        base.bucket = "B2"
        base.oracle = "tcpd-catalogue-B2"

    # Filter out placeholder pids. The collision rules in the brief say:
    # if one of N candidates is NA'S, silently prefer the OTHER. If ALL
    # are placeholders, skip with reason `tcpd-placeholder-only`.
    candidate_pids = [
        p for p in candidate_pids_raw
        if not pid_to_record[p].is_placeholder
    ]
    if not candidate_pids:
        base.skip_reason = "tcpd-placeholder-only"
        base.curator_note = (
            f"all {len(candidate_pids_raw)} TCPD candidate(s) are "
            f"placeholder rows ({sorted(candidate_pids_raw)})."
        )
        return base

    # --- Disambiguate -----------------------------------------------------
    if len(candidate_pids) == 1:
        chosen_pid = candidate_pids[0]
        disambig = "singleton"
    else:
        chosen_pid, disambig, skip_reason = _disambiguate(
            rec, candidate_pids, pid_to_record,
        )
        if chosen_pid is None:
            base.skip_reason = skip_reason
            base.curator_note = (
                f"{len(candidate_pids)} TCPD candidates "
                f"({sorted(candidate_pids)}) for bucket {base.bucket}; "
                f"disambiguation failed: {skip_reason}."
            )
            return base

    base.tcpd_state_disambiguation = disambig
    meta = pid_to_record[chosen_pid]
    base.tcpd_party_id = chosen_pid
    base.tcpd_party_type = meta.party_type
    base.tcpd_party_name = meta.party_name
    base.tcpd_frequent_abbrev = meta.frequent_abbrev
    base.tcpd_start_year = str(meta.start_year) if meta.start_year else ""
    base.tcpd_last_year = str(meta.last_year) if meta.last_year else ""

    # --- Map TCPD pid -> parties.csv row (or mint-new) -------------------
    bridge_keys = [meta.frequent_abbrev, meta.last_abbrev]
    bridge_keys += [a for a in meta.all_abbrevs if a not in bridge_keys]
    bridge_keys = [k for k in bridge_keys if k]

    bridge_hit_pid: str | None = None
    bridge_via: str = ""
    for k in bridge_keys:
        hit = claimed_aliases.get(k)
        if hit is not None:
            bridge_hit_pid = hit
            bridge_via = k
            break

    if bridge_hit_pid is not None:
        existing_row = by_pid_row[bridge_hit_pid]
        if _bridge_compat(
            meta.frequent_abbrev,
            existing_row.get("short", ""),
            existing_row.get("full", ""),
            meta.party_name,
        ):
            # Compatible -> alias-add.
            claimed_by = claimed_aliases.get(rec.label)
            if claimed_by is not None and claimed_by != bridge_hit_pid:
                base.skip_reason = "label-claimed-by-other-canonical"
                base.curator_note = (
                    f"would alias {rec.publisher_label!r} to "
                    f"{bridge_hit_pid} via {bridge_via!r} but the label "
                    f"is already aliased to {claimed_by!r}."
                )
                return base
            base.proposed_party_id = bridge_hit_pid
            base.action = "alias-add"
            base.curator_note = (
                f"TCPD pid {chosen_pid} ({meta.party_name!r}); bridges "
                f"to existing canonical via abbreviation {bridge_via!r}."
            )
            return base
        # Incompatible full-name: mint-new with disambiguated slug
        # (Step 4d in the docstring).
        return _emit_mint(
            base, rec, meta, by_pid_row, claimed_aliases,
            slug_to_iso, collision_with=bridge_hit_pid,
        )

    # No bridge hit -> mint-new with TCPD-preferred abbreviation.
    return _emit_mint(
        base, rec, meta, by_pid_row, claimed_aliases,
        slug_to_iso, collision_with=None,
    )


def _emit_mint(
    base: Verdict,
    rec: UnkLabel,
    meta: TcpdPartyRecord,
    by_pid_row: dict[str, dict[str, str]],
    claimed_aliases: dict[str, str],
    slug_to_iso: dict[str, str],
    *,
    collision_with: str | None,
) -> Verdict:
    """Build a mint-new verdict, applying the disambiguated-slug convention.

    When ``collision_with`` is set, the preferred abbreviation already
    points at a DIFFERENT canonical row; we try ``<abbr>_<state-iso>``
    then ``<abbr>_<start-year>``. Skips with reason
    ``mint-slug-collision-unresolvable`` if both disambiguators also
    collide.

    Even when ``collision_with`` is None (no bridge_keys hit), we still
    check whether the basic mint-slug would collide with an existing
    canonical pid. If it does AND the existing canonical's ``full`` is
    compatible with TCPD's Party_Name, we treat it as ``alias-add`` (the
    slug coincidence IS the bridge). If incompatible, we promote it to
    ``collision_with`` so the disambiguation path runs.
    """
    short_value = (
        meta.frequent_abbrev or meta.last_abbrev
        or (meta.all_abbrevs[0] if meta.all_abbrevs else "")
    )
    if not short_value:
        base.skip_reason = "tcpd-no-abbreviation"
        base.curator_note = (
            f"TCPD pid {meta.party_id} ({meta.party_name!r}) has no "
            f"Frequent_Abbreviation / Last_Abbreviation / Abbreviations[]; "
            f"cannot derive a mint slug."
        )
        return base

    # Skip mint when full name is itself a placeholder.
    if meta.is_placeholder:
        base.skip_reason = "tcpd-placeholder-full"
        base.curator_note = (
            f"TCPD pid {meta.party_id} carries placeholder Party_Name "
            f"({meta.party_name!r}); cannot mint."
        )
        return base

    basic_slug = _slug_from_abbrev(short_value)

    # When called WITHOUT a known collision (bridge_keys lookup missed),
    # the basic slug may still pre-exist in parties.csv for a row whose
    # short / aliases simply do not carry our TCPD abbreviation. In that
    # case the slug coincidence IS the bridge: if the existing row's
    # full is compatible -> alias-add; if incompatible -> promote to
    # collision_with so the disambiguation path runs.
    if collision_with is None and basic_slug in by_pid_row:
        existing_row = by_pid_row[basic_slug]
        if _bridge_compat(
            meta.frequent_abbrev,
            existing_row.get("short", ""),
            existing_row.get("full", ""),
            meta.party_name,
        ):
            claimed_by = claimed_aliases.get(rec.label)
            if claimed_by is not None and claimed_by != basic_slug:
                base.skip_reason = "label-claimed-by-other-canonical"
                base.curator_note = (
                    f"basic slug {basic_slug!r} pre-exists for TCPD pid "
                    f"{meta.party_id} ({meta.party_name!r}) with compatible "
                    f"Party_Name but publisher label "
                    f"{rec.publisher_label!r} is already aliased to "
                    f"{claimed_by!r}."
                )
                return base
            base.proposed_party_id = basic_slug
            base.action = "alias-add"
            base.curator_note = (
                f"TCPD pid {meta.party_id} ({meta.party_name!r}); basic "
                f"slug {basic_slug!r} pre-exists in parties.csv with "
                f"compatible Party_Name (short / aliases did not carry "
                f"TCPD abbreviation {short_value!r})."
            )
            return base
        # Incompatible full -> promote to collision_with for disambig.
        collision_with = basic_slug

    candidate_slugs: list[str] = [basic_slug]
    if collision_with is not None:
        # Try disambiguated forms.
        # Pick a single state if our row only covers one state (the
        # common case for B2 mints).
        sole_state = next(iter(rec.states)) if len(rec.states) == 1 else None
        if sole_state and sole_state in slug_to_iso:
            iso = slug_to_iso[sole_state].replace("-", "_")
            candidate_slugs.append(
                _slug_from_abbrev(f"{short_value}_{iso}")
            )
        if meta.start_year:
            candidate_slugs.append(
                _slug_from_abbrev(f"{short_value}_{meta.start_year}")
            )

    chosen_slug: str | None = None
    for slug in candidate_slugs:
        if slug in by_pid_row:
            continue
        if slug == UNK_PID:
            continue
        chosen_slug = slug
        break

    if chosen_slug is None:
        base.skip_reason = "mint-slug-collision-unresolvable"
        base.curator_note = (
            f"TCPD pid {meta.party_id} ({meta.party_name!r}); preferred "
            f"abbreviation {short_value!r} already canonical "
            f"({collision_with}); disambiguated slugs also collide "
            f"({candidate_slugs})."
        )
        return base

    claimed_by = claimed_aliases.get(rec.label)
    if claimed_by is not None and claimed_by != chosen_slug:
        # Publisher label already aliased to a different existing canonical.
        base.skip_reason = "label-claimed-by-other-canonical"
        base.curator_note = (
            f"would mint {chosen_slug} for TCPD pid {meta.party_id} "
            f"but label {rec.publisher_label!r} is already aliased to "
            f"{claimed_by!r}."
        )
        return base

    base.proposed_party_id = chosen_slug
    base.action = "mint-new"
    base.curator_note = (
        f"TCPD pid {meta.party_id} ({meta.party_name!r}); minting new "
        f"slug {chosen_slug!r} from "
        f"{'disambiguated abbreviation' if collision_with else 'frequent_abbrev'} "
        f"{short_value!r}."
    )
    if collision_with is not None:
        base.curator_note += (
            f" Disambiguated against existing canonical {collision_with} "
            f"with incompatible Party_Name."
        )
    return base


# --- emit -------------------------------------------------------------------


def _row_from_verdict(v: Verdict, *, fields: list[str]) -> dict[str, str]:
    """Project a Verdict dataclass to a dict for csv.DictWriter."""
    payload = {
        "external_key": v.external_key,
        "party_short_raw": v.party_short_raw,
        "state": v.state,
        "year": v.year,
        "n_rows": v.n_rows,
        "bucket": v.bucket,
        "tcpd_party_id": v.tcpd_party_id,
        "tcpd_party_type": v.tcpd_party_type,
        "tcpd_party_name": v.tcpd_party_name,
        "tcpd_frequent_abbrev": v.tcpd_frequent_abbrev,
        "tcpd_start_year": v.tcpd_start_year,
        "tcpd_last_year": v.tcpd_last_year,
        "tcpd_state_disambiguation": v.tcpd_state_disambiguation,
        "current_party_id": v.current_party_id,
        "proposed_party_id": v.proposed_party_id,
        "action": v.action,
        "oracle": v.oracle,
        "skip_reason": v.skip_reason,
        "curator_note": v.curator_note,
    }
    return {k: payload.get(k, "") for k in fields}


def write_verdict_csvs(
    out_dir: Path, verdicts: list[Verdict], skipped: list[Verdict],
) -> tuple[Path, Path]:
    """Write verdict.csv (resolved) + skipped.csv (unresolved) under out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    verdict_path = out_dir / "verdict.csv"
    skipped_path = out_dir / "skipped.csv"
    with verdict_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=VERDICT_FIELDS, lineterminator="\n",
        )
        writer.writeheader()
        for v in verdicts:
            writer.writerow(_row_from_verdict(v, fields=VERDICT_FIELDS))
    with skipped_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=SKIPPED_FIELDS, lineterminator="\n",
        )
        writer.writeheader()
        for v in skipped:
            writer.writerow(_row_from_verdict(v, fields=SKIPPED_FIELDS))
    return verdict_path, skipped_path


def report(verdicts: list[Verdict], skipped: list[Verdict]) -> None:
    """Print a per-bucket / per-action / per-skip summary."""
    print()
    print(
        f"verdicts (resolved): {len(verdicts)} labels covering "
        f"{sum(v.n_rows for v in verdicts)} UNK rows"
    )
    print(
        f"skipped:             {len(skipped)} labels covering "
        f"{sum(v.n_rows for v in skipped)} UNK rows"
    )

    by_bucket_action: Counter[tuple[str, str]] = Counter()
    rows_by_bucket_action: Counter[tuple[str, str]] = Counter()
    for v in verdicts:
        by_bucket_action[(v.bucket, v.action)] += 1
        rows_by_bucket_action[(v.bucket, v.action)] += v.n_rows
    print()
    print("by (bucket, action) labels / rows:")
    for (bucket, action), n in sorted(by_bucket_action.items()):
        print(
            f"  {bucket:>2s} {action:>10s}: {n:>5d} / "
            f"{rows_by_bucket_action[(bucket, action)]:>6d}"
        )

    by_disambig: Counter[str] = Counter()
    for v in verdicts:
        by_disambig[v.tcpd_state_disambiguation] += 1
    print()
    print("verdict disambiguation kind:")
    for kind, n in sorted(by_disambig.items()):
        print(f"  {kind:>15s}: {n}")

    by_skip: Counter[str] = Counter()
    rows_by_skip: Counter[str] = Counter()
    for v in skipped:
        by_skip[v.skip_reason] += 1
        rows_by_skip[v.skip_reason] += v.n_rows
    print()
    print("skip reasons (labels / rows):")
    for reason, n in sorted(by_skip.items(), key=lambda kv: -kv[1]):
        print(f"  {reason:>40s}: {n:>5d} / {rows_by_skip[reason]:>6d}")


# --- main entry -------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sha-tag",
        default=None,
        help=(
            "Override the verdict directory tag. Default: short git sha "
            "of HEAD."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N distinct labels (smoke test).",
    )
    args = parser.parse_args()

    print("[1/5] Loading TCPD parties catalogue...")
    pid_to_record, full_to_pids, abbr_to_pids = (
        build_tcpd_catalogue_indexes(TCPD_CATALOGUE)
    )
    print(
        f"      {len(pid_to_record)} Party_IDs; "
        f"{len(full_to_pids)} normalised full-name keys; "
        f"{len(abbr_to_pids)} abbreviation keys."
    )

    print("[2/5] Loading current parties.csv...")
    _, _, by_pid_row, claimed_aliases = _load_parties_csv()
    print(
        f"      {len(by_pid_row)} canonical party_ids; "
        f"{len(claimed_aliases)} claimed short/alias keys."
    )

    print("[3/5] Loading state-iso seed for disambiguated mint slugs...")
    slug_to_iso = _load_state_slug_to_iso()
    print(f"      {len(slug_to_iso)} state-slug -> ISO mappings.")

    print("[4/5] Walking UNK rows in candidacies.csv corpus...")
    unk_by_label = walk_unk_rows(ASSEMBLY_ROOT, PARLIAMENT_ROOT)
    total_unk_rows = sum(r.n_rows for r in unk_by_label.values())
    print(
        f"      {len(unk_by_label)} distinct UNK labels covering "
        f"{total_unk_rows} candidacies.csv rows."
    )

    print("[5/5] Correlating...")
    verdicts: list[Verdict] = []
    skipped: list[Verdict] = []
    labels = sorted(unk_by_label)
    if args.limit is not None:
        labels = labels[: args.limit]
    for label in labels:
        v = decide(
            unk_by_label[label],
            pid_to_record=pid_to_record,
            full_to_pids=full_to_pids,
            abbr_to_pids=abbr_to_pids,
            by_pid_row=by_pid_row,
            claimed_aliases=claimed_aliases,
            slug_to_iso=slug_to_iso,
        )
        if v.action in ("alias-add", "mint-new"):
            verdicts.append(v)
        else:
            skipped.append(v)

    sha = args.sha_tag or _git_short_sha()
    verdict_path, skipped_path = write_verdict_csvs(
        VERDICT_ROOT / sha, verdicts, skipped,
    )
    report(verdicts, skipped)
    print()
    print(f"verdict.csv written: {verdict_path.relative_to(REPO_ROOT).as_posix()}")
    print(f"skipped.csv written: {skipped_path.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
