"""Walk the post-rebind candidacies.csv corpus, emit the UNK ledger.

See ``__init__.py`` for the high-level rationale. This is the executable
entry point.

Output: ``datasets/_ops/unk-ledger-2026-06-12.csv`` (CSV with header,
LF line endings, sorted by ``(body, state_slug, year, publisher_label)``).

Schema (14 columns):

  - ``body``: ``assembly`` | ``parliament``.
  - ``state_slug``: LGD state slug from the partition (assembly) or row
    (parliament). Always populated - every PC row carries a state.
  - ``year``: 4-digit election year parsed from the event-id partition
    name (the digits embedded in ``AeMar2003`` / ``LsGenJun2024`` /
    etc.).
  - ``event_id``: full event identifier verbatim (the ``election=...``
    partition segment).
  - ``publisher_label``: ``UPPER(party_short_raw)`` for the publisher
    label that resolved to ``parties.IN.UNK``. Upper-cased for stability
    so the join against the correlator's ``skipped.csv`` is exact (the
    correlator's ``external_key`` is also UPPER).
  - ``n_rows``: count of candidacy rows in this bucket.
  - ``tcpd_party_id`` / ``tcpd_party_name`` / ``tcpd_party_type`` /
    ``tcpd_start_year`` / ``tcpd_last_year`` / ``tcpd_state_name``:
    context from TCPD's per-party catalogue when the publisher label
    matches any of ``Party_Name`` (B1) / ``Frequent_Abbreviation`` /
    ``Last_Abbreviation`` / ``Abbreviations`` (B2). Empty when the
    label has no TCPD match (genuinely not in the 1962-2021 catalogue).
    Placeholder rows (``Party_Name == "NA'S"`` /
    ``"EXPANDED PARTY NAME NOT RELEASED BY THE ECI"``) are filtered out
    of the TCPD context just as they are in the correlator - their
    presence in the skip_reason is preserved instead.
    When the label matches multiple non-placeholder TCPD rows the
    candidate with the longest start->last window is picked (the most
    "established" claim is the most useful operator hint; this is an
    informational hint, not a binding decision, so deterministic
    tie-breaking is good enough).
  - ``skip_reason``: classification from the most recent correlator
    ``skipped.csv`` join (``not-in-tcpd-catalogue`` /
    ``tcpd-state-year-collision`` / ``tcpd-no-year-coverage`` /
    ``tcpd-placeholder-only`` / ``tcpd-state-disambig-contradiction`` /
    ``multiple-tcpd-candidates-unresolved`` / etc.). Empty when the
    correlator's per-label table has no entry for this publisher_label
    (rare; would mean the correlator resolved the label in some buckets
    but the bucket-level mint collision prevented it landing in others).
  - ``next_lookup_source``: hint for the next correlation pass:
    ``eci-statreport-<year>`` when year >= 1977 (ECI started publishing
    comprehensive statistical reports for general elections that year);
    ``wikipedia-and-press`` otherwise (pre-1977 micro-parties + cases
    where the publisher label isn't even in TCPD - a Wikipedia /
    contemporary-press search is the realistic next step). The heuristic
    is a hint, not a contract.

The tool is read-only against the corpus. The only file it writes is
the ledger CSV.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

# --- paths ------------------------------------------------------------------

TCPD_CATALOGUE = (
    REPO_ROOT
    / "datasets"
    / "ephemeral"
    / "TCPD-PoliticalPartiesIndia_1962_2021.csv"
)
ASSEMBLY_ROOT = REPO_ROOT / "datasets" / "elections" / "assembly"
PARLIAMENT_ROOT = REPO_ROOT / "datasets" / "elections" / "parliament"

# Correlator's verdict tree - we re-use its most recent skipped.csv to
# enrich the ledger's skip_reason column.
TCPD_CATALOGUE_VERDICT_ROOT = (
    REPO_ROOT / "datasets" / "ephemeral" / "party-parity" / "tcpd-catalogue"
)

LEDGER_DEFAULT_PATH = REPO_ROOT / "datasets" / "_ops" / "unk-ledger-2026-06-12.csv"

UNK_PID = "parties.IN.UNK"

# Same placeholder-name set as the correlator (kept in sync inline; the
# correlator's set is the authoritative copy at
# ``tools/correlate_unk_via_tcpd_catalogue/__main__.py`` -
# ``TCPD_PLACEHOLDER_NAMES``).
TCPD_PLACEHOLDER_NAMES: frozenset[str] = frozenset(
    {
        "NA'S",
        "EXPANDED PARTY NAME NOT RELEASED BY THE ECI",
    }
)

# Ledger schema (14 columns, written in this order).
LEDGER_FIELDS: list[str] = [
    "body",
    "state_slug",
    "year",
    "event_id",
    "publisher_label",
    "n_rows",
    "tcpd_party_id",
    "tcpd_party_name",
    "tcpd_party_type",
    "tcpd_start_year",
    "tcpd_last_year",
    "tcpd_state_name",
    "skip_reason",
    "next_lookup_source",
]


# --- helpers ----------------------------------------------------------------


def _normalise(label: str) -> str:
    """Upper-case, trim, collapse whitespace - the join key."""
    return re.sub(r"\s+", " ", (label or "").strip().upper())


def _year_from_event_id(event_id: str) -> str:
    """Extract the 4-digit year from an event-id partition value.

    Event-id shapes seen on disk: ``AeMar2003`` / ``LsGenJun2024`` /
    ``AeOct1962`` / ``Ls1971``. The 4-digit year is always present.
    Returns empty string if none found (defensive; not seen in practice).
    """
    m = re.search(r"(\d{4})", event_id or "")
    return m.group(1) if m else ""


def _next_lookup_source(year: str) -> str:
    """Heuristic: ECI statreports cover general elections from 1977 on.

    Returns ``eci-statreport-<year>`` when ``year >= 1977``, else
    ``wikipedia-and-press``. The heuristic is informational; the
    operator chooses the actual next step.
    """
    if year and year.isdigit() and int(year) >= 1977:
        return f"eci-statreport-{year}"
    return "wikipedia-and-press"


# --- TCPD catalogue index ---------------------------------------------------


def _build_tcpd_index(
    catalogue_csv: Path,
) -> tuple[
    dict[str, dict[str, str]],
    dict[str, list[str]],
    dict[str, list[str]],
]:
    """Return ``(pid_to_meta, full_to_pids, abbr_to_pids)``.

    - ``pid_to_meta[pid]``: collapsed per-party metadata (the row with
      the most-recent ``(Last_Year, Start_Year)`` carries
      ``party_name`` / ``party_type`` / ``state_name``; the
      ``start_year`` / ``last_year`` columns are min / max across rows).
    - ``full_to_pids[normalised(Party_Name)]``: list of pids sharing
      that full name (placeholder rows EXCLUDED so the ledger's TCPD
      context never carries a placeholder).
    - ``abbr_to_pids[upper(abbrev)]``: list of pids using that
      abbreviation (placeholder rows EXCLUDED for the same reason).
    """
    pid_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    if not catalogue_csv.exists():
        return {}, {}, {}
    with catalogue_csv.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            pid = (row.get("Party_ID") or "").strip()
            if pid in ("", "0"):
                continue
            pid_rows[pid].append(row)

    pid_to_meta: dict[str, dict[str, str]] = {}
    full_to_pids: dict[str, list[str]] = defaultdict(list)
    abbr_to_pids: dict[str, list[str]] = defaultdict(list)

    for pid, rows in pid_rows.items():
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
        party_name = (canonical.get("Party_Name") or "").strip()
        is_placeholder = party_name.upper().strip() in TCPD_PLACEHOLDER_NAMES

        all_abbrevs: set[str] = set()
        for r in rows:
            for col in ("Frequent_Abbreviation", "Last_Abbreviation"):
                v = (r.get(col) or "").strip().upper()
                if v:
                    all_abbrevs.add(v)
            for token in (r.get("Abbreviations") or "").split("|"):
                v = token.strip().upper()
                if v:
                    all_abbrevs.add(v)

        # state_name = canonical row's State_Name (sometimes "All_States"
        # for nationwide parties; we keep it verbatim).
        state_name = (canonical.get("State_Name") or "").strip()

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

        pid_to_meta[pid] = {
            "party_id": pid,
            "party_name": party_name,
            "party_type": (canonical.get("Party_Type") or "").strip(),
            "state_name": state_name,
            "start_year": str(start_year) if start_year else "",
            "last_year": str(last_year) if last_year else "",
        }

        if is_placeholder:
            continue

        normalised_full = _normalise(party_name)
        if normalised_full:
            full_to_pids[normalised_full].append(pid)
        for abbrev in all_abbrevs:
            abbr_to_pids[abbrev].append(pid)

    return pid_to_meta, dict(full_to_pids), dict(abbr_to_pids)


def _tcpd_lookup(
    label_upper: str,
    *,
    pid_to_meta: dict[str, dict[str, str]],
    full_to_pids: dict[str, list[str]],
    abbr_to_pids: dict[str, list[str]],
) -> dict[str, str]:
    """Look up TCPD context for an UPPER publisher label.

    Returns the 6-tuple of TCPD columns as a dict (keys
    ``tcpd_party_id`` / ``tcpd_party_name`` / ``tcpd_party_type`` /
    ``tcpd_start_year`` / ``tcpd_last_year`` / ``tcpd_state_name``).
    Empty values when no match.

    Resolution order: B1 (full-name) -> B2 (abbreviation). When multiple
    pids share the key, the candidate with the longest
    (start_year -> last_year) window is picked - the most-established
    claim is the most useful operator hint. Tie-break on `pid` for
    determinism.
    """
    empty = {
        "tcpd_party_id": "",
        "tcpd_party_name": "",
        "tcpd_party_type": "",
        "tcpd_start_year": "",
        "tcpd_last_year": "",
        "tcpd_state_name": "",
    }
    candidates = list(full_to_pids.get(label_upper, []))
    if not candidates:
        candidates = list(abbr_to_pids.get(label_upper, []))
    if not candidates:
        return empty

    def _window_key(pid: str) -> tuple[int, str]:
        m = pid_to_meta.get(pid, {})
        sy = m.get("start_year") or ""
        ly = m.get("last_year") or ""
        try:
            span = int(ly) - int(sy)
        except ValueError:
            span = 0
        # Sort by widest span DESC, then by pid ASC for determinism.
        return (-span, pid)

    chosen = sorted(candidates, key=_window_key)[0]
    meta = pid_to_meta.get(chosen, {})
    return {
        "tcpd_party_id": meta.get("party_id", ""),
        "tcpd_party_name": meta.get("party_name", ""),
        "tcpd_party_type": meta.get("party_type", ""),
        "tcpd_start_year": meta.get("start_year", ""),
        "tcpd_last_year": meta.get("last_year", ""),
        "tcpd_state_name": meta.get("state_name", ""),
    }


# --- skipped.csv join -------------------------------------------------------


def _latest_skipped_csv() -> Path | None:
    """Return the newest skipped.csv under the catalogue verdict tree."""
    if not TCPD_CATALOGUE_VERDICT_ROOT.exists():
        return None
    candidates = sorted(
        TCPD_CATALOGUE_VERDICT_ROOT.glob("*/skipped.csv"),
        key=lambda p: p.stat().st_mtime,
    )
    return candidates[-1] if candidates else None


def _load_skip_reasons(skipped_csv: Path | None) -> dict[str, str]:
    """Build ``UPPER(label) -> skip_reason`` from the most recent skipped.csv."""
    out: dict[str, str] = {}
    if skipped_csv is None or not skipped_csv.exists():
        return out
    with skipped_csv.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            key = (row.get("external_key") or "").strip().upper()
            reason = (row.get("skip_reason") or "").strip()
            if key and reason:
                out[key] = reason
    return out


# --- corpus walk ------------------------------------------------------------


def _walk_unk_buckets() -> dict[tuple[str, str, str, str, str], int]:
    """Walk candidacies.csv corpus, return UNK bucket -> n_rows count.

    Bucket key = ``(body, state_slug, year, event_id, publisher_label_upper)``.
    """
    csv.field_size_limit(10**7)
    buckets: Counter[tuple[str, str, str, str, str]] = Counter()
    for path in sorted(ASSEMBLY_ROOT.glob("state=*/election=*/candidacies.csv")):
        partition_state = ""
        event_id = ""
        for part in path.parts:
            if part.startswith("state="):
                partition_state = part.split("=", 1)[1]
            elif part.startswith("election="):
                event_id = part.split("=", 1)[1]
        year = _year_from_event_id(event_id)
        with path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if (row.get("party_id") or "").strip() != UNK_PID:
                    continue
                raw = (row.get("party_short_raw") or "").strip()
                if not raw:
                    continue
                # Row may carry an over-riding state column; prefer it
                # when present so the ledger keys on the row's truth
                # rather than the partition (in practice they always
                # agree for AE; the partition wins as a fallback).
                state_slug = (row.get("state") or "").strip() or partition_state
                buckets[("assembly", state_slug, year, event_id, raw.upper())] += 1

    for path in sorted(PARLIAMENT_ROOT.glob("election=*/candidacies.csv")):
        event_id = ""
        for part in path.parts:
            if part.startswith("election="):
                event_id = part.split("=", 1)[1]
        year = _year_from_event_id(event_id)
        with path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                if (row.get("party_id") or "").strip() != UNK_PID:
                    continue
                raw = (row.get("party_short_raw") or "").strip()
                if not raw:
                    continue
                state_slug = (row.get("state") or "").strip()
                buckets[("parliament", state_slug, year, event_id, raw.upper())] += 1

    return dict(buckets)


# --- emit -------------------------------------------------------------------


def emit_ledger(out_path: Path) -> tuple[int, int, int]:
    """Emit the ledger CSV. Returns (rows, distinct_labels, distinct_buckets)."""
    print("[1/4] Loading TCPD per-party catalogue...")
    pid_to_meta, full_to_pids, abbr_to_pids = _build_tcpd_index(TCPD_CATALOGUE)
    print(
        f"      {len(pid_to_meta)} Party_IDs; "
        f"{len(full_to_pids)} full-name keys; "
        f"{len(abbr_to_pids)} abbreviation keys."
    )

    print("[2/4] Loading correlator skipped.csv for skip_reason context...")
    skipped_csv = _latest_skipped_csv()
    skip_reasons = _load_skip_reasons(skipped_csv)
    if skipped_csv:
        rel = skipped_csv.relative_to(REPO_ROOT).as_posix()
        print(
            f"      loaded {len(skip_reasons)} skip_reason rows from {rel}."
        )
    else:
        print(
            "      no skipped.csv found under "
            "datasets/ephemeral/party-parity/tcpd-catalogue/; skip_reason "
            "column will be empty for every row."
        )

    print("[3/4] Walking candidacies.csv corpus for UNK buckets...")
    buckets = _walk_unk_buckets()
    print(
        f"      {len(buckets)} distinct (body, state, year, event, label) buckets; "
        f"{sum(buckets.values())} total UNK rows."
    )

    print("[4/4] Writing ledger...")
    rows_out: list[dict[str, str]] = []
    distinct_labels: set[str] = set()
    for (body, state_slug, year, event_id, publisher_label), n_rows in buckets.items():
        tcpd = _tcpd_lookup(
            publisher_label,
            pid_to_meta=pid_to_meta,
            full_to_pids=full_to_pids,
            abbr_to_pids=abbr_to_pids,
        )
        skip_reason = skip_reasons.get(publisher_label, "")
        row = {
            "body": body,
            "state_slug": state_slug,
            "year": year,
            "event_id": event_id,
            "publisher_label": publisher_label,
            "n_rows": str(n_rows),
            "tcpd_party_id": tcpd["tcpd_party_id"],
            "tcpd_party_name": tcpd["tcpd_party_name"],
            "tcpd_party_type": tcpd["tcpd_party_type"],
            "tcpd_start_year": tcpd["tcpd_start_year"],
            "tcpd_last_year": tcpd["tcpd_last_year"],
            "tcpd_state_name": tcpd["tcpd_state_name"],
            "skip_reason": skip_reason,
            "next_lookup_source": _next_lookup_source(year),
        }
        rows_out.append(row)
        distinct_labels.add(publisher_label)

    rows_out.sort(
        key=lambda r: (r["body"], r["state_slug"], r["year"], r["publisher_label"])
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=LEDGER_FIELDS, lineterminator="\n"
        )
        writer.writeheader()
        for r in rows_out:
            writer.writerow(r)

    rel = out_path.relative_to(REPO_ROOT).as_posix()
    print(f"      wrote {len(rows_out)} rows to {rel}.")

    # Surface a quick top-of-list summary.
    tcpd_rec = sum(1 for r in rows_out if r["tcpd_party_id"])
    pct = (100.0 * tcpd_rec / len(rows_out)) if rows_out else 0.0
    print()
    print(
        f"  ledger summary: {len(rows_out)} rows, "
        f"{len(distinct_labels)} distinct labels, "
        f"{len(buckets)} distinct buckets."
    )
    print(
        f"  TCPD recognition rate among remaining UNK: "
        f"{tcpd_rec} / {len(rows_out)} rows = {pct:.1f}%."
    )

    skip_tally: Counter[str] = Counter(
        (r["skip_reason"] or "(no correlator entry)") for r in rows_out
    )
    print("  skip_reason tally:")
    for reason, n in skip_tally.most_common():
        print(f"    {n:>4d}  {reason}")

    next_tally: Counter[str] = Counter(r["next_lookup_source"] for r in rows_out)
    print("  next_lookup_source tally:")
    for kind, n in sorted(next_tally.items()):
        print(f"    {n:>4d}  {kind}")

    label_rows: Counter[str] = Counter()
    for r in rows_out:
        label_rows[r["publisher_label"]] += int(r["n_rows"])
    print("  top 10 labels by n_rows:")
    for lbl, n in label_rows.most_common(10):
        print(f"    {n:>4d}  {lbl}")

    return len(rows_out), len(distinct_labels), len(buckets)


# --- main entry -------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=LEDGER_DEFAULT_PATH,
        help=(
            "Output ledger path. Default: "
            "datasets/_ops/unk-ledger-2026-06-12.csv."
        ),
    )
    args = parser.parse_args(argv)
    emit_ledger(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
