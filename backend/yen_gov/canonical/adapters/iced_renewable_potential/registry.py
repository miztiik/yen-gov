"""ICED renewable-energy potential - feed registry.

One :class:`RenewablePotentialSpec` per ICED potential feed. Adding a new
feed (e.g. a future small-hydro or offshore-wind potential study) means
appending one spec here; the parser, emitter, and CLI are unchanged.

> **Provenance.** The ICED dashboard is the machine-readable access surface
> (and the publisher of the harmonised series), so ``source_producer`` names
> the NITI Aayog India Climate & Energy Dashboard, matching the rest of the
> ICED indicator family. The underlying technical assessments are named in
> each spec's ``concept_description`` (NISE for solar, NIWE for wind, MNRE /
> the Biomass Atlas for bio-energy). ``source_id`` is DERIVED from the
> (producer, title, vintage) triple, never hand-written.

> **Scenarios are not facets.** Solar and wind each publish two scenario
> variants (solar @3% vs @6.69% wasteland; wind @120m vs @150m AGL). These
> are ALTERNATIVE estimates of the same quantity, NOT additive components, so
> each spec keeps ONE headline scenario rather than fragmenting into two
> files or summing. Bio-energy publishes biomass and cogeneration-bagasse,
> which ARE physically-distinct additive streams, so its spec keeps both and
> the emitter sums them per state.
"""
from __future__ import annotations

from .parser import RenewablePotentialSpec

__all__ = ["SHIPPED_SPECS", "spec_by_indicator_id"]

# The ICED dashboard is the publisher / access surface for all three feeds
# (matches the producer string used across the ICED indicator family).
_ICED_PRODUCER = "NITI Aayog India Climate & Energy Dashboard"
# Single assessment-year snapshot the operator stages. Bump when staging a
# newer assessment; source_id re-derives, so the citation ledger tracks it.
_ASSESSMENT_VINTAGE = "2025-26"
# Citizen-openable dashboard landing page (the renewable-potential views live
# under the dashboard; the dashboard root is the stable entry point).
_ICED_URL = "https://iced.niti.gov.in"


SHIPPED_SPECS: tuple[RenewablePotentialSpec, ...] = (
    RenewablePotentialSpec(
        indicator_id="solar-potential-mw",
        name="Solar power potential",
        concept_id="solar-energy-potential",
        concept_noun="Solar power potential",
        concept_description=(
            "Modelled maximum solar PV capacity (MW) a state could build, "
            "estimated by the National Institute of Solar Energy (NISE) from "
            "the headline scenario of 3% of the state's wasteland area at "
            "current module efficiency. This is buildable potential driven by "
            "geography (desert / arid land / irradiation), NOT installed "
            "capacity and NOT a policy achievement - a large potential is an "
            "endowment, not a ranking of effort."
        ),
        unit="MW",
        unit_canonical="MW",
        normalisation="absolute",
        topic="energy",
        entity_kinds="country state",
        update_period_days=365,
        derivation=None,
        source_producer=_ICED_PRODUCER,
        source_title="Renewable Energy Potential - Solar (state-wise) API",
        source_vintage=_ASSESSMENT_VINTAGE,
        source_url=_ICED_URL,
        staging_filename="solar_potential_by_state.json",
        keep_sub_sources=("solar @3% wasteland area",),
    ),
    RenewablePotentialSpec(
        indicator_id="wind-potential-mw",
        name="Wind power potential",
        concept_id="wind-energy-potential",
        concept_noun="Wind power potential",
        concept_description=(
            "Modelled maximum wind capacity (MW) a state could build, "
            "estimated by the National Institute of Wind Energy (NIWE) at "
            "150 metres above ground level (the current headline hub height). "
            "This is buildable potential driven by geography (wind corridors, "
            "coastline, terrain), NOT installed capacity and NOT a policy "
            "achievement - a few states with strong wind corridors dominate "
            "the national total."
        ),
        unit="MW",
        unit_canonical="MW",
        normalisation="absolute",
        topic="energy",
        entity_kinds="country state",
        update_period_days=365,
        derivation=None,
        source_producer=_ICED_PRODUCER,
        source_title="Renewable Energy Potential - Wind (state-wise) API",
        source_vintage=_ASSESSMENT_VINTAGE,
        source_url=_ICED_URL,
        staging_filename="wind_potential_by_state.json",
        keep_sub_sources=("wind @150m agl",),
    ),
    RenewablePotentialSpec(
        indicator_id="bio-energy-potential-mw",
        name="Bio-energy potential",
        concept_id="bio-energy-potential",
        concept_noun="Bio-energy potential",
        concept_description=(
            "Modelled maximum bio-energy capacity (MW) a state could build, "
            "summed across the two physically-additive streams the assessment "
            "publishes: agricultural / forestry biomass and bagasse-based "
            "cogeneration at sugar mills. This is buildable potential driven "
            "by a state's crop residue and sugar industry, NOT installed "
            "capacity and NOT a policy achievement."
        ),
        unit="MW",
        unit_canonical="MW",
        normalisation="absolute",
        topic="energy",
        entity_kinds="country state",
        update_period_days=365,
        derivation=(
            "Sum of the biomass and cogeneration-bagasse potential streams "
            "per state (both are additive components of the same buildable "
            "bio-energy capacity)."
        ),
        source_producer=_ICED_PRODUCER,
        source_title="Renewable Energy Potential - Bioenergy (state-wise) API",
        source_vintage=_ASSESSMENT_VINTAGE,
        source_url=_ICED_URL,
        staging_filename="bio_energy_potential_by_state.json",
        keep_sub_sources=("biomass", "cogeneration-bagasse"),
    ),
)


def spec_by_indicator_id(indicator_id: str) -> RenewablePotentialSpec:
    """Return the shipped spec for ``indicator_id`` or raise ``KeyError``."""
    for spec in SHIPPED_SPECS:
        if spec.indicator_id == indicator_id:
            return spec
    raise KeyError(
        f"unknown renewable-potential indicator_id {indicator_id!r}; known: "
        f"{[s.indicator_id for s in SHIPPED_SPECS]}"
    )
