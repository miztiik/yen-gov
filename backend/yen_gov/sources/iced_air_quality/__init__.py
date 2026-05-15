"""yen-gov ICED air-quality adapter (Phase A, Wave 1).

Owns two indicators today:

  ``environment/state_thermal_fgd_installed_share_pct``
      Share of each state's coal thermal capacity (MW) that has actually
      installed flue-gas desulphurisation, against the MoEF&CC's 2015
      directive. Snapshot from ICED's `/air-quality/fgd` endpoint.

  ``environment/state_pm25_annual_mean_ug_m3``
      Per (state, year), unweighted arithmetic mean of CPCB station-year
      annual means for PM2.5. NO2 / SO2 / PM10 follow as mechanical
      derivations from the same markers feed.

Sequencing (per Hans + Fowler, 2026-05-15) — FGD ships first because it
is the cleanest air-quality governance metric (named policy, observed
asset count, no monitor-density argument). PM2.5 follows because it is
the highest-salience health metric, but ships with the
`not_comparable_across_states` honesty flag set so the chart suppresses
state ranking (CPCB monitors are urban-biased and unevenly distributed).

Provenance discipline: ICED is a re-publisher of CEA/MoEF&CC/CPCB data;
every artifact this package emits MUST list both the ICED API URL we
fetched and the upstream authority URL. See :mod:`.parsers` and
:mod:`.markers_parsers` for rationale.

Public surface:

- :func:`parsers.extract_state_rows`               — FGD pure parser.
- :func:`ingest.ingest_fgd`                        — FGD fetch + write.
- :func:`markers_parsers.aggregate_state_year_mean` — markers parser.
- :func:`markers_ingest.ingest_pm25`               — PM2.5 fetch + write.
"""

from .markers_parsers import (
    COVID_GAP_YEAR,
    NO2_FIELD,
    PM10_FIELD,
    PM25_FIELD,
    SO2_FIELD,
    StateYearMean,
    aggregate_state_year_mean,
)
from .parsers import (
    FGD_INSTALLED_STATUS,
    ParsedRow,
    emit_indicator_rows,
    extract_state_rows,
)

__all__ = (
    "FGD_INSTALLED_STATUS",
    "ParsedRow",
    "emit_indicator_rows",
    "extract_state_rows",
    "StateYearMean",
    "aggregate_state_year_mean",
    "PM25_FIELD",
    "NO2_FIELD",
    "SO2_FIELD",
    "PM10_FIELD",
    "COVID_GAP_YEAR",
)
