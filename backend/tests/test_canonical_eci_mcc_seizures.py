"""Contract tests for yen_gov.canonical.adapters.eci.mcc_seizures."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.adapters.eci.mcc_seizures import (
    PRODUCER,
    TITLE,
    VINTAGE_2019,
    _PUBLISHER_STATE_REMAP,
    _load_state_index,
    ingest,
    parse_eci_date,
    parse_number_or_none,
    resolve_state_slug,
    strip_ut_suffix,
)
from yen_gov.canonical.citation import derive_source_id


REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_CODES_CSV = REPO_ROOT / "datasets" / "data" / "entities" / "state_codes.csv"
EPHEMERAL_2019 = REPO_ROOT / "datasets" / "ephemeral" / "2019_eci_seizures.csv"


# --------------------------------------------------------------------------- #
# Pure helpers (always-on; no fixtures needed).
# --------------------------------------------------------------------------- #


class TestStripUtSuffix:
    """Both space-before-paren and no-space variants collapse to canonical."""

    def test_strips_with_space(self):
        assert strip_ut_suffix("Chandigarh (UT)") == "Chandigarh"

    def test_strips_without_space(self):
        # Publisher typo variant carried in the 2019 press note.
        assert strip_ut_suffix("Andaman & Nicobar Islands(UT)") == (
            "Andaman & Nicobar Islands"
        )

    def test_no_suffix_unchanged(self):
        assert strip_ut_suffix("Tamil Nadu") == "Tamil Nadu"

    def test_strips_surrounding_whitespace(self):
        assert strip_ut_suffix("  Goa  ") == "Goa"


class TestParseEciDate:
    """ECI ``DD-MMM-YY`` format must pivot 2-digit years on 2050 boundary."""

    def test_2019_window(self):
        assert parse_eci_date("29-Mar-19") == "2019-03-29"
        assert parse_eci_date("07-Apr-19") == "2019-04-07"

    def test_pivots_below_50_to_20xx(self):
        # 2024 election future-proof - check the pivot lands in the right century.
        assert parse_eci_date("01-Jan-24") == "2024-01-01"
        assert parse_eci_date("31-Dec-49") == "2049-12-31"

    def test_pivots_50_and_above_to_19xx(self):
        # 1985 historical fixture - parser supports earlier MCC if ever ingested.
        assert parse_eci_date("01-Jan-85") == "1985-01-01"

    def test_rejects_empty(self):
        with pytest.raises(ValueError):
            parse_eci_date("")

    def test_rejects_malformed(self):
        with pytest.raises(ValueError):
            parse_eci_date("2019-03-29")  # ISO not accepted by publisher format


class TestParseNumberOrNone:
    """Empty cell must map to None (publisher silence != 0)."""

    def test_empty_returns_none(self):
        assert parse_number_or_none("") is None

    def test_whitespace_returns_none(self):
        assert parse_number_or_none("   ") is None

    def test_zero_preserved(self):
        # Publisher's explicit 0 is a measurement, not silence.
        assert parse_number_or_none("0") == 0.0
        assert parse_number_or_none("0.00") == 0.0

    def test_decimal(self):
        assert parse_number_or_none("1.42") == 1.42


# --------------------------------------------------------------------------- #
# State-slug resolver (depends on state_codes.csv presence).
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def state_index():
    assert STATE_CODES_CSV.exists(), f"missing fixture: {STATE_CODES_CSV}"
    return _load_state_index(STATE_CODES_CSV)


class TestResolveStateSlug:
    """All 36 publisher state-name variants from the 2019 press note resolve.

    Uses the actual state_codes.csv (not a fixture) so the contract is
    end-to-end: any future state_codes.csv change that breaks resolution
    surfaces here, NOT silently at ingest time.
    """

    def test_canonical_lgd_name_match(self, state_index):
        # Bihar matches lgd_name exactly.
        assert resolve_state_slug("Bihar", index=state_index) == "bihar"

    def test_ut_suffix_stripped_and_resolved(self, state_index):
        # Chandigarh (UT) - typical UT pattern.
        assert resolve_state_slug("Chandigarh (UT)", index=state_index) == (
            "chandigarh"
        )

    def test_andaman_uses_remap_not_alias(self, state_index):
        # state_codes lgd_name is "Andaman And Nicobar Islands" but slug
        # is "andaman-and-nicobar" (no "-islands" suffix - operator-vs-runtime
        # divergence). The publisher's "Andaman & Nicobar Islands (UT)"
        # uses "&" which does not match the lgd_name "And" form. Resolved
        # via the _PUBLISHER_STATE_REMAP override.
        assert resolve_state_slug(
            "Andaman & Nicobar Islands (UT)", index=state_index
        ) == "andaman-and-nicobar"
        assert resolve_state_slug(
            "Andaman & Nicobar Islands(UT)", index=state_index  # typo variant
        ) == "andaman-and-nicobar"

    def test_nct_of_delhi_remapped(self, state_index):
        # state_codes lgd_name is just "Delhi" - publisher's "NCT of Delhi"
        # routes via remap.
        assert resolve_state_slug("NCT of Delhi", index=state_index) == "delhi"

    def test_pre_merger_uts_keep_historical_slugs(self, state_index):
        # 2019 was BEFORE the Jan-2020 merger of Dadra and Nagar Haveli +
        # Daman and Diu. The publisher carries them as separate rows; we
        # preserve the distinction by mapping to historical slugs (NOT
        # the post-merger "dadra-and-nagar-haveli-and-daman-and-diu"). The
        # historical slugs intentionally have no entry in modern
        # state_codes.csv.
        assert resolve_state_slug(
            "Dadra and Nagar Haveli (UT)", index=state_index
        ) == "dadra-and-nagar-haveli"
        assert resolve_state_slug(
            "Daman and Diu (UT)", index=state_index
        ) == "daman-and-diu"

    def test_jammu_and_kashmir_lowercase_and(self, state_index):
        # Publisher uses "and" (lowercase); state_codes lgd_name uses
        # "And" (capital). UPPER-comparison resolves cleanly.
        assert resolve_state_slug("Jammu and Kashmir", index=state_index) == (
            "jammu-and-kashmir"
        )

    def test_unresolved_returns_none(self, state_index):
        # Defensive: a publisher row with a vocabulary the operator has not
        # yet curated returns None and the ingest call raises (caller
        # surfaces the gap rather than silently dropping rows).
        assert resolve_state_slug("Atlantis", index=state_index) is None

    def test_empty_returns_none(self, state_index):
        assert resolve_state_slug("", index=state_index) is None
        assert resolve_state_slug("   ", index=state_index) is None


class TestPublisherRemapClosed:
    """The remap dict must stay minimal and explicit (no broad heuristics)."""

    def test_exactly_four_overrides(self):
        # Updating this number requires explicit operator review per the
        # plan-doc D-decisions (no silent vocabulary expansion).
        assert len(_PUBLISHER_STATE_REMAP) == 4

    def test_keys_are_upper_post_strip(self):
        for key in _PUBLISHER_STATE_REMAP.keys():
            assert key == key.upper(), f"remap key not UPPER: {key!r}"
            assert "(UT)" not in key, (
                f"remap key carries (UT) suffix; strip_ut_suffix runs first: "
                f"{key!r}"
            )


# --------------------------------------------------------------------------- #
# End-to-end ingest oracle (writes to tmp_path; uses real fixtures).
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(
    not EPHEMERAL_2019.exists(),
    reason="ephemeral 2019_eci_seizures.csv absent; integration oracle skipped",
)
class TestIngestEndToEnd:
    """End-to-end oracle: 36 states x 10 dates = 360 rows, no duplicates."""

    def test_emits_canonical_csv_with_bijection(self, tmp_path):
        # Copy state_codes.csv into the tmp repo root so the adapter's
        # default resolver finds it.
        tmp_state_codes = (
            tmp_path / "datasets" / "data" / "entities" / "state_codes.csv"
        )
        tmp_state_codes.parent.mkdir(parents=True, exist_ok=True)
        tmp_state_codes.write_bytes(STATE_CODES_CSV.read_bytes())

        result = ingest(
            input_csv=EPHEMERAL_2019,
            repo_root=tmp_path,
            election_year=2019,
        )

        assert result.row_count == 360
        assert result.unique_state_slugs == 36
        assert result.unique_dates == 10

        # File-on-disk check: header + 360 rows = 361 lines.
        text = result.output_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        assert len(lines) == 361
        assert lines[0].startswith("state_slug,date,cash_inr_crore,")

        # Re-read via csv.DictReader and verify bijection.
        with result.output_path.open(encoding="utf-8", newline="") as fh:
            out_rows = list(csv.DictReader(fh))
        keys = [(r["state_slug"], r["date"]) for r in out_rows]
        assert len(set(keys)) == 360, "(state_slug, date) is not a bijection"

        # source_id is the deterministic derive_source_id() value.
        expected_src = derive_source_id(PRODUCER, TITLE, VINTAGE_2019)
        assert {r["source_id"] for r in out_rows} == {expected_src}

        # Empty publisher cells stayed empty (not coerced to 0).
        # West Bengal 2019-03-29 has the publisher's blank
        # liquor_qty_lakh_litres - verify it round-trips as empty.
        wb_row = next(
            r for r in out_rows
            if r["state_slug"] == "west-bengal" and r["date"] == "2019-03-29"
        )
        # At least one of the documented blank columns must be empty
        # (publisher silence preserved as NULL, never 0).
        blank_cols = [
            "liquor_qty_lakh_litres",
            "drugs_qty_kg",
            "precious_metals_qty_kg",
        ]
        assert any(wb_row[c] == "" for c in blank_cols), (
            "publisher silence must round-trip as empty string, not 0; "
            f"actual values: {[(c, wb_row[c]) for c in blank_cols]}"
        )

        # Pre-2020-merger UTs both present with historical slugs.
        slugs = {r["state_slug"] for r in out_rows}
        assert "dadra-and-nagar-haveli" in slugs
        assert "daman-and-diu" in slugs
        assert "dadra-and-nagar-haveli-and-daman-and-diu" not in slugs
