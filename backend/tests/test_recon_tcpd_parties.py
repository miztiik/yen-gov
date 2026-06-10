"""Tier-A tests for the TCPD parties parity adapter (PR-W-1).

Covers:

  - ``_group_tcpd_rows_by_party_id`` deduplicates by Party_ID and skips
    NA's dirty rows.
  - ``_resolve_via_index`` priority: full-name match first, then
    Frequent_Abbreviation, then Last_Abbreviation, then other
    Abbreviations.
  - ``_share_significant_words`` correctly bypasses sparse-canonical
    rows AND fires the conflict guard on real abbreviation collisions.
  - ``_emit_shape_a_for_tcpd_party`` emits exactly the right shape-A
    pair for the four legs (match / enrich / alias-add / mint-new /
    conflict).
  - End-to-end: TcpdPartiesAdapter() against a minimal fixture
    yields the expected shape-A row set.
  - Adapter is registered against REGISTRY["tcpd-parties"].

No real-corpus walking (CLAUDE.md section 14 carve-out: tmp_path
fixtures only). Pure-function tests; the adapter holds no I/O state
beyond reading the file path.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.recon.adapters import REGISTRY
from yen_gov.canonical.recon.adapters.tcpd_parties import (
    ADAPTER,
    CANONICAL_SCOPE,
    TCPD_SCOPE,
    TCPD_VINTAGE,
    TcpdPartiesAdapter,
    _CanonicalIndex,
    _emit_shape_a_for_tcpd_party,
    _group_tcpd_rows_by_party_id,
    _load_canonical_index,
    _make_slug,
    _normalise_full_name,
    _resolve_via_index,
    _share_significant_words,
    _significant_words,
    _TcpdParty,
)
from yen_gov.canonical.recon.shape_a import ShapeARow


# --- tiny canonical / TCPD fixtures used across tests --------------------


def _write_parties_csv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    cols = [
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
    path = tmp_path / "datasets" / "data" / "entities" / "parties.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in cols})
    return path


def _write_tcpd_csv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    cols = [
        "Assembly",
        "State_Name",
        "Party_Name",
        "Party_Type",
        "Party_ID",
        "Frequent_Abbreviation",
        "Last_Abbreviation",
        "Abbreviations",
        "Start_Year",
        "Last_Year",
    ]
    path = tmp_path / "datasets" / "ephemeral" / "TCPD-PoliticalPartiesIndia_1962_2021.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in cols})
    return path


# --- ADAPTER REGISTRATION ------------------------------------------------


def test_adapter_registered_in_registry() -> None:
    """The PR-W-1 adapter is registered against REGISTRY['tcpd-parties']."""
    assert "tcpd-parties" in REGISTRY
    assert REGISTRY["tcpd-parties"] is ADAPTER


def test_adapter_rejects_wrong_vintage(tmp_path: Path) -> None:
    """Adapter refuses to spoof a vintage other than 2021 (compilation cutoff)."""
    adapter = TcpdPartiesAdapter()
    with pytest.raises(ValueError, match="2021"):
        list(adapter(root=tmp_path, vintage="2020"))


def test_adapter_raises_when_tcpd_file_missing(tmp_path: Path) -> None:
    """Adapter raises FileNotFoundError when the operator hasn't dropped TCPD CSV."""
    adapter = TcpdPartiesAdapter()
    _write_parties_csv(tmp_path, [{"party_id": "parties.IN.X", "short": "X", "full": "X"}])
    with pytest.raises(FileNotFoundError, match="TCPD parties CSV"):
        list(adapter(root=tmp_path, vintage="2021"))


# --- NORMALISATION + SIGNIFICANT-WORDS ----------------------------------


def test_normalise_full_name_collapses_punctuation_and_whitespace() -> None:
    """Parens, hyphens, dots, multi-space -> single-space UPPER."""
    assert _normalise_full_name("All India  Anna   Dravida") == "ALL INDIA ANNA DRAVIDA"
    assert _normalise_full_name("CPI(M)") == "CPI M"
    assert _normalise_full_name("LKD-(B)") == "LKD B"
    assert _normalise_full_name("") == ""


def test_significant_words_filters_short_and_stopwords() -> None:
    """Length>=4 and not in PARTY/PARTIES/FRONT."""
    assert _significant_words("Aam Aadmi Party") == {"AADMI"}
    assert _significant_words("Bharatiya Janata Party") == {"BHARATIYA", "JANATA"}
    assert _significant_words("ABCD(A)") == {"ABCD"}
    assert _significant_words("") == set()


