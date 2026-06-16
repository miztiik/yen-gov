"""Contract tests for yen_gov.canonical.adapters.tn_ceo.electors_by_sex."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.adapters.tn_ceo.electors_by_sex import (
    DELIM_YEAR,
    EXPECTED_AC_COUNT,
    FILE_CLASS,
    PRODUCER,
    STATE_SLUG,
    TITLE,
    VARIABLE_ID,
    VINTAGE_2021,
    _SEX_FACET_COLUMNS,
    ingest,
    is_atomic_ac_row,
    load_tn_ac_index,
    parse_ac_no,
    parse_count,
)
from yen_gov.canonical.citation import derive_source_id


REPO_ROOT = Path(__file__).resolve().parents[2]
ELECTORAL_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "electoral.csv"
EPHEMERAL_TN = (
    REPO_ROOT / "datasets" / "ephemeral" / "tn_acwise_gendercount.csv"
)


# --------------------------------------------------------------------------- #
# Module-level constants - guard the wire-format identity.
# --------------------------------------------------------------------------- #


class TestModuleConstants:
    """Module-level identity must match columns.json + variables.csv shape."""

    def test_file_class_is_seed_file_path(self):
        # The constant points at the SEED file (not the glob); the adapter
        # passes the glob form to write_csv via a local variable. This
        # constant exists primarily for documentation and external import.
        assert FILE_CLASS == (
            "datasets/data/datapoints/electoral_geo/"
            "electors-persons-by-sex.csv"
        )

    def test_variable_id_has_no_grain_prefix(self):
        # Anti-pattern guard per CLAUDE.md section 10 + Max's verdict:
        # variable identity is SAME across grains; renderer dispatches by
        # entity_kind. A grain prefix like "ac-electors-..." would split
        # the conceptual indicator across grain-specific siblings.
        assert not VARIABLE_ID.startswith("ac-")
        assert not VARIABLE_ID.startswith("pc-")
        assert VARIABLE_ID == "electors-persons-by-sex"

    def test_vintage_is_string_year(self):
        # Vintage is a string per derive_source_id() contract; the time
        # column is the int cast. Mismatch would corrupt source_id hash.
        assert VINTAGE_2021 == "2021"
        assert int(VINTAGE_2021) == 2021

    def test_delim_year_and_universe_size(self):
        # If the entities catalogue drifts (e.g. TN delim_year=2008 cohort
        # changes from 234 ACs), this test surfaces the drift BEFORE the
        # ingest produces a row-count mismatch in production.
        assert DELIM_YEAR == 2008
        assert EXPECTED_AC_COUNT == 234
        assert STATE_SLUG == "tamil-nadu"

    def test_sex_facet_map_matches_columns_json_enum(self):
        # The canonical sex enum is declared in columns.json as
        # ["male", "female", "third_gender"]. The publisher labels
        # map to exactly those three values.
        assert set(_SEX_FACET_COLUMNS.values()) == {
            "male",
            "female",
            "third_gender",
        }
        # Publisher uses title-case labels with "Third Gender" (two words).
        assert set(_SEX_FACET_COLUMNS.keys()) == {
            "Male",
            "Female",
            "Third Gender",
        }


# --------------------------------------------------------------------------- #
# Pure predicates and parsers.
# --------------------------------------------------------------------------- #


class TestIsAtomicAcRow:
    """Only positive-integer ``Sl No.`` rows are atomic AC observations."""

    def test_one_is_atomic(self):
        assert is_atomic_ac_row({"Sl No.": "1"}) is True

    def test_max_ac_is_atomic(self):
        assert is_atomic_ac_row({"Sl No.": "234"}) is True

    def test_total_subtotal_rejected(self):
        assert is_atomic_ac_row({"Sl No.": "Total"}) is False

    def test_grand_total_rejected(self):
        assert is_atomic_ac_row({"Sl No.": "Grand Total"}) is False

    def test_empty_rejected(self):
        assert is_atomic_ac_row({"Sl No.": ""}) is False

    def test_missing_key_rejected(self):
        assert is_atomic_ac_row({}) is False

    def test_whitespace_rejected(self):
        assert is_atomic_ac_row({"Sl No.": "   "}) is False


class TestParseAcNo:
    """Atomic-row ``AC No.`` parser - integer or raise."""

    def test_valid_integer(self):
        assert parse_ac_no({"AC No.": "1"}, line_no=2) == 1
        assert parse_ac_no({"AC No.": "234"}, line_no=235) == 234

    def test_rejects_blank(self):
        with pytest.raises(ValueError, match="AC No."):
            parse_ac_no({"AC No.": ""}, line_no=2)

    def test_rejects_non_integer(self):
        with pytest.raises(ValueError, match="AC No."):
            parse_ac_no({"AC No.": "abc"}, line_no=2)


class TestParseCount:
    """Electors-count parser - zero is valid, blank raises."""

    def test_zero_preserved(self):
        # Third-gender bucket frequently zero; must round-trip as 0, not None.
        assert parse_count("0", line_no=2, column="Third Gender") == 0

    def test_positive_integer(self):
        assert parse_count("123359", line_no=2, column="Male") == 123359

    def test_comma_grouping_tolerated(self):
        # Publisher 2021 uses raw integers; this guards forward-compat
        # against future vintages adopting the Indian-numbering grouping.
        assert parse_count("1,23,359", line_no=2, column="Male") == 123359

    def test_rejects_blank(self):
        # Publisher always populates counts (zero is a valid measurement);
        # a blank cell is a data-shape error.
        with pytest.raises(ValueError, match="empty"):
            parse_count("", line_no=2, column="Male")

    def test_rejects_negative(self):
        with pytest.raises(ValueError, match="negative"):
            parse_count("-1", line_no=2, column="Male")

    def test_rejects_non_integer(self):
        with pytest.raises(ValueError, match="integer"):
            parse_count("12.5", line_no=2, column="Male")


# --------------------------------------------------------------------------- #
# AC-resolver oracle - corpus-grounded.
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def ac_resolver():
    assert ELECTORAL_CSV.exists(), f"missing fixture: {ELECTORAL_CSV}"
    return load_tn_ac_index(ELECTORAL_CSV)


class TestLoadTnAcIndex:
    """The TN-2008 AC universe must be exactly 234 entities."""

    def test_universe_size_is_234(self, ac_resolver):
        assert len(ac_resolver.by_eci_no) == EXPECTED_AC_COUNT

    def test_eci_no_1_resolves(self, ac_resolver):
        # Gummidipoondi - sample row from the row-c handover for grounding.
        entity_id = ac_resolver.by_eci_no.get(1)
        assert entity_id is not None
        assert entity_id.startswith("IN-AC-2008-tamil-nadu-")

    def test_eci_no_234_resolves(self, ac_resolver):
        # Last AC in the TN-2008 cohort.
        entity_id = ac_resolver.by_eci_no.get(234)
        assert entity_id is not None

    def test_all_keys_are_in_1_234_range(self, ac_resolver):
        # The publisher numbers ACs 1..234 contiguously; any gap surfaces
        # here BEFORE the publisher-row resolution raises.
        keys = set(ac_resolver.by_eci_no.keys())
        assert keys == set(range(1, EXPECTED_AC_COUNT + 1))


# --------------------------------------------------------------------------- #
# End-to-end ingest oracle.
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    not EPHEMERAL_TN.exists(),
    reason="ephemeral tn_acwise_gendercount.csv absent; integration skipped",
)
class TestIngestEndToEnd:
    """702 rows = 234 ACs x 3 sex facets, composite PK bijection."""

    def test_emits_canonical_csv_with_bijection(self, tmp_path):
        # Copy electoral.csv into the tmp repo root so the adapter's
        # default resolver finds it.
        tmp_electoral = (
            tmp_path / "datasets" / "data" / "entities" / "electoral.csv"
        )
        tmp_electoral.parent.mkdir(parents=True, exist_ok=True)
        tmp_electoral.write_bytes(ELECTORAL_CSV.read_bytes())

        result = ingest(
            input_csv=EPHEMERAL_TN,
            repo_root=tmp_path,
        )

        # Headline counts.
        assert result.row_count == 702
        assert result.unique_entity_ids == 234
        assert result.unique_sex_facets == 3
        assert result.grand_total_observed == 1

        # File-on-disk check: header + 702 rows = 703 lines.
        text = result.output_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        assert len(lines) == 703
        assert lines[0] == (
            "entity_id,time,value,sex,source_id,processing_level"
        )

        # Re-read via csv.DictReader and verify the composite-PK bijection.
        with result.output_path.open(encoding="utf-8", newline="") as fh:
            out_rows = list(csv.DictReader(fh))
        keys = [(r["entity_id"], r["time"], r["sex"]) for r in out_rows]
        assert len(set(keys)) == 702, (
            "(entity_id, time, sex) composite key is not a bijection"
        )

        # Every row carries the deterministic source_id.
        expected_src = derive_source_id(PRODUCER, TITLE, VINTAGE_2021)
        assert {r["source_id"] for r in out_rows} == {expected_src}

        # Every row carries processing_level=minor (pure mechanical
        # transcode; no normalisation, no joins-against-curator).
        assert {r["processing_level"] for r in out_rows} == {"minor"}

        # Every row carries time=2021 (vintage).
        assert {r["time"] for r in out_rows} == {"2021"}

        # Every row's sex is in the closed enum.
        assert {r["sex"] for r in out_rows} == {
            "male", "female", "third_gender",
        }

        # Spot-check the first publisher row: Gummidipoondi (AC No. 1):
        #   Male=123359, Female=130734, Third Gender=36
        gummidi = [
            r for r in out_rows
            if r["entity_id"] == "IN-AC-2008-tamil-nadu-4062"
        ]
        assert len(gummidi) == 3
        by_sex = {r["sex"]: int(float(r["value"])) for r in gummidi}
        assert by_sex == {"male": 123359, "female": 130734, "third_gender": 36}

    def test_grand_total_matches_facet_sum(self, tmp_path):
        # Cross-check: emitted facet-row values must sum to the publisher's
        # Grand Total. The plan-doc grand-total row is:
        #   Male=28030658, Female=29304905, Third Gender=7728
        # This is an oracle test: if the publisher silently introduces or
        # drops a row in a future vintage, the cross-total will diverge.
        tmp_electoral = (
            tmp_path / "datasets" / "data" / "entities" / "electoral.csv"
        )
        tmp_electoral.parent.mkdir(parents=True, exist_ok=True)
        tmp_electoral.write_bytes(ELECTORAL_CSV.read_bytes())

        ingest(input_csv=EPHEMERAL_TN, repo_root=tmp_path)
        out_path = (
            tmp_path / "datasets" / "data" / "datapoints" / "electoral_geo"
            / "electors-persons-by-sex.csv"
        )
        with out_path.open(encoding="utf-8", newline="") as fh:
            out_rows = list(csv.DictReader(fh))

        totals: dict[str, int] = {}
        for r in out_rows:
            totals[r["sex"]] = totals.get(r["sex"], 0) + int(float(r["value"]))
        assert totals == {
            "male": 28030658,
            "female": 29304905,
            "third_gender": 7728,
        }
