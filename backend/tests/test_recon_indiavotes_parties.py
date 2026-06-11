"""Tier-A tests for the IndiaVotes parties parity adapter (UNK-enrichment).

Covers:

  - ``_read_indiavotes_snapshot`` reads the operator-committed snapshot
    CSV and tolerates empty cells per column, skips iv_type==independent
    and rows missing abbrev/full.
  - ``recognition_from_iv_type`` maps IV's type-column verbatim to the
    parties.csv recognition_scope enum; unknown tokens return "".
  - ``dissolved_year_from_active_to`` only sets dissolved_year when the
    upper bound is STRICTLY LESS than the data-current-year sentinel
    (no false retirements for currently-active parties).
  - ``_resolve_via_index`` dispatch order: normalised full-name match
    wins, then abbreviation lookup via canonical aliases.
  - ``_share_significant_words`` correctly bypasses sparse-canonical
    rows AND fires the conflict guard on real abbreviation collisions.
  - ``_emit_shape_a_for_iv_record`` dispatches on the four legs:
    no-canonical -> mint-new; canonical-by-full -> match or alias-add;
    canonical-by-alias-without-word-overlap -> conflict.
  - End-to-end: ``IndiaVotesPartiesAdapter()`` against a minimal fixture
    yields the expected shape-A row set with deterministic ordering.
  - Adapter is registered against ``REGISTRY["indiavotes-parties"]`` and
    rejects vintages other than the snapshot pin per ADR-0042.
  - ``_make_slug`` sanitises publisher abbreviations to the
    ``parties.IN.<UPPER>`` regex.

No real-corpus walking (CLAUDE.md section 14 carve-out: tmp_path
fixtures only). Pure-function tests; the adapter holds no I/O state
beyond reading the snapshot path.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.recon.adapters import REGISTRY
from yen_gov.canonical.recon.adapters.indiavotes_parties import (
    ADAPTER,
    CANONICAL_SCOPE,
    DEFAULT_INDIAVOTES_CSV,
    INDIAVOTES_SCOPE,
    INDIAVOTES_VINTAGE,
    IndiaVotesPartiesAdapter,
    _emit_shape_a_for_iv_record,
    _has_new_aliases,
    _IvRecord,
    _load_canonical_index,
    _make_slug,
    _normalise_full_name,
    _read_indiavotes_snapshot,
    _resolve_via_index,
    _share_significant_words,
    _significant_words,
    dissolved_year_from_active_to,
    recognition_from_iv_type,
)
from yen_gov.canonical.recon.shape_a import ShapeARow


# --- tiny canonical / IV fixtures used across tests ---------------------


_PARTIES_COLS: tuple[str, ...] = (
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
)


_IV_COLS: tuple[str, ...] = (
    "party_abbreviation",
    "party_full_name",
    "slug",
    "iv_type",
    "ls_seats_won",
    "vs_seats_won",
    "contested",
    "active_period_from",
    "active_period_to",
    "iv_url",
    "source_lane",
    "notes",
)


def _write_parties_csv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    path = tmp_path / "datasets" / "data" / "entities" / "parties.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_PARTIES_COLS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in _PARTIES_COLS})
    return path


def _write_iv_csv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    path = tmp_path / DEFAULT_INDIAVOTES_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_IV_COLS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in _IV_COLS})
    return path


# --- ADAPTER REGISTRATION -----------------------------------------------


def test_adapter_registered_in_registry() -> None:
    """The IndiaVotes adapter is registered against REGISTRY['indiavotes-parties']."""
    assert "indiavotes-parties" in REGISTRY
    assert REGISTRY["indiavotes-parties"] is ADAPTER


def test_adapter_rejects_wrong_vintage(tmp_path: Path) -> None:
    """Adapter refuses any vintage other than the snapshot pin (ADR-0042)."""
    adapter = IndiaVotesPartiesAdapter()
    with pytest.raises(ValueError, match=INDIAVOTES_VINTAGE):
        list(adapter(root=tmp_path, vintage="2025-01"))


def test_adapter_raises_when_snapshot_missing(tmp_path: Path) -> None:
    """Adapter raises FileNotFoundError when the snapshot CSV is absent."""
    adapter = IndiaVotesPartiesAdapter()
    _write_parties_csv(tmp_path, [{"party_id": "parties.IN.X", "short": "X", "full": "X"}])
    with pytest.raises(FileNotFoundError, match="IndiaVotes parties snapshot"):
        list(adapter(root=tmp_path, vintage=INDIAVOTES_VINTAGE))


# --- NORMALISATION + SIGNIFICANT WORDS ----------------------------------


def test_normalise_full_name_collapses_punctuation_and_whitespace() -> None:
    """Parens, hyphens, dots, multi-space -> single-space UPPER."""
    assert _normalise_full_name("All India  Anna   Dravida") == "ALL INDIA ANNA DRAVIDA"
    assert _normalise_full_name("CPI(M)") == "CPI M"
    assert _normalise_full_name("LKD-(B)") == "LKD B"
    assert _normalise_full_name("") == ""


def test_significant_words_filters_short_and_stopwords() -> None:
    """Length>=4 and not in PARTY / PARTIES / FRONT."""
    assert _significant_words("Aam Aadmi Party") == {"AADMI"}
    assert _significant_words("Bharatiya Janata Party") == {"BHARATIYA", "JANATA"}
    assert _significant_words("Front (variant)") == {"VARIANT"}
    assert _significant_words("") == set()


def test_share_significant_words_sparse_canonical_bypasses_guard() -> None:
    """When canonical_full == canonical_short, trust the by_alias hit."""
    assert _share_significant_words(
        "Akhil Bharatiya Congress Dal (Ambedkar)",
        "ABCD(A)",
        "ABCD(A)",
    ) is True


def test_share_significant_words_fires_on_real_collision() -> None:
    """Two distinct multi-word fulls with no shared content word -> conflict."""
    assert _share_significant_words(
        "awami aamjan party",
        "Aam Aadmi Party",
        "AAP",
    ) is False


def test_share_significant_words_finds_overlap() -> None:
    """BJP variants share BHARATIYA / JANATA."""
    assert _share_significant_words(
        "Bharatiya Janata Party",
        "Bharatiya Janata Party",
        "BJP",
    ) is True


# --- SLUG BUILDER --------------------------------------------------------


def test_make_slug_sanitises_punctuation() -> None:
    """Punctuation collapses to underscore; output matches parties.IN regex."""
    assert _make_slug("CPI(M)") == "parties.IN.CPI_M"
    assert _make_slug("LKD (B)") == "parties.IN.LKD_B"
    assert _make_slug("a.b.c") == "parties.IN.A_B_C"
    assert _make_slug("") == "parties.IN.UNK"


def test_make_slug_collapses_underscores() -> None:
    """Multi-underscore runs collapse to single."""
    assert _make_slug("---X---Y---") == "parties.IN.X_Y"


# --- RECOGNITION + DISSOLVED-YEAR MAPS ----------------------------------


def test_recognition_from_iv_type_known_values() -> None:
    """IV type tokens map to parties.csv recognition_scope enum."""
    assert recognition_from_iv_type("national") == "national"
    assert recognition_from_iv_type("state") == "state"
    assert recognition_from_iv_type("state-recognised") == "state"
    assert recognition_from_iv_type("unrecognised") == "unrecognised_registered"
    assert recognition_from_iv_type("unrecognized") == "unrecognised_registered"
    assert recognition_from_iv_type("registered_unrecognised") == "unrecognised_registered"
    assert recognition_from_iv_type("STATE") == "state"  # case-insensitive


def test_recognition_from_iv_type_unknown_returns_empty() -> None:
    """Unknown tokens return empty -> curator leaves cell empty for ECI fill."""
    assert recognition_from_iv_type("") == ""
    assert recognition_from_iv_type("something-new") == ""
    # 'independent' is filtered upstream (by _read_indiavotes_snapshot);
    # the mapping returns empty for it but rows of that type never reach
    # the curator's mint path.
    assert recognition_from_iv_type("independent") == ""


def test_dissolved_year_only_set_when_strictly_less_than_data_current_year() -> None:
    """IV's '2026' sentinel does NOT trigger dissolved; '1980' does."""
    assert dissolved_year_from_active_to("2026") == ""
    assert dissolved_year_from_active_to("2025") == "2025"
    assert dissolved_year_from_active_to("1980") == "1980"
    assert dissolved_year_from_active_to("") == ""
    assert dissolved_year_from_active_to("not-a-year") == ""


