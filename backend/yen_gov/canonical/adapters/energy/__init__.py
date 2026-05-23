"""Energy adapter — lifts legacy ``datasets/indicators/in/energy/*.json``
shards into BatchEnvelopes for the canonical Parquet store.

P.1.A C4 first-cut: 4 fact-tables emit data (plan-doc TODO row 0e.7 P.1):

* ``energy_installed_capacity``      — CEA per-fuel + ICED geographical +
                                       ICED allocated (parent totals).
* ``energy_generation``              — ICED per-state per-FY generation
                                       (publisher total + per-fuel breakdown).
* ``energy_demand_supply``           — RBI peak demand / peak met +
                                       ICED per-capita consumption.
* ``energy_distribution_performance`` — ICED ATC losses + sales-MU.

A 5th planned stem ``energy_fuel_consumption`` is reserved for P.1.C and
ships empty (no P.1.A indicators sit on it yet).

D33.8 invariant (compute-on-read totals): the adapter NEVER emits an
observation row whose ``indicator_id`` matches ``*-total-mw`` or
``*-thermal-mw``. The all-fuel totals are computed on-read in the frontend
from the per-fuel children — that is how methodology breaks
(mnre-offgrid-inclusion-2021-08, cea-coal-aggregate-proxy-fy22) stay
auditable instead of hidden inside a single aggregate. See
``datasets/taxonomy/methodology_breaks.json``.

Sub-fuel collapse: ICED publishes 7-9 sub-fuel buckets (bio-power, solar,
wind, small-hydro, waste-to-energy, oil-gas, large-hydro, ...). The
catalogue narrows to 5 canonical fuels per Hans' D33.8: coal, gas, hydro,
nuclear, renewable. The renewable child is the SUM of bio-power,
small-hydro, solar, wind, waste-to-energy — derivation="sum" on those
rows so a downstream consumer can read the sub-fuel resolution loss
explicitly. P.1.C may extend ``facet_axes_seed.py:fuel_type`` with new
canonical leaves; until then five-bucket is the contract.

The 9 attribution_geography defects called out in plan-doc TODO row 0e.7
P.1 §5 live in the LEGACY JSON shards' ``indicator.attribution_geography``
field, not in the canonical catalogue (``datasets/taxonomy/indicators.json``).
The catalogue is correctly authored per Hans (C1 PR `6f2c1cf2`); this
adapter uses the catalogue value, never the shard's tag. The 9 shard-tag
defects become moot at C6 (legacy-shard deletion). See commit message.

Hans+Max (data shape) + Gregor (contract) authorities apply per
CLAUDE.md §0a.
"""

from __future__ import annotations

from pathlib import Path

from yen_gov.canonical.envelope import BatchEnvelope

from .demand_supply import build_envelope as _build_demand_supply
from .distribution import build_envelope as _build_distribution
from .generation import build_envelope as _build_generation
from .installed_capacity import build_envelope as _build_installed_capacity


def build_envelopes(repo_root: Path) -> list[BatchEnvelope]:
    """Build the 4 P.1.A envelopes in canonical write-order.

    Write-order is alphabetical-by-stem (matches manifest enumeration
    order) and has no FK dependency between envelopes — each emits to a
    distinct ``energy_*`` parquet and shares only the cross-family
    ``sources.parquet`` (which C3 already seeded via `_upsert_energy_sources`).
    """
    return [
        _build_demand_supply(repo_root),
        _build_distribution(repo_root),
        _build_generation(repo_root),
        _build_installed_capacity(repo_root),
    ]
