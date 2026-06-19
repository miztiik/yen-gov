"""NITI ICED national energy-balance - feed registry.

Two specs, one per national energy-balance feed: the Source-wise Energy Supply
side (Total Primary Energy Supply by source) and the Sector-wise Energy
Consumption side (final consumption by sector x fuel). Each spec carries the
closed-enum slug map(s), the catalogue rows (variables.csv + concepts.csv), and
the citation triple (source.csv). ``source_id`` is DERIVED from the (producer,
title, vintage) triple, never hand-written; the two titles below reproduce the
existing on-disk source rows ``src-170d3536d908`` and ``src-29ecbb6dce9d``.

> **Provenance.** The ICED dashboard is the machine-readable access surface
> (and publisher of the harmonised national balance), so ``source_producer``
> names the NITI Aayog India Climate & Energy Dashboard, matching the rest of
> the ICED indicator family. The underlying balance follows the
> IEA/CEA/MoSPI energy-account methodology; ICED is the harmonised access
> surface.

> **Closed enums.** Both feeds report fixed vocabularies (six primary sources;
> eight demand sectors x four delivered carriers). The slug maps below ARE the
> closed enums - mirrored in columns.json. An upstream label absent from a map
> is raised by the parser (a new member must surface, never be silently
> dropped); widening an enum is a deliberate columns.json bump.
"""
from __future__ import annotations

from .parser import FinalEnergySpec, PrimaryEnergySpec

__all__ = ["FINAL_ENERGY_SPEC", "PRIMARY_ENERGY_SPEC"]

# Publisher / access surface for both feeds (matches the ICED family string).
_ICED_PRODUCER = "NITI Aayog India Climate & Energy Dashboard"
# Latest fiscal year carried by the feeds today; the API edition tag. Bump when
# staging a newer edition; source_id re-derives so the citation ledger tracks it.
_VINTAGE = "2024-25"
# The on-disk source.csv url for both rows (the ICED state-wise deep-dive
# access surface); kept verbatim so the catalogue upsert is byte-idempotent.
_ICED_URL = "https://icedapi.niti.gov.in/analytics/state-wise-deep-dive"


PRIMARY_ENERGY_SPEC = PrimaryEnergySpec(
    indicator_id="primary-energy-supply-mtoe",
    name="Total primary energy supply, by source",
    concept_id="primary-energy-supply",
    concept_noun="Primary energy supply",
    concept_description=(
        "India's Total Primary Energy Supply (TPES) in million tonnes of oil "
        "equivalent (mtoe), broken out by the six primary sources the national "
        "energy balance recognises (coal, oil, gas, hydro, nuclear, "
        "renewables). 'Primary' means energy as it enters the economy before "
        "conversion to electricity or fuels - so coal here is the coal burned "
        "across all uses, NOT just power-sector coal, and renewables / hydro / "
        "nuclear are counted as the primary energy they supply. The six "
        "sources sum to TPES; this is a national series only (no per-state "
        "split is published)."
    ),
    unit="mtoe",
    unit_canonical="mtoe",
    normalisation="absolute",
    topic="energy",
    entity_kinds="country",
    update_period_days=365,
    derivation=None,
    source_producer=_ICED_PRODUCER,
    source_title=(
        "Primary Energy Supply National API (national fiscal-year "
        "primary-energy supply (TPES) by source, mtoe)"
    ),
    source_vintage=_VINTAGE,
    source_url=_ICED_URL,
    staging_filename="source_wise_energy_supply.json",
    file_class="datasets/data/datapoints/geo_by_primary_source/*.csv",
    source_slugs={
        "Coal": "coal",
        "Gas": "gas",
        "Hydro": "hydro",
        "Nuclear": "nuclear",
        "Oil": "oil",
        "Renewables": "renewable",
    },
)


FINAL_ENERGY_SPEC = FinalEnergySpec(
    indicator_id="final-energy-consumption-mtoe",
    name="Final energy consumption, by sector and fuel",
    concept_id="final-energy-consumption",
    concept_noun="Final energy consumption",
    concept_description=(
        "India's final energy consumption in million tonnes of oil equivalent "
        "(mtoe) - the energy actually delivered to and used by end-use demand "
        "sectors, after conversion losses. Reported as a sector x fuel matrix: "
        "eight demand sectors (agriculture, industry, transport, residential, "
        "commercial, the city-gas-distribution 'CGD and others' bucket, the "
        "non-energy feedstock use, and a residual 'other') against four "
        "delivered carriers (coal, oil, gas, electricity). Electricity appears "
        "here as a DELIVERED carrier (final consumption counts the electricity "
        "a sector uses, not the coal/gas/hydro that generated it - that lives "
        "in primary supply). The matrix is sparse - not every sector uses "
        "every fuel. National series only (no per-state split is published)."
    ),
    unit="mtoe",
    unit_canonical="mtoe",
    normalisation="absolute",
    topic="energy",
    entity_kinds="country",
    update_period_days=365,
    derivation=None,
    source_producer=_ICED_PRODUCER,
    source_title=(
        "Final Energy Consumption National API (national fiscal-year "
        "final-energy consumption by sector x fuel composite, mtoe)"
    ),
    source_vintage=_VINTAGE,
    source_url=_ICED_URL,
    staging_filename="sector_wise_energy_consumption.json",
    file_class="datasets/data/datapoints/geo_by_sector_fuel/*.csv",
    sector_slugs={
        "Agriculture": "agriculture",
        "CGD-and-Others": "cgd-and-others",
        "Commercial": "commercial",
        "Industry": "industry",
        "Non-Energy": "non-energy",
        "Other": "other",
        "Residential": "residential",
        "Transport": "transport",
    },
    fuel_slugs={
        "Coal": "coal",
        "Electricity": "electricity",
        "Gas": "gas",
        "Oil": "oil",
    },
)