# --- SNAPSHOT READER -----------------------------------------------------


def test_read_indiavotes_snapshot_tolerates_empty_cells(tmp_path: Path) -> None:
    """Snapshot rows with empty optional cells round-trip safely."""
    iv_csv = _write_iv_csv(
        tmp_path,
        [
            {
                "party_abbreviation": "BJP",
                "party_full_name": "Bharatiya Janata Party",
                "iv_type": "national",
                "active_period_from": "1980",
                "active_period_to": "2026",
            },
            {
                "party_abbreviation": "X",
                "party_full_name": "Some Other Party",
                # all optional cells empty -> probe-only origin
            },
        ],
    )
    out = _read_indiavotes_snapshot(iv_csv)
    assert len(out) == 2
    bjp = next(r for r in out if r.abbrev == "BJP")
    assert bjp.full == "Bharatiya Janata Party"
    assert bjp.iv_type == "national"
    assert bjp.active_from == "1980"
    assert bjp.active_to == "2026"


def test_read_indiavotes_snapshot_skips_independent_rows(tmp_path: Path) -> None:
    """iv_type=independent rows are filtered (canonical IND sentinel covers it)."""
    iv_csv = _write_iv_csv(
        tmp_path,
        [
            {"party_abbreviation": "IND", "party_full_name": "Independent", "iv_type": "independent"},
            {"party_abbreviation": "BJP", "party_full_name": "Bharatiya Janata Party", "iv_type": "national"},
        ],
    )
    out = _read_indiavotes_snapshot(iv_csv)
    assert len(out) == 1
    assert out[0].abbrev == "BJP"


