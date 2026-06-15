"""ADR / MyNeta 2014 Lok Sabha winners-affidavit enrichment adapter.

Reads the ADR-curated affidavit-disclosure CSV at
`datasets/ephemeral/2014_lok_sabha_affidavits.csv` and UPSERTs four
disclosure columns onto matching winner rows in
`datasets/elections/parliament/election=2014/candidacies.csv`:

  * criminal_cases_declared
  * total_assets_inr
  * total_liabilities_inr
  * declared_election_expense_inr

These are entity-attribute columns on the candidacy dimension (Max's
Side A; OWID precedent — see `docs/concepts/indicator-catalogue.md`).
Aggregate rollups (e.g. "% of state's MPs with declared criminal cases")
are deferred to a future FB-1 PR.

Join strategy (all passes are deterministic exact-match — no fuzzy /
probabilistic logic, per plan D2):

  * Pass 1: normalised(affidavit.Constituency) ==
            normalised(winner.constituency_name)
            AND normalised(affidavit.Candidate) ==
                normalised(winner.candidate_name)
  * Pass 2: normalised(affidavit.AltSpelling)  ==
            normalised(winner.constituency_name)
            AND normalised(affidavit.Candidate) ==
                normalised(winner.candidate_name)
            (AltSpelling is the alternate constituency spelling in the
             affidavit source — verified by inspection.)
  * Pass 3: alias-resolved constituency match via
            `datasets/_overrides/affidavit-2014-pc-aliases.csv`
            (hand-curated 1-to-1 spelling-drift table, oracle-verified;
             see the overlay file's header for justification.)
  * Pass 4: single-winner-in-PC fallback after Passes 1-3 + alias
            resolution — if exactly one winner remains unclaimed for the
            normalised PC, claim it. Safe because each LS PC has exactly
            one winner by definition, so a constituency match + uniqueness
            implies the affidavit row IS that winner.

After all four passes, if `unmatched_count > 0`, write the unmatched
affidavit rows to
`datasets/_ops/affidavit-2014-unmatched-YYYY-MM-DD.csv` and exit with
code 2 (D2 / E1).
"""

from __future__ import annotations

import csv
import datetime as _dt
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from yen_gov.canonical.adapters.myneta._normalisers import (
    normalise_candidate_name,
    normalise_constituency_name,
)
from yen_gov.canonical.citation import derive_source_id

# Source citation triple — fed verbatim to `derive_source_id`. The three
# strings together form the durable identity of this source row in
# `datasets/data/entities/source.csv`. Editing any of these strings would
# mint a new source_id and orphan the previously-written rows.
SOURCE_PRODUCER = "Association for Democratic Reforms (ADR / MyNeta)"
SOURCE_TITLE = "Lok Sabha 2014 Winners — Affidavit Analysis (MyNeta)"
SOURCE_VINTAGE = "2014"
SOURCE_URL = "https://myneta.info/ls2014/"

# Election scope (matches `datasets/elections/parliament/election=2014/`).
ELECTION_YEAR = 2014

# Path constants — repo-relative; concatenated with the injected `root`.
AFFIDAVIT_REL_PATH = Path("datasets") / "ephemeral" / "2014_lok_sabha_affidavits.csv"
CANDIDACIES_REL_PATH = (
    Path("datasets")
    / "elections"
    / "parliament"
    / f"election={ELECTION_YEAR}"
    / "candidacies.csv"
)
ALIAS_OVERLAY_REL_PATH = (
    Path("datasets") / "_overrides" / "affidavit-2014-pc-aliases.csv"
)
SOURCE_CSV_REL_PATH = Path("datasets") / "data" / "entities" / "source.csv"
SOURCE_CSV_FIELDNAMES = ["source_id", "producer", "title", "vintage", "url"]

# The 4 columns this adapter writes onto candidacies.csv. Order matters:
# this is the order they will appear in the rewritten file. They are
# appended at the END of the existing column list to minimise churn for
# any consumer that reads by position.
ENRICHMENT_COLUMNS: tuple[str, ...] = (
    "criminal_cases_declared",
    "total_assets_inr",
    "total_liabilities_inr",
    "declared_election_expense_inr",
)

# Sidecar for Pass-2/3/4 matched rows. The processing_note marker is
# appended to the existing note (semicolon-separated) so that the
# upstream ECI/TCPD provenance is preserved alongside the affidavit-join
# attribution. Pass-1 matches get no note (the cleanest case).
_PROCESSING_NOTE_BY_PASS: dict[int, str] = {
    2: "affidavit join: AltSpelling constituency match",
    3: "affidavit join: PC-alias overlay",
    4: "affidavit join: 1:1 PC fallback",
}


