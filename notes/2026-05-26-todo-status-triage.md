# TODO status triage - 2026-05-26

Sidecar capturing 14 plan-docs under `TODO/` whose ship status was unclear
during the 2026-05-26 boundary cleanup pass. Each is flagged for follow-up
audit by a future maintainer or by the Explore subagent. NOT authoritative -
this is a working note.

Context: the May 2026 boundary phases (A through D.6) shipped via PRs #263,
#273, #288, #289 and friends; the docs-decomposition pass (this PR) lifted
the recurring "why polygons / why not GADM / why DIGIPIN deferred / why no
topographic raster / what TopoJSON is and is not" rationale into
[docs/concepts/boundary-data-philosophy.md](../docs/concepts/boundary-data-philosophy.md).
That work surfaced a backlog of older plan-docs that may already be shipped
or may be partial; this note enumerates them for a future cleanup pass.

## Status-unclear plan-docs

Action verb glossary:
- **AUDIT** -- verify whether already shipped (grep main for cited commits,
  cross-check against `docs/architecture/` for absorbed scope).
- **ARCHIVE** -- if confirmed shipped, `git mv` to `docs/archive/<date>-<slug>.md`
  with a top-of-file `Status: Shipped on <date> via <sha>; archived for history`
  stanza.
- **UPDATE** -- if partially shipped, edit open scope-block to reflect
  remaining work; promote unshipped slices to a fresh plan-doc with a
  fresh date prefix.
- **CLOSE** -- if blocked / dead / superseded, edit top to
  `Status: Closed -- <one-line reason>` and `git mv` to `docs/archive/`.

| # | Plan-doc | Recommended action | Notes |
|---|---|---|---|
| 1 | TODO/20260515-health-ingest-handover.md | AUDIT then ARCHIVE if shipped | Health family work has been active since May; ingest may be fully covered. |
| 2 | TODO/20260515-iced-aq-no2-so2-pm10-handover.md | AUDIT then ARCHIVE | AQ pollutants likely landed via ICED bulk-ingest path. |
| 3 | TODO/20260515-state-page-ia-rework-plan.md | AUDIT against `/s/<state>` route; may be ADR-superseded | StateOverview + StateTopic IA has shipped; this plan may be the historical anchor. |
| 4 | TODO/20260516-expected-geographies-audit.md | AUDIT | Coverage subsystem may have absorbed the audit. |
| 5 | TODO/20260516-inventory-lift-followups.md | AUDIT | Meadow-tier ADR-0041 may have absorbed the lift follow-ups. |
| 6 | docs/archive/plans/20260517-canonical-long-format-pivot.md | AUDIT | Canonical-store v3 + observations table likely closes this. |
| 7 | TODO/20260517-coverage-temporal-range-plan.md | AUDIT | `/data-completeness` route may already render this. |
| 8 | TODO/20260517-iced-bulk-ingest-and-parity-oracle.md | AUDIT | ICED bulk-ingest landed; parity oracle status unclear. |
| 9 | TODO/20260517-iced-country-entity-series-blocked.md | AUDIT | Confirm if the blocker still holds. |
| 10 | TODO/20260517-indicator-corpus-survey.md | AUDIT against current `/data-completeness` | Indicator inventory may have moved into the topics catalogue. |
| 11 | TODO/20260517-tcpd-tn-ae-people-sidecar-plan.md | AUDIT | TCPD TN AE landed via PR #193; people sidecar status unclear. |
| 12 | TODO/20260518-browser-governance-insight-assistant-plan.md | AUDIT - YENASK ADR-0040 likely covers | YENASK shipped via PRs #239, #241, #242, #243; this is the predecessor plan. |
| 13 | docs/archive/plans/20260519-indicator-topic-taxonomy-and-dir-structure-plan.md | AUDIT against T.0d topics consolidation | Topics taxonomy landed via T.0a/b/c/d and PR #182. |
| 14 | docs/archive/plans/20260521-phase-2-preflight-audit-gregor.md | AUDIT | Architect preflight note; may be stale. |

## Suggested workflow

1. For each row: `git log --all --oneline --grep="<plan-doc-anchor>"` to
   find any commits citing the plan-doc.
2. If shipped: edit the top of the file to add
   `**Status:** Shipped on <date> via <commit-sha>. Archived for history.`
   then `git mv` to `docs/archive/`.
3. If partially shipped: edit the open scope-block to reflect remaining
   work; promote unshipped slices to a fresh plan-doc with date prefix.
4. If blocked / dead: edit top to
   `**Status:** Closed - <one-line reason>` and `git mv` to `docs/archive/`.

This is a low-priority cleanup pass; no Holy Law deadline. Run when a
maintainer has a free afternoon.

## See also

- [docs/concepts/boundary-data-philosophy.md](../docs/concepts/boundary-data-philosophy.md)
  - the concept doc this triage note was extracted alongside.
- [docs/reference/documentation-structure.md](../docs/reference/documentation-structure.md)
  - the Diataxis routing rules that determine where each plan-doc's
  surviving scope should land if it gets archived.
- [CLAUDE.md section 5](../CLAUDE.md) - "Docs = agent memory" + "TODO/ +
  notes/ are non-authoritative" reminder. This file is a `notes/` working
  scratchpad, not a contract.
