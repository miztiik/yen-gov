"""Correlate parliament 2024 + 2019 UNK candidacies against ECI Statement-33.

The ECI Statistical Report Statement-33 (Constituency Wise Detailed Result)
is the publisher's authoritative per-(PC, candidate) listing for a Lok Sabha
general election. It carries the publisher's ``Party Name`` (abbreviation)
for every candidate. Our parliament 2024 + 2019 candidacies.csv has ~890
rows where ``party_id == parties.IN.UNK`` because the publisher label on
``party_short_raw`` does not match any row in
``datasets/data/entities/parties.csv``.

This tool joins each UNK candidacy row against the ECI Statement-33 file by
``(constituency_name, candidate_name)``, then resolves the joined ECI label
against parties.csv:

1. ``NOTA`` / ``IND``: alias-add to the corresponding sentinel pid.
2. Existing ``short`` / ``aliases`` match (case-insensitive): alias-add.
3. No match: ``mint-new`` with ``parties.IN.<abbr>``. If that pid already
   exists with a different full, disambiguate to ``<abbr>_LS<year>``.

Per-label aggregation: rows are grouped by ``party_short_raw`` across both
years; if a label's joined ECI rows disagree (e.g. publisher emits same
short for two genuinely-different parties), pick the dominant ECI label
when it covers >= 80% of joined rows; otherwise skip the label entirely
with reason ``eci-internal-collision``.

Output: emits ``verdict.csv`` + ``skipped.csv`` under
``datasets/ephemeral/party-parity/eci-ls-s33/<run-id>/``. The verdict.csv
uses the PR #952 schema consumed by ``tools.correlate_unk_apply``; the
``tcpd_*`` column names are historical (the apply tool was authored for
PR-Q2 TCPD work) and carry ECI ``Party Name`` here.

Run from the repo root:

    python -m tools.correlate_unk_via_eci_ls_statement33
    python -m tools.correlate_unk_via_eci_ls_statement33 --years 2024
    python -m tools.correlate_unk_via_eci_ls_statement33 --limit 100

Apply the verdict via the existing seam:

    python -m tools.correlate_unk_apply --verdict-csv <path-to-verdict>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PARTIES_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "parties.csv"
ECI_FILE_2024 = (
    REPO_ROOT
    / "datasets"
    / "ephemeral"
    / "2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv"
)
ECI_FILE_2019 = (
    REPO_ROOT
    / "datasets"
    / "ephemeral"
    / "2019_india_loksabha_33. Constituency Wise Detailed Result.csv"
)
VERDICT_ROOT = (
    REPO_ROOT / "datasets" / "ephemeral" / "party-parity" / "eci-ls-s33"
)

# Verdict CSV schema (matches PR #952 / correlate_unk_apply consumer).
# The ``tcpd_*`` column names are historical: the apply tool was authored
# for TCPD work but reads these columns as opaque source-publisher data,
# so we reuse the same shape for ECI here.
VERDICT_FIELDNAMES = [
    "action",
    "proposed_party_id",
    "party_short_raw",
    "tcpd_frequent_abbrev",
    "tcpd_party_name",
    "tcpd_party_type",
    "state",
    "tcpd_start_year",
    "tcpd_last_year",
]

SKIPPED_FIELDNAMES = ["party_short_raw", "n_rows", "reason", "detail"]

NOTA_SENTINEL = "parties.IN.NOTA"
IND_SENTINEL = "parties.IN.IND"

# Threshold for picking the dominant ECI label when a publisher's
# UNK label maps to multiple ECI labels across constituencies.
DOMINANT_THRESHOLD = 0.80

# Header detection looks at the first N rows of the ECI file; both the
# 2024 (preamble at row 0+1, header at row 2) and 2019 (header at row 0
# with a BOM prefix + leading whitespace) variants fall well within this.
HEADER_PROBE_DEPTH = 10


# --- normalisation ----------------------------------------------------------


def normalise(s: str) -> str:
    """NFKD-ASCII + uppercase + strip-(SC/ST) suffix + collapse punctuation.

    Handles common Unicode-vs-ASCII gotchas: accented vowels decompose to
    base + combining mark (the mark is dropped), and non-ASCII punctuation
    (en-dash, em-dash, etc.) is collapsed to a single space so that names
    like "Andre\u2013Garcia" and "Andre-Garcia" produce identical keys.
    """
    s = unicodedata.normalize("NFKD", s or "")
    # Drop combining marks (e.g. the acute that decomposes off of "e\u0301").
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    # Collapse any remaining non-ASCII run (en-dash, em-dash, non-Latin
    # scripts, etc.) to a single space so it does not get silently
    # concatenated across the missing-character gap.
    s = re.sub(r"[^\x00-\x7F]+", " ", s)
    s = s.upper()
    # Strip ECI category-suffix like " (SC)", " (ST)", " (sc/st)" etc.
    s = re.sub(r"\s*\(\s*(SC|ST|SC/ST|ST/SC)\s*\)\s*$", "", s)
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _slugify_abbr(abbr: str) -> str:
    """Make ``abbr`` slug-safe (uppercase, ``[A-Z0-9_]`` only)."""
    s = re.sub(r"[^A-Za-z0-9_]+", "_", (abbr or "").upper()).strip("_")
    return s or "UNK"


# --- ECI file loading -------------------------------------------------------


def _detect_eci_header(rows: list[list[str]]) -> int:
    """Find the header row containing 'pc name' + 'candidate'/'candidates' + 'party name'.

    Raises ``ValueError`` if no header is found within the first
    ``HEADER_PROBE_DEPTH`` rows.
    """
    for idx in range(min(len(rows), HEADER_PROBE_DEPTH)):
        cells = [(c or "").lstrip("\ufeff").strip().lower() for c in rows[idx]]
        joined = " ".join(cells)
        if (
            ("pc name" in joined or "constituency" in joined)
            and "party name" in joined
            and ("candidate" in joined or "candidates" in joined)
        ):
            return idx
    raise ValueError(
        f"no ECI header found in first {HEADER_PROBE_DEPTH} rows; "
        f"probed rows: {rows[:HEADER_PROBE_DEPTH]!r}"
    )


def _find_col(header: list[str], *candidates: str) -> int:
    """Return the first column index whose normalised name matches a candidate."""
    norm = [(h or "").lstrip("\ufeff").strip().lower() for h in header]
    for c in candidates:
        c_l = c.strip().lower()
        for i, h in enumerate(norm):
            if h == c_l:
                return i
    raise ValueError(f"no column match for {candidates!r} in header {header!r}")


def load_eci_index(path: Path) -> dict[tuple[str, str], str]:
    """Build ``(normalised_pc, normalised_candidate) -> Party Name`` index.

    Handles both the 2024 multi-header preamble shape and the 2019
    single-row BOM-prefixed shape. Duplicate keys keep the first value
    (rare collisions are surfaced via the per-label collision logic
    downstream).
    """
    with path.open(encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header_idx = _detect_eci_header(rows)
    header = rows[header_idx]
    col_pc = _find_col(header, "PC Name", "PC NAME")
    col_cand = _find_col(
        header, "Candidate Name", "CANDIDATES NAME", "CANDIDATE NAME"
    )
    col_party = _find_col(header, "Party Name", "PARTY NAME")
    out: dict[tuple[str, str], str] = {}
    for row in rows[header_idx + 1 :]:
        if len(row) <= max(col_pc, col_cand, col_party):
            continue
        pc = (row[col_pc] or "").strip()
        cand = (row[col_cand] or "").strip()
        party = (row[col_party] or "").strip()
        if not pc or not cand or not party:
            continue
        key = (normalise(pc), normalise(cand))
        out.setdefault(key, party)
    return out


# --- parties.csv loading ----------------------------------------------------


def load_parties_index(
    parties_csv: Path,
) -> tuple[set[str], dict[str, str], dict[str, str]]:
    """Return ``(existing_pids, short_to_pid, alias_to_pid)`` keyed UPPER."""
    existing_pids: set[str] = set()
    short_to_pid: dict[str, str] = {}
    alias_to_pid: dict[str, str] = {}
    with parties_csv.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid = (row.get("party_id") or "").strip()
            if not pid:
                continue
            existing_pids.add(pid)
            short = (row.get("short") or "").strip().upper()
            if short:
                short_to_pid[short] = pid
            for a in (row.get("aliases") or "").split("|"):
                a_u = a.strip().upper()
                if a_u:
                    alias_to_pid[a_u] = pid
    return existing_pids, short_to_pid, alias_to_pid


def load_unk_rows_for_year(repo_root: Path, year: int) -> list[dict[str, str]]:
    """Walk the per-year parliament candidacies.csv; return UNK rows only."""
    path = (
        repo_root
        / "datasets"
        / "elections"
        / "parliament"
        / f"election={year}"
        / "candidacies.csv"
    )
    out: list[dict[str, str]] = []
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("party_id") or "").strip() == "parties.IN.UNK":
                out.append({**row, "_year": str(year)})
    return out


# --- resolution -------------------------------------------------------------


def resolve_eci_label(
    eci_label: str,
    existing_pids: set[str],
    short_to_pid: dict[str, str],
    alias_to_pid: dict[str, str],
    year: int,
) -> tuple[str, str, bool]:
    """Resolve an ECI publisher label to a parties.csv pid action.

    Returns ``(action, proposed_pid, was_disambiguated)``. ``action`` is
    ``alias-add`` or ``mint-new``. ``was_disambiguated`` is True when a
    naive ``parties.IN.<abbr>`` would have collided with an existing row
    and the proposal carries an ``_LS<year>`` (or ``_<n>``) suffix.
    """
    eci_u = (eci_label or "").strip().upper()
    if eci_u == "NOTA":
        return ("alias-add", NOTA_SENTINEL, False)
    if eci_u == "IND":
        return ("alias-add", IND_SENTINEL, False)
    if eci_u in short_to_pid:
        return ("alias-add", short_to_pid[eci_u], False)
    if eci_u in alias_to_pid:
        return ("alias-add", alias_to_pid[eci_u], False)
    # mint-new
    base = f"parties.IN.{_slugify_abbr(eci_label)}"
    if base not in existing_pids:
        return ("mint-new", base, False)
    # disambiguate
    disamb = f"{base}_LS{year}"
    if disamb not in existing_pids:
        return ("mint-new", disamb, True)
    for i in range(2, 100):
        cand = f"{disamb}_{i}"
        if cand not in existing_pids:
            return ("mint-new", cand, True)
    raise RuntimeError(f"unable to disambiguate {base!r}")


# --- correlation main -------------------------------------------------------


def _run_id(verdict_rows: list[dict[str, str]]) -> str:
    """9-char SHA256 of the sorted verdict content (deterministic run id)."""
    if not verdict_rows:
        return "empty0000"
    encoded = "\n".join(
        sorted(",".join(r.get(k, "") for k in VERDICT_FIELDNAMES) for r in verdict_rows)
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:9]


def _eci_path_for_year(repo_root: Path, year: int) -> Path:
    if year == 2024:
        return (
            repo_root
            / "datasets"
            / "ephemeral"
            / "2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv"
        )
    if year == 2019:
        return (
            repo_root
            / "datasets"
            / "ephemeral"
            / "2019_india_loksabha_33. Constituency Wise Detailed Result.csv"
        )
    raise ValueError(f"unsupported year {year}; only 2024 and 2019 are mapped")


def correlate(
    *,
    years: list[int],
    limit: int | None = None,
    repo_root: Path = REPO_ROOT,
    parties_csv: Path | None = None,
    eci_path_for_year=None,
    verdict_root: Path | None = None,
) -> dict:
    """Run the correlator end-to-end. Returns a dict of stats + output paths.

    ``eci_path_for_year`` is a hook for tests: a callable
    ``year -> Path`` overriding the default file resolution. Falls back
    to ``_eci_path_for_year(repo_root, year)`` when None.
    """
    parties_csv = parties_csv or (repo_root / "datasets" / "data" / "entities" / "parties.csv")
    verdict_root = verdict_root or (
        repo_root / "datasets" / "ephemeral" / "party-parity" / "eci-ls-s33"
    )
    if eci_path_for_year is None:
        def eci_path_for_year(y: int) -> Path:  # type: ignore[misc]
            return _eci_path_for_year(repo_root, y)

    existing_pids, short_to_pid, alias_to_pid = load_parties_index(parties_csv)

    # 1) ECI indexes per year
    eci_indexes: dict[int, dict[tuple[str, str], str]] = {}
    for year in years:
        eci_indexes[year] = load_eci_index(eci_path_for_year(year))

    # 2) Walk UNK candidacies; collect per-label entries
    label_to_entries: dict[str, list[tuple[int, str | None, dict[str, str]]]] = (
        defaultdict(list)
    )
    per_year_in: Counter[int] = Counter()
    seen = 0
    for year in years:
        for row in load_unk_rows_for_year(repo_root, year):
            if limit is not None and seen >= limit:
                break
            per_year_in[year] += 1
            seen += 1
            key = (
                normalise(row.get("constituency_name", "")),
                normalise(row.get("candidate_name", "")),
            )
            eci_label = eci_indexes[year].get(key)
            label = (row.get("party_short_raw") or "").strip()
            label_to_entries[label].append((year, eci_label, row))

    # 3) Per-label verdict decision
    verdict_rows: list[dict[str, str]] = []
    skipped_rows: list[dict[str, str]] = []
    per_year_stats: dict[int, Counter[str]] = defaultdict(Counter)
    skip_reason_rows: Counter[str] = Counter()

    for label, entries in sorted(label_to_entries.items()):
        if not label:
            # Empty label: should never reach here in a clean corpus, but
            # surface defensively.
            skipped_rows.append(
                {
                    "party_short_raw": "",
                    "n_rows": str(len(entries)),
                    "reason": "empty-publisher-label",
                    "detail": f"{len(entries)} UNK rows with blank party_short_raw",
                }
            )
            skip_reason_rows["empty-publisher-label"] += len(entries)
            for y, _, _ in entries:
                per_year_stats[y]["empty-label-skip"] += 1
            continue

        joined = [(y, e, r) for y, e, r in entries if e]
        n_total = len(entries)
        n_joined = len(joined)
        if n_joined == 0:
            skipped_rows.append(
                {
                    "party_short_raw": label,
                    "n_rows": str(n_total),
                    "reason": "eci-no-match-on-name",
                    "detail": (
                        f"none of {n_total} rows joined against ECI Statement-33 "
                        f"by (constituency, candidate)"
                    ),
                }
            )
            skip_reason_rows["eci-no-match-on-name"] += n_total
            for y, _, _ in entries:
                per_year_stats[y]["unmatched-join"] += 1
            continue

        eci_counter: Counter[str] = Counter(e for _, e, _ in joined)
        dominant_label, dominant_count = eci_counter.most_common(1)[0]
        fraction = dominant_count / n_joined
        if fraction < DOMINANT_THRESHOLD:
            skipped_rows.append(
                {
                    "party_short_raw": label,
                    "n_rows": str(n_total),
                    "reason": "eci-internal-collision",
                    "detail": (
                        f"no dominant ECI label among {n_joined} joined rows "
                        f"(top {dominant_label!r}={dominant_count}); "
                        f"distribution: {dict(eci_counter)}"
                    ),
                }
            )
            skip_reason_rows["eci-internal-collision"] += n_total
            for y, _, _ in entries:
                per_year_stats[y]["collision-skip"] += 1
            continue

        # Choose a representative year for disambiguation - the year
        # contributing the most joined rows for this label.
        year_tally: Counter[int] = Counter(y for y, _, _ in joined)
        rep_year = year_tally.most_common(1)[0][0]

        action, proposed_pid, was_disambig = resolve_eci_label(
            dominant_label,
            existing_pids,
            short_to_pid,
            alias_to_pid,
            rep_year,
        )
        verdict_rows.append(
            {
                "action": action,
                "proposed_party_id": proposed_pid,
                "party_short_raw": label,
                "tcpd_frequent_abbrev": dominant_label,
                "tcpd_party_name": dominant_label,
                "tcpd_party_type": "",
                "state": "",
                "tcpd_start_year": "",
                "tcpd_last_year": "",
            }
        )
        # Refresh local indexes so a subsequent verdict in the same run
        # detects the just-proposed mint as a collision target.
        if action == "mint-new":
            existing_pids.add(proposed_pid)
            short_to_pid[dominant_label.upper()] = proposed_pid

        if was_disambig:
            # Audit-log the disambiguation in skipped.csv as informational.
            skipped_rows.append(
                {
                    "party_short_raw": label,
                    "n_rows": str(n_total),
                    "reason": "existing-collision-disambiguated",
                    "detail": (
                        f"naive parties.IN.{_slugify_abbr(dominant_label)} already "
                        f"exists; mint as {proposed_pid}"
                    ),
                }
            )
            skip_reason_rows["existing-collision-disambiguated"] += 0  # informational

        bucket = "alias-resolved" if action == "alias-add" else "mint-resolved"
        for y, e, _ in joined:
            per_year_stats[y][bucket] += 1
        # Track the UNJOINED minority of an otherwise-resolved label.
        for y, e, _ in entries:
            if e is None:
                per_year_stats[y]["unmatched-within-resolved-label"] += 1

    # 4) Write outputs
    run_id = _run_id(verdict_rows)
    out_dir = verdict_root / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    verdict_path = out_dir / "verdict.csv"
    skipped_path = out_dir / "skipped.csv"
    with verdict_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=VERDICT_FIELDNAMES, lineterminator="\n")
        w.writeheader()
        w.writerows(verdict_rows)
    with skipped_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SKIPPED_FIELDNAMES, lineterminator="\n")
        w.writeheader()
        w.writerows(skipped_rows)

    return {
        "verdict_path": verdict_path,
        "skipped_path": skipped_path,
        "verdict_rows": len(verdict_rows),
        "skipped_rows": len(skipped_rows),
        "per_year_in": dict(per_year_in),
        "per_year_stats": {y: dict(per_year_stats[y]) for y in per_year_stats},
        "skip_reasons": dict(skip_reason_rows),
        "run_id": run_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--years",
        default="2024,2019",
        help="Comma-separated election years (default: 2024,2019)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit total UNK rows scanned (for fast smoke runs).",
    )
    args = parser.parse_args()
    years = [int(y.strip()) for y in args.years.split(",") if y.strip()]
    if not years:
        raise SystemExit("--years must be non-empty")

    result = correlate(years=years, limit=args.limit)

    print(f"verdict.csv: {result['verdict_path'].relative_to(REPO_ROOT).as_posix()}")
    print(f"skipped.csv: {result['skipped_path'].relative_to(REPO_ROOT).as_posix()}")
    print(f"run_id:      {result['run_id']}")
    print()
    print("=== per-year stats ===")
    for year in years:
        n_in = result["per_year_in"].get(year, 0)
        bucket = result["per_year_stats"].get(year, {})
        bucket_s = ", ".join(f"{k}={v}" for k, v in sorted(bucket.items()))
        print(f"  {year}: UNK in = {n_in}, {bucket_s}")
    print()
    print(f"  verdict rows: {result['verdict_rows']}")
    print(f"  skipped rows: {result['skipped_rows']}")
    print()
    print("=== skip-reason histogram (in UNK candidacy rows) ===")
    for r, n in sorted(result["skip_reasons"].items()):
        print(f"  {r}: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