# ---------------------------------------------------------------------------
# Internal dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AffidavitRow:
    sno: str
    candidate: str
    constituency: str
    party: str
    criminal_cases: str
    education: str
    total_assets: str
    liabilities: str
    sex: str
    alt_spelling: str
    election_expense: str

    @classmethod
    def from_dict(cls, raw: dict[str, str]) -> "AffidavitRow":
        return cls(
            sno=(raw.get("Sno") or "").strip(),
            candidate=(raw.get("Candidate") or "").strip(),
            constituency=(raw.get("Constituency") or "").strip(),
            party=(raw.get("Party") or "").strip(),
            criminal_cases=(raw.get("CriminalCase") or "").strip(),
            education=(raw.get("Education") or "").strip(),
            total_assets=(raw.get("TotalAssets") or "").strip(),
            liabilities=(raw.get("Liabilities") or "").strip(),
            sex=(raw.get("Sex") or "").strip(),
            alt_spelling=(raw.get("AltSpelling") or "").strip(),
            election_expense=(raw.get("ElectionExpense") or "").strip(),
        )


@dataclass(frozen=True)
class AdapterReport:
    """Structured summary of an adapter run.

    Used by CLI + tests. Includes raw counters AND the resolved
    source_id (handy for downstream verification + handover-doc receipts).
    """

    affidavit_count: int
    winner_count: int
    pass1_matched: int
    pass2_matched: int
    pass3_matched: int
    pass4_matched: int
    unmatched_count: int
    source_id: str
    unmatched_csv_path: Path | None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def enrich_2014_ls_candidacies(root: Path, affidavit_path: Path) -> AdapterReport:
    """Execute the full Row B enrichment.

    Args:
        root: repo root (the dir that contains `datasets/`).
        affidavit_path: absolute or repo-relative path to the affidavit CSV.

    Returns:
        AdapterReport with per-pass counters and resolved source_id.

    Side effects (on success — `unmatched_count == 0`):
        * Writes 4 new columns (or refreshes existing values) into
          `<root>/datasets/elections/parliament/election=2014/candidacies.csv`
          for each matched winner row.
        * Idempotently registers the ADR/MyNeta source citation in
          `<root>/datasets/data/entities/source.csv`. The `source_id`
          column on candidacy rows is NOT touched (the ECI-publisher
          attribution of votes / party / position stays pristine); the
          MyNeta citation chain is preserved out-of-band via
          source.csv + columns.json changelog + commit message.
        * Stamps `processing_level='major'` and appends a
          `processing_note` marker on Pass 2/3/4 matches.

    Side effects (on `unmatched_count > 0`):
        * Writes the unmatched-affidavit list to
          `<root>/datasets/_ops/affidavit-2014-unmatched-YYYY-MM-DD.csv`.
        * Does NOT touch candidacies.csv or source.csv. Idempotent abort.
    """
    affidavit_rows = _read_affidavits(affidavit_path)
    candidacies_path = root / CANDIDACIES_REL_PATH
    cand_fieldnames, cand_rows = _read_candidacies(candidacies_path)
    winners = [
        i for i, r in enumerate(cand_rows)
        if r.get("election_year", "").strip() == str(ELECTION_YEAR)
        and r.get("result", "").strip() == "won"
    ]

    aliases = _read_alias_overlay(root / ALIAS_OVERLAY_REL_PATH)

    matches, unmatched, per_pass = _join(
        affidavit_rows=affidavit_rows,
        winner_indices=winners,
        cand_rows=cand_rows,
        aliases=aliases,
    )

    if unmatched:
        # ABORT path (D2 / E1). Write sidecar; do NOT touch candidacies.
        sidecar = _write_unmatched_sidecar(root, unmatched)
        return AdapterReport(
            affidavit_count=len(affidavit_rows),
            winner_count=len(winners),
            pass1_matched=per_pass[1],
            pass2_matched=per_pass[2],
            pass3_matched=per_pass[3],
            pass4_matched=per_pass[4],
            unmatched_count=len(unmatched),
            source_id="",
            unmatched_csv_path=sidecar,
        )

    # ENRICH path. Register source FIRST so the citation row exists in
    # source.csv (operator-visible audit trail for the affidavit data);
    # then rewrite candidacies.csv with the 4 new cols populated. We do
    # NOT stamp source_id onto candidacy rows — the ECI publisher
    # attribution there stays pristine (see `_apply_enrichment` docstring
    # for the full attribution chain).
    source_id = _get_or_mint_source(root)
    _apply_enrichment(
        candidacies_path=candidacies_path,
        cand_fieldnames=cand_fieldnames,
        cand_rows=cand_rows,
        matches=matches,
    )

    return AdapterReport(
        affidavit_count=len(affidavit_rows),
        winner_count=len(winners),
        pass1_matched=per_pass[1],
        pass2_matched=per_pass[2],
        pass3_matched=per_pass[3],
        pass4_matched=per_pass[4],
        unmatched_count=0,
        source_id=source_id,
        unmatched_csv_path=None,
    )


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def _read_affidavits(path: Path) -> list[AffidavitRow]:
    with path.open(encoding="utf-8", newline="") as fh:
        return [AffidavitRow.from_dict(r) for r in csv.DictReader(fh)]


