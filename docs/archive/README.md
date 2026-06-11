# Archive

**Last Updated**: 2026-06-11

This directory is historical record, not current doctrine. Use it to answer "why did we do that then?" or to inspect a shipped plan's audit trail. For current contracts, read `CLAUDE.md`, `docs/architecture/`, `docs/concepts/`, and `docs/reference/`.

## Rules for Agents

- Do not treat archive files as current authority.
- Do not rewrite archived plan bodies to match today's paths or storage model.
- If durable knowledge is still useful, distill it into the correct live doc and link back here only as a historical receipt.
- If a file is moved inside the archive, update live inbound links in the same PR.

## Layout

| Path | Contents | Use |
| --- | --- | --- |
| [decisions/](decisions/) | Superseded or rejected ADR bodies preserved verbatim. | Historical decision receipts; current redirect map is [../reference/decision-index.md](../reference/decision-index.md). |
| [plans/](plans/) | Closed plan docs, execution plans, migration ledgers, and plan-support ledgers. | Audit trail for shipped or superseded work. |
| [notes/](notes/) | Recon notes, source-hunt verdicts, and one-off handovers. | Evidence trail; not doctrine. |

## Root-Level Historical Anchors

These files remain at archive root because many live docs and code comments already cite them directly:

| File | Why it stays here |
| --- | --- |
| [20260518-frontend-charting-modernisation-plan-snapshot.md](20260518-frontend-charting-modernisation-plan-snapshot.md) | High-traffic charting-modernisation receipt cited by chart code and chart subsystem docs. |
| [20260522-phase-2-p1-nfhs-5-planning-superseded-by-energy.md](20260522-phase-2-p1-nfhs-5-planning-superseded-by-energy.md) | Superseded NFHS-5 planning draft preserved for future health-family context. |
| [canonical-pivot-plan-20260522-snapshot.md](canonical-pivot-plan-20260522-snapshot.md) | Pre-slim canonical pivot snapshot. |
| [eci-statistical-report-recon-2026-05.md](eci-statistical-report-recon-2026-05.md) | ECI reconnaissance receipt linked from the live ECI source-adapter docs. |
| [handover-2026-05-11.md](handover-2026-05-11.md) | Historical IA handover archived from `docs/architecture/`. |
