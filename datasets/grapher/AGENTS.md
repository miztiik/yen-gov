# `datasets/grapher/` — Frontend-owned render catalogue

**Last Updated**: 2026-06-04

> **MIGRATING (2026-06-04).** Per the [CLAUDE.md](../../CLAUDE.md) doctrine-in-migration banner + [the platform-reset plan](../../TODO/20260603-data-and-charting-platform-reset-plan.md), the canonical data this catalogue annotates is moving to long-format CSV under `datasets/data/`, and ADRs are retiring into their subsystem/concept docs (keep-receipts; no new numbered ADR files). The render-catalogue split (render hints separated from canonical data shape) survives the rip; only the storage of the data it points at changes.

This directory holds the **grapher catalogue**: per-indicator and per-(topic, indicator) render hints that were previously inlined into canonical data schemas (`indicator-catalogue.schema.json`, `topic-catalogue.schema.json`, legacy `indicator.schema.json`).

Per [ADR-0045](../../docs/architecture/decisions/0045-grapher-catalogue-split.md) and [docs/concepts/schema-is-the-design-system.md](../../docs/concepts/schema-is-the-design-system.md), visualization choice is a frontend concern and MUST NOT live on the canonical data shape. The grapher catalogue is the dedicated home for `chart_type`, `default_mode`, `renderer_rules[]`, `facet_labels{}`, and per-topic `dimension`.

## Files

- `indicator_render.json` — per-indicator render hints. Validated by [`../schemas/grapher-indicator-render.schema.json`](../schemas/grapher-indicator-render.schema.json).
- `topic_render.json` — per-(topic, indicator) render hints. Validated by [`../schemas/grapher-topic-render.schema.json`](../schemas/grapher-topic-render.schema.json).

## Authoring rules

1. Rows are OPTIONAL. Absence == frontend default for the indicator's `value_kind` + `entity_kind`.
2. **No data fields** (id, unit, etc.) belong here — only render hints. Adding a data field is a contract violation.
3. Hand-authored for now; admin tooling may follow.
4. Frontend reads via `frontend/src/lib/grapher/catalogue.ts`.

## Cross-references

- [ADR-0044](../../docs/architecture/decisions/0044-grain-over-entity.md) — grain-over-entity (sister rip)
- [ADR-0045](../../docs/architecture/decisions/0045-grapher-catalogue-split.md) — why this directory exists
- [CLAUDE.md §10](../../CLAUDE.md) — anti-patterns forbidding render fields on canonical schemas