def _read_candidacies(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    return fieldnames, rows


def _read_alias_overlay(path: Path) -> dict[tuple[str, str], str]:
    """Return {(normalised_affidavit_pc, state_slug): normalised_canonical_pc}.

    If the overlay file is missing, returns an empty dict — adapter will
    still run, just without Pass 3. Tests that exercise Pass 3 supply a
    temp overlay via the alternate constructor path.

    The on-disk overlay carries a `#`-prefixed comment header above the
    actual CSV column row so that future curators have inline guidance
    on the file's purpose. We strip those comment lines before handing
    the byte stream to `csv.DictReader`.
    """
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as fh:
        # Filter out shell-style comment lines BEFORE csv parsing.
        data_lines = [ln for ln in fh if not ln.lstrip().startswith("#")]
    out: dict[tuple[str, str], str] = {}
    reader = csv.DictReader(data_lines)
    for row in reader:
        aff_pc = (row.get("normalised_affidavit_pc") or "").strip()
        can_pc = (row.get("normalised_canonical_pc") or "").strip()
        state = (row.get("state") or "").strip()
        if aff_pc and can_pc and state:
            out[(aff_pc, state)] = can_pc
    return out


# ---------------------------------------------------------------------------
# Join engine
# ---------------------------------------------------------------------------


def _join(
    *,
    affidavit_rows: list[AffidavitRow],
    winner_indices: list[int],
    cand_rows: list[dict[str, str]],
    aliases: dict[tuple[str, str], str],
) -> tuple[
    list[tuple[AffidavitRow, int, int]],  # [(affidavit, cand_row_index, pass_no)]
    list[AffidavitRow],
    dict[int, int],
]:
    """Run the four deterministic match passes.

    Returns (matches, unmatched, per_pass_counts). `matches` is a list of
    `(affidavit_row, candidacy_row_index, pass_no_1_to_4)`.
    """
    # Build lookup tables over the winner subset only.
    winner_by_const_cand: dict[tuple[str, str], list[int]] = {}
    winner_by_const: dict[str, list[int]] = {}
    for idx in winner_indices:
        w = cand_rows[idx]
        nc = normalise_constituency_name(w.get("constituency_name", ""))
        nn = normalise_candidate_name(w.get("candidate_name", ""))
        winner_by_const_cand.setdefault((nc, nn), []).append(idx)
        winner_by_const.setdefault(nc, []).append(idx)

    matches: list[tuple[AffidavitRow, int, int]] = []
    unmatched: list[AffidavitRow] = []
    claimed: set[int] = set()
    per_pass: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}

    def _claim(idx_list: list[int]) -> int | None:
        free = [i for i in idx_list if i not in claimed]
        if len(free) == 1:
            return free[0]
        return None

    for aff in affidavit_rows:
        nc_const = normalise_constituency_name(aff.constituency)
        nc_alt = normalise_constituency_name(aff.alt_spelling)
        nn_cand = normalise_candidate_name(aff.candidate)

        # Pass 1: (Constituency, Candidate)
        idx = _claim(winner_by_const_cand.get((nc_const, nn_cand), []))
        if idx is not None:
            matches.append((aff, idx, 1))
            claimed.add(idx)
            per_pass[1] += 1
            continue

        # Pass 2: (AltSpelling-as-Constituency, Candidate)
        if nc_alt:
            idx = _claim(winner_by_const_cand.get((nc_alt, nn_cand), []))
            if idx is not None:
                matches.append((aff, idx, 2))
                claimed.add(idx)
                per_pass[2] += 1
                continue

        # Pass 3: alias overlay. We do not know the state from the
        # affidavit row directly, so we sweep all (key, state) -> canonical
        # mappings whose key matches either affidavit spelling. The state
        # constrains the candidate by virtue of the winner-side lookup.
        alias_candidates: list[int] = []
        for (alias_key, state_slug), canonical_pc in aliases.items():
            if alias_key in (nc_const, nc_alt):
                # Restrict to winners in (canonical_pc) AND state.
                for w_idx in winner_by_const.get(canonical_pc, []):
                    if cand_rows[w_idx].get("state", "").strip() == state_slug:
                        if w_idx not in claimed:
                            alias_candidates.append(w_idx)
        # Dedupe + uniqueness
        alias_candidates = list({i: None for i in alias_candidates}.keys())
        if len(alias_candidates) == 1:
            idx = alias_candidates[0]
            matches.append((aff, idx, 3))
            claimed.add(idx)
            per_pass[3] += 1
            continue
        elif len(alias_candidates) > 1:
            # Tie-break by candidate name match.
            cand_filtered = [
                i for i in alias_candidates
                if normalise_candidate_name(
                    cand_rows[i].get("candidate_name", "")
                ) == nn_cand
            ]
            if len(cand_filtered) == 1:
                idx = cand_filtered[0]
                matches.append((aff, idx, 3))
                claimed.add(idx)
                per_pass[3] += 1
                continue

        # Pass 4: single-winner-in-PC fallback. Try both affidavit spellings.
        for nc_try in (nc_const, nc_alt):
            if not nc_try:
                continue
            idx = _claim(winner_by_const.get(nc_try, []))
            if idx is not None:
                matches.append((aff, idx, 4))
                claimed.add(idx)
                per_pass[4] += 1
                break
        else:
            unmatched.append(aff)
            continue
        # break-from-for-else gymnastics: if we hit the break, we matched

    return matches, unmatched, per_pass


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------


