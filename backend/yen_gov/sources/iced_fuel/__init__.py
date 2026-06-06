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

The legacy network-fetch + folded-indicator-JSON orchestrator
(``ingest_iced_fuel`` + ``IngestSummary``) was retired in B4-pt2.1 per
parent plan section 21.4. The B1.4.3 canonical CSV emission stays under
``.ingest`` (exercised by ``backend/tests/test_iced_fuel_csv_repoint.py``).
"""

from .ingest import IndicatorEmitResult

__all__ = ["IndicatorEmitResult"]
