"""ICED sub-fuel -> canonical 5-bucket fuel-axis collapse.

Per Hans's D33.8 ruling the canonical energy fuel axis is a closed
5-bucket enum ``{coal, gas, hydro, nuclear, renewable}`` (the
``geo_by_fuel/*.csv`` ``fuel_type`` enum adds ``all`` for the published
aggregate member). ICED ships finer-grained source labels (kebab-case:
``small-hydro``, ``oil-gas``, ``bio-power``, ``solar``, ``wind``,
``waste-to-energy`` ...) that must collapse onto those 5 buckets at emit
time so the faceted installed-capacity CSVs stay enum-conformant.

This map was originally ``canonical/adapters/energy/_shared.py:SUB_FUEL_TO_CANONICAL``;
that module was deleted in the X1b parquet-writer-chain retirement
(commit ``8ea74f243``). It is restored here verbatim as a small, tested,
ICED-scoped helper (the CEA adapter maps its workbook fuel COLUMNS to
canonical buckets directly and does not need this label map).
"""

from __future__ import annotations

# Canonical 5-bucket fuel ordering (Hans D33.8). The ``all`` published
# aggregate member of the geo_by_fuel enum is NOT in this tuple -- it is
# the publisher total, derived separately, never a render-time sum.
CANONICAL_FUELS: tuple[str, ...] = ("coal", "gas", "hydro", "nuclear", "renewable")

# ICED upstream source label -> canonical 5-bucket fuel_type. Recovered
# verbatim from 8ea74f243^:backend/yen_gov/canonical/adapters/energy/_shared.py.
SUB_FUEL_TO_CANONICAL: dict[str, str] = {
    "coal": "coal",
    "hydro": "hydro",  # ICED "Hydro" = large hydro (> 25 MW)
    "nuclear": "nuclear",
    "oil-gas": "gas",  # ICED labelling: gas + diesel + furnace oil
    "gas": "gas",  # CEA per-fuel shard already uses "gas"
    "renewable": "renewable",  # CEA per-fuel shard already uses "renewable"
    # Renewables -- collapse to the 5-bucket "renewable" canonical.
    "wind": "renewable",
    "solar": "renewable",
    "small-hydro": "renewable",
    "bio-power": "renewable",
    "biomass": "renewable",
    "waste-to-energy": "renewable",
}


class UnknownFuelLabelError(KeyError):
    """An ICED source label outside the known collapse map.

    Raised (rather than silently dropped) so a new upstream fuel label
    surfaces as a hard boundary failure for a Hans+Max disposition,
    never an undercount on the faceted total.
    """


def collapse_fuel(label: str) -> str:
    """Return the canonical 5-bucket ``fuel_type`` for an ICED source label.

    Args:
        label: ICED source string, kebab-case as ICED ships it
            (``small-hydro``, ``oil-gas`` ...).

    Raises:
        UnknownFuelLabelError: ``label`` is not in ``SUB_FUEL_TO_CANONICAL``.
            Fail fast at the boundary -- a new sub-fuel is a data-shape
            decision (CLAUDE.md section 0a), not a silent drop.
    """
    try:
        return SUB_FUEL_TO_CANONICAL[label]
    except KeyError as exc:
        raise UnknownFuelLabelError(
            f"unknown ICED fuel label {label!r}; not in SUB_FUEL_TO_CANONICAL. "
            f"Adding a new sub-fuel is a Hans+Max data-shape call per "
            f"CLAUDE.md section 0a, not a mechanical map edit."
        ) from exc
