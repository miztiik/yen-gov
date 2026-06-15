"""Contract tests for the ADR/MyNeta Lok Sabha 2014 winners-affidavit adapter.

Layered the same way `test_canonical_eci_mcc_seizures.py` is:

    1. Pure unit tests on the three name/constituency/party normalisers
       (`backend/yen_gov/canonical/adapters/myneta/_normalisers.py`) —
       no fixtures, no filesystem; fastest possible reviewer feedback.
    2. Integration tests on `enrich_2014_ls_candidacies` using tiny
       handwritten fixtures in `tmp_path` (no dependency on the live
       on-disk `datasets/elections/parliament/election=2014/candidacies.csv`
       so the test is hermetic and CI-stable).
    3. Adilabad oracle spot-check baked in: 2014 ADILABAD winner Godam
       Nagesh has criminal_cases=0, total_assets=10,378,857. This row is
       a "canonical exemplar" — if this assertion ever flips, either
       (a) the affidavit publisher changed their figures (audit upstream
       before allowing the test to change) or (b) the adapter's coercion
       lost a digit (regression).

Per plan D2 / E1: when ANY affidavit row stays unmatched after all four
passes, the adapter MUST exit 2 and emit the
`datasets/_ops/affidavit-2014-unmatched-YYYY-MM-DD.csv` sidecar — the
tampered-fixture test exercises that abort path.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.adapters.myneta._normalisers import (
    normalise_candidate_name,
    normalise_constituency_name,
    normalise_party_short,
)
from yen_gov.canonical.adapters.myneta.lok_sabha_2014_winners import (
    ENRICHMENT_COLUMNS,
    SOURCE_PRODUCER,
    SOURCE_TITLE,
    SOURCE_VINTAGE,
    enrich_2014_ls_candidacies,
)


# --------------------------------------------------------------------------- #
# Unit tests — normalisers (pure functions; zero fixtures).
# --------------------------------------------------------------------------- #


class TestNormaliseCandidateName:
    def test_lowercases(self):
        assert normalise_candidate_name("RAMSHANKAR KATHERIA") == "ramshankar katheria"

    def test_strips_dr_honorific_with_dot(self):
        assert normalise_candidate_name("Dr. Ramshankar Katheria") == "ramshankar katheria"

    def test_strips_shri_honorific(self):
        assert normalise_candidate_name("Shri Narendra Modi") == "narendra modi"

    def test_strips_smt_honorific(self):
        assert normalise_candidate_name("Smt. Sonia Gandhi") == "sonia gandhi"

    def test_strips_backslashes_tcpd_quirk(self):
        # TCPD writers occasionally wrap surnames in escaped backslashes:
        #   "JANARDAN SINGH \\SIGRIWAL\\" -> "janardan singh sigriwal".
        assert (
            normalise_candidate_name("JANARDAN SINGH \\SIGRIWAL\\")
            == "janardan singh sigriwal"
        )

    def test_strips_internal_dots(self):
        assert normalise_candidate_name("P.C. Gaddigoudar") == "pc gaddigoudar"

    def test_collapses_internal_whitespace(self):
        assert normalise_candidate_name("Babul   Supriyo") == "babul supriyo"


class TestNormaliseConstituencyName:
    def test_lowercases(self):
        assert normalise_constituency_name("AMRITSAR") == "amritsar"

    def test_strips_trailing_paren_qualifier(self):
        # Affidavit publisher carries parenthetical clarifiers we drop:
        #   "Ahmadabad (East)" -> "ahmadabad" (the qualifier is metadata,
        #   not part of the joinable name).
        assert normalise_constituency_name("Ahmadabad (East)") == "ahmadabad"

    def test_strips_sc_st_paren_qualifier(self):
        assert normalise_constituency_name("Jamui (SC)") == "jamui"
        assert normalise_constituency_name("Bastar (ST)") == "bastar"

    def test_collapses_hyphen_whitespace(self):
        # "Barddhaman - Durgapur" -> "barddhaman-durgapur" (no spaces
        # around the hyphen; the affidavit dialect uses spaces, TCPD
        # does not).
        assert (
            normalise_constituency_name("Barddhaman - Durgapur")
            == "barddhaman-durgapur"
        )

    def test_strips_internal_dots(self):
        assert normalise_constituency_name("Mainpuri(GEN)") == "mainpuri"


class TestNormalisePartyShort:
    def test_uppercases(self):
        assert normalise_party_short("bjp") == "BJP"

    def test_strips_dots(self):
        assert normalise_party_short("c.p.i.m") == "CPIM"

    def test_strips_whitespace(self):
        assert normalise_party_short(" T ") == "T"


# --------------------------------------------------------------------------- #
# Integration tier — hermetic mini-fixtures.
# --------------------------------------------------------------------------- #


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    """Build a minimal repo-shaped directory under `tmp_path`.

    Creates the exact tree the adapter reaches into:
        datasets/data/entities/source.csv       (header only)
        datasets/elections/parliament/election=2014/candidacies.csv
        datasets/_overrides/affidavit-2014-pc-aliases.csv  (with 1 alias)

    The candidacies fixture is constructed so each pass has at least
    one match, so we can exercise the full join engine:
        - Pass 1: (CONSTITUENCY, CANDIDATE) exact match.
        - Pass 2: AltSpelling fallback.
        - Pass 3: Alias overlay (the Aruku/Araku canonical case).
        - Pass 4: Single-winner-in-PC fallback after Pass 1-3 misses.
    """
    root = tmp_path

    # --- source.csv: header + one pre-existing unrelated ECI row so the
    # adapter must APPEND (not rewrite). Mirrors the live file shape.
    src_dir = root / "datasets" / "data" / "entities"
    src_dir.mkdir(parents=True, exist_ok=True)
    src_csv = src_dir / "source.csv"
    src_csv.write_text(
        "source_id,producer,title,vintage,url\n"
        "src-fakeECI,Election Commission of India,General Election to Lok Sabha 2014,2014,\n",
        encoding="utf-8",
    )

    # --- candidacies.csv: 5 winners (one per requested pass + 1 loser).
    cand_dir = root / "datasets" / "elections" / "parliament" / "election=2014"
    cand_dir.mkdir(parents=True, exist_ok=True)
    cand_fieldnames = [
        "entity_id", "state", "election_year", "constituency_no",
        "constituency_name", "candidate_name", "party_id", "party_short_raw",
        "votes", "vote_share_pct", "position", "result", "sex", "age",
        "education", "profession", "candidate_type", "source_id",
        "processing_level", "processing_note",
    ]
    cand_rows = [
        # Pass 1 target: AGRA / DR. RAMSHANKAR KATHERIA (one word, per
        # affidavit publisher convention; the normaliser strips the Dr.
        # honorific from both sides and lowercases for an exact match).
        {
            "entity_id": "IN-PC-AGRA", "state": "uttar-pradesh", "election_year": "2014",
            "constituency_no": "18", "constituency_name": "AGRA",
            "candidate_name": "DR. RAMSHANKAR KATHERIA", "party_id": "parties.IN.BJP",
            "party_short_raw": "BJP", "votes": "583716", "vote_share_pct": "54.46",
            "position": "1", "result": "won", "sex": "M", "age": "",
            "education": "", "profession": "", "candidate_type": "",
            "source_id": "src-fakeECI", "processing_level": "minor",
            "processing_note": "",
        },
        # Pass 2 target: AMETHI vs winner_const='SULTANPUR' but candidate match
        # We'll set this up so AltSpelling matches winner_const.
        {
            "entity_id": "IN-PC-AMETHI", "state": "uttar-pradesh", "election_year": "2014",
            "constituency_no": "37", "constituency_name": "AMETHI",
            "candidate_name": "RAHUL GANDHI", "party_id": "parties.IN.INC",
            "party_short_raw": "INC", "votes": "408651", "vote_share_pct": "46.71",
            "position": "1", "result": "won", "sex": "M", "age": "",
            "education": "", "profession": "", "candidate_type": "",
            "source_id": "src-fakeECI", "processing_level": "minor",
            "processing_note": "",
        },
        # Pass 3 target: ARUKU canonical vs ARAKU affidavit (alias overlay row)
        {
            "entity_id": "IN-PC-ARUKU", "state": "andhra-pradesh", "election_year": "2014",
            "constituency_no": "1", "constituency_name": "ARUKU",
            "candidate_name": "KOTHAPALLI GEETHA", "party_id": "parties.IN.YSRCP",
            "party_short_raw": "YSRCP", "votes": "385383", "vote_share_pct": "44.69",
            "position": "1", "result": "won", "sex": "F", "age": "",
            "education": "", "profession": "", "candidate_type": "",
            "source_id": "src-fakeECI", "processing_level": "minor",
            "processing_note": "",
        },
        # Pass 4 target: PC where candidate name diverges but only one winner exists
        {
            "entity_id": "IN-PC-AKBARPUR", "state": "uttar-pradesh", "election_year": "2014",
            "constituency_no": "55", "constituency_name": "AKBARPUR",
            "candidate_name": "DEVENDRA SINGH @ BHOLE SINGH", "party_id": "parties.IN.BJP",
            "party_short_raw": "BJP", "votes": "481584", "vote_share_pct": "48.49",
            "position": "1", "result": "won", "sex": "M", "age": "",
            "education": "", "profession": "", "candidate_type": "",
            "source_id": "src-fakeECI", "processing_level": "minor",
            "processing_note": "",
        },
        # Loser - must stay NULL on all 4 enrichment cols.
        {
            "entity_id": "IN-PC-AGRA", "state": "uttar-pradesh", "election_year": "2014",
            "constituency_no": "18", "constituency_name": "AGRA",
            "candidate_name": "UPENDRA SINGH (LOSER)", "party_id": "parties.IN.INC",
            "party_short_raw": "INC", "votes": "283000", "vote_share_pct": "26.40",
            "position": "2", "result": "lost", "sex": "M", "age": "",
            "education": "", "profession": "", "candidate_type": "",
            "source_id": "src-fakeECI", "processing_level": "minor",
            "processing_note": "",
        },
        # Adilabad oracle row - Pass 1 exact match for the gold-standard
        # assertion ((cc, ta, tl, exp) = (0, 10378857, 148784, 2215311)).
        {
            "entity_id": "IN-PC-ADILABAD", "state": "telangana", "election_year": "2014",
            "constituency_no": "1", "constituency_name": "ADILABAD",
            "candidate_name": "GODAM NAGESH", "party_id": "parties.IN.TRS",
            "party_short_raw": "TRS", "votes": "446158", "vote_share_pct": "40.21",
            "position": "1", "result": "won", "sex": "M", "age": "",
            "education": "", "profession": "", "candidate_type": "",
            "source_id": "src-fakeECI", "processing_level": "minor",
            "processing_note": "",
        },
    ]
    cand_csv = cand_dir / "candidacies.csv"
    with cand_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cand_fieldnames, lineterminator="\n")
        writer.writeheader()
        for r in cand_rows:
            writer.writerow(r)

    # --- alias overlay (single row exercising the Pass 3 ARUKU <- ARAKU case).
    aliases_dir = root / "datasets" / "_overrides"
    aliases_dir.mkdir(parents=True, exist_ok=True)
    aliases_csv = aliases_dir / "affidavit-2014-pc-aliases.csv"
    aliases_csv.write_text(
        "# fixture alias overlay\n"
        "normalised_affidavit_pc,normalised_canonical_pc,state,note\n"
        "araku,aruku,andhra-pradesh,fixture\n",
        encoding="utf-8",
    )

    return root


@pytest.fixture
def affidavit_csv(tmp_path: Path) -> Path:
    """Affidavit fixture: one row per intended pass (4 rows total).

    Column shape matches the live ephemeral file exactly so the adapter
    sees realistic publisher header names. Note that the live file uses
    the column name `CriminalCase` (singular), not `CriminalCases` —
    this is verified against the on-disk file.
    """
    rows_csv = tmp_path / "fixture_affidavits.csv"
    fieldnames = [
        "Sno", "Candidate", "Constituency", "Party", "CriminalCase",
        "Education", "TotalAssets", "Liabilities", "Sex", "AltSpelling",
        "ElectionExpense",
    ]
    rows = [
        # Pass 1 target: AGRA / Dr. Ramshankar Katheria
        {
            "Sno": "2", "Candidate": "Dr. Ramshankar Katheria", "Constituency": "Agra",
            "Party": "BJP", "CriminalCase": "1", "Education": "Graduate",
            "TotalAssets": "20000000", "Liabilities": "50000", "Sex": "M",
            "AltSpelling": "AGRA", "ElectionExpense": "2500000",
        },
        # Pass 2 target: AltSpelling=AMETHI carries the canonical match
        {
            "Sno": "5", "Candidate": "Rahul Gandhi", "Constituency": "Amethi UP",
            "Party": "INC", "CriminalCase": "0", "Education": "Graduate Professional",
            "TotalAssets": "92000000", "Liabilities": "100000", "Sex": "M",
            "AltSpelling": "AMETHI", "ElectionExpense": "2700000",
        },
        # Pass 3 target: ARAKU (affidavit) vs ARUKU (canonical) - alias overlay
        {
            "Sno": "32", "Candidate": "Kothapalli Geetha", "Constituency": "Araku",
            "Party": "YSRCP", "CriminalCase": "0", "Education": "Post Graduate",
            "TotalAssets": "65147467", "Liabilities": "1500000", "Sex": "F",
            "AltSpelling": "ARAKU", "ElectionExpense": "1900000",
        },
        # Pass 4 target: AKBARPUR - candidate name diverges; only winner
        # in PC so 1:1 fallback claims it.
        {
            "Sno": "7", "Candidate": "Devendra Singh Urf Bhole Singh",
            "Constituency": "Akbarpur", "Party": "BJP", "CriminalCase": "2",
            "Education": "10th Pass", "TotalAssets": "5000000",
            "Liabilities": "200000", "Sex": "M", "AltSpelling": "AKBARPUR",
            "ElectionExpense": "1500000",
        },
        # Adilabad oracle: gold standard for the canonical figure
        # (criminal=0, total_assets=10,378,857, liabilities=148784,
        # election_expense=2,215,311). Pass 1 exact match.
        {
            "Sno": "1", "Candidate": "Godam Nagesh", "Constituency": "Adilabad",
            "Party": "T", "CriminalCase": "0", "Education": "Graduate",
            "TotalAssets": "10378857", "Liabilities": "148784", "Sex": "M",
            "AltSpelling": "ADILABAD", "ElectionExpense": "2215311",
        },
    ]
    with rows_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    return rows_csv


class TestEnrichmentHappyPath:
    """Full enrichment exercises Pass 1 + 2 + 3 + 4 + Adilabad oracle."""

    def test_all_5_affidavits_match(self, fake_repo: Path, affidavit_csv: Path):
        report = enrich_2014_ls_candidacies(
            root=fake_repo, affidavit_path=affidavit_csv
        )
        assert report.unmatched_count == 0
        assert report.pass1_matched == 2  # AGRA + ADILABAD
        assert report.pass2_matched == 1  # AMETHI via AltSpelling
        assert report.pass3_matched == 1  # ARUKU via alias overlay
        assert report.pass4_matched == 1  # AKBARPUR via 1:1 fallback
        assert report.source_id  # non-empty MyNeta source_id minted

    def test_header_extended_with_4_cols(
        self, fake_repo: Path, affidavit_csv: Path
    ):
        enrich_2014_ls_candidacies(root=fake_repo, affidavit_path=affidavit_csv)
        cand_csv = (
            fake_repo / "datasets" / "elections" / "parliament"
            / "election=2014" / "candidacies.csv"
        )
        with cand_csv.open(encoding="utf-8", newline="") as fh:
            header = next(csv.reader(fh))
        for col in ENRICHMENT_COLUMNS:
            assert col in header

    def test_winner_source_id_preserved_per_user_binding(
        self, fake_repo: Path, affidavit_csv: Path
    ):
        """The 'don't change data already published' invariant:
        every candidacy row's source_id MUST stay as the upstream
        publisher's (here `src-fakeECI`). The MyNeta source_id is
        registered in source.csv for the citation ledger, but is
        NOT stamped onto the row.
        """
        enrich_2014_ls_candidacies(root=fake_repo, affidavit_path=affidavit_csv)
        cand_csv = (
            fake_repo / "datasets" / "elections" / "parliament"
            / "election=2014" / "candidacies.csv"
        )
        with cand_csv.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        for r in rows:
            assert r["source_id"] == "src-fakeECI", (
                f"source_id was overwritten for {r['constituency_name']}"
            )

    def test_loser_rows_stay_null_on_all_4_cols(
        self, fake_repo: Path, affidavit_csv: Path
    ):
        enrich_2014_ls_candidacies(root=fake_repo, affidavit_path=affidavit_csv)
        cand_csv = (
            fake_repo / "datasets" / "elections" / "parliament"
            / "election=2014" / "candidacies.csv"
        )
        with cand_csv.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        losers = [r for r in rows if r["result"] != "won"]
        assert losers, "fixture must have at least one loser row"
        for r in losers:
            for col in ENRICHMENT_COLUMNS:
                assert r[col] == "", f"loser {r['candidate_name']} has {col}={r[col]!r}"

    def test_adilabad_oracle_exact(self, fake_repo: Path, affidavit_csv: Path):
        """The canonical exemplar — Godam Nagesh / ADILABAD / 2014.

        If this assertion ever flips, audit the affidavit publisher's
        upstream change OR investigate a regression in the coercion path.
        """
        enrich_2014_ls_candidacies(root=fake_repo, affidavit_path=affidavit_csv)
        cand_csv = (
            fake_repo / "datasets" / "elections" / "parliament"
            / "election=2014" / "candidacies.csv"
        )
        with cand_csv.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        adilabad = [r for r in rows if r["constituency_name"] == "ADILABAD"]
        assert len(adilabad) == 1
        r = adilabad[0]
        assert r["criminal_cases_declared"] == "0"
        assert r["total_assets_inr"] == "10378857"
        assert r["total_liabilities_inr"] == "148784"
        assert r["declared_election_expense_inr"] == "2215311"

    def test_pass2_3_4_get_major_processing_level(
        self, fake_repo: Path, affidavit_csv: Path
    ):
        """Pass 2/3/4 matches MUST flip processing_level to 'major' and
        write a processing_note marker. Pass 1 matches stay 'minor'."""
        enrich_2014_ls_candidacies(root=fake_repo, affidavit_path=affidavit_csv)
        cand_csv = (
            fake_repo / "datasets" / "elections" / "parliament"
            / "election=2014" / "candidacies.csv"
        )
        with cand_csv.open(encoding="utf-8", newline="") as fh:
            rows = {r["constituency_name"]: r for r in csv.DictReader(fh)}
        # AGRA winner = Pass 1, minor, empty note.
        assert rows["AGRA"]["processing_level"] == "minor"
        assert rows["AGRA"]["processing_note"] == ""
        # AMETHI winner = Pass 2.
        assert rows["AMETHI"]["processing_level"] == "major"
        assert "AltSpelling" in rows["AMETHI"]["processing_note"]
        # ARUKU winner = Pass 3 (alias overlay).
        assert rows["ARUKU"]["processing_level"] == "major"
        assert "alias" in rows["ARUKU"]["processing_note"]
        # AKBARPUR winner = Pass 4.
        assert rows["AKBARPUR"]["processing_level"] == "major"
        assert "1:1" in rows["AKBARPUR"]["processing_note"] or (
            "fallback" in rows["AKBARPUR"]["processing_note"]
        )

    def test_source_csv_appended_with_myneta_row(
        self, fake_repo: Path, affidavit_csv: Path
    ):
        report = enrich_2014_ls_candidacies(
            root=fake_repo, affidavit_path=affidavit_csv
        )
        src_csv = fake_repo / "datasets" / "data" / "entities" / "source.csv"
        with src_csv.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        # Pre-existing + MyNeta = 2 rows.
        assert len(rows) == 2
        myneta = [r for r in rows if r["producer"] == SOURCE_PRODUCER]
        assert len(myneta) == 1
        assert myneta[0]["title"] == SOURCE_TITLE
        assert myneta[0]["vintage"] == SOURCE_VINTAGE
        assert myneta[0]["source_id"] == report.source_id

    def test_idempotent_on_second_run(
        self, fake_repo: Path, affidavit_csv: Path
    ):
        """Two back-to-back runs must produce the SAME on-disk state.

        Guards against the source.csv getting double-appended OR the
        candidacies CSV growing extra columns on the second pass.
        """
        enrich_2014_ls_candidacies(root=fake_repo, affidavit_path=affidavit_csv)
        cand_csv = (
            fake_repo / "datasets" / "elections" / "parliament"
            / "election=2014" / "candidacies.csv"
        )
        src_csv = fake_repo / "datasets" / "data" / "entities" / "source.csv"
        bytes_cand_1 = cand_csv.read_bytes()
        bytes_src_1 = src_csv.read_bytes()
        enrich_2014_ls_candidacies(root=fake_repo, affidavit_path=affidavit_csv)
        assert cand_csv.read_bytes() == bytes_cand_1
        assert src_csv.read_bytes() == bytes_src_1


class TestEnrichmentAbortOnUnmatched:
    """D2 / E1: any unmatched affidavit row -> exit 2 + sidecar."""

    def test_unmatched_row_writes_sidecar_and_aborts(
        self, fake_repo: Path, affidavit_csv: Path
    ):
        # Append a deliberately-unmatchable affidavit row.
        with affidavit_csv.open("a", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "Sno", "Candidate", "Constituency", "Party", "CriminalCase",
                    "Education", "TotalAssets", "Liabilities", "Sex",
                    "AltSpelling", "ElectionExpense",
                ],
                lineterminator="\n",
            )
            writer.writerow({
                "Sno": "999",
                "Candidate": "Made Up Person",
                "Constituency": "Imaginarium",
                "Party": "XYZ",
                "CriminalCase": "0",
                "Education": "Unknown",
                "TotalAssets": "1",
                "Liabilities": "0",
                "Sex": "U",
                "AltSpelling": "IMAGINARIUM",
                "ElectionExpense": "0",
            })

        report = enrich_2014_ls_candidacies(
            root=fake_repo, affidavit_path=affidavit_csv
        )
        assert report.unmatched_count == 1
        assert report.source_id == ""  # NOT minted on abort
        assert report.unmatched_csv_path is not None
        assert report.unmatched_csv_path.exists()

        # Sidecar must contain the unmatchable row.
        with report.unmatched_csv_path.open(encoding="utf-8", newline="") as fh:
            unmatched_rows = list(csv.DictReader(fh))
        assert len(unmatched_rows) == 1
        assert unmatched_rows[0]["Candidate"] == "Made Up Person"
        assert unmatched_rows[0]["Constituency"] == "Imaginarium"
        assert "failure_reason" in unmatched_rows[0]

    def test_abort_does_not_touch_candidacies(
        self, fake_repo: Path, affidavit_csv: Path
    ):
        """When abort fires, the live candidacies.csv must NOT have been
        rewritten (no 4 new cols, no source.csv row appended)."""
        cand_csv = (
            fake_repo / "datasets" / "elections" / "parliament"
            / "election=2014" / "candidacies.csv"
        )
        src_csv = fake_repo / "datasets" / "data" / "entities" / "source.csv"
        cand_bytes_before = cand_csv.read_bytes()
        src_bytes_before = src_csv.read_bytes()

        with affidavit_csv.open("a", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "Sno", "Candidate", "Constituency", "Party", "CriminalCase",
                    "Education", "TotalAssets", "Liabilities", "Sex",
                    "AltSpelling", "ElectionExpense",
                ],
                lineterminator="\n",
            )
            writer.writerow({
                "Sno": "999", "Candidate": "Made Up", "Constituency": "Nowhere",
                "Party": "ZZZ", "CriminalCase": "", "Education": "",
                "TotalAssets": "", "Liabilities": "", "Sex": "",
                "AltSpelling": "NOWHERE", "ElectionExpense": "",
            })

        report = enrich_2014_ls_candidacies(
            root=fake_repo, affidavit_path=affidavit_csv
        )
        assert report.unmatched_count == 1
        assert cand_csv.read_bytes() == cand_bytes_before
        assert src_csv.read_bytes() == src_bytes_before
