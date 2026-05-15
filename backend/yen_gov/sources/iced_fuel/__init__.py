"""Adapter for the ICED v0 fuel-source consumption + power-purchase family.

Three sibling v0 AES-encrypted endpoints expose state-level fuel
consumption and power-procurement mix:

- ``/energy/fuel-sources/coal/consumption-domestic-state``
  -- per-state coal consumption (Mt) by coal grade.
- ``/energy/fuel-sources/oil/consumptionStateProductTrend``
  -- per-state oil-product consumption (kt) by product
  (diesel, petrol, LPG, kerosene, naphtha, pet-coke, others).
- ``/statelevel-power-purchase-quantum-and-cost``
  -- per-state share (%) of electricity purchased by source
  (coal, hydro, solar, wind, nuclear, gas, etc.).

All three were confirmed by the 2026-05-15 ICED full-triage sweep
(see ``.runtime/iced_recon/full_triage_20260515073024.md``) and reconned
directly via ``tools/iced_fuel_recon.py``.
"""

from .ingest import IngestSummary, ingest_iced_fuel

__all__ = ["IngestSummary", "ingest_iced_fuel"]
