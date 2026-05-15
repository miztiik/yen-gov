"""yen-gov ICED air-quality adapter (Phase A, Wave 1).

Owns one indicator today:

  ``environment/state_thermal_fgd_installed_share_pct``
      Share of each state's coal thermal capacity (MW) that has actually
      installed flue-gas desulphurisation, against the MoEF&CC's 2015
      directive. Snapshot from ICED's `/air-quality/fgd` endpoint.

Sequencing (per Hans + Fowler, 2026-05-15) — FGD ships first because it
is the cleanest air-quality governance metric (named policy, observed
asset count, no monitor-density argument). PM2.5 from the NAMP station
file follows in a separate commit.

Provenance discipline: ICED is a re-publisher of CEA/MoEF&CC data; every
artifact this package emits MUST list both the ICED API URL we fetched
and the upstream policy URL. See :mod:`.parsers` for rationale.

Public surface:

- :func:`parsers.extract_state_rows` — pure parser, fixture-testable.
- :func:`ingest.ingest_fgd`           — fetch + parse + write artifact.
"""

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
)
