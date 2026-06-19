"""Citation-row identity anchor for the 5 livestock (NDLM) sources.

P.2 Livestock (NDLM): 5 distinct upstream endpoints on the Bharat
Pashudhan portal published by the Department of Animal Husbandry &
Dairying, Ministry of Fisheries, Animal Husbandry & Dairying,
Government of India:

1. Owner Registration & Land Holding (district-wise, by financial year)
2. Pashu Aadhaar Animal Registrations (district-wise, by financial year)
3. NADCP Vaccination Coverage (district-wise, by financial year)
4. Breeding Interventions / ABIP+RGM (district-wise, by financial year)
5. NAIP IV -- AI Coverage, Pregnancies, Calves (district-wise, by
   financial year)

The portal exposes the same endpoint contract for both calendar-year
(CY) and financial-year (FY) basis selections via a single ``period``
discriminator on the request payload, so the citation is one row per
endpoint (not per period-basis); the CY/FY duality is carried at the
observation row via ``period_label`` per CLAUDE.md section 12.

Post-B3 (2026-06-06): this module is now CITATION-IDENTITY-ANCHOR only.
The X1b retirement of ``datasets/taxonomy/sources.parquet`` removed the
parquet-UPSERT side; the citation rows themselves move to
``datasets/data/entities/source.csv`` via B2a's seed/source_csv emit
path. The ``LIVESTOCK_NICKNAME_TO_PRODUCER_TITLE`` +
``LIVESTOCK_SOURCE_ID_BY_NICKNAME`` constants stay because the
livestock adapter at ``adapters/livestock/_shared.source_id_for`` reads
the (producer, title) IDENTITY pair to derive the per-(nickname,
vintage) source_id at adapter time.

``derive_source_id(producer, title, vintage)`` is the only way to
compute ``source_id`` -- NEVER hand-author (CLAUDE.md section 10 +
ADR-0032). If a triple is edited here, every downstream FK goes
dangling and the catalogue compile fails closed.

DAHD authority + vintage decisions (Hans + Max pin):

- DAHD is the issuing authority for each of these series (the Bharat
  Pashudhan portal is the official data product of the Department).
  ``is_issuing_authority = True`` -> ``confidence_tier = "gold"``.
- ``verification_method = "live-fetch"`` because the endpoints are
  continuously-updated public JSON APIs (no archived-snapshot tier
  needed; the snapshot lives in ``.runtime/raw/ndlm/`` per how-to).
- License: ``OGL-IN-1.0`` (Open Government Licence India -- default
  for all DAHD data products per the portal's footer).
- Vintage: ``"2024-25"`` was the first scheduled vintage; subsequent
  vintages use ``source_id_for(nickname, vintage)`` to derive new
  citation triples without re-baking constants here.
"""

from __future__ import annotations

from yen_gov.canonical.citation import derive_source_id
from yen_gov.canonical.row_models import SourceRow

__all__ = [
    "LIVESTOCK_NICKNAME_TO_PRODUCER_TITLE",
    "LIVESTOCK_SOURCE_ID_BY_NICKNAME",
    "LIVESTOCK_SOURCES",
    "SOURCE_NICKNAMES",
]


# Operator nicknames for the 5 livestock sources. Adapters look up the
# materialised source_id by nickname rather than rebuilding the
# triple-hash each time.
SOURCE_NICKNAMES: tuple[str, ...] = (
    "ndlm_owner_registration",
    "ndlm_pashu_aadhaar",
    "ndlm_nadcp_vaccination",
    "ndlm_breeding_abip_rgm",
    "ndlm_naip_iv",
)


# (producer, title, vintage) triples. The producer string is the
# canonical DAHD attribution (verbatim from the portal's "About"
# page). Vintage is the FY24-25 first-scheduled ingest; subsequent
# vintages add ADDITIONAL rows under the same nickname (the hash
# discriminates triples, not nicknames).
_PRODUCER = (
    "Department of Animal Husbandry & Dairying, "
    "Ministry of Fisheries, Animal Husbandry & Dairying, "
    "Government of India"
)

_TRIPLES: dict[str, tuple[str, str, str]] = {
    "ndlm_owner_registration": (
        _PRODUCER,
        "Bharat Pashudhan \u2014 Owner Registration & Land Holding (district-wise)",
        "2024-25",
    ),
    "ndlm_pashu_aadhaar": (
        _PRODUCER,
        "Bharat Pashudhan \u2014 Pashu Aadhaar Animal Registrations (district-wise)",
        "2024-25",
    ),
    "ndlm_nadcp_vaccination": (
        _PRODUCER,
        "Bharat Pashudhan \u2014 NADCP Vaccination Coverage (district-wise)",
        "2024-25",
    ),
    "ndlm_breeding_abip_rgm": (
        _PRODUCER,
        "Bharat Pashudhan \u2014 Breeding Interventions ABIP+RGM (district-wise)",
        "2024-25",
    ),
    "ndlm_naip_iv": (
        _PRODUCER,
        "Bharat Pashudhan \u2014 NAIP IV AI Coverage, Pregnancies, Calves (district-wise)",
        "2024-25",
    ),
}