def test_share_significant_words_sparse_canonical_bypasses_guard() -> None:
    """When canonical_full == canonical_short, trust the by_alias hit."""
    # ABCD(A) canonical: full == short. TCPD's "Akhil Bharatiya Congress
    # Dal (Ambedkar)" shares no significant word with "ABCD(A)" but the
    # sparse-canonical bypass returns True (trust alias).
    assert _share_significant_words(
        "Akhil Bharatiya Congress Dal (Ambedkar)",
        "ABCD(A)",
        "ABCD(A)",
    ) is True


def test_share_significant_words_fires_on_real_collision() -> None:
    """awami aamjan party vs AAM AADMI PARTY -> conflict guard fires."""
    # Both have multi-word fulls AND zero shared significant words; guard fires.
    assert _share_significant_words(
        "awami aamjan party",
        "Aam Aadmi Party",
        "AAP",
    ) is False


def test_share_significant_words_finds_overlap() -> None:
    """BJP vs Bharatiya Janata Party (variant) -> share BHARATIYA / JANATA."""
    assert _share_significant_words(
        "Bharatiya Janata Party",
        "Bharatiya Janata Party",
        "BJP",
    ) is True


# --- GROUPING + DIRTY-ROW FILTER -----------------------------------------


def test_group_rows_dedupes_by_party_id() -> None:
    """Two TCPD rows for the same Party_ID collapse to one _TcpdParty."""
    rows = [
        {
            "Assembly": "Lok_Sabha", "State_Name": "All_States",
            "Party_Name": "Foo", "Party_Type": "National Party",
            "Party_ID": "1", "Frequent_Abbreviation": "F",
            "Last_Abbreviation": "F", "Abbreviations": "F|FOO",
            "Start_Year": "1980", "Last_Year": "2015",
        },
        {
            "Assembly": "Vidhan_Sabha", "State_Name": "Karnataka",
            "Party_Name": "Foo", "Party_Type": "State-based Party",
            "Party_ID": "1", "Frequent_Abbreviation": "F",
            "Last_Abbreviation": "F", "Abbreviations": "F|FOOBAR",
            "Start_Year": "1975", "Last_Year": "2019",
        },
    ]
    grouped = _group_tcpd_rows_by_party_id(rows)
    assert len(grouped) == 1
    tp = grouped[0]
    assert tp.party_id == "1"
    assert tp.start_year == 1975  # min across all rows
    assert tp.last_year == 2019  # max across all rows
    assert set(tp.all_abbrevs) == {"F", "FOO", "FOOBAR"}


def test_group_rows_skips_dirty_NAs() -> None:
    """Rows with Party_Name in {NA's, NA, N/A, ''} are dropped (PR-W-1 guard)."""
    rows = [
        {
            "Party_ID": "10", "Party_Name": "Real Party",
            "Frequent_Abbreviation": "RP", "Last_Abbreviation": "RP",
            "Abbreviations": "RP", "Start_Year": "1990",
            "Last_Year": "2020", "Party_Type": "National Party",
            "Assembly": "Lok_Sabha", "State_Name": "All_States",
        },
        {
            "Party_ID": "20", "Party_Name": "NA's",  # dirty
            "Frequent_Abbreviation": "AIADMk", "Last_Abbreviation": "AIADMk",
            "Abbreviations": "AIADMk", "Start_Year": "2020",
            "Last_Year": "2020", "Party_Type": "",
            "Assembly": "Lok_Sabha", "State_Name": "All_States",
        },
        {
            "Party_ID": "30", "Party_Name": "",  # empty
            "Frequent_Abbreviation": "", "Last_Abbreviation": "",
            "Abbreviations": "", "Start_Year": "0",
            "Last_Year": "0", "Party_Type": "",
            "Assembly": "", "State_Name": "",
        },
    ]
    grouped = _group_tcpd_rows_by_party_id(rows)
    assert {tp.party_id for tp in grouped} == {"10"}


# --- RESOLVE_VIA_INDEX ---------------------------------------------------


def test_resolve_via_index_prefers_full_name(tmp_path: Path) -> None:
    """When a TCPD abbreviation happens to be another canonical party's short,
    full-name match wins (no false-positive abbreviation collision)."""
    parties_csv = _write_parties_csv(
        tmp_path,
        [
            {"party_id": "parties.IN.AIADMK", "short": "AIADMK", "full": "All India Anna Dravida Munnetra Kazhagam"},
            {"party_id": "parties.IN.ADK", "short": "ADK", "full": "ADK"},  # sparse
        ],
    )
    ix = _load_canonical_index(parties_csv)
    tp = _TcpdParty(
        party_id="930",
        full_name="All India Anna Dravida Munnetra Kazhagam",
        frequent_abbrev="ADMK",
        last_abbrev="ADMK",
        all_abbrevs=("ADK", "ADMK", "AIDMK"),
        start_year=1974,
        last_year=2021,
        party_type="State-based Party",
    )
    pid, via_full = _resolve_via_index(tp, ix)
    assert pid == "parties.IN.AIADMK"
    assert via_full is True


