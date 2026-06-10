"""Tier-A tests for the Wikipedia parties parity adapter (PR-W-3).

Covers:

  - ``_read_wikipedia_snapshot`` reads the operator-committed snapshot
    CSV and tolerates empty cells per column.
  - ``_resolve_via_index`` dispatch order: direct ``parties.IN.<slug>``
    id wins, then normalised full-name match, then by_alias fallback.
    Direct-id misses return ``(None, False)`` so the caller mints under
    the curator-named slug (curator intent preserved).
  - ``_share_significant_words`` correctly bypasses sparse-canonical
    rows AND fires the conflict guard on real abbreviation collisions.
  - ``_emit_shape_a_for_wiki_record`` dispatches on the four Q1 fact
    classes (brand_colour / symbol_asset / wikipedia URL /
    name_native_script) so each missing-cell-in-canonical surfaces as
    ``enrich``; existing disagreement surfaces as ``conflict``.
  - End-to-end: ``WikipediaPartiesAdapter()`` against a minimal fixture
    yields the expected shape-A row set (match / enrich / mint-new /
    conflict legs).
  - Adapter is registered against ``REGISTRY["wikipedia-parties"]`` and
    rejects vintages other than the snapshot pin per ADR-0042.

No real-corpus walking (CLAUDE.md section 14 carve-out: tmp_path
fixtures only). Pure-function tests; the adapter holds no I/O state
beyond reading the snapshot path.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from yen_gov.canonical.recon.adapters import REGISTRY
from yen_gov.canonical.recon.adapters.wikipedia_parties import (
    ADAPTER,
    CANONICAL_ID_PREFIX,
    CANONICAL_SCOPE,
    DEFAULT_WIKIPEDIA_CSV,
    WIKIPEDIA_SCOPE,
    WIKIPEDIA_VINTAGE,
    WikipediaPartiesAdapter,
    _CanonicalIndex,
    _emit_shape_a_for_wiki_record,
    _has_disputed_overwrite,
    _has_enrichable_fields,
    _load_canonical_index,
    _make_slug,
    _normalise_full_name,
    _read_wikipedia_snapshot,
    _resolve_via_index,
    _share_significant_words,
    _significant_words,
    _WikiRecord,
)
from yen_gov.canonical.recon.shape_a import ShapeARow


# --- tiny canonical / Wikipedia fixtures used across tests ---------------


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


_WIKI_COLS: tuple[str, ...] = (
    "party_id_or_short",
    "full_name",
    "native_script_name",
    "brand_colour_hex",
    "symbol_asset_url",
    "wikipedia_url",
    "myneta_url",
    "recognition_blurb",
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


def _write_wiki_csv(tmp_path: Path, rows: list[dict[str, str]]) -> Path:
    path = tmp_path / DEFAULT_WIKIPEDIA_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_WIKI_COLS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in _WIKI_COLS})
    return path


# --- ADAPTER REGISTRATION ------------------------------------------------


def test_adapter_registered_in_registry() -> None:
    """The PR-W-3 adapter is registered against REGISTRY['wikipedia-parties']."""
    assert "wikipedia-parties" in REGISTRY
    assert REGISTRY["wikipedia-parties"] is ADAPTER


def test_adapter_rejects_wrong_vintage(tmp_path: Path) -> None:
    """Adapter refuses any vintage other than the snapshot pin (ADR-0042)."""
    adapter = WikipediaPartiesAdapter()
    with pytest.raises(ValueError, match=WIKIPEDIA_VINTAGE):
        list(adapter(root=tmp_path, vintage="2025-01"))


def test_adapter_raises_when_snapshot_missing(tmp_path: Path) -> None:
    """Adapter raises FileNotFoundError when the snapshot CSV is absent."""
    adapter = WikipediaPartiesAdapter()
    _write_parties_csv(tmp_path, [{"party_id": "parties.IN.X", "short": "X", "full": "X"}])
    with pytest.raises(FileNotFoundError, match="Wikipedia parties snapshot"):
        list(adapter(root=tmp_path, vintage=WIKIPEDIA_VINTAGE))


# --- NORMALISATION + SIGNIFICANT-WORDS ----------------------------------


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
    # Sparse-canonical row: full == short after normalisation (the
    # X1a-fu2 transcode default where parties.csv ``full`` was never
    # authored beyond the slug-tail). Guard bypasses.
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
    """Bharatiya Janata Party variants share BHARATIYA / JANATA."""
    assert _share_significant_words(
        "Bharatiya Janata Party",
        "Bharatiya Janata Party",
        "BJP",
    ) is True


# --- SLUG BUILDER --------------------------------------------------------


def test_make_slug_sanitises_punctuation() -> None:
    assert _make_slug("CPI(M)") == "parties.IN.CPI_M"
    assert _make_slug("LKD (B)") == "parties.IN.LKD_B"
    assert _make_slug("a.b.c") == "parties.IN.A_B_C"
    assert _make_slug("") == "parties.IN.UNK"


def test_make_slug_collapses_underscores() -> None:
    assert _make_slug("---X---Y---") == "parties.IN.X_Y"


# --- SNAPSHOT READER -----------------------------------------------------


def test_read_wikipedia_snapshot_tolerates_empty_cells(tmp_path: Path) -> None:
    """Snapshot rows with empty optional cells round-trip safely."""
    wiki_csv = _write_wiki_csv(
        tmp_path,
        [
            {
                "party_id_or_short": "parties.IN.BJP",
                "full_name": "Bharatiya Janata Party",
                "brand_colour_hex": "#FF9933",
                # other cells intentionally empty
            },
            {
                "party_id_or_short": "X",
                "full_name": "Some Other Party",
                # all enrichable cells empty -> match leg
            },
        ],
    )
    out = _read_wikipedia_snapshot(wiki_csv)
    assert len(out) == 2
    bjp = next(r for r in out if r.party_id_or_short == "parties.IN.BJP")
    assert bjp.brand_colour == "#FF9933"
    assert bjp.symbol_asset == ""
    assert bjp.native_script == ""
    assert bjp.notes == ""


# --- RESOLVE_VIA_INDEX ---------------------------------------------------


def test_resolve_via_index_direct_id_wins(tmp_path: Path) -> None:
    """When ``party_id_or_short`` starts with parties.IN. and exists, return it."""
    parties_csv = _write_parties_csv(
        tmp_path,
        [{"party_id": "parties.IN.BJP", "short": "BJP", "full": "Bharatiya Janata Party"}],
    )
    ix = _load_canonical_index(parties_csv)
    rec = _WikiRecord(
        party_id_or_short="parties.IN.BJP",
        full="anything",
        native_script="",
        brand_colour="",
        symbol_asset="",
        wikipedia_url="",
        myneta_url="",
        recognition_blurb="",
        notes="",
    )
    pid, via_full = _resolve_via_index(rec, ix)
    assert pid == "parties.IN.BJP"
    assert via_full is True


def test_resolve_via_index_direct_id_missing_returns_none(tmp_path: Path) -> None:
    """Direct id that does NOT exist in canonical -> (None, False) so the
    caller mints under the curator-specified slug."""
    parties_csv = _write_parties_csv(tmp_path, [])
    ix = _load_canonical_index(parties_csv)
    rec = _WikiRecord(
        party_id_or_short="parties.IN.NOTREAL",
        full="A New Curator-Specified Party",
        native_script="",
        brand_colour="",
        symbol_asset="",
        wikipedia_url="",
        myneta_url="",
        recognition_blurb="",
        notes="",
    )
    pid, via_full = _resolve_via_index(rec, ix)
    assert pid is None
    assert via_full is False


def test_resolve_via_index_prefers_full_name_over_alias(tmp_path: Path) -> None:
    """When ``party_id_or_short`` is a short (NOT direct id), full-name match
    wins over the by_alias fallback (no false-positive abbreviation collision).
    """
    parties_csv = _write_parties_csv(
        tmp_path,
        [
            {
                "party_id": "parties.IN.AIADMK",
                "short": "AIADMK",
                "full": "All India Anna Dravida Munnetra Kazhagam",
            },
            # Sparse-canonical row whose short collides with one of the
            # Wikipedia abbreviations: by_alias would hit this, but
            # by_full wins first.
            {"party_id": "parties.IN.ADK", "short": "ADK", "full": "ADK"},
        ],
    )
    ix = _load_canonical_index(parties_csv)
    rec = _WikiRecord(
        party_id_or_short="ADK",
        full="All India Anna Dravida Munnetra Kazhagam",
        native_script="",
        brand_colour="",
        symbol_asset="",
        wikipedia_url="",
        myneta_url="",
        recognition_blurb="",
        notes="",
    )
    pid, via_full = _resolve_via_index(rec, ix)
    assert pid == "parties.IN.AIADMK"
    assert via_full is True


def test_resolve_via_index_alias_fallback(tmp_path: Path) -> None:
    """Full-name miss -> short lookup via by_alias still resolves."""
    parties_csv = _write_parties_csv(
        tmp_path,
        [{"party_id": "parties.IN.BJP", "short": "BJP", "full": "Bharatiya Janata Party"}],
    )
    ix = _load_canonical_index(parties_csv)
    rec = _WikiRecord(
        party_id_or_short="BJP",
        full="Bharatiya Janata Party (regional)",  # different from canonical full
        native_script="",
        brand_colour="",
        symbol_asset="",
        wikipedia_url="",
        myneta_url="",
        recognition_blurb="",
        notes="",
    )
    pid, via_full = _resolve_via_index(rec, ix)
    assert pid == "parties.IN.BJP"
    assert via_full is False  # by_alias path


def test_resolve_via_index_full_miss_returns_none(tmp_path: Path) -> None:
    parties_csv = _write_parties_csv(tmp_path, [])
    ix = _load_canonical_index(parties_csv)
    rec = _WikiRecord(
        party_id_or_short="HJC",
        full="Haryana Janhit Congress",
        native_script="",
        brand_colour="",
        symbol_asset="",
        wikipedia_url="",
        myneta_url="",
        recognition_blurb="",
        notes="",
    )
    pid, via_full = _resolve_via_index(rec, ix)
    assert pid is None
    assert via_full is False


# --- ENRICHABLE FIELDS DETECTION (Q1 fact classes) -----------------------


def test_has_enrichable_fields_brand_colour() -> None:
    rec = _WikiRecord(
        party_id_or_short="parties.IN.X",
        full="X",
        native_script="",
        brand_colour="#FF9933",
        symbol_asset="",
        wikipedia_url="",
        myneta_url="",
        recognition_blurb="",
        notes="",
    )
    assert _has_enrichable_fields(rec, {"brand_colour": ""}) is True
    assert _has_enrichable_fields(rec, {"brand_colour": "#FF9933"}) is False


def test_has_enrichable_fields_symbol_asset() -> None:
    rec = _WikiRecord(
        party_id_or_short="parties.IN.X",
        full="X",
        native_script="",
        brand_colour="",
        symbol_asset="party-symbols/lotus.svg",
        wikipedia_url="",
        myneta_url="",
        recognition_blurb="",
        notes="",
    )
    assert _has_enrichable_fields(rec, {"symbol_asset": ""}) is True
    assert _has_enrichable_fields(rec, {"symbol_asset": "party-symbols/lotus.svg"}) is False


def test_has_enrichable_fields_wikipedia_url() -> None:
    rec = _WikiRecord(
        party_id_or_short="parties.IN.X",
        full="X",
        native_script="",
        brand_colour="",
        symbol_asset="",
        wikipedia_url="https://en.wikipedia.org/wiki/X",
        myneta_url="",
        recognition_blurb="",
        notes="",
    )
    assert _has_enrichable_fields(rec, {"wikipedia": ""}) is True
    assert _has_enrichable_fields(rec, {"wikipedia": "https://en.wikipedia.org/wiki/X"}) is False


def test_has_enrichable_fields_native_script() -> None:
    rec = _WikiRecord(
        party_id_or_short="parties.IN.X",
        full="X",
        native_script="भारतीय जनता पार्टी",
        brand_colour="",
        symbol_asset="",
        wikipedia_url="",
        myneta_url="",
        recognition_blurb="",
        notes="",
    )
    assert _has_enrichable_fields(rec, {"name_native_script": ""}) is True
    assert _has_enrichable_fields(rec, {"name_native_script": "भारतीय जनता पार्टी"}) is False


def test_has_disputed_overwrite_brand_colour_case_insensitive() -> None:
    """Different hex case ('#FF9933' vs '#ff9933') is NOT a conflict."""
    rec = _WikiRecord(
        party_id_or_short="parties.IN.BJP",
        full="Bharatiya Janata Party",
        native_script="",
        brand_colour="#FF9933",
        symbol_asset="",
        wikipedia_url="",
        myneta_url="",
        recognition_blurb="",
        notes="",
    )
    assert _has_disputed_overwrite(rec, {"brand_colour": "#ff9933"}) is False
    # But a REAL disagreement does fire:
    assert _has_disputed_overwrite(rec, {"brand_colour": "#00FF00"}) is True


# --- EMIT_SHAPE_A_FOR_WIKI_RECORD ----------------------------------------


def test_emit_shape_a_match_when_canonical_complete(tmp_path: Path) -> None:
    """Canonical already has all Q1 fields -> action=match + canonical pair."""
    parties_csv = _write_parties_csv(
        tmp_path,
        [
            {
                "party_id": "parties.IN.BJP",
                "short": "BJP",
                "full": "Bharatiya Janata Party",
                "brand_colour": "#FF9933",
                "symbol_asset": "party-symbols/lotus.svg",
                "wikipedia": "https://en.wikipedia.org/wiki/Bharatiya_Janata_Party",
                "name_native_script": "भारतीय जनता पार्टी",
            }
        ],
    )
    ix = _load_canonical_index(parties_csv)
    rec = _WikiRecord(
        party_id_or_short="parties.IN.BJP",
        full="Bharatiya Janata Party",
        native_script="भारतीय जनता पार्टी",
        brand_colour="#FF9933",
        symbol_asset="party-symbols/lotus.svg",
        wikipedia_url="https://en.wikipedia.org/wiki/Bharatiya_Janata_Party",
        myneta_url="",
        recognition_blurb="National party",
        notes="",
    )
    out = _emit_shape_a_for_wiki_record(rec, ix)
    assert len(out) == 2
    wiki_row, canon_row = out
    assert wiki_row.external_scope == WIKIPEDIA_SCOPE
    assert wiki_row.external_vintage == WIKIPEDIA_VINTAGE
    assert wiki_row.proposed_action == "match"
    assert wiki_row.proposed_party_id == "parties.IN.BJP"
    assert canon_row.external_scope == CANONICAL_SCOPE
    assert canon_row.proposed_action == "match"
    assert canon_row.proposed_party_id == "parties.IN.BJP"


def test_emit_shape_a_enrich_when_canonical_missing_q1_field(tmp_path: Path) -> None:
    """Canonical missing brand_colour -> action=enrich (one Q1 gap suffices)."""
    parties_csv = _write_parties_csv(
        tmp_path,
        [
            {
                "party_id": "parties.IN.BJP",
                "short": "BJP",
                "full": "Bharatiya Janata Party",
            }
        ],
    )
    ix = _load_canonical_index(parties_csv)
    rec = _WikiRecord(
        party_id_or_short="parties.IN.BJP",
        full="Bharatiya Janata Party",
        native_script="",
        brand_colour="#FF9933",
        symbol_asset="",
        wikipedia_url="",
        myneta_url="",
        recognition_blurb="",
        notes="",
    )
    out = _emit_shape_a_for_wiki_record(rec, ix)
    assert len(out) == 2
    assert out[0].proposed_action == "enrich"
    assert out[1].proposed_action == "match"  # canonical pair stays match


def test_emit_shape_a_mint_new_when_no_canonical_match(tmp_path: Path) -> None:
    """No canonical match -> action=mint-new, only wikipedia row (no pair)."""
    parties_csv = _write_parties_csv(tmp_path, [])
    ix = _load_canonical_index(parties_csv)
    rec = _WikiRecord(
        party_id_or_short="parties.IN.HJC",
        full="Haryana Janhit Congress",
        native_script="",
        brand_colour="#00AA00",
        symbol_asset="",
        wikipedia_url="https://en.wikipedia.org/wiki/Haryana_Janhit_Congress",
        myneta_url="",
        recognition_blurb="State-based party",
        notes="",
    )
    out = _emit_shape_a_for_wiki_record(rec, ix)
    assert len(out) == 1
    assert out[0].proposed_action == "mint-new"
    assert out[0].proposed_party_id == "parties.IN.HJC"
    assert out[0].external_scope == WIKIPEDIA_SCOPE


def test_emit_shape_a_alias_collision_emits_conflict(tmp_path: Path) -> None:
    """by_alias hit + zero shared significant words -> both legs conflict."""
    parties_csv = _write_parties_csv(
        tmp_path,
        [
            {
                "party_id": "parties.IN.AAP",
                "short": "AAP",
                "full": "Aam Aadmi Party",
            }
        ],
    )
    ix = _load_canonical_index(parties_csv)
    # Wikipedia record uses the AAP short for a DIFFERENT party
    # ("awami aamjan party") -> alias collision, full-name guard fires.
    rec = _WikiRecord(
        party_id_or_short="AAP",
        full="awami aamjan party",
        native_script="",
        brand_colour="",
        symbol_asset="",
        wikipedia_url="",
        myneta_url="",
        recognition_blurb="",
        notes="",
    )
    out = _emit_shape_a_for_wiki_record(rec, ix)
    assert len(out) == 2
    assert out[0].proposed_action == "conflict"
    assert out[1].proposed_action == "conflict"
    assert "abbreviation collision" in (out[0].notes or "")


def test_emit_shape_a_disputed_overwrite_takes_precedence_over_enrich(tmp_path: Path) -> None:
    """Real disagreement on a Q1-owned cell becomes ``conflict``, not ``enrich``.

    PR-W-3 fill-empty-only semantics: when canonical has a non-empty
    brand_colour and Wikipedia disagrees, the curator decides.
    """
    parties_csv = _write_parties_csv(
        tmp_path,
        [
            {
                "party_id": "parties.IN.X",
                "short": "X",
                "full": "Party X",
                "brand_colour": "#000000",
            }
        ],
    )
    ix = _load_canonical_index(parties_csv)
    rec = _WikiRecord(
        party_id_or_short="parties.IN.X",
        full="Party X",
        native_script="",
        brand_colour="#FFFFFF",  # disagrees with canonical #000000
        symbol_asset="",
        wikipedia_url="",
        myneta_url="",
        recognition_blurb="",
        notes="",
    )
    out = _emit_shape_a_for_wiki_record(rec, ix)
    assert len(out) == 2
    assert out[0].proposed_action == "conflict"


# --- END-TO-END ADAPTER --------------------------------------------------


def test_adapter_end_to_end_minimal_fixture(tmp_path: Path) -> None:
    """Full adapter pass on a 3-record fixture -> shape-A rows for compare.

    Coverage matrix:

      - BJP: direct-id + canonical sparse on brand_colour -> enrich
      - INC: direct-id + canonical complete -> match
      - HJC: direct-id missing in canonical -> mint-new
    """
    _write_parties_csv(
        tmp_path,
        [
            {
                "party_id": "parties.IN.BJP",
                "short": "BJP",
                "full": "Bharatiya Janata Party",
            },
            {
                "party_id": "parties.IN.INC",
                "short": "INC",
                "full": "Indian National Congress",
                "brand_colour": "#00BFFF",
                "symbol_asset": "party-symbols/hand.svg",
                "wikipedia": "https://en.wikipedia.org/wiki/Indian_National_Congress",
                "name_native_script": "भारतीय राष्ट्रीय कांग्रेस",
            },
        ],
    )
    _write_wiki_csv(
        tmp_path,
        [
            {
                "party_id_or_short": "parties.IN.BJP",
                "full_name": "Bharatiya Janata Party",
                "brand_colour_hex": "#FF9933",
            },
            {
                "party_id_or_short": "parties.IN.INC",
                "full_name": "Indian National Congress",
                "brand_colour_hex": "#00BFFF",
                "symbol_asset_url": "party-symbols/hand.svg",
                "wikipedia_url": "https://en.wikipedia.org/wiki/Indian_National_Congress",
                "native_script_name": "भारतीय राष्ट्रीय कांग्रेस",
            },
            {
                "party_id_or_short": "parties.IN.HJC",
                "full_name": "Haryana Janhit Congress",
                "brand_colour_hex": "#00AA00",
            },
        ],
    )
    adapter = WikipediaPartiesAdapter()
    shape_a_rows = list(adapter(root=tmp_path, vintage=WIKIPEDIA_VINTAGE))

    by_pid: dict[str, list[ShapeARow]] = {}
    for r in shape_a_rows:
        by_pid.setdefault(r.proposed_party_id, []).append(r)

    # BJP: canonical missing brand_colour -> enrich + canonical pair.
    assert "parties.IN.BJP" in by_pid
    bjp_wiki = next(r for r in by_pid["parties.IN.BJP"] if r.external_scope == WIKIPEDIA_SCOPE)
    bjp_canon = next(r for r in by_pid["parties.IN.BJP"] if r.external_scope == CANONICAL_SCOPE)
    assert bjp_wiki.proposed_action == "enrich"
    assert bjp_canon.proposed_action == "match"

    # INC: canonical already has all 4 Q1 cells -> match + canonical pair.
    assert "parties.IN.INC" in by_pid
    inc_wiki = next(r for r in by_pid["parties.IN.INC"] if r.external_scope == WIKIPEDIA_SCOPE)
    assert inc_wiki.proposed_action == "match"

    # HJC: direct id NOT in canonical -> mint-new, only wikipedia row.
    assert "parties.IN.HJC" in by_pid
    assert len(by_pid["parties.IN.HJC"]) == 1
    assert by_pid["parties.IN.HJC"][0].proposed_action == "mint-new"


def test_adapter_emits_stable_order_across_runs(tmp_path: Path) -> None:
    """Same snapshot -> same emission order (sorted by (party_id_or_short, full))."""
    _write_parties_csv(tmp_path, [])
    _write_wiki_csv(
        tmp_path,
        [
            {"party_id_or_short": "parties.IN.B", "full_name": "B"},
            {"party_id_or_short": "parties.IN.A", "full_name": "A"},
            {"party_id_or_short": "parties.IN.C", "full_name": "C"},
        ],
    )
    adapter = WikipediaPartiesAdapter()
    rows1 = list(adapter(root=tmp_path, vintage=WIKIPEDIA_VINTAGE))
    rows2 = list(adapter(root=tmp_path, vintage=WIKIPEDIA_VINTAGE))
    pids1 = [r.proposed_party_id for r in rows1]
    pids2 = [r.proposed_party_id for r in rows2]
    assert pids1 == pids2
    assert pids1 == ["parties.IN.A", "parties.IN.B", "parties.IN.C"]


def test_canonical_id_prefix_constant() -> None:
    """The CANONICAL_ID_PREFIX constant matches parties.IN. (sanity check)."""
    assert CANONICAL_ID_PREFIX == "parties.IN."