def test_read_indiavotes_snapshot_skips_rows_missing_abbrev_or_full(tmp_path: Path) -> None:
    """Defensive: skip degenerate rows the scraper might emit."""
    iv_csv = _write_iv_csv(
        tmp_path,
        [
            {"party_abbreviation": "", "party_full_name": "Missing Abbrev"},
            {"party_abbreviation": "X", "party_full_name": ""},
            {"party_abbreviation": "Y", "party_full_name": "Yes Party"},
        ],
    )
    out = _read_indiavotes_snapshot(iv_csv)
    assert [r.abbrev for r in out] == ["Y"]


# --- RESOLVE_VIA_INDEX --------------------------------------------------


def test_resolve_via_index_prefers_full_name_over_alias(tmp_path: Path) -> None:
    """When IV's full uniquely matches canonical's full, that wins over alias."""
    parties_csv = _write_parties_csv(
        tmp_path,
        [
            {
                "party_id": "parties.IN.AIADMK",
                "short": "AIADMK",
                "full": "All India Anna Dravida Munnetra Kazhagam",
            },
            # Sparse-canonical row whose short collides: by_alias would hit
            # it, but by_full wins first.
            {"party_id": "parties.IN.ADK", "short": "ADK", "full": "ADK"},
        ],
    )
    ix = _load_canonical_index(parties_csv)
    rec = _IvRecord(
        abbrev="ADMK",  # would hit by_alias on parties.IN.ADK if no full
        full="All India Anna Dravida Munnetra Kazhagam",
        slug="adk",
        iv_type="state",
        iv_url="",
        active_from="",
        active_to="",
        source_lane="probe",
        notes="",
    )
    pid, via_full = _resolve_via_index(rec, ix)
    assert pid == "parties.IN.AIADMK"
    assert via_full is True


def test_resolve_via_index_falls_back_to_alias(tmp_path: Path) -> None:
    """When IV's full does NOT match any canonical full, alias lookup wins."""
    parties_csv = _write_parties_csv(
        tmp_path,
        [
            {"party_id": "parties.IN.BJP", "short": "BJP", "full": "Bharatiya Janata Party"},
        ],
    )
    ix = _load_canonical_index(parties_csv)
    rec = _IvRecord(
        abbrev="BJP",
        full="Bharatiya Janta Party",  # IV's spelling differs
        slug="bjp",
        iv_type="national",
        iv_url="",
        active_from="",
        active_to="",
        source_lane="listing",
        notes="",
    )
    pid, via_full = _resolve_via_index(rec, ix)
    assert pid == "parties.IN.BJP"
    assert via_full is False


def test_resolve_via_index_no_match_returns_none(tmp_path: Path) -> None:
    """When neither full nor alias hits, returns (None, False) for mint-new."""
    parties_csv = _write_parties_csv(tmp_path, [])
    ix = _load_canonical_index(parties_csv)
    rec = _IvRecord(
        abbrev="NEWPARTY",
        full="A Brand New Party",
        slug="newparty",
        iv_type="unrecognised",
        iv_url="",
        active_from="2025",
        active_to="2026",
        source_lane="probe",
        notes="",
    )
    pid, via_full = _resolve_via_index(rec, ix)
    assert pid is None
    assert via_full is False


# --- _has_new_aliases ----------------------------------------------------


