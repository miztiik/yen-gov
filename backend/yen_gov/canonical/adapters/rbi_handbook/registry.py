"""RBI Handbook of Statistics on Indian States - table registry.

One :class:`HbsTableSpec` per Handbook table. Adding a new table (this
section or any future one - State Domestic Product, Fiscal, Banking,
Prices) means appending one spec here; the parser, resolver, emitter,
and CLI are unchanged. That is the "reusable across RBI stats" property
the tool is built for.

> **Provenance doctrine (Holy Law #9, Hans + Max verdict).** RBI is a
> *republisher* of these vital statistics; the issuing authority is the
> SRS / Office of the Registrar General & Census Commissioner (ORGI).
> So ``source_producer`` names ORGI/SRS (source-of-origin) and
> ``source_title`` names the RBI Handbook as the machine-readable access
> surface. ``source_id`` is DERIVED from the triple, never hand-written.

> **No fragmentation (user directive 2026-06-16).** Each measure is ONE
> file. The vital rates are naturally single-series. Life Expectancy is
> published as Male / Female / Total under each multi-year window; the
> spec keeps only the Total band (``value_sub_label="Total"``) so it is
> one comparable series, not three fragmented files. A male/female facet
> is a deferred Hans + Max decision (facet column vs sibling file-class),
> NOT three more files.

First cohort = the SRS annual vital rates the user asked for (fertility
+ the cheapest honest companions) plus Life Expectancy. Census-decadal
structural items (literacy, sex ratio, density, decadal growth) and the
methodology-unstable Poverty Rate are deliberately deferred per the
Hans + Max indicator-set verdict (see the plan-doc).
"""
from __future__ import annotations

from .parser import (
    TIME_CALENDAR_YEAR,
    TIME_INTERVAL_WINDOW_END,
    HbsTableSpec,
)

__all__ = ["SHIPPED_SPECS", "spec_by_indicator_id"]

# Source-of-origin agencies (NOT "RBI"; RBI is the access surface).
_SRS_PRODUCER = "Office of the Registrar General & Census Commissioner, India"
_SRS_VITAL_TITLE = (
    "Sample Registration System (via RBI Handbook of Statistics on "
    "Indian States)"
)
_SRS_LIFE_TABLE_TITLE = (
    "SRS Abridged Life Tables (via RBI Handbook of Statistics on "
    "Indian States)"
)
# RBI Handbook edition the operator stages. Bump when staging a newer
# edition; source_id re-derives, so the citation ledger tracks the edition.
_HBS_EDITION = "2024-25"
_SRS_URL = "https://censusindia.gov.in/census.website/data/SRSSTAT"
_SRS_LIFE_URL = "https://censusindia.gov.in/census.website/data/SRSALT"

# Aggregate / footnote labels RBI prints below the state block; dropped so
# the resolver does not raise on them. Prefix-matched (parser._is_skip), so
# 'Source: SRS 2024' and 'Notes on the table' are covered. NOTE: the
# all-India row ('All India' / 'India') is NOT skipped - it resolves to the
# country entity 'IN' and is kept (entity_kinds includes country).
_COMMON_SKIP = (
    "All States and UTs",
    "All States/UTs",
    "Note",
    "Notes",
    "Source",
    "Figures",
    "Provisional",
)


