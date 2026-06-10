"""Tier-A corpus oracle: every party_id referenced anywhere FK-resolves.

This is the always-on Tier-A safety net created in PR-1 of the 2026-06-10
electoral-data-quality plan (CLAUDE.md section 15 + plan section 5). It walks
the on-disk corpus and asserts that every ``party_id`` value referenced from

  - ``datasets/elections/assembly/state=*/election=*/candidacies.csv``
  - ``datasets/elections/parliament/election=*/candidacies.csv``
  - ``datasets/data/datapoints/electoral/*_election_results.csv``
    (specifically ``value_text`` for ``*-(winner|leading|runnerup)-party-id``
    indicator rows)

is EITHER

  (a) in the set of ``party_id`` values declared in
      ``datasets/data/entities/parties.csv``,
  (b) the explicit sentinel ``parties.IN.UNK``, or
  (c) empty string ONLY if the row also carries non-null ``party_short_raw``
      (the citizen-UI fallback path; the publisher label survives so the row
      stays auditable per CLAUDE.md section 10 "no silent demotion").

Empty-string ``party_id`` WITHOUT ``party_short_raw`` is the TN-2026 AIADMK
bug class (Wave 0 / Diagnostic finding) and is the defining failure mode this
test exists to prevent.

This test runs against the REAL on-disk corpus (no fixtures). CLAUDE.md
section 14 carve-out: corpus-walking pytest is allowed at Tier-A when the
walk is the contract (here: FK closure). The walk is bounded (only the
~300 files enumerated above) and the test fails fast on the first batch of
~20 offenders so a regression PR sees an actionable report.

**At PR-3 (2026-06-10)** the xfail flipped to a strict assert. PR-3 fixed
the writer Path B (4 modules in ``backend/yen_gov/canonical/reingest/``: every
``"party_id": lookup.get(raw_party.upper()) if raw_party else None`` seam now
emits ``parties.IN.UNK`` on a lookup miss instead of None) AND ran a
one-time corpus regen (``python -m tools.elections_party_id_repair --apply``)
that backfilled the on-disk historical rows to the post-fix contract. From
PR-3 onward, FK closure is enforced as a contract.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

# The 3 party_id sentinels lifted into parties.csv by PR-0. Empty-string
# party_id is NEVER one of these (sentinels are explicit ids); see brief
# item 6 condition (c).
SENTINEL_UNK = "parties.IN.UNK"

# The long-format electoral CSV indicator_ids whose value_text is itself a
# party_id (FK to parties.csv). All other rows in those CSVs are numeric
# observations and not subject to this check.
PARTY_ID_INDICATOR_RE = re.compile(
    r"^(ac|pc|state)-(winner|leading|runnerup)-party-id$"
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_valid_party_ids() -> set[str]:
    parties_csv = (
        REPO_ROOT / "datasets" / "data" / "entities" / "parties.csv"
    )
    with parties_csv.open(encoding="utf-8", newline="") as fh:
        return {
            (row.get("party_id") or "").strip()
            for row in csv.DictReader(fh)
            if (row.get("party_id") or "").strip()
        }


def _candidacies_paths() -> list[Path]:
    assembly = sorted(
        (REPO_ROOT / "datasets" / "elections" / "assembly").glob(
            "state=*/election=*/candidacies.csv"
        )
    )
    parliament = sorted(
        (REPO_ROOT / "datasets" / "elections" / "parliament").glob(
            "election=*/candidacies.csv"
        )
    )
    return assembly + parliament


def _electoral_paths() -> list[Path]:
    return sorted(
        (REPO_ROOT / "datasets" / "data" / "datapoints" / "electoral").glob(
            "*_election_results.csv"
        )
    )


def _walk_corpus() -> tuple[
    list[tuple[str, int, str]],
    list[tuple[str, int, str]],
    list[tuple[str, int, str]],
    int,
    int,
    int,
]:
    """Walk candidacies + electoral CSVs and bucket FK-closure violations.

    Returns ``(f1, f2, f3, n_files, n_rows_scanned, n_party_id_rows)`` where:

      - ``f1`` are candidacies rows with empty party_id AND empty
        party_short_raw (TN-2026 bug class).
      - ``f2`` are rows whose party_id is non-empty, not parties.IN.UNK, and
        not in parties.csv (FK violation).
      - ``f3`` are electoral CSV rows with empty value_text for a
        ``*-party-id`` indicator (empty-FK in long-format).

    Each list carries the first ~20 offenders as ``(relpath, line_no,
    offending_value)`` triples so the failure dump is actionable without
    drowning the reader.
    """
    valid = _load_valid_party_ids()
    f1: list[tuple[str, int, str]] = []
    f2: list[tuple[str, int, str]] = []
    f3: list[tuple[str, int, str]] = []
    n_f1 = n_f2 = n_f3 = 0
    n_files = n_rows = 0

    for path in _candidacies_paths():
        n_files += 1
        rel = path.relative_to(REPO_ROOT).as_posix()
        with path.open(encoding="utf-8", newline="") as fh:
            for idx, row in enumerate(csv.DictReader(fh), start=2):
                n_rows += 1
                pid = (row.get("party_id") or "").strip()
                raw = (row.get("party_short_raw") or "").strip()
                if pid == "":
                    if not raw:
                        n_f1 += 1
                        if len(f1) < 20:
                            f1.append((rel, idx, "<empty-no-raw>"))
                    continue
                if pid == SENTINEL_UNK:
                    continue
                if pid not in valid:
                    n_f2 += 1
                    if len(f2) < 20:
                        f2.append((rel, idx, pid))

    for path in _electoral_paths():
        n_files += 1
        rel = path.relative_to(REPO_ROOT).as_posix()
        with path.open(encoding="utf-8", newline="") as fh:
            for idx, row in enumerate(csv.DictReader(fh), start=2):
                n_rows += 1
                indicator = (row.get("indicator_id") or "").strip()
                if not PARTY_ID_INDICATOR_RE.match(indicator):
                    continue
                pid = (row.get("value_text") or "").strip()
                if pid == "":
                    n_f3 += 1
                    if len(f3) < 20:
                        f3.append((rel, idx, "<electoral-empty>"))
                    continue
                if pid == SENTINEL_UNK:
                    continue
                if pid not in valid:
                    n_f2 += 1
                    if len(f2) < 20:
                        f2.append((rel, idx, pid))

    return f1, f2, f3, n_files, n_rows, n_f1 + n_f2 + n_f3


def test_party_id_fk_closure() -> None:
    """Every party_id referenced anywhere FK-resolves to parties.csv.

    Sentinel ``parties.IN.UNK`` is allowed. Empty-string party_id is allowed
    ONLY if ``party_short_raw`` is present (citizen-UI fallback path with
    publisher label preserved). Empty party_id without raw label is the
    TN-2026 AIADMK bug class and must be ZERO.

    PR-1 staged this test under ``xfail`` while the TN-2026 + corpus-wide
    regen was pending; PR-3 (2026-06-10) shipped the writer fix + the
    corpus-wide regen and flipped this to a strict assert. From PR-3 onward
    every empty-``party_id`` row is mechanically substituted with the
    explicit ``parties.IN.UNK`` sentinel (PR-0 catalogue row); the publisher
    label survives on ``party_short_raw``. PR-W-1's TCPD-bulk alias
    enrichment + follow-up regen will flip 2471 distinct labels from UNK to
    real party_ids; the test stays green throughout.
    """
    f1, f2, f3, n_files, _n_rows, n_offending = _walk_corpus()

    if n_offending == 0:
        return  # FK closure holds; PR-3 must flip the xfail mark to strict.

    msg_lines = [
        f"FK closure violated: {n_offending} offending rows across "
        f"{n_files} files.",
        "",
        f"F1 (TN-2026 bug class, empty party_id + empty party_short_raw): "
        f"{len(f1)} examples shown of total. First 20:",
    ]
    msg_lines.extend(f"    {r}" for r in f1)
    msg_lines.append("")
    msg_lines.append(
        f"F2 (FK violation, party_id not in parties.csv): "
        f"{len(f2)} examples shown of total. First 20:"
    )
    msg_lines.extend(f"    {r}" for r in f2)
    msg_lines.append("")
    msg_lines.append(
        f"F3 (electoral long-format empty value_text for *-party-id "
        f"indicator): {len(f3)} examples shown of total. First 20:"
    )
    msg_lines.extend(f"    {r}" for r in f3)
    msg_lines.append("")
    msg_lines.append(
        "Run `python -m yen_gov check-party-resolution` to regenerate the "
        "affected slices via the canonical resolver."
    )
    raise AssertionError("\n".join(msg_lines))


def test_party_id_fk_indicator_regex_matches_known_ids() -> None:
    """Lightweight contract: the indicator-id regex covers the canonical set.

    Defends against silent drift if a new ``*-runnerup-party-id`` flavour is
    added and the regex needs an update. The set below is the documented
    closure (Wave 0 / Hans section 2 + the electoral indicator catalogue).
    """
    must_match = {
        "ac-winner-party-id",
        "ac-leading-party-id",
        "ac-runnerup-party-id",
        "pc-winner-party-id",
        "pc-leading-party-id",
        "pc-runnerup-party-id",
        "state-winner-party-id",
        "state-leading-party-id",
        "state-runnerup-party-id",
    }
    must_not_match = {
        "ac-winner-candidate-id",
        "ac-margin-votes",
        "pc-turnout-pct",
        "winner-party-id",
        "state-party-vote-share-pct",
    }
    for indicator_id in must_match:
        assert PARTY_ID_INDICATOR_RE.match(indicator_id), indicator_id
    for indicator_id in must_not_match:
        assert not PARTY_ID_INDICATOR_RE.match(indicator_id), indicator_id
