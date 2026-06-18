"""ICED ICE-vs-EV (VAHAN) registrations - feed registry.

One :class:`EvShareSpec` for the state-wise EV-share indicator. The registry
shape mirrors the renewable-potential adapter so a future VAHAN-derived feed
(e.g. a vehicle-category-specific EV share) is one appended spec, no parser
edit.

> **Provenance.** The ICED dashboard is the machine-readable access surface
> (and the publisher of the harmonised series); ``source_producer`` names the
> NITI Aayog India Climate & Energy Dashboard, matching the rest of the ICED
> indicator family. The underlying registration counts originate from the
> Ministry of Road Transport & Highways VAHAN portal (named in the concept
> description). ``source_id`` is DERIVED from the (producer, title, vintage)
> triple, never hand-written.

> **Share, not absolute (Hans verdict).** The indicator is the EV SHARE of new
> registrations, not the absolute EV count. Absolute counts just track market
> size; the share is the cross-state-comparable transition signal.
"""
from __future__ import annotations

from .parser import EvShareSpec

__all__ = ["SHIPPED_SPECS", "spec_by_indicator_id"]

# The ICED dashboard is the publisher / access surface (matches the producer
# string used across the ICED indicator family).
_ICED_PRODUCER = "NITI Aayog India Climate & Energy Dashboard"
# Publisher edition tag the operator staged. Bump when staging a newer edition;
# source_id re-derives, so the citation ledger tracks it.
_FEED_VINTAGE = "2024-25"
# Citizen-openable dashboard landing page (the stable entry point).
_ICED_URL = "https://iced.niti.gov.in"


SHIPPED_SPECS: tuple[EvShareSpec, ...] = (
    EvShareSpec(
        indicator_id="ev-share-of-registrations-pct",
        name="EV share of new vehicle registrations",
        concept_id="ev-registration-share",
        concept_noun="EV registration share",
        concept_description=(
            "Share of newly-registered vehicles that are electric, in percent "
            "- the EV-transition signal. For each state and year, the count of "
            "newly-registered electric vehicles (all vehicle categories) "
            "divided by the count of ALL newly-registered vehicles. This is a "
            "share of NEW registrations in the year, NOT the share of vehicles "
            "on the road; the on-road stock turns over slowly, so the stock "
            "share lags this flow share by years."
        ),
        unit="%",
        unit_canonical="%",
        normalisation="share",
        topic="energy",
        entity_kinds="state",
        update_period_days=365,
        derivation=(
            "Per (state, year): 100 * sum(VAHAN new registrations with "
            "fuelCategory = 'Electric Vehicle') / sum(VAHAN new registrations "
            "across all fuelCategory), summed over all vehicle categories. "
            "Cells with zero total registrations are dropped."
        ),
        source_producer=_ICED_PRODUCER,
        source_title="ICE vs EV (VAHAN) State-wise API",
        source_vintage=_FEED_VINTAGE,
        source_url=_ICED_URL,
        staging_filename="ice_ev_vahan.json",
        electric_fuel_categories=("Electric Vehicle",),
    ),
)


def spec_by_indicator_id(indicator_id: str) -> EvShareSpec:
    """Return the shipped spec for ``indicator_id`` or raise ``KeyError``."""
    for spec in SHIPPED_SPECS:
        if spec.indicator_id == indicator_id:
            return spec
    raise KeyError(
        f"unknown EV-share indicator_id {indicator_id!r}; known: "
        f"{[s.indicator_id for s in SHIPPED_SPECS]}"
    )
