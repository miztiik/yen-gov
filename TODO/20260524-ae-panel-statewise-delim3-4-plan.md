# AE Panel Statewise DelimID 3/4 Ingestion Plan

**Last Updated**: 2026-05-24
**Status**: ACTIVE — tooling through Kerala (`S11`) merged; Punjab (`S19`) state PR in progress.
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
| 0 | Tooling and plan | Dry-run/report surface, bounded `--delim-id` filters, plan-doc, source-doc update, adapter tests. No Parquet data writes. | DONE — PR #181 |
| 1 | Goa (`S05`) | State-only dry-run, event registration for missing `S05` rows, `DelimID=3` and `DelimID=4` ingest, inventory/provenance/coverage updates. | DONE — PR #185 |
| 2 | Himachal Pradesh (`S08`) | State-only dry-run, event registration for missing `S08` rows, `DelimID=3` and only missing `DelimID=4` event (`2012`) ingest, inventory/provenance/coverage updates. | DONE — PR #186 |
| 3 | Tripura (`S23`) | State-only dry-run, event registration for missing `S23` rows, `DelimID=3` and only missing `DelimID=4` event (`2013`) ingest, inventory/provenance/coverage updates. | DONE — PR #187 |
| 4 | Meghalaya (`S15`) | State-only dry-run, event registration for missing `S15` rows, `DelimID=3` and only missing `DelimID=4` event (`2013`) ingest, inventory/provenance/coverage updates. | DONE — PR #188 |
| 5 | Puducherry (`U07`) | State-only dry-run, event registration for missing `U07` rows, `DelimID=3` from 1977 onward and only missing `DelimID=4` event (`2011`) ingest, inventory/provenance/coverage updates. | DONE — PR #189 |
| 6 | Sikkim (`S21`) | State-only dry-run, event registration for missing `S21` rows, `DelimID=3` and `DelimID=4` ingest, inventory/provenance/coverage updates. | DONE — PR #190 |
| 7 | Frontend default-event fix | `defaultEventForState` now chooses max `polled_on` rather than catalogue order / stale flags, preventing historical backfills from becoming the default event. | DONE — PR #191 |
| 8 | Arunachal Pradesh (`S02`) | State-only dry-run, event registration for missing `S02` rows, `DelimID=3` and `DelimID=4` ingest, inventory/provenance/coverage updates. | DONE — PR #192 |
| 9 | Telangana (`S29`) | State-only dry-run, event registration for missing `S29` rows, `DelimID=4` ingest, inventory/provenance/coverage updates. | DONE — PR #194 |
| 10 | Andhra Pradesh (`S01`, 2014 current-state slice) | State-only dry-run with `--min-year 2014 --max-year 2014`, event registration for `AcGenMay2014`, `DelimID=4` ingest, inventory/provenance/coverage updates. Pre-2014 undivided Andhra Pradesh remains deferred. | DONE — PR #195 |
| 11 | Chhattisgarh (`S26`) | State-only dry-run, event registration for missing `S26` rows, `DelimID=3` and `DelimID=4` ingest, inventory/provenance/coverage updates. | DONE — PR #197 |
| 12 | Jharkhand (`S27`) | State-only dry-run, event registration for missing `S27` rows, scoped ingest through 2014 to preserve the existing 2019 Section-10 slice, inventory/provenance/coverage updates. | DONE — PR #198 |
| 13 | Uttarakhand (`S28`) | State-only dry-run, event registration for missing `S28` rows, scoped ingest through 2012 to preserve existing 2017/2022 Section-10 slices, inventory/provenance/coverage updates. | DONE — PR #199 |
| 14 | Manipur (`S14`) | State-only dry-run, event registration for missing `S14` rows, scoped ingest from 1980 through 2012 to preserve existing 2017/2022 Section-10 slices and defer pre-1977 rows, inventory/provenance/coverage updates. | DONE — PR #200 |
| 15 | Mizoram (`S16`) | State-only dry-run, event registration for missing `S16` rows, `DelimID=3` and `DelimID=4` ingest through 2018, inventory/provenance/coverage updates. | DONE — PR #201 |
| 16 | Nagaland (`S17`) | State-only dry-run, event registration for missing `S17` rows, scoped ingest from 1977 through 2013 to preserve existing 2018/2023 Section-10 slices and defer pre-1977 rows, inventory/provenance/coverage updates. | DONE — PR #202 |
| 17 | Delhi (`U05`) | State-only dry-run, event registration for missing `U05` rows, scoped ingest from 1977 through 2015 to preserve existing 2020/2025 rows, inventory/provenance/coverage updates. | DONE — PR #203 |
| 18 | Haryana (`S07`) | State-only dry-run, event registration for missing `S07` rows, scoped ingest from 1977 through 2014 to preserve existing 2019/2024 rows, inventory/provenance/coverage updates. | DONE — PR #204 |
| 19 | Kerala (`S11`) | State-only dry-run, event registration for missing `S11` rows, scoped ingest from 1977 through 2011 to preserve existing 2016/2021/2026 rows, inventory/provenance/coverage updates. | DONE — PR #205 |
| 20 | Punjab (`S19`) | State-only dry-run, event registration for missing `S19` rows, scoped ingest from 1977 through 2012 to preserve existing 2017/2022 rows, inventory/provenance/coverage updates. | ACTIVE — this PR |
| 21+ | Remaining states | Proceed from small/low-risk states to medium states, then large/reorganisation-heavy states. | QUEUED |