# Per-source license / confidence_tier / verification_method / authority
# / url_main / notes. All 5 endpoints share the same NDLM hostname
# (``bharatpashudhan-api.ndlm.co.in``); the url_main is the public
# portal landing page (the operator-facing surface), not the JSON
# endpoint (which is documented in the NDLM how-to). DAHD is the
# issuing authority for each series -- gold tier, live-fetch, OGL-IN-1.0.
#
# Pashu Aadhaar carries the strongest caveat string in ``notes`` per
# Hans's honest-renderer pin (plan-doc \u00a73 + plan-doc-pashu-aadhaar):
# the registry counts TAGGED animals, not population; there is no
# de-registration event, so the curve is monotone-non-decreasing and
# must NOT be interpreted as a population census. The renderer carries
# this caveat in ``renderer_rules: ["no_rank_table"]`` and
# ``comparability: "directional_only"`` on the indicator row (lands in
# PR 3, the end-to-end Pashu Aadhaar slice).
_BY_NICKNAME: dict[str, tuple[str, str, str, bool, str, str | None]] = {
    "ndlm_owner_registration": (
        "OGL-IN-1.0",
        "gold",
        "live-fetch",
        True,
        "https://bharatpashudhan.gov.in/",
        "Bharat Pashudhan owner-registration counts (animal-owner identity records on the portal) and the corresponding land-holding ladder. DAHD is the issuing authority. Period-basis selectable at request time (CY or FY); both vintages are ingested per CLAUDE.md \u00a712.",
    ),
    "ndlm_pashu_aadhaar": (
        "OGL-IN-1.0",
        "gold",
        "live-fetch",
        True,
        "https://bharatpashudhan.gov.in/",
        "Bharat Pashudhan Pashu Aadhaar counts (UID-tagged animals on the portal). DAHD is the issuing authority. CAVEAT (Hans, plan-doc-pashu-aadhaar \u00a72): the registry counts TAGGED animals, not the underlying livestock population; there is no de-registration event so the curve is monotone-non-decreasing. Indicator-row carries comparability=directional_only + renderer_rules=[\"no_rank_table\"] + excluded_notes so the citizen-surface never silently presents this as a population census or cross-state rank-table.",
    ),
    "ndlm_nadcp_vaccination": (
        "OGL-IN-1.0",
        "gold",
        "live-fetch",
        True,
        "https://bharatpashudhan.gov.in/",
        "Bharat Pashudhan NADCP (National Animal Disease Control Programme) vaccination coverage -- doses administered per district per FY. DAHD is the issuing authority. Period-basis selectable at request time (CY or FY).",
    ),
    "ndlm_breeding_abip_rgm": (
        "OGL-IN-1.0",
        "gold",
        "live-fetch",
        True,
        "https://bharatpashudhan.gov.in/",
        "Bharat Pashudhan breeding-intervention counts under ABIP (Accelerated Breed Improvement Programme) + RGM (Rashtriya Gokul Mission) -- two distinct programme facets aggregated to district. DAHD is the issuing authority. Period-basis selectable at request time (CY or FY).",
    ),
    "ndlm_naip_iv": (
        "OGL-IN-1.0",
        "gold",
        "live-fetch",
        True,
        "https://bharatpashudhan.gov.in/",
        "Bharat Pashudhan NAIP IV (National Artificial Insemination Programme, Phase IV) -- AI coverage, pregnancies, calves born, per district per FY. DAHD is the issuing authority. Period-basis selectable at request time (CY or FY); CY/FY duality verified at recon (TN FY24-25: 1,529,434 vs CY24: 1,396,453).",
    ),
}


def _build_livestock_source_rows() -> tuple[SourceRow, ...]:
    rows: list[SourceRow] = []
    for nickname in SOURCE_NICKNAMES:
        producer, title, vintage = _TRIPLES[nickname]
        license_, tier, method, is_authority, url_main, notes = _BY_NICKNAME[nickname]
        rows.append(
            SourceRow(
                source_id=derive_source_id(producer, title, vintage),
                producer=producer,
                title=title,
                vintage=vintage,
                license=license_,  # type: ignore[arg-type]
                confidence_tier=tier,  # type: ignore[arg-type]
                is_issuing_authority=is_authority,
                verification_method=method,  # type: ignore[arg-type]
                url_main=url_main,
                citation_full=None,
                notes=notes,
            )
        )
    return tuple(rows)


LIVESTOCK_SOURCES: tuple[SourceRow, ...] = _build_livestock_source_rows()
LIVESTOCK_SOURCE_ID_BY_NICKNAME: dict[str, str] = {
    nickname: row.source_id
    for nickname, row in zip(SOURCE_NICKNAMES, LIVESTOCK_SOURCES, strict=True)
}

# (producer, title) pair per nickname. Exposed so that
# ``yen_gov.canonical.adapters.livestock._shared.source_id_for`` can
# derive a vintage-specific ``source_id`` at runtime without
# round-tripping through the SourceRow ledger. This map carries the
# IDENTITY half of the citation triple; vintage is the per-snapshot
# parameter the adapter applies via ``derive_source_id``.
#
# Why this exists (architectural fix, 2026-05-26): adapters used to
# carry a frozen ``SOURCE_IDS[nickname]`` constant in _shared.py that
# baked vintage="2024-25" into every observation row's FK. When a
# future operator snapshot window lands (ADR-0042: live-fetch endpoints
# get a new source row per new snapshot), the new vintage's source_id
# must FK observation rows fetched in that window. The runtime helper
# eliminates the frozen constant + lets adapters discover meadow
# snapshot dirs and pick the correct source_id per dir.
LIVESTOCK_NICKNAME_TO_PRODUCER_TITLE: dict[str, tuple[str, str]] = {
    nickname: (_TRIPLES[nickname][0], _TRIPLES[nickname][1])
    for nickname in SOURCE_NICKNAMES
}