def test_has_new_aliases_skips_canonical_short_match() -> None:
    """When IV abbrev equals canonical short, no alias-add needed."""
    canonical = {"party_id": "parties.IN.BJP", "short": "BJP", "aliases": ""}
    rec = _IvRecord(
        abbrev="bjp",  # case-insensitive comparison
        full="Bharatiya Janata Party",
        slug="bjp",
        iv_type="national",
        iv_url="",
        active_from="",
        active_to="",
        source_lane="listing",
        notes="",
    )
    assert _has_new_aliases(rec, canonical) is False


def test_has_new_aliases_skips_existing_alias() -> None:
    """When IV abbrev is already in aliases pipe-list, no alias-add."""
    canonical = {"party_id": "parties.IN.AIADMK", "short": "AIADMK", "aliases": "ADMK|AIDMK"}
    rec = _IvRecord(
        abbrev="ADMK",
        full="All India Anna Dravida Munnetra Kazhagam",
        slug="admk",
        iv_type="state",
        iv_url="",
        active_from="",
        active_to="",
        source_lane="listing",
        notes="",
    )
    assert _has_new_aliases(rec, canonical) is False


def test_has_new_aliases_returns_true_for_new_publisher_label() -> None:
    """When IV abbrev is novel, alias-add is signalled."""
    canonical = {"party_id": "parties.IN.AIADMK", "short": "AIADMK", "aliases": "ADMK"}
    rec = _IvRecord(
        abbrev="ANNADMK",
        full="All India Anna Dravida Munnetra Kazhagam",
        slug="annadmk",
        iv_type="state",
        iv_url="",
        active_from="",
        active_to="",
        source_lane="probe",
        notes="",
    )
    assert _has_new_aliases(rec, canonical) is True


# --- EMIT SHAPE-A: MINT-NEW LEG -----------------------------------------


def test_emit_shape_a_mint_new_when_no_canonical_match(tmp_path: Path) -> None:
    """No canonical -> single mint-new row only (UNVERIFIED leg)."""
    parties_csv = _write_parties_csv(tmp_path, [])
    ix = _load_canonical_index(parties_csv)
    rec = _IvRecord(
        abbrev="KJP",
        full="Karnataka Jantha Paksha",
        slug="kjp",
        iv_type="state",
        iv_url="https://www.indiavotes.com/parties/kjp/",
        active_from="2012",
        active_to="2025",
        source_lane="probe",
        notes="",
    )
    out = _emit_shape_a_for_iv_record(rec, ix)
    assert len(out) == 1
    row = out[0]
    assert row.proposed_action == "mint-new"
    assert row.proposed_party_id == "parties.IN.KJP"
    assert row.external_scope == INDIAVOTES_SCOPE
    assert row.external_vintage == INDIAVOTES_VINTAGE
    assert "iv_type=state" in (row.notes or "")
    assert "slug=kjp" in (row.notes or "")


# --- EMIT SHAPE-A: MATCH + ALIAS-ADD LEGS -------------------------------


def test_emit_shape_a_match_when_alias_already_present(tmp_path: Path) -> None:
    """IV abbrev already in canonical short -> match leg (dual emit)."""
    parties_csv = _write_parties_csv(
        tmp_path,
        [{"party_id": "parties.IN.BJP", "short": "BJP", "full": "Bharatiya Janata Party"}],
    )
    ix = _load_canonical_index(parties_csv)
    rec = _IvRecord(
        abbrev="BJP",
        full="Bharatiya Janata Party",
        slug="bjp",
        iv_type="national",
        iv_url="",
        active_from="1980",
        active_to="2026",
        source_lane="listing",
        notes="",
    )
    out = _emit_shape_a_for_iv_record(rec, ix)
    assert len(out) == 2
    actions = sorted(r.proposed_action for r in out)
    assert actions == ["match", "match"]
    scopes = sorted(r.external_scope for r in out)
    assert scopes == [INDIAVOTES_SCOPE, CANONICAL_SCOPE]


def test_emit_shape_a_alias_add_when_new_publisher_label(tmp_path: Path) -> None:
    """IV abbrev not in canonical aliases -> alias-add leg (dual emit)."""
    parties_csv = _write_parties_csv(
        tmp_path,
        [
            {
                "party_id": "parties.IN.AIADMK",
                "short": "AIADMK",
                "full": "All India Anna Dravida Munnetra Kazhagam",
                "aliases": "ADMK",
            },
        ],
    )
    ix = _load_canonical_index(parties_csv)
    rec = _IvRecord(
        abbrev="ANNADMK",
        full="All India Anna Dravida Munnetra Kazhagam",
        slug="annadmk",
        iv_type="state",
        iv_url="",
        active_from="",
        active_to="",
        source_lane="probe",
        notes="",
    )
    out = _emit_shape_a_for_iv_record(rec, ix)
    iv_row = next(r for r in out if r.external_scope == INDIAVOTES_SCOPE)
    canon_row = next(r for r in out if r.external_scope == CANONICAL_SCOPE)
    assert iv_row.proposed_action == "alias-add"
    assert canon_row.proposed_action == "match"
    assert iv_row.proposed_party_id == "parties.IN.AIADMK"