def _coerce_int_or_none(s: str) -> int | None:
    """Affidavit numeric cells: empty string, '-1', or 'Nil' -> None.

    ADR encodes "not disclosed" as -1, blank, or sometimes "Nil". This
    helper folds all three into None so the candidacies CSV stays clean.
    """
    if s is None:
        return None
    t = s.strip()
    if not t:
        return None
    if t in ("-1", "Nil", "nil", "NIL", "N/A", "NA"):
        return None
    try:
        # Some cells carry commas e.g. "1,23,456" — strip them.
        return int(t.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def _apply_enrichment(
    *,
    candidacies_path: Path,
    cand_fieldnames: list[str],
    cand_rows: list[dict[str, str]],
    matches: list[tuple[AffidavitRow, int, int]],
) -> None:
    """Rewrite candidacies.csv with the 4 new cols populated for matches.

    Other (non-matched) rows keep an empty string in the 4 new cols.

    Per user binding 2026-06-15 ("dont try to change data already
    published"): `source_id` on the candidacies row is NOT touched. The
    ECI-publisher attribution of votes / party / position stays
    pristine. The MyNeta affidavit-source citation chain is preserved
    out-of-band via:
      * source.csv carries the MyNeta source_id row (registered by
        `_get_or_mint_source`).
      * columns.json x-changelog entry for the schema bump explicitly
        cites the MyNeta source_id and the 4 new cols.
      * The PR commit message + handover-doc bake in the same trail.
    A future schema bump may introduce a sidecar column (e.g.
    `affidavit_source_id`) to make the linkage explicit on the row; the
    plan-doc defers that to FB-1.

    Pass 2/3/4 matches still receive `processing_level='major'` + a
    `processing_note` marker citing the join pass — that IS a publisher
    enrichment audit-trail, distinct from row source attribution.
    """
    # Extend header if needed.
    new_fieldnames = list(cand_fieldnames)
    for col in ENRICHMENT_COLUMNS:
        if col not in new_fieldnames:
            new_fieldnames.append(col)

    # Initialise blank cells for ALL rows so the CSV is rectangular.
    for r in cand_rows:
        for col in ENRICHMENT_COLUMNS:
            r.setdefault(col, "")

    # Apply matched values.
    for aff, idx, pass_no in matches:
        row = cand_rows[idx]
        values = {
            "criminal_cases_declared": _coerce_int_or_none(aff.criminal_cases),
            "total_assets_inr": _coerce_int_or_none(aff.total_assets),
            "total_liabilities_inr": _coerce_int_or_none(aff.liabilities),
            "declared_election_expense_inr": _coerce_int_or_none(aff.election_expense),
        }
        for col, val in values.items():
            row[col] = "" if val is None else str(val)
        # processing_level + note for Pass 2/3/4 only (Pass 1 = clean
        # exact match, no enrichment audit-trail needed). Idempotent:
        # skip the append if the marker is already present (so back-to-
        # back runs of the adapter produce byte-identical output).
        if pass_no in _PROCESSING_NOTE_BY_PASS:
            row["processing_level"] = "major"
            existing_note = (row.get("processing_note") or "").strip()
            marker = _PROCESSING_NOTE_BY_PASS[pass_no]
            if marker in existing_note:
                # Already stamped on a prior run; leave note unchanged.
                pass
            elif existing_note:
                row["processing_note"] = f"{existing_note}; {marker}"
            else:
                row["processing_note"] = marker

    _write_csv(candidacies_path, new_fieldnames, cand_rows)


def _write_csv(
    path: Path,
    fieldnames: list[str],
    rows: Iterable[dict[str, str]],
) -> None:
    """LF-newline CSV writer that matches the repo's existing on-disk
    encoding convention (LF, UTF-8, no BOM, no trailing newline-quirks)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for r in rows:
            # Restrict to declared fieldnames to defend against accidental
            # extra keys leaking in via setdefault elsewhere.
            writer.writerow({k: r.get(k, "") for k in fieldnames})


def _write_unmatched_sidecar(
    root: Path,
    unmatched: list[AffidavitRow],
) -> Path:
    today = _dt.date.today().isoformat()
    out_path = root / "datasets" / "_ops" / f"affidavit-2014-unmatched-{today}.csv"
    fieldnames = [
        "Sno",
        "Candidate",
        "Constituency",
        "Party",
        "AltSpelling",
        "failure_reason",
    ]
    rows: list[dict[str, str]] = []
    for aff in unmatched:
        rows.append({
            "Sno": aff.sno,
            "Candidate": aff.candidate,
            "Constituency": aff.constituency,
            "Party": aff.party,
            "AltSpelling": aff.alt_spelling,
            "failure_reason": (
                "no candidacies winner matched on Pass 1-4 "
                "(constituency/altspelling/alias/1:1-fallback)"
            ),
        })
    _write_csv(out_path, fieldnames, rows)
    return out_path


# ---------------------------------------------------------------------------
# source.csv idempotent register
# ---------------------------------------------------------------------------


def _get_or_mint_source(root: Path) -> str:
    """Find or insert the ADR/MyNeta citation row.

    Returns the row's `source_id`. Pattern mirrors thecont1 adapter.
    """
    csv_path = root / SOURCE_CSV_REL_PATH
    rows: list[dict[str, str]] = []
    if csv_path.exists():
        with csv_path.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))

    for row in rows:
        if (
            (row.get("producer") or "").strip() == SOURCE_PRODUCER
            and (row.get("title") or "").strip() == SOURCE_TITLE
            and (row.get("vintage") or "").strip() == SOURCE_VINTAGE
        ):
            return (row.get("source_id") or "").strip()

    source_id = derive_source_id(
        producer=SOURCE_PRODUCER,
        title=SOURCE_TITLE,
        vintage=SOURCE_VINTAGE,
    )
    new_row = {
        "source_id": source_id,
        "producer": SOURCE_PRODUCER,
        "title": SOURCE_TITLE,
        "vintage": SOURCE_VINTAGE,
        "url": SOURCE_URL,
    }
    # APPEND-only: never rewrite the whole file. Matches the convention
    # used by `thecont1_mh_ae2024._get_or_mint_thecont1_source`.
    with csv_path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=SOURCE_CSV_FIELDNAMES, lineterminator="\n"
        )
        writer.writerow(new_row)
    return source_id


# ---------------------------------------------------------------------------
# CLI shim — invoked by `python -m yen_gov enrich-2014-ls-candidacies-with-affidavits`
# ---------------------------------------------------------------------------


def main(root: Path, affidavit_path: Path) -> int:
    """Pure CLI shim. Prints a JSON report; returns OS exit code (0 or 2)."""
    import json

    report = enrich_2014_ls_candidacies(root=root, affidavit_path=affidavit_path)
    payload = {
        "affidavit_count": report.affidavit_count,
        "winner_count": report.winner_count,
        "pass1_matched": report.pass1_matched,
        "pass2_matched": report.pass2_matched,
        "pass3_matched": report.pass3_matched,
        "pass4_matched": report.pass4_matched,
        "unmatched_count": report.unmatched_count,
        "source_id": report.source_id,
        "unmatched_csv_path": (
            str(report.unmatched_csv_path) if report.unmatched_csv_path else None
        ),
    }
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return 0 if report.unmatched_count == 0 else 2
