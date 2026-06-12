"""Tests for ``tools.correlate_unk_via_eci_ls_statement33`` (PR-Q3).

Covers the brief's fixtures end-to-end via real CSV files under
``tmp_path`` (Holy Law #7, no mocks):

  - header detection across the 2024 multi-header preamble + 2019
    single-row BOM-prefixed shapes
  - (constituency, candidate) join with NFKD-ASCII + collapse-whitespace
    normalisation
  - NOTA / IND sentinel resolution
  - alias-add path against existing parties.csv rows
  - mint-new path with default ``parties.IN.<abbr>`` slug
  - existing-collision disambiguation (``<abbr>_LS<year>`` suffix)
  - dominant-label tally (80% threshold) and skip-on-no-majority
  - skipped.csv shape + reason histogram

All fixtures are tiny hand-crafted CSVs that mirror the on-disk shapes.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from tools.correlate_unk_via_eci_ls_statement33.__main__ import (
    SKIPPED_FIELDNAMES,
    VERDICT_FIELDNAMES,
    correlate,
    load_eci_index,
    normalise,
    resolve_eci_label,
)


PARTIES_FIELDNAMES = [
    "party_id",
    "short",
    "full",
    "eci_codes",
    "brand_colour",
    "symbol_asset",
    "wikipedia",
    "aliases",
    "recognition_scope",
    "home_state_codes",
    "founded_year",
    "dissolved_year",
    "predecessor_party_ids",
    "successor_party_ids",
    "name_history",
    "claims_to_parent_name",
    "name_native_script",
    "is_sentinel",
]

CANDIDACIES_FIELDNAMES = [
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


# --- fixture builders -------------------------------------------------------


def _write_parties_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=PARTIES_FIELDNAMES, lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in PARTIES_FIELDNAMES})


def _write_candidacies_csv(
    path: Path, rows: list[dict[str, str]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=CANDIDACIES_FIELDNAMES, lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in CANDIDACIES_FIELDNAMES})


def _write_eci_2024_csv(path: Path, data_rows: list[list[str]]) -> None:
    """Mirror the 2024 ECI Statement-33 shape: title row + partial group
    row + real header at row index 2 + data rows.

    Each data row must have 17 cells (matches on-disk shape; trailing
    empties are stripped by csv.reader).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    title_row = ["33 - CONSTITUENCY WISE DETAILED RESULT"] + [""] * 19
    partial = ([""] * 10) + ["Votes Secured", "", "", "% of Votes Secured"] + ([""] * 6)
    header = [
        "State Name",
        "PC Name",
        "Candidate Name",
        "Gender",
        "Age",
        "Category",
        "Party Name",
        "Party Symbol",
        "Total Votes Polled In\nThe Constituency",
        "Valid Votes",
        "General",
        "Postal",
        "Total",
        "Over Total Electors In Constituency",
        "Over Total Votes Polled In Constituency",
        "Over Total Valid Votes Polled In Constituency",
        "Total Electors",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(title_row)
        w.writerow(partial)
        w.writerow(header)
        for r in data_rows:
            w.writerow(r)


def _write_eci_2019_csv(path: Path, data_rows: list[list[str]]) -> None:
    """Mirror the 2019 ECI Statement-33 shape: BOM-prefixed single-row
    header with leading/trailing whitespace + data rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "\ufeff State Name ",
        " PC NAME ",
        " CANDIDATES NAME ",
        " SEX ",
        " AGE ",
        " CATEGORY ",
        " PARTY NAME ",
        " PARTY SYMBOL ",
        " GENERAL ",
        " POSTAL ",
        " TOTAL ",
        "OVER TOTAL ELECTORS IN CONSTITUENCY",
        "OVER TOTAL VOTES POLLED IN CONSTITUENCY",
        "Total Electors",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for r in data_rows:
            w.writerow(r)


def _unk_candidacy(
    *,
    pc: str,
    candidate: str,
    party_short_raw: str,
    year: int,
    state: str = "andhra-pradesh",
) -> dict[str, str]:
    """Build a candidacies.csv row with party_id=parties.IN.UNK."""
    return {
        "entity_id": f"IN-PC-2008-{state}-eci1",
        "state": state,
        "election_year": str(year),
        "constituency_no": "0",
        "constituency_name": pc,
        "candidate_name": candidate,
        "party_id": "parties.IN.UNK",
        "party_short_raw": party_short_raw,
        "votes": "1000",
        "vote_share_pct": "0.1",
        "position": "5",
        "result": "lost",
        "sex": "M",
        "age": "40",
        "education": "",
        "profession": "",
        "candidate_type": "challenger",
        "source_id": "src-test00000000",
    }


def _eci_2024_row(
    *,
    state: str = "Andhra Pradesh",
    pc: str = "Test PC",
    candidate: str = "TEST CANDIDATE",
    party: str = "BJP",
) -> list[str]:
    return [
        state,
        pc,
        candidate,
        "MALE",
        "40",
        "GENERAL",
        party,
        "Test Symbol",
        "1000000",
        "950000",
        "500000",
        "1000",
        "501000",
        "30.0",
        "40.0",
        "42.0",
        "1500000",
    ]


def _eci_2019_row(
    *,
    state: str = "Bihar",
    pc: str = "Samastipur (SC)",
    candidate: str = "Ramchandra Paswan",
    party: str = "LJP",
) -> list[str]:
    return [
        state,
        pc,
        candidate,
        "MALE",
        "58",
        "SC",
        party,
        "Bungalow",
        "561460",
        "983",
        "562443",
        "33.49",
        "55.15",
        "1679030",
    ]


def _setup_repo(
    tmp_path: Path,
    *,
    parties_rows: list[dict[str, str]],
    eci_2024_data: list[list[str]] | None = None,
    eci_2019_data: list[list[str]] | None = None,
    candidacies_2024: list[dict[str, str]] | None = None,
    candidacies_2019: list[dict[str, str]] | None = None,
) -> Path:
    """Build a tmp_path repo skeleton: parties.csv + ECI files + candidacies."""
    repo_root = tmp_path / "repo"
    _write_parties_csv(repo_root / "datasets/data/entities/parties.csv", parties_rows)
    if eci_2024_data is not None:
        _write_eci_2024_csv(
            repo_root
            / "datasets/ephemeral/2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv",
            eci_2024_data,
        )
    if eci_2019_data is not None:
        _write_eci_2019_csv(
            repo_root
            / "datasets/ephemeral/2019_india_loksabha_33. Constituency Wise Detailed Result.csv",
            eci_2019_data,
        )
    if candidacies_2024 is not None:
        _write_candidacies_csv(
            repo_root / "datasets/elections/parliament/election=2024/candidacies.csv",
            candidacies_2024,
        )
    if candidacies_2019 is not None:
        _write_candidacies_csv(
            repo_root / "datasets/elections/parliament/election=2019/candidacies.csv",
            candidacies_2019,
        )
    return repo_root


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --- tests ------------------------------------------------------------------


def test_normalise_strips_category_suffix_and_punctuation():
    """Brief: ECI publishes 'Samastipur (SC)' but our candidacies have
    'SAMASTIPUR'. The normaliser strips the SC/ST suffix."""
    assert normalise("Samastipur (SC)") == "SAMASTIPUR"
    assert normalise("Aruku  ") == "ARUKU"
    assert normalise("Andaman & Nicobar Islands") == "ANDAMAN NICOBAR ISLANDS"
    assert normalise("Dr. ASHOK Kumar") == "DR ASHOK KUMAR"
    # Unicode accent + en-dash become ASCII whitespace
    assert normalise("Sonia\u2013Gandhi") == "SONIA GANDHI"
    # Devanagari is stripped to empty under NFKD-ASCII; defensive contract
    assert normalise("दिल्ली") == ""


def test_header_detection_2024_shape(tmp_path: Path):
    """Brief: detect the real header (row index 2) in the 2024 file."""
    path = tmp_path / "eci2024.csv"
    _write_eci_2024_csv(
        path,
        [
            _eci_2024_row(pc="Araku", candidate="GUMMA THANUJA RANI", party="YSRCP"),
            _eci_2024_row(pc="Vizianagaram", candidate="SRINIVASA RAO", party="YGATLSIP"),
        ],
    )
    idx = load_eci_index(path)
    assert idx[(normalise("Araku"), normalise("GUMMA THANUJA RANI"))] == "YSRCP"
    assert idx[(normalise("Vizianagaram"), normalise("SRINIVASA RAO"))] == "YGATLSIP"


def test_header_detection_2019_shape_with_bom(tmp_path: Path):
    """Brief: detect the BOM-prefixed header at row 0 in the 2019 file."""
    path = tmp_path / "eci2019.csv"
    _write_eci_2019_csv(
        path,
        [
            _eci_2019_row(pc="Samastipur (SC)", candidate="Ramchandra Paswan", party="LJP"),
        ],
    )
    idx = load_eci_index(path)
    # Note the (SC) is stripped during normalisation.
    assert idx[(normalise("Samastipur"), normalise("Ramchandra Paswan"))] == "LJP"


def test_constituency_candidate_join_resolves_via_alias_add(tmp_path: Path):
    """Brief: a UNK row joined to an ECI label that matches an existing
    parties.csv short via alias-add."""
    parties_rows = [
        {"party_id": "parties.IN.UNK", "short": "UNK", "full": "Unresolved Party", "is_sentinel": "true"},
        {"party_id": "parties.IN.IND", "short": "IND", "full": "Independent", "is_sentinel": "true"},
        {"party_id": "parties.IN.NOTA", "short": "NOTA", "full": "None of the Above", "is_sentinel": "true"},
        {"party_id": "parties.IN.YSRCP", "short": "YSRCP", "full": "Yuvajana Sramika Rythu Congress Party"},
    ]
    eci_2024 = [
        _eci_2024_row(pc="Araku", candidate="GUMMA THANUJA RANI", party="YSRCP"),
    ]
    candidacies = [
        _unk_candidacy(
            pc="Araku", candidate="GUMMA THANUJA RANI", party_short_raw="YSRC", year=2024
        ),
    ]
    repo_root = _setup_repo(
        tmp_path,
        parties_rows=parties_rows,
        eci_2024_data=eci_2024,
        candidacies_2024=candidacies,
    )
    result = correlate(years=[2024], repo_root=repo_root)
    verdict = _read_csv(result["verdict_path"])
    assert len(verdict) == 1
    row = verdict[0]
    assert row["action"] == "alias-add"
    assert row["proposed_party_id"] == "parties.IN.YSRCP"
    assert row["party_short_raw"] == "YSRC"
    assert row["tcpd_frequent_abbrev"] == "YSRCP"


def test_constituency_candidate_join_resolves_via_mint_new(tmp_path: Path):
    """Brief: a UNK row joined to an ECI label NOT in parties.csv -> mint-new."""
    parties_rows = [
        {"party_id": "parties.IN.UNK", "short": "UNK", "full": "Unresolved Party", "is_sentinel": "true"},
        {"party_id": "parties.IN.IND", "short": "IND", "full": "Independent", "is_sentinel": "true"},
        {"party_id": "parties.IN.NOTA", "short": "NOTA", "full": "None of the Above", "is_sentinel": "true"},
    ]
    eci_2024 = [
        _eci_2024_row(pc="Vizianagaram", candidate="SRINIVASA RAO", party="YGATLSIP"),
    ]
    candidacies = [
        _unk_candidacy(
            pc="Vizianagaram",
            candidate="SRINIVASA RAO",
            party_short_raw="YGATLSIP",
            year=2024,
        ),
    ]
    repo_root = _setup_repo(
        tmp_path,
        parties_rows=parties_rows,
        eci_2024_data=eci_2024,
        candidacies_2024=candidacies,
    )
    result = correlate(years=[2024], repo_root=repo_root)
    verdict = _read_csv(result["verdict_path"])
    assert len(verdict) == 1
    row = verdict[0]
    assert row["action"] == "mint-new"
    assert row["proposed_party_id"] == "parties.IN.YGATLSIP"
    assert row["tcpd_frequent_abbrev"] == "YGATLSIP"
    assert row["tcpd_party_name"] == "YGATLSIP"


def test_nota_row_maps_to_sentinel(tmp_path: Path):
    """Brief: ECI 'NOTA' row maps to parties.IN.NOTA via alias-add; no mint."""
    parties_rows = [
        {"party_id": "parties.IN.UNK", "short": "UNK", "full": "Unresolved Party", "is_sentinel": "true"},
        {"party_id": "parties.IN.IND", "short": "IND", "full": "Independent", "is_sentinel": "true"},
        {"party_id": "parties.IN.NOTA", "short": "NOTA", "full": "None of the Above", "is_sentinel": "true"},
    ]
    eci_2024 = [
        _eci_2024_row(pc="Test PC", candidate="NONE OF THE ABOVE", party="NOTA"),
    ]
    candidacies = [
        _unk_candidacy(
            pc="Test PC", candidate="NONE OF THE ABOVE", party_short_raw="None of the Above", year=2024
        ),
    ]
    repo_root = _setup_repo(
        tmp_path,
        parties_rows=parties_rows,
        eci_2024_data=eci_2024,
        candidacies_2024=candidacies,
    )
    result = correlate(years=[2024], repo_root=repo_root)
    verdict = _read_csv(result["verdict_path"])
    assert len(verdict) == 1
    row = verdict[0]
    assert row["action"] == "alias-add"
    assert row["proposed_party_id"] == "parties.IN.NOTA"


def test_independent_row_maps_to_sentinel(tmp_path: Path):
    """Brief: ECI 'IND' row maps to parties.IN.IND via alias-add; no mint."""
    parties_rows = [
        {"party_id": "parties.IN.UNK", "short": "UNK", "full": "Unresolved Party", "is_sentinel": "true"},
        {"party_id": "parties.IN.IND", "short": "IND", "full": "Independent", "is_sentinel": "true"},
        {"party_id": "parties.IN.NOTA", "short": "NOTA", "full": "None of the Above", "is_sentinel": "true"},
    ]
    eci_2024 = [
        _eci_2024_row(pc="Rohtak", candidate="SATISH KUMAR", party="IND"),
    ]
    candidacies = [
        _unk_candidacy(
            pc="Rohtak", candidate="SATISH KUMAR", party_short_raw="ESBD", year=2024
        ),
    ]
    repo_root = _setup_repo(
        tmp_path,
        parties_rows=parties_rows,
        eci_2024_data=eci_2024,
        candidacies_2024=candidacies,
    )
    result = correlate(years=[2024], repo_root=repo_root)
    verdict = _read_csv(result["verdict_path"])
    assert len(verdict) == 1
    row = verdict[0]
    assert row["action"] == "alias-add"
    assert row["proposed_party_id"] == "parties.IN.IND"
    assert row["party_short_raw"] == "ESBD"


def test_unicode_punctuation_normalisation_still_joins(tmp_path: Path):
    """Brief: candidate name with accented char + en-dash still joins
    against ASCII + hyphen via the NFKD-ASCII normaliser."""
    parties_rows = [
        {"party_id": "parties.IN.UNK", "short": "UNK", "full": "Unresolved Party", "is_sentinel": "true"},
        {"party_id": "parties.IN.IND", "short": "IND", "full": "Independent", "is_sentinel": "true"},
        {"party_id": "parties.IN.NOTA", "short": "NOTA", "full": "None of the Above", "is_sentinel": "true"},
        {"party_id": "parties.IN.INC", "short": "INC", "full": "Indian National Congress"},
    ]
    # ECI side: accented + en-dash; PC carries "and" (matches candidacies)
    eci_2024 = [
        _eci_2024_row(
            pc="Andaman and Nicobar Islands",
            candidate="Andr\u00e9\u2013Garcia",
            party="INC",
        ),
    ]
    # candidacies.csv side: ASCII + hyphen
    candidacies = [
        _unk_candidacy(
            pc="Andaman and Nicobar Islands",
            candidate="Andre-Garcia",
            party_short_raw="INC_VARIANT",
            year=2024,
        ),
    ]
    repo_root = _setup_repo(
        tmp_path,
        parties_rows=parties_rows,
        eci_2024_data=eci_2024,
        candidacies_2024=candidacies,
    )
    result = correlate(years=[2024], repo_root=repo_root)
    verdict = _read_csv(result["verdict_path"])
    assert len(verdict) == 1
    row = verdict[0]
    assert row["action"] == "alias-add"
    assert row["proposed_party_id"] == "parties.IN.INC"
    assert row["party_short_raw"] == "INC_VARIANT"


def test_eci_no_match_on_name_skips(tmp_path: Path):
    """Brief: a UNK row that fails to join (publisher mismatch) lands in
    skipped.csv with reason eci-no-match-on-name."""
    parties_rows = [
        {"party_id": "parties.IN.UNK", "short": "UNK", "full": "Unresolved Party", "is_sentinel": "true"},
        {"party_id": "parties.IN.IND", "short": "IND", "full": "Independent", "is_sentinel": "true"},
        {"party_id": "parties.IN.NOTA", "short": "NOTA", "full": "None of the Above", "is_sentinel": "true"},
    ]
    # ECI has NO row matching the candidacy's (pc, candidate)
    eci_2024 = [
        _eci_2024_row(pc="Other PC", candidate="OTHER CANDIDATE", party="BJP"),
    ]
    candidacies = [
        _unk_candidacy(
            pc="Missing PC", candidate="ABSENT CANDIDATE", party_short_raw="ZZZP", year=2024
        ),
    ]
    repo_root = _setup_repo(
        tmp_path,
        parties_rows=parties_rows,
        eci_2024_data=eci_2024,
        candidacies_2024=candidacies,
    )
    result = correlate(years=[2024], repo_root=repo_root)
    verdict = _read_csv(result["verdict_path"])
    skipped = _read_csv(result["skipped_path"])
    assert verdict == []
    assert len(skipped) == 1
    row = skipped[0]
    assert row["party_short_raw"] == "ZZZP"
    assert row["reason"] == "eci-no-match-on-name"
    assert row["n_rows"] == "1"


def test_eci_internal_collision_skips(tmp_path: Path):
    """Brief: same publisher label joins to two genuinely different ECI
    labels with no dominant majority -> skip with reason eci-internal-collision."""
    parties_rows = [
        {"party_id": "parties.IN.UNK", "short": "UNK", "full": "Unresolved Party", "is_sentinel": "true"},
        {"party_id": "parties.IN.IND", "short": "IND", "full": "Independent", "is_sentinel": "true"},
        {"party_id": "parties.IN.NOTA", "short": "NOTA", "full": "None of the Above", "is_sentinel": "true"},
    ]
    # Same publisher label "AMBIG" but ECI splits it across BJP / INC equally
    eci_2024 = [
        _eci_2024_row(pc="PC One", candidate="CAND A", party="BJP"),
        _eci_2024_row(pc="PC Two", candidate="CAND B", party="INC"),
    ]
    candidacies = [
        _unk_candidacy(pc="PC One", candidate="CAND A", party_short_raw="AMBIG", year=2024),
        _unk_candidacy(pc="PC Two", candidate="CAND B", party_short_raw="AMBIG", year=2024),
    ]
    repo_root = _setup_repo(
        tmp_path,
        parties_rows=parties_rows,
        eci_2024_data=eci_2024,
        candidacies_2024=candidacies,
    )
    result = correlate(years=[2024], repo_root=repo_root)
    verdict = _read_csv(result["verdict_path"])
    skipped = _read_csv(result["skipped_path"])
    assert verdict == []
    assert len(skipped) == 1
    row = skipped[0]
    assert row["party_short_raw"] == "AMBIG"
    assert row["reason"] == "eci-internal-collision"
    assert row["n_rows"] == "2"


def test_dominant_label_above_threshold_resolves(tmp_path: Path):
    """Brief: 4 of 5 joined rows agree on ECI label (80% threshold met) ->
    verdict for the majority; the 1 outlier silently rides along but is
    captured in the per-year stats."""
    parties_rows = [
        {"party_id": "parties.IN.UNK", "short": "UNK", "full": "Unresolved Party", "is_sentinel": "true"},
        {"party_id": "parties.IN.IND", "short": "IND", "full": "Independent", "is_sentinel": "true"},
        {"party_id": "parties.IN.NOTA", "short": "NOTA", "full": "None of the Above", "is_sentinel": "true"},
    ]
    # 4 rows ECI=ESBD, 1 row ECI=IND -> 4/5 = 80%
    eci_2024 = [
        _eci_2024_row(pc=f"PC {i}", candidate=f"CAND {i}", party="ESBD") for i in range(4)
    ] + [
        _eci_2024_row(pc="PC 5", candidate="CAND 5", party="IND"),
    ]
    candidacies = [
        _unk_candidacy(pc=f"PC {i}", candidate=f"CAND {i}", party_short_raw="ESBD", year=2024)
        for i in range(4)
    ] + [
        _unk_candidacy(pc="PC 5", candidate="CAND 5", party_short_raw="ESBD", year=2024),
    ]
    repo_root = _setup_repo(
        tmp_path,
        parties_rows=parties_rows,
        eci_2024_data=eci_2024,
        candidacies_2024=candidacies,
    )
    result = correlate(years=[2024], repo_root=repo_root)
    verdict = _read_csv(result["verdict_path"])
    assert len(verdict) == 1
    row = verdict[0]
    assert row["action"] == "mint-new"
    assert row["proposed_party_id"] == "parties.IN.ESBD"
    assert row["tcpd_frequent_abbrev"] == "ESBD"


def test_existing_collision_disambiguated_mint(tmp_path: Path):
    """Brief: proposed parties.IN.ESBD already exists with different full;
    mint as parties.IN.ESBD_LS2024 and surface the disambiguation in
    skipped.csv as informational."""
    parties_rows = [
        {"party_id": "parties.IN.UNK", "short": "UNK", "full": "Unresolved Party", "is_sentinel": "true"},
        {"party_id": "parties.IN.IND", "short": "IND", "full": "Independent", "is_sentinel": "true"},
        {"party_id": "parties.IN.NOTA", "short": "NOTA", "full": "None of the Above", "is_sentinel": "true"},
        # Existing parties.IN.ESBD with a DIFFERENT short (so the label
        # itself does not resolve via alias-add)
        {"party_id": "parties.IN.ESBD", "short": "ESBD_LEGACY", "full": "Legacy ESBD party"},
    ]
    eci_2024 = [
        _eci_2024_row(pc="PC X", candidate="CAND X", party="ESBD"),
    ]
    candidacies = [
        _unk_candidacy(pc="PC X", candidate="CAND X", party_short_raw="ESBD", year=2024),
    ]
    repo_root = _setup_repo(
        tmp_path,
        parties_rows=parties_rows,
        eci_2024_data=eci_2024,
        candidacies_2024=candidacies,
    )
    result = correlate(years=[2024], repo_root=repo_root)
    verdict = _read_csv(result["verdict_path"])
    assert len(verdict) == 1
    row = verdict[0]
    assert row["action"] == "mint-new"
    assert row["proposed_party_id"] == "parties.IN.ESBD_LS2024"
    skipped = _read_csv(result["skipped_path"])
    # skipped.csv carries the informational disambiguation row
    disamb = [r for r in skipped if r["reason"] == "existing-collision-disambiguated"]
    assert len(disamb) == 1
    assert "ESBD_LS2024" in disamb[0]["detail"]


def test_verdict_csv_schema_matches_apply_consumer(tmp_path: Path):
    """The verdict.csv columns MUST match the PR #952 schema that
    tools.correlate_unk_apply consumes (action / proposed_party_id /
    party_short_raw / tcpd_frequent_abbrev / tcpd_party_name /
    tcpd_party_type / state / tcpd_start_year / tcpd_last_year)."""
    parties_rows = [
        {"party_id": "parties.IN.UNK", "short": "UNK", "full": "Unresolved Party", "is_sentinel": "true"},
        {"party_id": "parties.IN.IND", "short": "IND", "full": "Independent", "is_sentinel": "true"},
        {"party_id": "parties.IN.NOTA", "short": "NOTA", "full": "None of the Above", "is_sentinel": "true"},
    ]
    eci_2024 = [
        _eci_2024_row(pc="PC A", candidate="CAND A", party="NEWP"),
    ]
    candidacies = [
        _unk_candidacy(pc="PC A", candidate="CAND A", party_short_raw="NEWP", year=2024),
    ]
    repo_root = _setup_repo(
        tmp_path,
        parties_rows=parties_rows,
        eci_2024_data=eci_2024,
        candidacies_2024=candidacies,
    )
    result = correlate(years=[2024], repo_root=repo_root)
    with result["verdict_path"].open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert list(reader.fieldnames or []) == VERDICT_FIELDNAMES
    with result["skipped_path"].open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        assert list(reader.fieldnames or []) == SKIPPED_FIELDNAMES


def test_resolve_eci_label_priority_order():
    """Pure-function contract: NOTA/IND first, then short, then alias, then mint."""
    existing = {
        "parties.IN.UNK",
        "parties.IN.IND",
        "parties.IN.NOTA",
        "parties.IN.BJP",
        "parties.IN.YSRCP",
    }
    short_idx = {"BJP": "parties.IN.BJP", "YSRCP": "parties.IN.YSRCP"}
    alias_idx = {"YSRC": "parties.IN.YSRCP"}
    # sentinels
    assert resolve_eci_label("NOTA", existing, short_idx, alias_idx, 2024) == (
        "alias-add",
        "parties.IN.NOTA",
        False,
    )
    assert resolve_eci_label("IND", existing, short_idx, alias_idx, 2024) == (
        "alias-add",
        "parties.IN.IND",
        False,
    )
    # short hit
    assert resolve_eci_label("BJP", existing, short_idx, alias_idx, 2024) == (
        "alias-add",
        "parties.IN.BJP",
        False,
    )
    # alias hit
    assert resolve_eci_label("YSRC", existing, short_idx, alias_idx, 2024) == (
        "alias-add",
        "parties.IN.YSRCP",
        False,
    )
    # mint-new
    assert resolve_eci_label("NEWP", existing, short_idx, alias_idx, 2024) == (
        "mint-new",
        "parties.IN.NEWP",
        False,
    )


def test_both_years_aggregate_into_single_verdict(tmp_path: Path):
    """A label appearing in 2024 AND 2019 with same ECI mapping -> one
    verdict row (cross-year aggregation; alias-add applies to all years)."""
    parties_rows = [
        {"party_id": "parties.IN.UNK", "short": "UNK", "full": "Unresolved Party", "is_sentinel": "true"},
        {"party_id": "parties.IN.IND", "short": "IND", "full": "Independent", "is_sentinel": "true"},
        {"party_id": "parties.IN.NOTA", "short": "NOTA", "full": "None of the Above", "is_sentinel": "true"},
    ]
    eci_2024 = [_eci_2024_row(pc="PC 2024", candidate="C24", party="XYZP")]
    eci_2019 = [_eci_2019_row(pc="PC 2019", candidate="C19", party="XYZP")]
    cand_2024 = [_unk_candidacy(pc="PC 2024", candidate="C24", party_short_raw="XYZP", year=2024)]
    cand_2019 = [_unk_candidacy(pc="PC 2019", candidate="C19", party_short_raw="XYZP", year=2019)]
    repo_root = _setup_repo(
        tmp_path,
        parties_rows=parties_rows,
        eci_2024_data=eci_2024,
        eci_2019_data=eci_2019,
        candidacies_2024=cand_2024,
        candidacies_2019=cand_2019,
    )
    result = correlate(years=[2024, 2019], repo_root=repo_root)
    verdict = _read_csv(result["verdict_path"])
    assert len(verdict) == 1
    assert verdict[0]["proposed_party_id"] == "parties.IN.XYZP"
    assert result["per_year_in"] == {2024: 1, 2019: 1}


def test_run_id_is_deterministic(tmp_path: Path):
    """Same input -> same run id (deterministic, content-derived)."""
    parties_rows = [
        {"party_id": "parties.IN.UNK", "short": "UNK", "full": "Unresolved Party", "is_sentinel": "true"},
        {"party_id": "parties.IN.IND", "short": "IND", "full": "Independent", "is_sentinel": "true"},
        {"party_id": "parties.IN.NOTA", "short": "NOTA", "full": "None of the Above", "is_sentinel": "true"},
    ]
    eci_2024 = [_eci_2024_row(pc="PC A", candidate="C", party="MNOP")]
    cand = [_unk_candidacy(pc="PC A", candidate="C", party_short_raw="MNOP", year=2024)]
    repo_root_1 = _setup_repo(
        tmp_path / "r1",
        parties_rows=parties_rows,
        eci_2024_data=eci_2024,
        candidacies_2024=cand,
    )
    repo_root_2 = _setup_repo(
        tmp_path / "r2",
        parties_rows=parties_rows,
        eci_2024_data=eci_2024,
        candidacies_2024=cand,
    )
    r1 = correlate(years=[2024], repo_root=repo_root_1)
    r2 = correlate(years=[2024], repo_root=repo_root_2)
    assert r1["run_id"] == r2["run_id"]