# --- EMIT SHAPE-A: CONFLICT LEG -----------------------------------------


def test_emit_shape_a_conflict_when_abbrev_collides(tmp_path: Path) -> None:
    """by_alias hit + zero significant-word overlap -> dual conflict rows."""
    parties_csv = _write_parties_csv(
        tmp_path,
        [
            {
                "party_id": "parties.IN.AAP",
                "short": "AAP",
                "full": "Aam Aadmi Party",
                "aliases": "",
            },
        ],
    )
    ix = _load_canonical_index(parties_csv)
    rec = _IvRecord(
        abbrev="AAP",  # collides with canonical
        full="Awami Aamjan Party",  # no significant-word overlap with canonical full
        slug="aap-x",
        iv_type="unrecognised",
        iv_url="",
        active_from="",
        active_to="",
        source_lane="probe",
        notes="",
    )
    out = _emit_shape_a_for_iv_record(rec, ix)
    assert len(out) == 2
    actions = [r.proposed_action for r in out]
    assert actions.count("conflict") == 2


# --- END-TO-END ADAPTER --------------------------------------------------


def test_adapter_full_run_sorts_by_abbrev(tmp_path: Path) -> None:
    """Adapter sorts records by abbrev for deterministic output ordering."""
    _write_parties_csv(
        tmp_path,
        [
            {"party_id": "parties.IN.BJP", "short": "BJP", "full": "Bharatiya Janata Party"},
        ],
    )
    _write_iv_csv(
        tmp_path,
        [
            {
                "party_abbreviation": "ZZZ",
                "party_full_name": "Zee Party",
                "slug": "zzz",
                "iv_type": "unrecognised",
            },
            {
                "party_abbreviation": "AAA",
                "party_full_name": "Alpha Party",
                "slug": "aaa",
                "iv_type": "unrecognised",
            },
            {
                "party_abbreviation": "BJP",
                "party_full_name": "Bharatiya Janata Party",
                "slug": "bjp",
                "iv_type": "national",
            },
        ],
    )
    adapter = IndiaVotesPartiesAdapter()
    rows = list(adapter(root=tmp_path, vintage=INDIAVOTES_VINTAGE))
    iv_rows = [r for r in rows if r.external_scope == INDIAVOTES_SCOPE]
    assert [r.external_key for r in iv_rows] == ["AAA", "BJP", "ZZZ"]


def test_adapter_emits_dual_oracle_for_matched_rows(tmp_path: Path) -> None:
    """Matched rows emit BOTH indiavotes-parties + yen-gov-canonical -> VERIFIED."""
    _write_parties_csv(
        tmp_path,
        [
            {
                "party_id": "parties.IN.BJP",
                "short": "BJP",
                "full": "Bharatiya Janata Party",
                "aliases": "",
            },
        ],
    )
    _write_iv_csv(
        tmp_path,
        [
            {
                "party_abbreviation": "BJP",
                "party_full_name": "Bharatiya Janata Party",
                "slug": "bjp",
                "iv_type": "national",
            },
        ],
    )
    adapter = IndiaVotesPartiesAdapter()
    rows = list(adapter(root=tmp_path, vintage=INDIAVOTES_VINTAGE))
    scopes = sorted(r.external_scope for r in rows)
    assert scopes == [INDIAVOTES_SCOPE, CANONICAL_SCOPE]


def test_adapter_emits_single_row_for_mint_new(tmp_path: Path) -> None:
    """Unmatched rows emit ONLY the indiavotes-parties row -> UNVERIFIED."""
    _write_parties_csv(tmp_path, [])
    _write_iv_csv(
        tmp_path,
        [
            {
                "party_abbreviation": "NEWPARTY",
                "party_full_name": "Brand New Party",
                "slug": "newparty",
                "iv_type": "unrecognised",
            },
        ],
    )
    adapter = IndiaVotesPartiesAdapter()
    rows = list(adapter(root=tmp_path, vintage=INDIAVOTES_VINTAGE))
    assert len(rows) == 1
    assert rows[0].external_scope == INDIAVOTES_SCOPE
    assert rows[0].proposed_action == "mint-new"
    assert rows[0].proposed_party_id == "parties.IN.NEWPARTY"
