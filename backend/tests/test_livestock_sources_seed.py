"""Tier-A tests for ``yen_gov.canonical.livestock_sources_seed``.

Per CLAUDE.md section 15: in-process Pydantic + constant checks only.
Asserts the 5 source_id hashes (Owner Reg + Pashu Aadhaar + NADCP +
Breeding + NAIP IV) are deterministic and the gold-tier / live-fetch
/ OGL-IN-1.0 invariants hold (DAHD is the issuing authority for each
Bharat Pashudhan series per Hans + Max pin).

Post-B3 (2026-06-06): the parquet-UPSERT helpers
(upsert_livestock_sources, upsert_livestock_sources_to_parquet) were
removed because ``datasets/taxonomy/sources.parquet`` was retired in
X1b (#814). The livestock adapter at
``adapters/livestock/_shared.source_id_for`` consumes the
identity-anchor constants only.
"""

from __future__ import annotations

from yen_gov.canonical.livestock_sources_seed import (
    LIVESTOCK_SOURCE_ID_BY_NICKNAME,
    LIVESTOCK_SOURCES,
    SOURCE_NICKNAMES,
)


def test_five_sources_built():
    """Exactly 5 sources: Owner Reg + Pashu Aadhaar + NADCP +
    Breeding ABIP+RGM + NAIP IV (one row per NDLM upstream endpoint,
    per ADR-0032 citation identity = (producer, title, vintage)).
    The CY / FY duality is carried at the observation row via
    ``period_label`` per CLAUDE.md section 12, not at the citation row.
    """
    assert len(LIVESTOCK_SOURCES) == 5
    assert len(SOURCE_NICKNAMES) == 5
    assert set(LIVESTOCK_SOURCE_ID_BY_NICKNAME) == set(SOURCE_NICKNAMES)


def test_source_id_hashes_are_deterministic():
    """The 5 derive_source_id outputs MUST be stable across runs. If a
    triple is edited in livestock_sources_seed.py, the hash changes and
    every downstream FK on observation rows in
    ``datasets/data/datapoints/...livestock...csv`` goes dangling. The
    expected hashes were captured at PR 1 seed time (2026-05-25) from
    the verbatim DAHD producer + title + vintage triples.
    """
    expected = {
        "ndlm_owner_registration": "src-d98dc531ef7e",
        "ndlm_pashu_aadhaar": "src-7e5d4aac4995",
        "ndlm_nadcp_vaccination": "src-1d0c0fbf96e3",
        "ndlm_breeding_abip_rgm": "src-fb1694ab6a11",
        "ndlm_naip_iv": "src-93a2a72db482",
    }
    for nickname, src_id in expected.items():
        assert LIVESTOCK_SOURCE_ID_BY_NICKNAME[nickname] == src_id, (
            f"source_id drift for {nickname!r}: producer/title/vintage triple "
            f"changed since PR 1 seed. Either roll back the triple change or "
            f"re-derive AND update any datasets/livestock/*.parquet source_id "
            f"FKs in the SAME commit (per ADR-0032 + CLAUDE.md Holy Law #9)."
        )


def test_license_tier_authority_invariants():
    """DAHD is the gold issuing authority for every Bharat Pashudhan
    series (the portal is the official data product of the Department
    of Animal Husbandry & Dairying). All 5 rows must be:

    - confidence_tier = "gold"
    - is_issuing_authority = True
    - verification_method = "live-fetch" (continuously-updated JSON APIs)
    - license = "OGL-IN-1.0" (Open Government Licence India)
    """
    by_nick = {nick: row for nick, row in zip(SOURCE_NICKNAMES, LIVESTOCK_SOURCES)}
    for nick in SOURCE_NICKNAMES:
        row = by_nick[nick]
        assert row.confidence_tier == "gold", nick
        assert row.is_issuing_authority is True, nick
        assert row.verification_method == "live-fetch", nick
        assert row.license == "OGL-IN-1.0", nick
        assert row.vintage == "2024-25", nick
        assert "Animal Husbandry" in row.producer, nick
        assert row.notes is not None and len(row.notes) > 0, nick


def test_pashu_aadhaar_carries_honest_renderer_caveat():
    """Hans pin (plan-doc-pashu-aadhaar section 2): the Pashu Aadhaar
    registry counts TAGGED animals, not the underlying livestock
    population; the curve is monotone-non-decreasing because there is
    no de-registration event. The honest-renderer caveat must be
    surfaced in the source row's notes so any downstream FK on this
    source can carry that framing into the citizen surface.
    """
    by_nick = {nick: row for nick, row in zip(SOURCE_NICKNAMES, LIVESTOCK_SOURCES)}
    notes = by_nick["ndlm_pashu_aadhaar"].notes
    assert notes is not None
    assert "tagged" in notes.lower() or "TAGGED" in notes
    assert "population" in notes.lower()
    assert "directional_only" in notes or "no_rank_table" in notes
