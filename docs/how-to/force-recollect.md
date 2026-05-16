# How to force re-collection of an indicator

**Last Updated**: 2026-05-17
**Audience**: operators with local clone of `yen-gov`.

There is no force-refetch flag in `processing.json`, no CLI option,
and no admin button. By design — see [collection-inventory](../concepts/collection-inventory.md)
and [ADR-0003](../architecture/decisions/0003-no-fetch-cache.md).
`rm` IS the force mechanism.

## Recipe

1. Identify the indicator path:
   ```
   datasets/indicators/in/<topic>/<id>.json
   ```
2. Identify the `.runtime/raw/<source>/...` files the adapter caches
   on its way to that indicator. Most adapters keep their cache under
   `.runtime/raw/<adapter-name>/`.
3. Delete those raw files:
   ```powershell
   Remove-Item .runtime/raw/<adapter-name>/<path-to-files> -Force
   ```
4. Re-run the collector. The pipeline command and module vary by
   indicator (see the adapter's own README under
   `backend/yen_gov/sources/<adapter>/`).
5. Verify:
   ```powershell
   git diff datasets/indicators/in/<topic>/<id>.json
   ```
   If the upstream bytes were identical, `sources[].fetched_at`
   should be **unchanged** (fetch-once-freeze) and only legitimate
   value changes should appear. If `fetched_at` smears across rows
   on a no-op re-run, that is a provenance bug — see
   [data-provenance](../concepts/data-provenance.md) and CLAUDE.md
   §10 anti-patterns.

## Why no flag

A boolean force-refetch flag in config is itself state. State
duplicates state: now you have the indicator file *and* a flag that
says "this indicator wants to be re-collected", and operators have
to remember to clear it. `rm` is unambiguous, leaves no residue, and
already worked.

The `collection_inventory.refetch_requested` flag is **triage status**,
not a second force mechanism. Operators use it to mark "this needs
re-pulling on the next pass" so the team can see the queue; the
planner clears it after a successful re-collect.

## Related

- [collection-inventory](../concepts/collection-inventory.md)
- [folded-indicator](../concepts/folded-indicator.md)
- [ADR-0003 — No fetch cache](../architecture/decisions/0003-no-fetch-cache.md)
