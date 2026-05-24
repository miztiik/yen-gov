# AE Panel Statewise DelimID 3/4 Ingestion Plan

**Last Updated**: 2026-05-24
**Status**: ACTIVE — tooling PR in progress; no new state slice ingested by this plan yet.
**Scope**: `datasets/ephemeral/All_States_AE.csv` statewise ingestion through the canonical elections Parquet writer.
**Spec**: [`docs/architecture/backend/sources-eci.md`](../docs/architecture/backend/sources-eci.md), [`docs/architecture/data/canonical-store.md`](../docs/architecture/data/canonical-store.md), [`docs/architecture/data/elections-indicators.md`](../docs/architecture/data/elections-indicators.md).
**Decision rationale**: [ADR-0030](../docs/architecture/decisions/0030-canonical-store-duckdb-wasm.md), [ADR-0032](../docs/architecture/decisions/0032-sources-citation-ledger.md), [ADR-0036](../docs/architecture/decisions/0036-state-identity-and-slice-registration.md).

---

## Decision Snapshot

User approved the conservative route on 2026-05-24: do not ingest the all-states AE panel wholesale. Ingest one state per PR, and inside that state only the two supported delimitation windows:

- `DelimID=3` — pre-2008 assembly cycle represented by the current adapter as `delim_year=1976`.
- `DelimID=4` — post-2008 assembly cycle represented as `delim_year=2008`.

Every state PR must be merged to `main` before the next state starts. This keeps retries, reversions, party-resolution fixes, and event-registration corrections scoped to one state.

## Source And Target

- Source input: `datasets/ephemeral/All_States_AE.csv`.
- Canonical fact target: `datasets/elections/state=in_<state>/election_results.parquet`.
- Canonical dimension targets: `datasets/elections/dim_acs.parquet`, `datasets/elections/dim_persons.parquet`, `datasets/elections/elections_candidacies.parquet`, `datasets/elections/dim_parties.parquet`, `datasets/elections/dim_party_alliances.parquet`.
- Provenance target: `datasets/taxonomy/sources.parquet` using ECI citation-ledger rows with `verification_method="transcribed"`.
- Inventory target: `datasets/elections/_inventory.json` plus the generated election coverage report.

## PR Sequence

| Step | PR | Contents | Status |
| --- | --- | --- | :-: |
| 0 | Tooling and plan | Dry-run/report surface, bounded `--delim-id` filters, plan-doc, source-doc update, adapter tests. No Parquet data writes. | ACTIVE |
| 1 | Goa (`S05`) | State-only dry-run, event registration for missing `S05` rows, `DelimID=3` and `DelimID=4` ingest, inventory/provenance/coverage updates. | QUEUED |
| 2 | Himachal Pradesh (`S08`) | Same state-only loop. | QUEUED |
| 3 | Tripura (`S23`) | Same state-only loop. | QUEUED |
| 4 | Meghalaya (`S15`) | Same state-only loop. | QUEUED |
| 5 | Puducherry (`U07`) | Same state-only loop. | QUEUED |
| 6+ | Remaining states | Proceed from small/low-risk states to medium states, then large/reorganisation-heavy states. | QUEUED |

Already-merged panel states are out of the first wave: Tamil Nadu (`S22`, PR #178), Gujarat (`S06`, PR #179), and Maharashtra (`S13`, PR #180).

## Initial Dry-Run Findings

The tooling PR ran read-only preflights against the first two candidate states:

| State | Included rows | `DelimID=3` rows | `DelimID=4` rows | Missing event rows | Unresolved party rows | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Goa (`S05`) | 2,034 | 1,187 | 847 | 1,402 across 6 events | 181 | First state PR candidate |
| Himachal Pradesh (`S08`) | 4,385 | 3,040 | 1,345 | 3,499 across 9 events | 266 | Second candidate after Goa pattern proves out |

Goa's missing event registrations: 1989-11, 1994-11, 1999-06, 2002-06, 2007-06, and 2012-03. Its already-registered events in this slice are 2017-03 (`AcGenFeb2017`) and 2022-03 (`AcGenFeb2022`).

## Per-State Loop

1. Start from clean `main` after the prior state PR has merged.
2. Create `feat/ae-panel-<state-code-lower>-delim3-4`.
3. Run dry-run report for the state with `--delim-id 3 --delim-id 4`.
4. Add only that state's missing `(state_code, year) -> EventInfo` rows in `backend/yen_gov/sources/eci/events.py`.
5. Ingest the state with `DelimID=3`; inspect row counts, discrepancy report, unresolved parties, manifest diff, and source FK closure.
6. Ingest the same state with `DelimID=4`; repeat the same inspection.
7. Run `python -m yen_gov coverage --root .`; commit the updated inventory/report if it changes.
8. Run backend tests and Tier-B validation.
9. Open the state PR, merge when green, fast-forward local `main`, then move to the next state.

## Verification Gates

Every state PR must pass:

1. Targeted backend tests for the AE panel adapter and event registry.
2. Dry-run output showing the exact years, row counts, missing events, unresolved parties, and skipped unsupported rows.
3. Post-ingest inspection for both `DelimID=3` and `DelimID=4` windows.
4. Full backend `pytest -q`.
5. `python -m yen_gov validate --root .`.
6. `python -m yen_gov coverage --root .` with committed inventory/report updates.
7. Browser smoke if the newly ingested state changes citizen-visible election pages.

## Deferred

- `DelimID=1` and `DelimID=2` rows.
- Pre-1977 national ingestion.
- `Goa_Daman_&_Diu` historical entity and partition design.
- Mass party-taxonomy curation for every unresolved panel token.
- Cross-state batching.

## See also

- [`docs/architecture/backend/sources-eci.md`](../docs/architecture/backend/sources-eci.md)
- [`docs/architecture/data/elections-indicators.md`](../docs/architecture/data/elections-indicators.md)
- [`docs/concepts/data-provenance.md`](../docs/concepts/data-provenance.md)
- [`TODO/20260517-tcpd-tn-ae-people-sidecar-plan.md`](20260517-tcpd-tn-ae-people-sidecar-plan.md)