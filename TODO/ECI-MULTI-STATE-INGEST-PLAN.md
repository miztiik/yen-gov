# ECI Multi-State Ingest Follow-Ups

**Last Updated**: 2026-05-15

This TODO is intentionally narrow. The shipped Statistical Report mechanics, category-pin rules, static-catalog path, and archived-party registry design live in [docs/architecture/backend/sources-eci.md](../docs/architecture/backend/sources-eci.md). Historical recon facts live in [docs/archive/eci-statistical-report-recon-2026-05.md](../docs/archive/eci-statistical-report-recon-2026-05.md).

## Open Follow-Ups

- **Lok Sabha 2024 PC ingest**: build the PC result path from ECI Statistical Report category `1` plus, if needed, per-PC digital index cards category `11`. Body `PC` already exists in the schema/model stack.
- **Full party-registration source**: add a future adapter for `notification.eci.gov.in` only if archived-cohort party-code coverage needs to move beyond the registry derivable from existing live `parties.json` files.
- **2021-and-earlier assembly archive**: fetch one representative `old.eci.gov.in/files/file/<id>-<slug>/` page from a reachable network before choosing HTML, XLSX, or PDF parsing.

## Closed Work

The old N1-N6 implementation plan is closed and should not be used as an authority. The current authority is the ECI adapter doc linked above.
