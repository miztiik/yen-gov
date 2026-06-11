"""Tests for the Rajasthan AE Nov 2023 IndiaVotes ingest.

Asserts the ingest produces the canonical CSV shape the rest of the corpus
expects + per-party seat counts within tolerance of the public oracle. Walks
the on-disk artifacts the ingest tool wrote (not synthetic fixtures) so the
test doubles as a self-check on the snapshot data quality.

Mocks: NONE. CLAUDE.md section 10 carve-out — the ingest is a one-shot
file-to-file transform and a fixture would just duplicate the snapshot.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CANDIDACIES_CSV = (
    REPO_ROOT
    / "datasets"
    / "elections"
    / "assembly"
    / "state=rajasthan"
    / "election=2023"
    / "candidacies.csv"
)
SUMMARY_CSV = (
    REPO_ROOT
    / "datasets"
    / "elections"
    / "assembly"
    / "state=rajasthan"
    / "election=2023"
    / "summary.csv"
)
SOURCE_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "source.csv"

# IndiaVotes-side party_short_raw counts for the Nov 2023 Rajasthan event.
# Sourced from the master page partyTally (200 seats, sum verified):
#   BJP=115, INC=70, IND=8, BHRTADVSIP=3, BSP=2, RLP=1, RLD=1.
#
# Brief named an ECI-derived oracle with INC=69 + RLM=1; the +1 INC delta is
# Karanpur (postponed; declared INC post-result-day in Jan 2024) and the
# RLM/RLD shift is a party-identity disagreement (Wikipedia + IndiaVotes
# both show RLD won that 1 seat, not RLM). Tolerance lets the test land
# without re-litigating the publisher disagreement.
EXPECTED_BY_RAW = {
    "BJP": 115,
    "INC": 70,
    "BHRTADVSIP": 3,
    "BSP": 2,
    "RLP": 1,
    "RLD": 1,
    "IND": 8,
}
TOLERANCE = 2  # per CLAUDE.md section 10 + brief stop-condition.

# RJ-2023 IndiaVotes citation triple; matches the values
# ``tools/elections_rj_ae2023_ingest/__main__.py`` writes to source.csv.
SOURCE_PRODUCER = "IndiaVotes"
SOURCE_TITLE = "Rajasthan Vidhan Sabha 2023"
SOURCE_VINTAGE = "2023-11"

# 13 of 200 RJ ACs use the ``-eci<N>`` suffix on the entity_id when the LGD
# code is unavailable (urban centres in district HQs); the remaining 187
# carry the plain ``-<lgd_code>`` form. The regex accepts both shapes.
ENTITY_ID_RE = re.compile(r"^IN-AC-2008-rajasthan-(?:eci)?\d{1,4}$")


@pytest.fixture(scope="module")
def candidacies() -> list[dict[str, str]]:
    if not CANDIDACIES_CSV.exists():
        pytest.skip(
            f"{CANDIDACIES_CSV.relative_to(REPO_ROOT).as_posix()} missing; "
            "run tools/elections_rj_ae2023_ingest/__main__.py first"
        )
    with CANDIDACIES_CSV.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def summary() -> list[dict[str, str]]:
    if not SUMMARY_CSV.exists():
        pytest.skip(f"{SUMMARY_CSV.relative_to(REPO_ROOT).as_posix()} missing")
    with SUMMARY_CSV.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def test_candidacies_csv_header_is_canonical(candidacies: list[dict[str, str]]) -> None:
    expected = [
        "entity_id",
        "state",
        "election_year",
        "constituency_no",
        "constituency_name",
        "candidate_name",
        "party_id",
        "party_short_raw",
        "votes",
        "vote_share_pct",
        "position",
        "result",
        "sex",
        "age",
        "education",
        "profession",
        "candidate_type",
        "source_id",
    ]
    assert candidacies, "no rows in candidacies.csv"
    assert list(candidacies[0].keys()) == expected, (
        "candidacies.csv header drift from 2018 RJ template"
    )


def test_summary_csv_header_is_canonical(summary: list[dict[str, str]]) -> None:
    expected = [
        "entity_id",
        "state",
        "election_year",
        "constituency_name",
        "electors",
        "votes_polled",
        "turnout_pct",
        "winner_candidate",
        "winner_party_id",
        "winner_party_short_raw",
        "winner_votes",
        "winner_share_pct",
        "runnerup_candidate",
        "runnerup_party_id",
        "runnerup_party_short_raw",
        "runnerup_votes",
        "margin_votes",
        "margin_pct",
        "source_id",
    ]
    assert summary, "no rows in summary.csv"
    assert list(summary[0].keys()) == expected, (
        "summary.csv header drift from 2018 RJ template"
    )


def test_summary_has_200_acs(summary: list[dict[str, str]]) -> None:
    # Brief stop-condition: AC count != 200 -> STOP. Hard assert.
    assert len(summary) == 200, f"expected 200 ACs, got {len(summary)}"


def test_summary_entity_ids_match_2008_rajasthan_delim(
    summary: list[dict[str, str]],
) -> None:
    for row in summary:
        assert ENTITY_ID_RE.match(row["entity_id"]), (
            f"summary.csv entity_id {row['entity_id']!r} not on 2008 RJ delim "
            "(IN-AC-2008-rajasthan-<eci_no> shape)"
        )
        assert row["state"] == "rajasthan"
        assert row["election_year"] == "2023"


def test_per_party_winner_oracle_within_tolerance(
    summary: list[dict[str, str]],
) -> None:
    """Winner-side party tally (per row from summary.csv) within +/- tolerance of oracle."""

    actuals: dict[str, int] = {}
    for row in summary:
        raw = (row.get("winner_party_short_raw") or "").strip()
        actuals[raw] = actuals.get(raw, 0) + 1
    total = sum(actuals.values())
    assert total == 200, f"summary.csv winner rows sum to {total}, expected 200"

    failures: list[str] = []
    for raw, expected in EXPECTED_BY_RAW.items():
        actual = actuals.get(raw, 0)
        delta = abs(actual - expected)
        if delta > TOLERANCE:
            failures.append(
                f"  {raw}: got {actual}, expected {expected} +/- {TOLERANCE} "
                f"(delta {delta})"
            )
    assert not failures, (
        "per-party oracle outside tolerance:\n"
        + "\n".join(failures)
        + f"\n(actuals: {sorted(actuals.items(), key=lambda kv: -kv[1])[:12]})"
    )


def test_every_party_id_resolves_or_is_unk(
    candidacies: list[dict[str, str]],
) -> None:
    """party_id always populated; UNK rows preserve the publisher label.

    PR-3 doctrine (CLAUDE.md section 10 no silent demotion): every row
    carries party_id; rows whose IndiaVotes party_abbreviation has no
    alias in parties.csv take ``parties.IN.UNK`` as the canonical id AND
    keep the publisher abbreviation on party_short_raw so the UNK
    sibling PR's later alias-add re-resolves them via a simple re-emit.
    """
    for row in candidacies:
        party_id = (row.get("party_id") or "").strip()
        assert party_id, f"empty party_id in row {row.get('entity_id')!r}/{row.get('candidate_name')!r}"
        assert party_id.startswith("parties.IN."), (
            f"party_id {party_id!r} does not match parties.IN.* shape"
        )
        if party_id == "parties.IN.UNK":
            assert (row.get("party_short_raw") or "").strip(), (
                f"UNK fallback row at "
                f"{row.get('entity_id')!r}/{row.get('candidate_name')!r} "
                "lacks party_short_raw (would silently demote the "
                "publisher label; violates CLAUDE.md section 10)"
            )


def test_votes_field_always_numeric_non_negative(
    candidacies: list[dict[str, str]],
) -> None:
    for row in candidacies:
        votes = (row.get("votes") or "").strip()
        assert votes != "", f"empty votes in {row.get('entity_id')!r}/{row.get('candidate_name')!r}"
        try:
            v = int(votes)
        except ValueError as exc:  # pragma: no cover - assertion fires first
            raise AssertionError(
                f"non-numeric votes {votes!r} in "
                f"{row.get('entity_id')!r}/{row.get('candidate_name')!r}"
            ) from exc
        assert v >= 0, f"negative votes {v} in {row.get('entity_id')!r}"


def test_position_1_row_is_winner_in_each_ac(
    candidacies: list[dict[str, str]],
    summary: list[dict[str, str]],
) -> None:
    """For each AC, the candidacies row with position=1 must match the summary winner."""

    by_entity: dict[str, list[dict[str, str]]] = {}
    for row in candidacies:
        by_entity.setdefault(row["entity_id"], []).append(row)
    summary_by_entity = {row["entity_id"]: row for row in summary}

    mismatches: list[str] = []
    for entity_id, summary_row in summary_by_entity.items():
        ac_rows = by_entity.get(entity_id, [])
        position_1 = [r for r in ac_rows if r.get("position") == "1"]
        if len(position_1) != 1:
            mismatches.append(
                f"{entity_id}: {len(position_1)} rows with position=1 (expected 1)"
            )
            continue
        w = position_1[0]
        if w.get("candidate_name") != summary_row.get("winner_candidate"):
            mismatches.append(
                f"{entity_id}: position=1 candidate {w.get('candidate_name')!r} "
                f"!= summary winner_candidate {summary_row.get('winner_candidate')!r}"
            )
        if w.get("votes") != summary_row.get("winner_votes"):
            mismatches.append(
                f"{entity_id}: position=1 votes {w.get('votes')!r} "
                f"!= summary winner_votes {summary_row.get('winner_votes')!r}"
            )
    assert not mismatches, (
        "summary winner does not match candidacies position=1:\n"
        + "\n".join(mismatches[:10])
    )


def test_source_csv_carries_indiavotes_row() -> None:
    """source.csv must carry exactly one row matching the IndiaVotes RJ-2023 triple."""

    assert SOURCE_CSV.exists(), f"{SOURCE_CSV.relative_to(REPO_ROOT).as_posix()} missing"
    matches: list[dict[str, str]] = []
    with SOURCE_CSV.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if (
                row.get("producer") == SOURCE_PRODUCER
                and row.get("title") == SOURCE_TITLE
                and row.get("vintage") == SOURCE_VINTAGE
            ):
                matches.append(row)
    assert len(matches) == 1, (
        f"expected 1 row in source.csv with "
        f"producer={SOURCE_PRODUCER!r} title={SOURCE_TITLE!r} vintage={SOURCE_VINTAGE!r}; "
        f"got {len(matches)}"
    )
    assert matches[0]["source_id"].startswith("src-")


def test_candidacies_source_id_fks_to_source_csv(
    candidacies: list[dict[str, str]],
) -> None:
    """Every candidacies row's source_id resolves into source.csv (FK closure)."""

    sources_ids: set[str] = set()
    if SOURCE_CSV.exists():
        with SOURCE_CSV.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                sources_ids.add(row["source_id"])
    bad: list[str] = []
    for row in candidacies:
        sid = (row.get("source_id") or "").strip()
        if not sid:
            bad.append(f"{row.get('entity_id')!r}: empty source_id")
            continue
        if sid not in sources_ids:
            bad.append(f"{row.get('entity_id')!r}: {sid!r} not in source.csv")
    assert not bad, "source_id FK closure failure:\n" + "\n".join(bad[:10])
