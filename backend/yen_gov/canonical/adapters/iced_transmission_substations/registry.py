"""ICED transmission-substation list - feed registry.

ONE :class:`TransmissionSubstationSpec` for the ICED transmission-substation
inventory feed. The feed is a single national asset list (no state field), so
the indicator is country-grain only; the analytical detail lives on the
``voltage_class`` facet axis rather than a geography axis.

> **Provenance (D2, ingest plan Row 10/11).** The substation list is an
> ICED-derived rollup (sum of MVA by voltage class) that names no single
> upstream issuing authority, so it is KEPT under the org-led label NITI Aayog
> ICED (``ICED_ORG_PRODUCER``), never the dashboard product name. ``source_id``
> is DERIVED from the (producer, title, vintage) triple, never hand-written.

> **National grain is honest, not a shortcut.** The upstream feed has no state
> attribution, so attributing a substation to a state would be invention. The
> series is therefore ``entity_id = "IN"`` only - a national grid build-out
> indicator - with the build-out detail carried on the voltage_class facet.
"""
from __future__ import annotations

from yen_gov.canonical.iced_authority_map import ICED_ORG_PRODUCER

from .parser import VOLTAGE_CLASSES, TransmissionSubstationSpec

__all__ = ["SHIPPED_SPEC"]

# D2 (ingest plan Row 10): ICED is not a product-name producer. The substation
# list is an ICED-derived rollup (sum of MVA by voltage class) with no single
# upstream authority, so it is KEPT under the org-led label NITI Aayog ICED
# (iced_authority_map decision src-d9484e65a17e).
_ICED_PRODUCER = ICED_ORG_PRODUCER
# Dashboard snapshot edition the operator stages. Bump when staging a newer
# snapshot; source_id re-derives, so the citation ledger tracks it.
_SNAPSHOT_VINTAGE = "2024-25"
# Citizen-openable dashboard landing page (the transmission views live under
# the dashboard; the dashboard root is the stable entry point).
_ICED_URL = "https://iced.niti.gov.in"


SHIPPED_SPEC = TransmissionSubstationSpec(
    indicator_id="substation-capacity-commissioned-mva",
    name="Transmission substation capacity commissioned (MVA)",
    concept_id="substation-capacity-commissioned",
    concept_noun="Transmission substation capacity commissioned",
    concept_description=(
        "Transmission substation capacity commissioned per year, by voltage "
        "class; national. The summed nameplate capacity (MVA) of transmission "
        "substations brought into service each fiscal year, grouped by their "
        "governing (highest) voltage tier. An indicator of grid build-out - "
        "how much high-voltage switching/transformation capacity the country "
        "adds each year. The source carries NO state attribution, so this is a "
        "national-only series; it is NOT installed generation capacity and NOT "
        "a per-state ranking."
    ),
    unit="MVA",
    unit_canonical="MVA",
    normalisation="absolute",
    topic="energy",
    entity_kinds="country",
    update_period_days=365,
    derivation=(
        "Sum of nameplate substation capacity (MVA) commissioned each fiscal "
        "year, grouped by governing voltage class (the highest winding voltage "
        "of each asset, bucketed into hvdc / 765kv / 400kv / 220kv / other). "
        "National only - the feed has no per-state attribution."
    ),
    source_producer=_ICED_PRODUCER,
    source_title="Transmission Substation List API",
    source_vintage=_SNAPSHOT_VINTAGE,
    source_url=_ICED_URL,
    staging_filename="transmission_substation_list.json",
    entity_id="IN",
    facet_column="voltage_class",
    voltage_classes=VOLTAGE_CLASSES,
)
