"""Regression test pinning party_resolver coverage of TCPD's 1962-1998
LS GE corpus per TODO/20260613-party-deferred-followups-plan.md PR-6
(collapsed-with-receipt).

PR-6 originally scoped ~30-50 new parties.csv rows + a resolver alias
expansion to push pre-1999 LS GE UNK rate below the 5% target.
Orchestrator pre-flight on origin/main HEAD d27e1554b discovered the
resolver already achieves 99.73% coverage on the full TCPD
``All_States_GE.csv`` 1962-1998 corpus (483 of 516 distinct labels
resolve; 54,592 of 54,742 candidacy rows). All 30 top-frequency
historical TCPD labels (covering 48,948 of the 54,742 corpus rows =
89.4%) resolve cleanly to canonical party_ids that are ALREADY on disk.

The 5 specific party_ids the plan-doc PR-6 section 8 named as ``NEW``
(``parties.IN.INC_I`` + ``parties.IN.JNP`` + ``parties.IN.BJS`` +
``parties.IN.LKD`` + ``parties.IN.BLD``) are on parties.csv with one
naming refinement: the canonical project id for the Janata Party
(1977-1988) is ``parties.IN.JP`` and the TCPD label ``JNP`` resolves
to it via the alias pipe-list ``JANATA PARTY|JAP|JNP|JNP (JP)`` on
that row, per the orchestrator brief's directive: "If party_id naming
convention differs (e.g. ``parties.IN.JANATA_PARTY`` not
``parties.IN.JNP``), defer naming to the existing convention."

The Hans 3b BJP-1980 founding annotation that PR-10 needs reads off
``parties.IN.BJS.successor_party_ids = parties.IN.JP|parties.IN.BJP`` -
that lineage chain is in place today, so PR-10's "Descended from
Bharatiya Jana Sangh" chip on ``/parties/bjp`` is unblockable.

The 33 long-tail UNK labels (150 rows = 0.27%) are SMP/BJC/KCP/PHJ/URC/
DBP/TEC/NCJ/MLP/ML and 23 others, each appearing in 1-34 corpus rows.
Each requires Hans+Max curator disambiguation (e.g. ``SMP`` could be
Samajwadi Mazdoor Party or Samyukta Maharashtra Parishad across
different states/decades) and per CLAUDE.md section 0a authority table
belong to Hans+Max, not autonomous-agent territory. The plan-doc's
ESCALATE E4 default ("assign to ``parties.IN.UNK``, surface in the UNK
ledger for Hans+Max review, do NOT block other rows") already
authorises the 0.27% residual.

No-op receipt per CLAUDE.md section 10 "no-op rows carry a receipt":
this test IS the receipt, locking the existing coverage so future
parties.csv edits cannot silently regress the historical-ingest gate.
See plan-doc section 8 update for the collapse rationale.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.party_resolver import load_resolver


@pytest.fixture(autouse=True)
def _reset_resolver_cache() -> None:
    """Clear the lru_cache so each test builds a fresh resolver from the
    live on-disk parties.csv. Mirrors the convention used by the
    ``test_party_resolver_*`` siblings."""
    load_resolver.cache_clear()


#: Top-30 TCPD 1962-1998 LS GE party labels sorted by candidacy-row count
#: per the PR-6 orchestrator pre-flight against
#: ``datasets/ephemeral/All_States_GE.csv``. The right-hand value is the
#: canonical ``party_id`` the resolver MUST return; both sides cite the
#: live on-disk parties.csv state at PR-6 collapse time.
TOP30_TCPD_HISTORICAL_LABELS: list[tuple[str, str, int]] = [
    ("IND", "parties.IN.IND", 32244),
    ("INC", "parties.IN.INC", 4450),
    ("BJP", "parties.IN.BJP", 1783),
    ("BSP", "parties.IN.BSP", 955),
    ("JD", "parties.IN.JD", 941),
    ("CPI", "parties.IN.CPI", 727),
    ("DDP", "parties.IN.DDP", 719),
    # JNP resolves to parties.IN.JP via alias - the project canonical id
    # for the Janata Party (1977-1988) is JP, not JNP. JNP is an alias.
    ("JNP", "parties.IN.JP", 665),
    ("CPM", "parties.IN.CPIM", 590),
    # Hans+Max doctrine-lock (plan-doc section 0): INC(I) is its own row
    # with ``successor_party_ids = [parties.IN.INC]``, NOT collapsed into
    # modern INC. Test pins the doctrine.
    ("INC(I)", "parties.IN.INC_I", 498),
    ("JP", "parties.IN.JP", 477),
    ("BJS", "parties.IN.BJS", 431),
    ("SWA", "parties.IN.SWA", 413),
    ("BLD", "parties.IN.BLD", 405),
    ("PSP", "parties.IN.PSP", 342),
    ("AIIC(T)", "parties.IN.AIIC_T", 321),
    ("JNP(S)", "parties.IN.JNP_S", 294),
    ("SP", "parties.IN.SP", 279),
    ("NCO", "parties.IN.NCO", 257),
    ("LKD", "parties.IN.LKD", 249),
    ("SHS", "parties.IN.SHS", 243),
    ("DMK", "parties.IN.DMK", 232),
    ("RPI", "parties.IN.RPI", 223),
    ("SSP", "parties.IN.SSP", 219),
    ("INC(U)", "parties.IN.INC_U", 212),
    ("JS", "parties.IN.JS", 196),
    ("TDP", "parties.IN.TDP", 174),
    # Publisher OR-form: TCPD writes "JNP (JP)" in some rows. Same
    # canonical id as plain "JNP" (parties.IN.JP).
    ("JNP (JP)", "parties.IN.JP", 155),
    ("SAP", "parties.IN.SAP", 138),
    ("RJD", "parties.IN.RJD", 116),
]


def test_top30_tcpd_historical_labels_resolve_to_canonical_party_ids() -> None:
    """Every one of the 30 top-frequency TCPD 1962-1998 LS GE labels
    MUST resolve to its expected canonical party_id. Covers 48,948 of
    54,742 corpus rows (89.4%).

    This is the load-bearing oracle for PR-8 (pre-1999 LS ingest
    dispatch). If this regresses, the 89.4% of pre-1999 candidacies
    that should resolve will start producing ``parties.IN.UNK`` rows
    instead - a silent demotion that CLAUDE.md section 10 forbids.
    """
    resolver = load_resolver()
    failures: list[str] = []
    for label, expected_pid, rows in TOP30_TCPD_HISTORICAL_LABELS:
        actual = resolver.resolve(party_short=label, eci_code=None)
        if actual != expected_pid:
            failures.append(
                f"  {label!r:<16} expected={expected_pid!r:<28} "
                f"got={actual!r:<28} (rows={rows})"
            )
    assert not failures, (
        "Top-30 TCPD 1962-1998 LS GE label resolution regressed. "
        "If a parties.csv edit moved a canonical id, update the right-hand "
        "side of TOP30_TCPD_HISTORICAL_LABELS in this test. If the resolver "
        "actually broke, fix it before merge.\n"
        + "\n".join(failures)
    )


def test_inc_i_doctrine_separate_from_modern_inc() -> None:
    """Doctrine-lock: the publisher's ``INC(I)`` label resolves to the
    SEPARATE ``parties.IN.INC_I`` row (Indira faction, 1978-1996), NOT
    to modern ``parties.IN.INC``. Plain ``INC`` continues to resolve to
    modern Congress.

    Per Hans+Max plan-doc section 0 lock ("Bhattacharya methodology-break
    discipline: name what changed"). If this regresses, every pre-1989
    INC(I) candidacy starts getting wrongly attributed to modern INC -
    a category error visible on every party page.
    """
    resolver = load_resolver()
    assert resolver.resolve("INC(I)", None) == "parties.IN.INC_I"
    assert resolver.resolve("INC", None) == "parties.IN.INC"


def test_bjs_lineage_chain_points_to_bjp_for_hans_3b_chip() -> None:
    """Hans 3b prerequisite for PR-10: the BJP-1980 founding annotation
    chip ("Descended from Bharatiya Jana Sangh") on ``/parties/bjp``
    reads off ``parties.IN.BJS.successor_party_ids``. That field MUST
    contain ``parties.IN.BJP`` so the chip lights up.

    Co-locking ``parties.IN.JP`` in the same field captures the
    historical 4-faction Janata Party merger (BJS dissolved 1977 into
    JNP/JP; JNP/JP later split with BJP forming 1980 from the
    ex-Jana-Sangh wing). Both lineages survive in the chain today.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    parties_csv = repo_root / "datasets" / "data" / "entities" / "parties.csv"
    assert parties_csv.exists(), f"parties.csv missing at {parties_csv}"

    with parties_csv.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        bjs_row = next(
            (r for r in reader if r.get("party_id") == "parties.IN.BJS"),
            None,
        )
    assert bjs_row is not None, (
        "parties.IN.BJS row missing from parties.csv - PR-10's "
        "BJP-1980 founding chip ('Descended from Bharatiya Jana Sangh') "
        "cannot light up without this row."
    )
    successors = (bjs_row.get("successor_party_ids") or "").strip()
    assert "parties.IN.BJP" in successors, (
        f"parties.IN.BJS.successor_party_ids must include parties.IN.BJP "
        f"so PR-10's BJP-1980 founding chip can render. Today: "
        f"successor_party_ids={successors!r}. Fix by editing the BJS row "
        f"in datasets/data/entities/parties.csv."
    )


def test_tcpd_pre1999_resolver_row_coverage_above_99pct() -> None:
    """Audit-trail receipt: when the operator has the TCPD ephemeral
    panel on disk, resolver ROW-coverage of the 1962-1998 LS GE corpus
    must remain at >=99% of candidacy rows.

    Row-coverage (not label-coverage) is the load-bearing metric: it
    determines how many pre-1999 candidacies the PR-8 ingest will
    surface as ``parties.IN.UNK`` ledger entries vs canonical
    party_ids. Label-coverage is sensitive to long-tail TCPD vintages
    introducing new 1-row labels that need Hans+Max curator review;
    a single such label would tank a label-coverage metric without
    indicating a real regression. Hence the assertion only targets
    row-coverage.

    The TCPD file lives at ``datasets/ephemeral/All_States_GE.csv`` per
    the ephemeral-tier convention (gitignored; operator-pulled per
    plan-doc section 4 / ESCALATE E2). On CI or fresh clones the file
    is absent and the test SKIPs - no contract leak, the durable
    regression check is the ``test_top30_*`` test above which runs
    unconditionally.

    Pre-flight baseline at PR-6 (2026-06-13): 99.73% rows (54,592 of
    54,742); 93.60% labels (483 of 516). The 0.27% residual is 33
    long-tail labels in 150 corpus rows; each is a Hans+Max curator
    disambiguation question per ESCALATE E4 default.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    tcpd_ge = repo_root / "datasets" / "ephemeral" / "All_States_GE.csv"
    if not tcpd_ge.exists():
        pytest.skip(
            f"TCPD All_States_GE.csv not on disk at {tcpd_ge}; "
            "this is the expected state on CI + fresh clones because "
            "datasets/ephemeral/ is gitignored (per ephemeral-tier "
            "convention). The audit test runs locally when an operator "
            "has the TCPD panel pulled."
        )

    resolver = load_resolver()
    csv.field_size_limit(10 ** 7)
    label_counts: dict[str, int] = {}
    with tcpd_ge.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                year = int(row.get("Year") or 0)
            except ValueError:
                continue
            if year < 1962 or year > 1998:
                continue
            party = (row.get("Party") or "").strip()
            if party:
                label_counts[party] = label_counts.get(party, 0) + 1

    if not label_counts:
        pytest.skip(
            "TCPD All_States_GE.csv has no 1962-1998 rows; file may be "
            "a partial/different vintage. Audit cannot run."
        )

    total_labels = len(label_counts)
    total_rows = sum(label_counts.values())
    unk_labels = 0
    unk_rows = 0
    for label, rows in label_counts.items():
        if resolver.resolve(label, None) == "parties.IN.UNK":
            unk_labels += 1
            unk_rows += rows

    row_coverage = 1.0 - (unk_rows / total_rows)

    # Floor at 99% (baseline 99.73%); any regression below 99% means
    # a parties.csv edit accidentally retired a heavily-used alias.
    # Label-coverage (93.60% at PR-6 baseline) is informational, not
    # asserted - new long-tail TCPD vintages routinely add 1-row labels
    # that need Hans+Max curator review.
    assert row_coverage >= 0.99, (
        f"TCPD 1962-1998 LS GE ROW coverage dropped below 99%: "
        f"{row_coverage:.2%} ({total_rows - unk_rows}/{total_rows} rows "
        f"resolved; {unk_rows} UNK across {unk_labels}/{total_labels} "
        f"labels). Baseline at PR-6 was 99.73%. Likely cause: a "
        f"parties.csv edit retired an alias that the historical TCPD "
        f"corpus relies on heavily. Investigate by running the resolver "
        f"against the corpus and inspecting which heavy label went UNK."
    )