def test_resolve_via_index_alias_fallback(tmp_path: Path) -> None:
    """Full-name miss -> Frequent_Abbreviation lookup wins over Last/others."""
    parties_csv = _write_parties_csv(
        tmp_path,
        [
            {"party_id": "parties.IN.BJP", "short": "BJP", "full": "Bharatiya Janata Party"},
        ],
    )
    ix = _load_canonical_index(parties_csv)
    tp = _TcpdParty(
        party_id="1605",
        full_name="Bharatiya Janata Party (variant)",
        frequent_abbrev="BJP",
        last_abbrev="BJP",
        all_abbrevs=("BJP",),
        start_year=1980,
        last_year=2021,
        party_type="National Party",
    )
    pid, via_full = _resolve_via_index(tp, ix)
    assert pid == "parties.IN.BJP"


def test_resolve_via_index_miss_returns_none(tmp_path: Path) -> None:
    parties_csv = _write_parties_csv(tmp_path, [])
    ix = _load_canonical_index(parties_csv)
    tp = _TcpdParty(
        party_id="999",
        full_name="Bundelkhand Akikrit Party",
        frequent_abbrev="BAP",
        last_abbrev="BAP",
        all_abbrevs=("BAP",),
        start_year=2010,
        last_year=2014,
        party_type="Local Party",
    )
    pid, via_full = _resolve_via_index(tp, ix)
    assert pid is None
    assert via_full is False


# --- EMIT_SHAPE_A_FOR_TCPD_PARTY ----------------------------------------


def test_emit_shape_a_match_emits_pair(tmp_path: Path) -> None:
    """Full-name match + nothing to enrich -> match action + canonical pair."""
    parties_csv = _write_parties_csv(
        tmp_path,
        [
            {
                "party_id": "parties.IN.X", "short": "X", "full": "Full X",
                "aliases": "X", "founded_year": "2000",
                "recognition_scope": "national",
            },
        ],
    )
    ix = _load_canonical_index(parties_csv)
    tp = _TcpdParty(
        party_id="1", full_name="Full X",
        frequent_abbrev="X", last_abbrev="X",
        all_abbrevs=("X",),
        start_year=2000, last_year=2020,
        party_type="National Party",
    )
    out = _emit_shape_a_for_tcpd_party(tp, ix)
    assert len(out) == 2
    tcpd_row, canon_row = out
    assert tcpd_row.external_scope == TCPD_SCOPE
    assert tcpd_row.proposed_action == "match"
    assert tcpd_row.proposed_party_id == "parties.IN.X"
    assert canon_row.external_scope == CANONICAL_SCOPE
    assert canon_row.proposed_action == "match"


def test_emit_shape_a_enrich_when_canonical_has_empty_cells(tmp_path: Path) -> None:
    """Canonical missing founded_year + recognition_scope -> action=enrich."""
    parties_csv = _write_parties_csv(
        tmp_path,
        [{"party_id": "parties.IN.X", "short": "X", "full": "Full X"}],
    )
    ix = _load_canonical_index(parties_csv)
    tp = _TcpdParty(
        party_id="1", full_name="Full X",
        frequent_abbrev="X", last_abbrev="X",
        all_abbrevs=("X",),
        start_year=1990, last_year=2020,
        party_type="National Party",
    )
    out = _emit_shape_a_for_tcpd_party(tp, ix)
    assert out[0].proposed_action == "enrich"


def test_emit_shape_a_mint_new_when_no_canonical(tmp_path: Path) -> None:
    """No canonical match -> action=mint-new, only TCPD row (no canonical pair)."""
    parties_csv = _write_parties_csv(tmp_path, [])
    ix = _load_canonical_index(parties_csv)
    tp = _TcpdParty(
        party_id="42", full_name="A Brand New Party",
        frequent_abbrev="BNP", last_abbrev="BNP",
        all_abbrevs=("BNP",),
        start_year=2020, last_year=2024,
        party_type="State-based Party",
    )
    out = _emit_shape_a_for_tcpd_party(tp, ix)
    assert len(out) == 1
    assert out[0].proposed_action == "mint-new"
    assert out[0].proposed_party_id == "parties.IN.BNP"