Already-merged panel states are out of the first wave: Tamil Nadu (`S22`, PR #178), Gujarat (`S06`, PR #179), and Maharashtra (`S13`, PR #180).

## Initial Dry-Run Findings

The tooling PR ran read-only preflights against the first two candidate states:

| State | Included rows | `DelimID=3` rows | `DelimID=4` rows | Missing event rows | Unresolved party rows | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Goa (`S05`) | 2,034 | 1,187 | 847 | 1,402 across 6 events | 181 | First state PR candidate |
| Himachal Pradesh (`S08`) | 4,385 | 3,040 | 1,345 | 3,499 across 9 events | 266 | Second candidate after Goa pattern proves out |

Goa's missing event registrations: 1989-11, 1994-11, 1999-06, 2002-06, 2007-06, and 2012-03. Its already-registered events in this slice are 2017-03 (`AcGenFeb2017`) and 2022-03 (`AcGenFeb2022`).

Goa write verification after the state PR emit: 9,620 observation rows, 8 events, 80 AC dimension rows across `delim_year` 1976/2008, 181 candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Goa `source_id` values.

Himachal Pradesh dry-run found 4,385 approved rows (`DelimID=3`: 3,040; `DelimID=4`: 1,345) across 11 events. The state PR writes 1977-2007 plus 2012 only; 2017 and 2022 remain on their existing Section-10 source because the panel disagreed with prior canonical turnout totals while winner votes matched. The scoped write adds 1977, 1982, 1985, 1990, 1993, 1998, 2003, 2007, and 2012.

Tripura dry-run found 2,923 approved rows (`DelimID=3`: 1,998; `DelimID=4`: 925) across 10 events. The state PR writes 1977-2008 plus 2013 only; 2018 and 2023 remain on their existing Section-10 source unless a later parity check deliberately promotes them. The scoped write adds 1977, 1983, 1988, 1993, 1998, 2003, 2008, and 2013. Post-ingest verification showed 14,913 Tripura observation rows, 10 events, 60 ACs in every event, 253 candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Tripura `source_id` values.

Meghalaya dry-run found 3,322 approved rows (`DelimID=3`: 2,119; `DelimID=4`: 1,203) across 10 events. The state PR writes 1978-2008 plus 2013 only; 2018 and 2023 remain on their existing Section-10 source because both have countermanded-seat handling already represented in the canonical slice. The scoped write adds 1978, 1983, 1988, 1993, 1998, 2003, 2008 (`AcGenMar2008`), and 2013. Post-ingest verification showed 15,554 Meghalaya observation rows, 10 events, 60 ACs in every newly added event, 615 newly added candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Meghalaya `source_id` values.

Puducherry dry-run found 2,503 `DelimID=3/4` rows, but the state PR excludes the deferred 1974 slice and preserves existing 2016/2021 Section-10 slices. The scoped write adds 1977, 1980, 1985, 1990, 1991 (`AcGenJun1991`), 1996, 2001, 2006, and 2011 (`AcGenApr2011`). Post-ingest verification showed 11,012 Puducherry observation rows, 12 U07 events on disk, 30 ACs in every event, 23 newly added candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Puducherry `source_id` values.

Sikkim dry-run found 1,437 approved rows (`DelimID=3`: 935; `DelimID=4`: 502) across 9 missing events. The state PR writes 1979-2019 and preserves the existing 2024 Section-10 slice. The scoped write adds 1979 (`AcGenOct1979`), 1985, 1989, 1994, 1999, 2004, 2009 (`AcGenApr2009`), 2014 (`AcGenApr2014`), and 2019. Post-ingest verification showed 8,025 Sikkim observation rows, 10 S21 events on disk, 32 ACs in every event except the 2004 slice's 28 contested ACs, 243 newly added candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Sikkim `source_id` values.

Arunachal Pradesh dry-run found 1,591 approved rows (`DelimID=3`: 975; `DelimID=4`: 616) across 10 missing events. The state PR writes 1978-2019 and preserves the existing 2024 Section-10 slice. The scoped write adds 1978, 1980 (`AcGenJan1980`), 1984, 1990, 1995, 1999, 2004, 2009, 2014, and 2019. Post-ingest verification showed 10,598 Arunachal observation rows, 11 S02 events on disk, 30 ACs in 1978/1980/1984, 60 ACs in 1990/1995/2009/2014/2019, 59 contested ACs in 1999, 57 contested ACs in 2004, 50 newly added candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Arunachal `source_id` values.

Telangana dry-run found 3,728 approved rows (`DelimID=4`: 3,728) across 2 missing events. The state PR writes 2014 and 2018, preserving the existing 2023 Section-10 slice. The 2014 rows are scoped to `State_Name=Telangana`; undivided Andhra Pradesh rows remain outside this current-state slice. Post-ingest verification showed 16,972 Telangana observation rows, 3 S29 events on disk, 119 ACs in every event, 586 newly added candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Telangana `source_id` values.

Andhra Pradesh 2014 dry-run found 2,416 approved rows (`DelimID=4`: 2,416) across 1 missing current-state event. The state PR writes only 2014 with `--min-year 2014 --max-year 2014`, preserving existing 2019/2024 Section-10 slices and leaving pre-2014 undivided Andhra Pradesh out of scope. Post-ingest verification showed 18,850 Andhra Pradesh observation rows, 3 S01 events on disk, 175 ACs in every event, 377 newly added candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Andhra Pradesh `source_id` values.

Chhattisgarh dry-run found 4,320 writeable approved rows (`DelimID=3`: 819; `DelimID=4`: 3,501) across 4 missing events after skipping 142 blank-month rows. The state PR writes 2003 (`AcGenDec2003`), 2008 (`AcGenNov2008`), 2013 (`AcGenNov2013`), and 2018 (`AcGenNov2018`), preserving the existing 2023 Section-10 slice. Post-ingest verification showed 19,245 Chhattisgarh observation rows, 5 S26 events on disk, 90 ACs in every event, 397 newly added candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Chhattisgarh `source_id` values.

Jharkhand dry-run found 5,395 writeable approved rows (`DelimID=3`: 1,390; `DelimID=4`: 4,005) across 4 events after skipping 241 blank-month rows. The state PR writes only the three missing events through 2014 (`AcGenFeb2005`, `AcGenDec2009`, `AcGenDec2014`) and preserves the existing 2019 Section-10 slice. Post-ingest verification showed 19,838 Jharkhand observation rows, 5 S27 events on disk, 81 ACs in every event, 528 newly added candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Jharkhand `source_id` values.

Uttarakhand dry-run found 3,909 writeable approved rows (`DelimID=3`: 1,712; `DelimID=4`: 2,197) across 5 events after skipping 93 blank-month rows. The state PR writes only the three missing events through 2012 (`AcGenFeb2002`, `AcGenFeb2007`, `AcGenJan2012`) and preserves the existing 2017/2022 Section-10 slices. Post-ingest verification showed 13,936 Uttarakhand observation rows, 5 S28 events on disk, 70 ACs in every event except the 2007 slice's 69 contested ACs, 236 newly added candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Uttarakhand `source_id` values.

Manipur dry-run found 3,638 writeable approved rows (`DelimID=3`: 2,708; `DelimID=4`: 930) across 11 events after skipping 101 blank-month rows and 418 non-D3/D4 rows. The state PR excludes the pre-1977 1974 slice, writes 1980 through 2012, and preserves the existing 2017/2022 Section-10 slices. Post-ingest verification showed 16,046 Manipur observation rows, 10 S14 events on disk, 60 ACs in every event except the 1990 slice's 54 contested ACs, 389 newly added candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Manipur `source_id` values.

Mizoram dry-run found 1,916 writeable approved rows (`DelimID=3`: 1,279; `DelimID=4`: 637) across 11 missing events after skipping 62 blank-month rows and 155 non-D3/D4 rows. The state PR writes 1978 through 2018 and preserves the existing 2023 Section-10 slice. Post-ingest verification showed 10,767 Mizoram observation rows, 12 S16 events on disk, 30 ACs in 1978/1979/1984 and 40 ACs in every later event, 298 newly added candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Mizoram `source_id` values.

Nagaland dry-run found 2,410 writeable approved rows (`DelimID=3`: 1,506; `DelimID=4`: 904) across 12 events after skipping 72 blank-month rows and 244 non-D3/D4 rows. The state PR excludes the pre-1977 1974 slice, writes 1977 through 2013, and preserves the existing 2018/2023 Section-10 slices. Post-ingest verification showed 12,959 Nagaland observation rows, 11 S17 events on disk, 60 ACs in every newly written event, 364 newly added candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Nagaland `source_id` values.

Delhi dry-run found 6,830 writeable approved rows (`DelimID=3`: 3,590; `DelimID=4`: 3,240) across 9 events after skipping 99 blank-month rows and 270 non-D3/D4 rows. The state PR writes 1977 through 2015 and preserves the existing 2020/2025 rows. The 1977 and 1983 rows are Delhi Metropolitan Council elections carried by the ECI AE panel; the event notes mark that the Council had an advisory role and no legislative powers. Post-ingest verification showed 28,406 Delhi observation rows, 10 U05 events on disk, 56/55 contested seats for the 1977/1983 Metropolitan Council rows and 70 ACs in every Assembly event, 512 newly added candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Delhi `source_id` values.

Haryana dry-run found 13,334 writeable approved rows (`DelimID=3`: 9,412; `DelimID=4`: 3,922) across 10 events after skipping 424 blank-month rows and 1,281 non-D3/D4 rows. The state PR writes 1977 through 2014 and preserves the existing 2019/2024 rows. Post-ingest verification showed 49,597 Haryana observation rows, 11 S07 events on disk, 90 ACs in every event, 920 newly added candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Haryana `source_id` values.

Kerala dry-run found 10,152 writeable approved rows (`DelimID=3`: 6,741; `DelimID=4`: 3,411) across 11 events after skipping 337 blank-month rows and 1,506 non-D3/D4 rows. The state PR writes 1977 through 2011 and preserves the existing 2016/2021/2026 rows. Post-ingest verification showed 47,329 Kerala observation rows, 12 S11 events on disk, 140 ACs in every event, 135 newly added candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Kerala `source_id` values.

Punjab dry-run found 9,260 writeable approved rows (`DelimID=3`: 5,499; `DelimID=4`: 3,761) across 10 events after skipping 214 blank-month rows and 2,333 non-D3/D4 rows. The state PR writes 1977 through 2012 and preserves the existing 2017/2022 rows. Post-ingest verification showed 35,728 Punjab observation rows, 10 S19 events on disk, 117 ACs in every event except the 2007 slice's 116 contested ACs, 261 newly added candidacies mapped to `parties.IN.UNK` with `party_short_raw` preserved, and zero dangling Punjab `source_id` values.

## Remaining State Classes

The normal queue remains state-by-state, but not every pending token is equally safe:

- **Straight current-state queue**: Punjab (`S19`, active), Rajasthan (`S20`), Karnataka (`S10`), Assam (`S03`), Odisha (`S18`), West Bengal (`S25`), Bihar (`S04`), Madhya Pradesh (`S12`), Uttar Pradesh (`S24`). Delhi's 1977/1983 rows are the Metropolitan Council caveat documented in the source adapter spec.
- **Filterable split-state queue**: Andhra Pradesh (`S01`) post-2014 only; the 2014 current-state slice is done in PR #195. Pre-2014 Andhra rows describe undivided Andhra Pradesh and need a historical entity decision.
- **Deferred/problem tokens**: `Goa_Daman_&_Diu`, `Madras`, `Mysore`, and `Jammu_&_Kashmir`. `Madras`/`Mysore` are legacy predecessor names; `Goa_Daman_&_Diu` is a predecessor UT; `Jammu_&_Kashmir` needs a post-2019 state/UT split plan.

## Normal-State Execution Queue

| # | State token | Code | Approved rows | `DelimID=3` | `DelimID=4` | Status |
| ---: | --- | --- | ---: | ---: | ---: | --- |
| 1 | `Chhattisgarh` | `S26` | 4,462 | 886 | 3,576 | DONE — PR #197 |
| 2 | `Jharkhand` | `S27` | 5,636 | 1,428 | 4,208 | DONE — PR #198 |
| 3 | `Uttarakhand` | `S28` | 4,002 | 1,755 | 2,247 | DONE — PR #199 |
| 4 | `Manipur` | `S14` | 3,739 | 2,781 | 958 | DONE — PR #200 |
| 5 | `Mizoram` | `S16` | 1,978 | 1,311 | 667 | DONE — PR #201 |
| 6 | `Nagaland` | `S17` | 2,482 | 1,543 | 939 | DONE — PR #202 |
| 7 | `Delhi` | `U05` | 6,929 | 3,651 | 3,278 | DONE — PR #203 |
| 8 | `Haryana` | `S07` | 13,758 | 9,727 | 4,031 | DONE — PR #204 |
| 9 | `Kerala` | `S11` | 10,489 | 6,955 | 3,534 | DONE — PR #205 |
| 10 | `Punjab` | `S19` | 9,474 | 5,618 | 3,856 | ACTIVE — verified in this PR |
| 11 | `Rajasthan` | `S20` | 19,867 | 12,782 | 7,085 | QUEUED |
| 12 | `Karnataka` | `S10` | 23,719 | 12,289 | 11,430 | QUEUED |
| 13 | `Assam` | `S03` | 10,817 | 7,470 | 3,347 | QUEUED |
| 14 | `Odisha` | `S18` | 11,209 | 7,034 | 4,175 | QUEUED |
| 15 | `West_Bengal` | `S25` | 18,607 | 11,918 | 6,689 | QUEUED |
| 16 | `Bihar` | `S04` | 46,942 | 35,453 | 11,489 | QUEUED |
| 17 | `Madhya_Pradesh` | `S12` | 29,305 | 19,521 | 9,784 | QUEUED |
| 18 | `Uttar_Pradesh` | `S24` | 76,120 | 58,652 | 17,468 | QUEUED |

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