SHIPPED_SPECS: tuple[HbsTableSpec, ...] = (
    HbsTableSpec(
        indicator_id="total-fertility-rate",
        name="Total fertility rate",
        concept_id="total-fertility-rate",
        concept_noun="Total fertility rate",
        concept_description=(
            "Average number of children a woman would bear if she "
            "experienced current age-specific fertility rates through her "
            "reproductive life. About 2.1 is replacement level; lower or "
            "higher is a stage of the demographic transition, not a "
            "governance score."
        ),
        unit="children per woman",
        unit_canonical="children per woman",
        normalisation="ratio",
        topic="health",
        entity_kinds="country state",
        update_period_days=365,
        source_producer=_SRS_PRODUCER,
        source_title=_SRS_VITAL_TITLE,
        source_vintage=_HBS_EDITION,
        source_url=_SRS_URL,
        staging_filename="table-total-fertility-rate.xlsx",
        time_kind=TIME_CALENDAR_YEAR,
        skip_labels=_COMMON_SKIP,
        all_india_labels=("All India", "All-India", "India"),
    ),
    HbsTableSpec(
        indicator_id="crude-birth-rate-per-1000",
        name="Birth rate (per 1,000)",
        concept_id="crude-birth-rate",
        concept_noun="Crude birth rate",
        concept_description=(
            "Live births per 1,000 mid-year population in a calendar year, "
            "as estimated by the Sample Registration System. Falls "
            "naturally with development; read alongside fertility, not as a "
            "standalone ranking."
        ),
        unit="per 1,000 population",
        unit_canonical="per 1,000 population",
        normalisation="ratio",
        topic="demography",
        entity_kinds="country state",
        update_period_days=365,
        source_producer=_SRS_PRODUCER,
        source_title=_SRS_VITAL_TITLE,
        source_vintage=_HBS_EDITION,
        source_url=_SRS_URL,
        staging_filename="table-birth-rate.xlsx",
        time_kind=TIME_CALENDAR_YEAR,
        skip_labels=_COMMON_SKIP,
        all_india_labels=("All India", "All-India", "India"),
    ),
    HbsTableSpec(
        indicator_id="crude-death-rate-per-1000",
        name="Death rate (per 1,000)",
        concept_id="crude-death-rate",
        concept_noun="Crude death rate",
        concept_description=(
            "Deaths per 1,000 mid-year population in a calendar year (SRS). "
            "NOT age-standardised: a state with an older population can show "
            "a higher crude death rate despite better health, so a naive "
            "'lowest wins' ranking is misleading. Pair with infant "
            "mortality and life expectancy."
        ),
        unit="per 1,000 population",
        unit_canonical="per 1,000 population",
        normalisation="ratio",
        topic="demography",
        entity_kinds="country state",
        update_period_days=365,
        source_producer=_SRS_PRODUCER,
        source_title=_SRS_VITAL_TITLE,
        source_vintage=_HBS_EDITION,
        source_url=_SRS_URL,
        staging_filename="table-death-rate.xlsx",
        time_kind=TIME_CALENDAR_YEAR,
        skip_labels=_COMMON_SKIP,
        all_india_labels=("All India", "All-India", "India"),
    ),
    HbsTableSpec(
        indicator_id="infant-mortality-rate-per-1000",
        name="Infant mortality rate (per 1,000 live births)",
        concept_id="infant-mortality-rate",
        concept_noun="Infant mortality rate",
        concept_description=(
            "Infant (under-1) deaths per 1,000 live births in a calendar "
            "year (SRS). A core health-system outcome; lower is better and "
            "the measure is broadly comparable across states."
        ),
        unit="per 1,000 live births",
        unit_canonical="per 1,000 live births",
        normalisation="ratio",
        topic="health",
        entity_kinds="country state",
        update_period_days=365,
        source_producer=_SRS_PRODUCER,
        source_title=_SRS_VITAL_TITLE,
        source_vintage=_HBS_EDITION,
        source_url=_SRS_URL,
        staging_filename="table-infant-mortality-rate.xlsx",
        time_kind=TIME_CALENDAR_YEAR,
        skip_labels=_COMMON_SKIP,
        all_india_labels=("All India", "All-India", "India"),
    ),
    HbsTableSpec(
        indicator_id="life-expectancy-at-birth-years",
        name="Life expectancy at birth (years)",
        concept_id="life-expectancy-at-birth",
        concept_noun="Life expectancy at birth",
        concept_description=(
            "Average number of years a newborn would live if current "
            "age-specific mortality held through life (SRS Abridged Life "
            "Tables). Published for overlapping multi-year windows, so a "
            "point labelled 2020-2024 is a five-year-window estimate, not a "
            "single-year value; the window appears in the source vintage."
        ),
        # The normalisation enum [absolute, per_capita, per_area, share,
        # ratio, index] has no clean home for a duration in years; `ratio`
        # is the least-wrong fit. Whether to widen the enum (e.g. a
        # `duration` value) is a deferred Hans + Max concepts.csv call.
        unit="years",
        unit_canonical="years",
        normalisation="ratio",
        topic="health",
        entity_kinds="country state",
        update_period_days=365,
        source_producer=_SRS_PRODUCER,
        source_title=_SRS_LIFE_TABLE_TITLE,
        source_vintage=_HBS_EDITION,
        source_url=_SRS_LIFE_URL,
        staging_filename="table-life-expectancy.xlsx",
        time_kind=TIME_INTERVAL_WINDOW_END,
        # Life Expectancy is Male / Female / Total under each window; keep
        # only the Total band so the series is one file, not three.
        value_sub_label="Total",
        skip_labels=_COMMON_SKIP,
        all_india_labels=("All India", "All-India", "India"),
    ),
)


def spec_by_indicator_id(indicator_id: str) -> HbsTableSpec:
    """Return the shipped spec for ``indicator_id`` or raise ``KeyError``."""
    for spec in SHIPPED_SPECS:
        if spec.indicator_id == indicator_id:
            return spec
    raise KeyError(
        f"no RBI Handbook spec for indicator_id {indicator_id!r}; "
        f"known: {[s.indicator_id for s in SHIPPED_SPECS]}"
    )