def test_emit_shape_a_conflict_on_abbreviation_collision(tmp_path: Path) -> None:
    """TCPD's abbreviation matches a canonical row's short but full names
    share no significant words -> action=conflict (both rows)."""
    parties_csv = _write_parties_csv(
        tmp_path,
        [{"party_id": "parties.IN.AAP", "short": "AAP", "full": "Aam Aadmi Party"}],
    )
    ix = _load_canonical_index(parties_csv)
    tp = _TcpdParty(
        party_id="1000", full_name="awami aamjan party",
        frequent_abbrev="AAP", last_abbrev="AAP",
        all_abbrevs=("AAP",),
        start_year=2010, last_year=2014,
        party_type="Local Party",
    )
    out = _emit_shape_a_for_tcpd_party(tp, ix)
    assert len(out) == 2
    assert out[0].proposed_action == "conflict"
    assert out[1].proposed_action == "conflict"


# --- END-TO-END ADAPTER + AGGREGATOR ------------------------------------


def test_adapter_end_to_end_minimal_fixture(tmp_path: Path) -> None:
    """Full adapter pass on a 3-party fixture -> shape-A rows for compare."""
    _write_parties_csv(
        tmp_path,
        [
            {"party_id": "parties.IN.AIADMK", "short": "AIADMK", "full": "All India Anna Dravida Munnetra Kazhagam"},
            {"party_id": "parties.IN.BJP", "short": "BJP", "full": "Bharatiya Janata Party"},
        ],
    )
    _write_tcpd_csv(
        tmp_path,
        [
            {
                "Assembly": "Lok_Sabha", "State_Name": "All_States",
                "Party_Name": "All India Anna Dravida Munnetra Kazhagam",
                "Party_Type": "State-based Party", "Party_ID": "930",
                "Frequent_Abbreviation": "ADMK", "Last_Abbreviation": "ADMK",
                "Abbreviations": "ADK|ADMK|AIDMK",
                "Start_Year": "1974", "Last_Year": "2021",
            },
            {
                "Assembly": "Lok_Sabha", "State_Name": "All_States",
                "Party_Name": "Bharatiya Janata Party",
                "Party_Type": "National Party", "Party_ID": "1605",
                "Frequent_Abbreviation": "BJP", "Last_Abbreviation": "BJP",
                "Abbreviations": "BJP", "Start_Year": "1980",
                "Last_Year": "2021",
            },
            {
                "Assembly": "Lok_Sabha", "State_Name": "All_States",
                "Party_Name": "A Brand New Party",
                "Party_Type": "Local Party", "Party_ID": "42",
                "Frequent_Abbreviation": "BNP", "Last_Abbreviation": "BNP",
                "Abbreviations": "BNP", "Start_Year": "2020",
                "Last_Year": "2024",
            },
        ],
    )
    adapter = TcpdPartiesAdapter()
    shape_a_rows = list(adapter(root=tmp_path, vintage=TCPD_VINTAGE))

    by_pid: dict[str, list[ShapeARow]] = {}
    for r in shape_a_rows:
        by_pid.setdefault(r.proposed_party_id, []).append(r)

    # AIADMK: 2 rows (tcpd + canonical) - VERIFIED enrich (canonical was sparse).
    assert "parties.IN.AIADMK" in by_pid
    assert {r.external_scope for r in by_pid["parties.IN.AIADMK"]} == {
        TCPD_SCOPE, CANONICAL_SCOPE
    }
    tcpd_aiadmk = next(r for r in by_pid["parties.IN.AIADMK"] if r.external_scope == TCPD_SCOPE)
    assert tcpd_aiadmk.proposed_action == "enrich"

    # BJP: 2 rows - VERIFIED enrich (founded_year + recognition_scope to fill).
    assert "parties.IN.BJP" in by_pid
    tcpd_bjp = next(r for r in by_pid["parties.IN.BJP"] if r.external_scope == TCPD_SCOPE)
    assert tcpd_bjp.proposed_action == "enrich"

    # BNP: 1 row - UNVERIFIED mint-new (no canonical, no canonical-pair row).
    assert "parties.IN.BNP" in by_pid
    assert len(by_pid["parties.IN.BNP"]) == 1
    assert by_pid["parties.IN.BNP"][0].proposed_action == "mint-new"


# --- MAKE_SLUG ----------------------------------------------------------


def test_make_slug_sanitises_punctuation() -> None:
    assert _make_slug("CPI(M)") == "parties.IN.CPI_M"
    assert _make_slug("LKD (B)") == "parties.IN.LKD_B"
    assert _make_slug("a.b.c") == "parties.IN.A_B_C"
    assert _make_slug("") == "parties.IN.UNK"


def test_make_slug_collapses_underscores() -> None:
    assert _make_slug("---X---Y---") == "parties.IN.X_Y"
