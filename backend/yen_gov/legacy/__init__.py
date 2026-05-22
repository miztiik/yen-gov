"""yen-gov legacy code namespace.

Every module under this package implements behaviour that has a known
retirement path. Each module's docstring names the retirement PR (or
the plan section that gates it). When the gating PR lands and removes
the module's caller integrations, the module deletes with it.

Holy Law #5 (CLAUDE.md): structural fixes only. Legacy code in this
namespace is NOT a band-aid — it is the explicit, time-bound migration
path off a previous contract. Net-new code MUST NOT be added here.

Current residents:
  * folded_indicator_writer — v3.0/v4.0 folded-indicator artifact
    maintenance (methodology / series_spec / divergence carry-forward
    + collection_inventory derivation + operational-strip dict-equal
    write-skip). Retires alongside the canonical pivot of every
    indicator family per TODO/20260517-canonical-long-format-pivot.md
    §0e.7 (Phase 2 P.* PRs). When the last `datasets/indicators/in/<topic>/<id>.json`
    shard is deleted, the legacy call-sites in `core/io.py.write_artifact`
    delete with it and this module follows.
"""
