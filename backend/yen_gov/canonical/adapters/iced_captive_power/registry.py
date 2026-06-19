"""ICED captive-power - feed registry.

Two :class:`CaptivePowerSpec` rows, one per measure (capacity, generation).
Both read the SAME staged feed (``captive_power_industry.json``) and share the
SAME provenance triple, so the citation ledger carries ONE source row for the
pair; they differ only in which column the parser sums and in their identity /
unit.

> **One card per measure, not per industry.** The feed breaks captive power
> out across 22 industry categories (Aluminium, Cement, Iron & Steel, ...).
> Those are NOT republished as 22 separate indicators (Hans: no fragmentation)
> - the emitter sums them into a single state total per measure. The industry
> dimension is dropped.

> **Provenance (D2, ingest plan Row 10/11).** The underlying returns are the
> Central Electricity Authority's (CEA) captive generating-plant survey, so
> this is a passthrough: ``source_producer`` names the CEA issuing authority
> and the ICED access surface moves into the ``source_title`` (via
> ``VIA_ICED_SUFFIX``). ``source_id`` is DERIVED from the (producer, title,
> vintage) triple, never hand-written.
"""
from __future__ import annotations

from yen_gov.canonical.iced_authority_map import VIA_ICED_SUFFIX

from .parser import CaptivePowerSpec

__all__ = ["SHIPPED_SPECS", "spec_by_indicator_id"]

# D2 (ingest plan Row 10): the underlying returns are the CEA captive-generating
# plant survey (a passthrough), so the producer is the issuing authority and the
# ICED access surface moves into the title via VIA_ICED_SUFFIX (iced_authority_map
# decision src-3d0b1c141f6a). Shared across both measures (one source row).
_ICED_PRODUCER = "Central Electricity Authority"
_SOURCE_TITLE = "Captive Power (industry-wise) State-wise API" + VIA_ICED_SUFFIX
# Access edition the operator stages. Bump when staging a newer edition;
# source_id re-derives, so the citation ledger tracks it.
_VINTAGE = "2024-25"
# Citizen-openable dashboard landing page.
_ICED_URL = "https://iced.niti.gov.in"

# Captive power is self-reported by industry to the CEA and is widely
# understood to be under-reported; both descriptions carry this honesty cue.
_SELF_REPORT_CAVEAT = (
    "Self-reported by industry to the Central Electricity Authority (CEA) and "
    "widely understood to be under-reported, so read the totals as a lower "
    "bound, not a precise census. The all-India aggregate row and the source's "
    "combined 'Jammu and Kashmir and Ladakh' label (which cannot be split "
    "across the two post-2019 entities) are not included."
)


SHIPPED_SPECS: tuple[CaptivePowerSpec, ...] = (
    CaptivePowerSpec(
        indicator_id="captive-power-capacity-mw",
        name="Captive power capacity",
        concept_id="captive-power-capacity",
        concept_noun="Captive power capacity",
        concept_description=(
            "Installed capacity (MW) of captive power plants - generation that "
            "industry builds and runs behind the meter for its own use, summed "
            "across all industry categories in a state. A high captive total "
            "often signals industry routing around an unreliable or expensive "
            "public grid by self-generating, rather than a policy achievement. "
            + _SELF_REPORT_CAVEAT
        ),
        unit="MW",
        unit_canonical="MW",
        normalisation="absolute",
        topic="energy",
        entity_kinds="state",
        update_period_days=365,
        derivation=(
            "Sum of self-reported captive power capacity (MW) across all 22 "
            "industry categories per state and year; the industry dimension is "
            "dropped. stateWise rows only (the national fuel-mix 'sourceWise' "
            "rows are ignored)."
        ),
        source_producer=_ICED_PRODUCER,
        source_title=_SOURCE_TITLE,
        source_vintage=_VINTAGE,
        source_url=_ICED_URL,
        staging_filename="captive_power_industry.json",
        measure="capacity",
    ),
    CaptivePowerSpec(
        indicator_id="captive-power-generation-gwh",
        name="Captive power generation",
        concept_id="captive-power-generation",
        concept_noun="Captive power generation",
        concept_description=(
            "Electricity generated (GWh) by captive power plants - the energy "
            "industry produces behind the meter for its own use, summed across "
            "all industry categories in a state. High captive generation often "
            "signals industry self-supplying because the public grid is "
            "unreliable or costly. The CEA reports this in Million Units (MU); "
            "1 MU equals 1 GWh exactly, so the values are unchanged under the "
            "GWh label. " + _SELF_REPORT_CAVEAT
        ),
        unit="GWh",
        unit_canonical="GWh",
        normalisation="absolute",
        topic="energy",
        entity_kinds="state",
        update_period_days=365,
        derivation=(
            "Sum of self-reported captive power generation across all 22 "
            "industry categories per state and year; the industry dimension is "
            "dropped. The CEA reports in Million Units (1 MU = 1 GWh), emitted "
            "unchanged as GWh. stateWise rows only (the national fuel-mix "
            "'sourceWise' rows are ignored)."
        ),
        source_producer=_ICED_PRODUCER,
        source_title=_SOURCE_TITLE,
        source_vintage=_VINTAGE,
        source_url=_ICED_URL,
        staging_filename="captive_power_industry.json",
        measure="generation",
    ),
)


def spec_by_indicator_id(indicator_id: str) -> CaptivePowerSpec:
    """Return the shipped spec for ``indicator_id`` or raise ``KeyError``."""
    for spec in SHIPPED_SPECS:
        if spec.indicator_id == indicator_id:
            return spec
    raise KeyError(
        f"unknown captive-power indicator_id {indicator_id!r}; known: "
        f"{[s.indicator_id for s in SHIPPED_SPECS]}"
    )
