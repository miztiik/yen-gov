"""Fuel-type enum guard — every fuel-faceted indicator_id on the energy
fact-tables MUST suffix-encode one of the canonical 5 buckets:
``{coal, gas, hydro, nuclear, renewable}`` (Hans D33.8 ruling).

Sub-fuel labels (wind / solar / small-hydro / bio-power / waste-to-energy /
oil-gas / etc.) MUST have been collapsed by the adapter via
``SUB_FUEL_TO_CANONICAL`` in ``adapters/energy/_shared.py``. Catching a
``-solar`` or ``-oil-gas`` indicator_id at this layer means a sub-fuel
escaped the collapse and the catalogue / renderer expectations are
broken.

The test recognises a "fuel suffix" by matching the trailing segment
against the catalogue's atomic-fuel set. Indicator IDs with no fuel
suffix (e.g. ``state-peak-electricity-demand-mw``) are unaffected.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ENERGY_DIR = REPO_ROOT / "datasets" / "energy"

# Hans D33.8 canonical 5-bucket fuel axis. Mirrored from
# adapters/energy/_shared.py:CANONICAL_FUELS.
CANONICAL_FUELS = {"coal", "gas", "hydro", "nuclear", "renewable"}

# Stems that carry fuel-faceted indicators (installed_capacity +
# generation). Demand-supply + distribution-performance are
# scalar-only; no fuel suffix expected.
FUEL_FACETED_STEMS = ["energy_installed_capacity", "energy_generation"]


pytestmark = pytest.mark.skipif(
    not all((ENERGY_DIR / f"{s}.parquet").is_file() for s in FUEL_FACETED_STEMS),
    reason=(
        "energy fact-table parquets not on disk; "
        "run `python -m yen_gov lift-energy --root .` first"
    ),
)


@pytest.mark.parametrize("stem", FUEL_FACETED_STEMS)
def test_every_fuel_suffix_is_canonical(stem: str) -> None:
    """For every indicator_id whose trailing hyphen-segment matches a
    sub-fuel candidate, that segment MUST be in the canonical 5. Catches
    any leak of ICED sub-fuel labels (solar / wind / small-hydro / etc.)
    or typos.

    EXCEPTION (PR-V, 2026-05-26): percentage-valued fuel-faceted
    indicators (e.g. state-plant-load-factor-pct-*) MUST NOT collapse
    sub-fuels into 'renewable' — summing per-fuel PLF percentages is
    meaningless. PR-V uses a dedicated 1:1 publisher-to-canonical map
    (_PLF_PUBLISHER_TO_CANONICAL_FUEL) mapping bio-power -> biomass,
    small-hydro -> small-hydro, oil-gas -> gas, etc. The exempt prefix
    list below enumerates these intentional exceptions.
    """
    parquet = ENERGY_DIR / f"{stem}.parquet"
    con = duckdb.connect(":memory:")
    try:
        indicators = sorted({
            row[0]
            for row in con.execute(
                f"SELECT DISTINCT indicator_id FROM read_parquet('{parquet.as_posix()}')"
            ).fetchall()
        })
    finally:
        con.close()

    # Candidate fuels are listed from the union of (a) canonical 5,
    # (b) sub-fuel labels that the collapse map should have dropped.
    # Mirrored from SUB_FUEL_TO_CANONICAL keys.
    sub_fuel_leak_candidates = {
        "solar", "wind", "small-hydro", "bio-power", "biomass",
        "waste-to-energy", "oil-gas", "lignite", "diesel", "others",
    }
    # PR-V exemption: percentage-valued fuel-faceted indicator stems
    # where collapsing sub-fuels would compute meaningless aggregates.
    # Any indicator whose id begins with one of these prefixes is
    # ALLOWED to carry a sub-fuel suffix (biomass / small-hydro / etc.)
    # without triggering this guard.
    sub_fuel_exempt_prefixes = (
        "state-plant-load-factor-pct-",  # PR-V (percentage; cannot sum across fuels)
    )
    leaks: list[tuple[str, str]] = []
    for ind in indicators:
        if ind.startswith(sub_fuel_exempt_prefixes):
            continue
        # Split off the trailing segment; the catalogue's convention is
        # one hyphen separator before the fuel suffix on per-fuel children
        # (e.g. ``electricity-generation-gwh-coal``).
        last = ind.rsplit("-", 1)[-1]
        if last in sub_fuel_leak_candidates:
            leaks.append((ind, last))
    assert not leaks, (
        f"{stem}.parquet leaks sub-fuel labels into indicator_id: {leaks!r}. "
        f"Adapter must collapse via SUB_FUEL_TO_CANONICAL in adapters/energy/_shared.py."
    )


@pytest.mark.parametrize("stem", FUEL_FACETED_STEMS)
def test_canonical_fuel_renewable_is_present(stem: str) -> None:
    """Sanity: every fuel-faceted stem MUST emit at least one
    ``-renewable`` indicator (the collapse target for the
    multi-sub-fuel renewables aggregate). If absent, the collapse
    failed silently."""
    parquet = ENERGY_DIR / f"{stem}.parquet"
    con = duckdb.connect(":memory:")
    try:
        n = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{parquet.as_posix()}') "
            f"WHERE indicator_id LIKE '%-renewable'"
        ).fetchone()[0]
    finally:
        con.close()
    assert n > 0, (
        f"{stem}.parquet has ZERO ``*-renewable`` rows — the canonical 5-bucket "
        f"collapse silently dropped every renewable sub-fuel input."
    )
