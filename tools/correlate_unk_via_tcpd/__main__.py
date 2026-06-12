"""TCPD Party_ID correlator for UNK publisher labels.

See package docstring (``tools/correlate_unk_via_tcpd/__init__.py``) for the
full rationale + sources. This is the executable entry point.

Run from the repo root:

    python -m tools.correlate_unk_via_tcpd

Default dry-run prints the per-class tally + writes the verdict.csv. The
verdict path is printed at the end and is also returned in the per-row
ledger so the curator can pipe it into ``tools.correlate_unk_apply``.

Inputs (paths relative to repo root):

  - ``datasets/ephemeral/All_States_AE.csv`` (TCPD per-candidacy AE panel)
  - ``datasets/ephemeral/All_States_GE.csv`` (TCPD per-candidacy GE panel)
  - ``datasets/ephemeral/TCPD-PoliticalPartiesIndia_1962_2021.csv`` (TCPD
    per-party catalogue; Party_Name + Frequent_Abbreviation by Party_ID)
  - ``.tmp_parquet_recovery/elections_candidacies.parquet`` (operator-local,
    recovered from parent-of ``b8108ceb8``)
  - ``datasets/data/entities/parties.csv`` (current canonical roster)
  - ``datasets/elections/{assembly,parliament}/.../candidacies.csv`` (UNK
    rows to correlate)

Output:

  - ``datasets/ephemeral/party-parity/tcpd-correlate/<sha>/verdict.csv``
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

TCPD_AE = REPO_ROOT / "datasets" / "ephemeral" / "All_States_AE.csv"
TCPD_GE = REPO_ROOT / "datasets" / "ephemeral" / "All_States_GE.csv"
TCPD_CATALOGUE = (
    REPO_ROOT
    / "datasets"
    / "ephemeral"
    / "TCPD-PoliticalPartiesIndia_1962_2021.csv"
)
LEGACY_PARQUET = (
    REPO_ROOT / ".tmp_parquet_recovery" / "elections_candidacies.parquet"
)
PARTIES_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "parties.csv"
STATE_ISO_SEED = (
    REPO_ROOT / "datasets" / "data" / "entities" / "state_iso_seed.csv"
)
ASSEMBLY_ROOT = REPO_ROOT / "datasets" / "elections" / "assembly"
PARLIAMENT_ROOT = REPO_ROOT / "datasets" / "elections" / "parliament"

VERDICT_ROOT = (
    REPO_ROOT / "datasets" / "ephemeral" / "party-parity" / "tcpd-correlate"
)

UNK_PID = "parties.IN.UNK"


# --- data classes -----------------------------------------------------------


@dataclass(frozen=True)
class TcpdPartyMeta:
    """Per-Party_ID metadata projected from the TCPD per-party catalogue."""

    party_id: str
    party_name: str
    party_type: str
    frequent_abbrev: str
    last_abbrev: str
    all_abbrevs: tuple[str, ...]
    start_year: int | None


@dataclass
class UnkLabel:
    """Per-label aggregate of our on-disk UNK rows.

    Collapses ``(label, state, year)`` triples into a single per-label
    record with the set of distinct states + years for the verdict.csv
    state-disambiguation logic + sample columns.
    """

    label: str  # UPPER, stripped
    n_rows: int = 0
    states: set[str] = field(default_factory=set)  # lgd-slug shape
    years: set[int] = field(default_factory=set)


@dataclass
class Verdict:
    """One verdict.csv row. Pure dataclass projection for csv emit."""

    external_key: str  # UPPER(party_short_raw) - the key we group on
    party_short_raw: str  # publisher label, original case (sample)
    state: str  # pipe-delim of distinct states we saw this label in
    year: str  # year range "min-max" or single
    n_rows: int
    tcpd_party_id: str
    tcpd_party_type: str
    tcpd_party_name: str
    tcpd_frequent_abbrev: str
    current_party_id: str  # always parties.IN.UNK in this PR
    proposed_party_id: str
    action: str  # alias-add | mint-new | disputed | skip
    oracle: str  # tcpd-unique | tcpd-state | legacy-parquet | none
    curator_note: str


# --- index builders ---------------------------------------------------------


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
    """Build a ``parties.IN.<SLUG>`` id from a TCPD abbreviation.

    Same regex as the existing ``tcpd_parties._make_slug`` (kept local to
    avoid coupling to the recon adapter). Sanitises to ``[A-Z0-9_]+``,
    collapses multi-underscore runs, strips leading/trailing underscores.
    """
    s = re.sub(r"[^A-Za-z0-9]+", "_", (abbrev or "").upper()).strip("_")
    s = re.sub(r"_+", "_", s)
    return f"parties.IN.{s}" if s else UNK_PID


def _load_state_slug_to_iso() -> dict[str, str]:
    """Build ``lgd-slug -> ISO 3166-2`` map from ``state_iso_seed.csv``.

    Used to project the union of states a label appears in into
    ``home_state_codes`` for the mint payload. Falls back to empty string
    when a slug is unknown (e.g. legacy spellings the seed file does not
    cover).
    """
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


def _build_tcpd_panel_indexes() -> tuple[
    dict[str, set[str]],
    dict[tuple[str, str], set[str]],
    dict[str, Counter[str]],
]:
    """Read TCPD AE + GE and build the three lookup maps.

    Returns ``(lbl_to_pids, lbl_state_to_pids, pid_to_state_counts)``:

      - ``lbl_to_pids[UPPER(short)]``: set of distinct Party_ID strings
        the label resolves to anywhere in TCPD's per-candidacy panel.
      - ``lbl_state_to_pids[(UPPER(short), lgd_slug)]``: set of distinct
        Party_IDs for the (label, state) tuple. Used for class-B state
        disambiguation.
      - ``pid_to_state_counts[Party_ID][lgd_slug]``: per-Party_ID histogram
        of state appearances; used to derive ``home_state_codes`` on the
        mint payload (the slug with the highest count is the home state;
        ties broken by lex order for determinism).

    Rows with ``Party_ID in {'', '0'}`` are TCPD's null sentinel and are
    skipped at index build time.
    """
    lbl_to_pids: dict[str, set[str]] = defaultdict(set)
    lbl_state_to_pids: dict[tuple[str, str], set[str]] = defaultdict(set)
    pid_to_state_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for path in (TCPD_AE, TCPD_GE):
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                pid = (row.get("Party_ID") or "").strip()
                if pid in ("", "0"):
                    continue
                label = (row.get("Party") or "").strip().upper()
                if not label:
                    continue
                state_name = (row.get("State_Name") or "").strip()
                state_slug = TCPD_STATE_NAME_TO_SLUG.get(state_name, "")
                lbl_to_pids[label].add(pid)
                if state_slug:
                    lbl_state_to_pids[(label, state_slug)].add(pid)
                    pid_to_state_counts[pid][state_slug] += 1
    return lbl_to_pids, lbl_state_to_pids, pid_to_state_counts


def _build_tcpd_catalogue() -> dict[str, TcpdPartyMeta]:
    """Read TCPD per-party catalogue and project to ``Party_ID -> meta``.

    Picks the row with max ``Last_Year`` per Party_ID (TCPD's catalogue
    carries one row per (Assembly, State, Party_ID) tuple; the most-recent
    row carries the canonical Party_Name + Frequent_Abbreviation). Unions
    the pipe-delim ``Abbreviations`` column across all rows for the same
    Party_ID so the mint payload's ``aliases`` column carries every
    historical variant.

    Returns an empty dict when the catalogue file is missing (the
    correlator still works; mint payloads just have empty short / full
    cells, which the curator can backfill manually).
    """
    if not TCPD_CATALOGUE.exists():
        return {}
    # First pass: collect all rows per Party_ID.
    rows_by_pid: dict[str, list[dict[str, str]]] = defaultdict(list)
    with TCPD_CATALOGUE.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            pid = (row.get("Party_ID") or "").strip()
            if pid in ("", "0"):
                continue
            rows_by_pid[pid].append(row)
    out: dict[str, TcpdPartyMeta] = {}
    for pid, rows in rows_by_pid.items():
        # Pick most-recent row (max Last_Year; ties broken by max Start_Year).
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
            for a in (r.get("Abbreviations") or "").split("|"):
                v = a.strip().upper()
                if v:
                    all_abbrevs.add(v)
        try:
            start_year: int | None = min(
                int(r.get("Start_Year") or 0) for r in rows
                if (r.get("Start_Year") or "").strip().isdigit()
            )
        except ValueError:
            start_year = None
        if start_year == 0:
            start_year = None
        out[pid] = TcpdPartyMeta(
            party_id=pid,
            party_name=(canonical.get("Party_Name") or "").strip(),
            party_type=(canonical.get("Party_Type") or "").strip(),
            frequent_abbrev=(
                canonical.get("Frequent_Abbreviation") or ""
            ).strip().upper(),
            last_abbrev=(canonical.get("Last_Abbreviation") or "").strip().upper(),
            all_abbrevs=tuple(sorted(all_abbrevs)),
            start_year=start_year,
        )
    return out


def _build_parquet_index() -> dict[str, set[str]]:
    """Read the recovered legacy parquet and build ``label -> {party_id}``.

    Excludes ``parties.IN.UNK`` from the output set so a hit MUST carry
    real resolutions only. Returns empty dict when the parquet is missing
    (operator did not stage ``.tmp_parquet_recovery/``); the correlator
    treats class-D rescue as unavailable in that case.
    """
    if not LEGACY_PARQUET.exists():
        return {}
    try:
        import duckdb  # type: ignore[import-not-found]
    except ImportError:
        return {}
    con = duckdb.connect()
    rows = con.execute(
        f"""
        SELECT UPPER(TRIM(party_short_raw)) AS lbl,
               list(DISTINCT party_id) AS pids
        FROM '{LEGACY_PARQUET.as_posix()}'
        WHERE party_id IS NOT NULL
          AND party_id <> '{UNK_PID}'
          AND TRIM(COALESCE(party_short_raw, '')) <> ''
        GROUP BY UPPER(TRIM(party_short_raw))
        """
    ).fetchall()
    return {lbl: set(pids) for lbl, pids in rows}


def _load_parties_csv() -> tuple[
    list[str], list[dict[str, str]], dict[str, str], dict[str, str]
]:
    """Return ``(fieldnames, rows, by_pid, claimed_aliases)``.

    - ``by_pid``: ``party_id -> row dict`` for direct lookups.
    - ``claimed_aliases``: ``UPPER(short|alias) -> party_id`` for the
      collision check (matches ``recon_curate_tcpd_parties._apply_enrich``
      semantics so the resolver loader does not fail-loud post-apply).
    """
    with PARTIES_CSV.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    by_pid: dict[str, str] = {}
    claimed: dict[str, str] = {}
    for r in rows:
        pid = (r.get("party_id") or "").strip()
        if not pid:
            continue
        by_pid[pid] = pid
        short = (r.get("short") or "").upper().strip()
        if short:
            claimed[short] = pid
        for a in (r.get("aliases") or "").split("|"):
            v = a.strip().upper()
            if v:
                claimed[v] = pid
    return fieldnames, rows, by_pid, claimed


def _walk_unk_rows() -> dict[str, UnkLabel]:
    """Scan candidacies.csv corpus and aggregate UNK rows by UPPER(label).

    Returns ``{UPPER(party_short_raw): UnkLabel}`` summarising the per-
    label row count, set of states, and set of years. Skips rows whose
    ``party_short_raw`` is blank (those have no label to correlate; the
    sentinel ``parties.IN.UNK`` is the right answer per the Tier-A
    ``test_party_short_raw_preserved`` carve-out for true blanks, and
    in practice no such rows exist on the current corpus).
    """
    out: dict[str, UnkLabel] = {}
    paths = sorted(ASSEMBLY_ROOT.glob("state=*/election=*/candidacies.csv"))
    paths += sorted(PARLIAMENT_ROOT.glob("election=*/candidacies.csv"))
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
                    rec = UnkLabel(label=key)
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


def _state_disambiguates(
    label: str,
    our_states: set[str],
    lbl_state_to_pids: dict[tuple[str, str], set[str]],
) -> str | None:
    """Return single Party_ID if OUR states all resolve to the same TCPD pid.

    Returns ``None`` when:
      - any state has zero TCPD coverage for this label (no state row),
      - any state has multiple TCPD Party_IDs (state alone doesn't
        disambiguate), or
      - OUR states resolve to MULTIPLE distinct Party_IDs across them
        (state-level disambiguation contradicts itself; safer to surface
        as DISPUTED than to silently pick one).

    Returns the single Party_ID when every OUR state has exactly one TCPD
    Party_ID for this label AND they all agree.
    """
    if not our_states:
        return None
    pids: set[str] = set()
    for state in our_states:
        cand = lbl_state_to_pids.get((label, state))
        if not cand or len(cand) != 1:
            return None
        pids.update(cand)
    if len(pids) == 1:
        return next(iter(pids))
    return None


def _decide(
    rec: UnkLabel,
    *,
    lbl_to_pids: dict[str, set[str]],
    lbl_state_to_pids: dict[tuple[str, str], set[str]],
    pid_meta: dict[str, TcpdPartyMeta],
    parquet_idx: dict[str, set[str]],
    by_pid: dict[str, str],
    claimed_aliases: dict[str, str],
) -> Verdict:
    """Produce one Verdict per UnkLabel via the brief's decision tree.

    Tries oracles in order: TCPD-unique -> TCPD-state-disambig ->
    legacy-parquet-unique -> DISPUTED. For TCPD hits, looks up the per-
    Party_ID catalogue meta and decides alias-add vs mint-new based on
    whether TCPD's frequent abbreviation already matches an existing
    parties.csv short / alias.
    """
    label = rec.label
    sample_states = "|".join(sorted(rec.states)) if rec.states else ""
    if rec.years:
        y_min, y_max = min(rec.years), max(rec.years)
        sample_year = str(y_min) if y_min == y_max else f"{y_min}-{y_max}"
    else:
        sample_year = ""

    base = Verdict(
        external_key=label,
        party_short_raw=label,
        state=sample_states,
        year=sample_year,
        n_rows=rec.n_rows,
        tcpd_party_id="",
        tcpd_party_type="",
        tcpd_party_name="",
        tcpd_frequent_abbrev="",
        current_party_id=UNK_PID,
        proposed_party_id="",
        action="disputed",
        oracle="none",
        curator_note="",
    )

    pid_tcpd: str | None = None
    oracle = "none"
    pids = lbl_to_pids.get(label, set())
    if len(pids) == 1:
        pid_tcpd = next(iter(pids))
        oracle = "tcpd-unique"
    elif len(pids) > 1:
        disambig = _state_disambiguates(
            label, rec.states, lbl_state_to_pids
        )
        if disambig is not None:
            pid_tcpd = disambig
            oracle = "tcpd-state"
        else:
            # Real collision; emit disputed with the per-pid list for the
            # curator to triage.
            base.curator_note = (
                f"TCPD collision: label maps to {len(pids)} Party_IDs "
                f"({'|'.join(sorted(pids))}); state-disambiguation also "
                f"failed across our states ({sample_states or '<none>'})."
            )
            return base

    if pid_tcpd is None:
        # Class C/D: not in TCPD. Try legacy parquet.
        pq_pids = parquet_idx.get(label, set())
        if len(pq_pids) == 1:
            proposed = next(iter(pq_pids))
            if proposed in by_pid:
                # The label was historically resolved to this canonical pid;
                # add the publisher label as an alias.
                target = proposed
                # Collision check on the alias addition itself.
                claimed_by = claimed_aliases.get(label)
                if claimed_by is not None and claimed_by != target:
                    base.curator_note = (
                        f"legacy-parquet proposed {proposed} but label "
                        f"{label!r} is already claimed as alias by {claimed_by!r}."
                    )
                    return base
                base.proposed_party_id = target
                base.action = "alias-add"
                base.oracle = "legacy-parquet"
                base.curator_note = (
                    f"recovered from legacy elections_candidacies.parquet; "
                    f"target {proposed} present in current parties.csv."
                )
                return base
            # Parquet's party_id is no longer in parties.csv (e.g. retired
            # in a later cleanup). Surface as disputed for curator review.
            base.curator_note = (
                f"legacy-parquet proposed {proposed} but that pid is not in "
                f"current parties.csv (retired since the parquet snapshot)."
            )
            return base
        elif len(pq_pids) > 1:
            base.curator_note = (
                f"legacy-parquet collision: {len(pq_pids)} distinct "
                f"party_ids ({'|'.join(sorted(pq_pids))})."
            )
            return base
        # Truly unresolvable.
        base.curator_note = (
            "not in TCPD AE+GE panel; not in legacy elections_candidacies "
            "parquet; cannot resolve mechanically."
        )
        base.action = "skip"
        return base

    # TCPD oracle succeeded; look up catalogue meta for the mint/alias decision.
    meta = pid_meta.get(pid_tcpd)
    base.tcpd_party_id = pid_tcpd
    base.oracle = oracle
    if meta is None:
        base.tcpd_party_name = ""
        base.tcpd_party_type = ""
        base.tcpd_frequent_abbrev = ""
        base.curator_note = (
            f"TCPD Party_ID {pid_tcpd} present in AE/GE panel but absent "
            f"from per-party catalogue; cannot derive mint payload "
            f"(short / full / type / abbrevs)."
        )
        return base
    base.tcpd_party_name = meta.party_name
    base.tcpd_party_type = meta.party_type
    base.tcpd_frequent_abbrev = meta.frequent_abbrev

    # Step 1: does TCPD's preferred abbreviation already map in our roster?
    bridge_keys = [k for k in (meta.frequent_abbrev, meta.last_abbrev, label) if k]
    target_pid: str | None = None
    for k in bridge_keys:
        hit = claimed_aliases.get(k)
        if hit is not None:
            target_pid = hit
            break

    if target_pid is not None:
        # alias-add: the publisher label slots into the existing canonical row.
        claimed_by = claimed_aliases.get(label)
        if claimed_by is not None and claimed_by != target_pid:
            base.action = "disputed"
            base.curator_note = (
                f"would alias {label!r} to {target_pid} (matched via "
                f"{meta.frequent_abbrev or meta.last_abbrev}) but the label "
                f"is already claimed as alias by {claimed_by!r} for a "
                f"different canonical party."
            )
            return base
        base.proposed_party_id = target_pid
        base.action = "alias-add"
        bridge = (
            meta.frequent_abbrev
            if claimed_aliases.get(meta.frequent_abbrev) == target_pid
            else (meta.last_abbrev or label)
        )
        base.curator_note = (
            f"TCPD Party_ID {pid_tcpd} ({meta.party_name!r}); "
            f"bridges to existing canonical via abbreviation {bridge!r}."
        )
        return base

    # Step 2: no canonical match -> mint-new with slug from frequent_abbrev.
    abbrev_for_slug = meta.frequent_abbrev or meta.last_abbrev or label
    proposed = _slug_from_abbrev(abbrev_for_slug)
    if proposed in by_pid:
        # Slug collision: the abbrev maps to an existing canonical pid,
        # but that pid's short / aliases didn't carry our bridge keys.
        # Treat as alias-add (the slug IS the canonical row we'd target).
        claimed_by = claimed_aliases.get(label)
        if claimed_by is not None and claimed_by != proposed:
            base.action = "disputed"
            base.curator_note = (
                f"mint slug {proposed!r} already exists but label "
                f"{label!r} is claimed by {claimed_by!r}."
            )
            return base
        base.proposed_party_id = proposed
        base.action = "alias-add"
        base.curator_note = (
            f"TCPD Party_ID {pid_tcpd} ({meta.party_name!r}); slug "
            f"{proposed!r} pre-exists in parties.csv but short / aliases "
            f"do not carry the TCPD bridge keys "
            f"({'|'.join(bridge_keys)!r})."
        )
        return base

    # Fresh mint.
    claimed_by = claimed_aliases.get(label)
    if claimed_by is not None:
        base.action = "disputed"
        base.curator_note = (
            f"would mint {proposed} for TCPD Party_ID {pid_tcpd} but "
            f"label {label!r} is already aliased to {claimed_by!r}."
        )
        return base
    base.proposed_party_id = proposed
    base.action = "mint-new"
    base.curator_note = (
        f"TCPD Party_ID {pid_tcpd} ({meta.party_name!r}); minting new "
        f"slug {proposed!r} from frequent_abbrev {meta.frequent_abbrev!r}."
    )
    return base


# --- emit -------------------------------------------------------------------


VERDICT_FIELDS = [
    "external_key",
    "party_short_raw",
    "state",
    "year",
    "n_rows",
    "tcpd_party_id",
    "tcpd_party_type",
    "tcpd_party_name",
    "tcpd_frequent_abbrev",
    "current_party_id",
    "proposed_party_id",
    "action",
    "oracle",
    "curator_note",
]


def _write_verdict_csv(path: Path, verdicts: list[Verdict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=VERDICT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for v in verdicts:
            writer.writerow({
                "external_key": v.external_key,
                "party_short_raw": v.party_short_raw,
                "state": v.state,
                "year": v.year,
                "n_rows": v.n_rows,
                "tcpd_party_id": v.tcpd_party_id,
                "tcpd_party_type": v.tcpd_party_type,
                "tcpd_party_name": v.tcpd_party_name,
                "tcpd_frequent_abbrev": v.tcpd_frequent_abbrev,
                "current_party_id": v.current_party_id,
                "proposed_party_id": v.proposed_party_id,
                "action": v.action,
                "oracle": v.oracle,
                "curator_note": v.curator_note,
            })


def _report(verdicts: list[Verdict]) -> None:
    by_action: Counter[str] = Counter()
    by_oracle: Counter[tuple[str, str]] = Counter()
    rows_by_action: Counter[str] = Counter()
    rows_by_oracle: Counter[tuple[str, str]] = Counter()
    for v in verdicts:
        by_action[v.action] += 1
        by_oracle[(v.action, v.oracle)] += 1
        rows_by_action[v.action] += v.n_rows
        rows_by_oracle[(v.action, v.oracle)] += v.n_rows
    total_labels = sum(by_action.values())
    total_rows = sum(rows_by_action.values())
    print()
    print(f"verdicts: {total_labels} labels covering {total_rows} UNK rows")
    print()
    print("by action (labels / rows):")
    for action in ("alias-add", "mint-new", "disputed", "skip"):
        if by_action[action]:
            print(
                f"  {action:>10s}: {by_action[action]:>5d} / "
                f"{rows_by_action[action]:>6d}"
            )
    print()
    print("by (action, oracle):")
    for (action, oracle), count in sorted(by_oracle.items()):
        print(
            f"  {action:>10s} {oracle:>15s}: {count:>5d} labels / "
            f"{rows_by_oracle[(action, oracle)]:>6d} rows"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sha-tag",
        default=None,
        help=(
            "Override the verdict.csv directory tag. Default: short git "
            "sha of HEAD."
        ),
    )
    args = parser.parse_args()

    print("[1/6] Loading TCPD per-candidacy panel (AE + GE)...")
    lbl_to_pids, lbl_state_to_pids, _ = _build_tcpd_panel_indexes()
    print(f"      {len(lbl_to_pids)} distinct labels indexed across TCPD.")

    print("[2/6] Loading TCPD per-party catalogue...")
    pid_meta = _build_tcpd_catalogue()
    print(f"      {len(pid_meta)} distinct Party_IDs in catalogue.")

    print("[3/6] Loading legacy elections_candidacies.parquet (recovered)...")
    parquet_idx = _build_parquet_index()
    print(f"      {len(parquet_idx)} distinct labels with non-UNK resolution.")

    print("[4/6] Loading current parties.csv...")
    _, _, by_pid, claimed_aliases = _load_parties_csv()
    print(f"      {len(by_pid)} canonical party_ids; {len(claimed_aliases)} claimed aliases.")

    print("[5/6] Walking UNK rows in candidacies.csv corpus...")
    unk_by_label = _walk_unk_rows()
    total_unk_rows = sum(r.n_rows for r in unk_by_label.values())
    print(
        f"      {len(unk_by_label)} distinct UNK with-label publisher "
        f"labels covering {total_unk_rows} rows."
    )

    print("[6/6] Correlating...")
    verdicts: list[Verdict] = []
    for label in sorted(unk_by_label):
        verdicts.append(
            _decide(
                unk_by_label[label],
                lbl_to_pids=lbl_to_pids,
                lbl_state_to_pids=lbl_state_to_pids,
                pid_meta=pid_meta,
                parquet_idx=parquet_idx,
                by_pid=by_pid,
                claimed_aliases=claimed_aliases,
            )
        )

    sha = args.sha_tag or _git_short_sha()
    verdict_path = VERDICT_ROOT / sha / "verdict.csv"
    _write_verdict_csv(verdict_path, verdicts)
    _report(verdicts)
    print()
    print(f"verdict written: {verdict_path.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
