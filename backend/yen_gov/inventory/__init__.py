"""Collection-inventory derivation.

Public entry point: :func:`derive.derive_collection_inventory`.

See `docs/concepts/collection-inventory.md` (added in commit \u00a75.9) and
`TODO/20260517-folded-indicator-and-collection-inventory-handover.md`
\u00a75.4 for the algorithm rationale.
"""

from .derive import derive_collection_inventory, derive_temporal_range

__all__ = ["derive_collection_inventory", "derive_temporal_range"]
