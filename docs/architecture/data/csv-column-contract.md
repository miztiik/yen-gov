# CSV column contract (post-rip canonical)

**Last Updated**: 2026-06-13
**Owner**: Hans + Max (data shape) / Gregor (contract surface) per CLAUDE.md section 0a
**Status**: BINDING from D-DOC0 onward. Authoritative spec for every CSV under `datasets/data/` and `datasets/elections/`. Supersedes the Parquet-era column rules in [canonical-store.md](canonical-store.md) for CSV file classes.
**Status**: BINDING from D-DOC0 onward (chunk D-DOC0); ripple-corrected per the column-contract single-home rule.

---

## 1. Why this doc exists

The rip-and-replace deletes the ~60 JSON Schemas that used to validate Parquet artifacts. The new canonical store is long-format CSV under `datasets/data/` (+ per-election self-contained CSV under `datasets/elections/`) read in-browser by DuckDB-WASM `read_csv(columns=...)`. Three consumers need to agree on every column name + dtype + nullability for every file class:

1. The backend write-time validator (chunk B1 `canonical/csv_writer.py` + per-file CSV column validators).
2. The frontend typed reader (chunk F1 `queryCsv()` / `read_csv(columns=...)` maps).
3. The cross-format parity gate (chunk B2b) and the drift test (this doc's sibling test, chunk D-DOC0 / F1).

If those three drift, the rip introduces a class of silent value bugs no test catches. The contract surface IS the column schema (CLAUDE.md Holy Law #3, restated for CSV).

## 2. The one machine-readable home (no hand-typed second copy)

There is exactly **one** machine-readable column contract, at:

```
datasets/data/_schema/columns.json
```

`columns.json` is keyed by **file class** (a glob over the canonical tree, not a single file path), and for each class lists the columns in emission order with `{name, dtype, nullable, fk?, enum?, derived?}`. The retained JSON-Schema escape-hatch (`datasets/schemas/`) is reduced to a tiny set (per plan section 8 / D6) and does NOT mirror this contract.

Rules (FROZEN; reopening requires a Hans + Max + Gregor signoff per CLAUDE.md section 0a):

- The backend write-time validator reads `columns.json` and validates emitted CSV headers + per-row dtype + nullability + FK target + enum membership.
- The frontend `read_csv(columns=...)` map is **generated** (build-time codegen, or load-time fetch of the same `columns.json`) - **never** hand-typed. ADR-0047 alternative F (duplicate Python + TS constants) is rejected; drift is the failure mode the contract surface exists to prevent.
- The drift test (`backend/tests/test_csv_column_contract_drift.py`, authored in F1) asserts `writer-emitted header == columns.json == reader-expected columns` per file class.
- `read_csv_auto` is **banned** in any committed loader code. Every read is typed via `read_csv(columns={...})` sourced from this contract. (Plan invariant #4, section 22.4.)
- Filenames are exactly `<variable_id>.csv` for datapoints. Double-underscore (`__`) is banned in filenames and ids (plan section 21.6). The validator rejects `__`.

The on-disk JSON artifact lands as part of chunk B1 (it is a writer dependency); this doc is the human-readable spec the artifact materialises.

## 3. File classes and columns

Notation: `pk` = primary key column(s) for the file class; `fk -> <file>.<col>` = foreign key target; `enum {a, b, c}` = closed-enum membership; `derived` = F7 computed at write time, never hand-authored; nullability is explicit per column.

### 3.1 Catalogue (one row per concept / variable / topic)

#### `datasets/data/variables.csv`

| column | dtype | nullable | note |
| --- | --- | --- | --- |
| `indicator_id` | string | no (pk) | kebab `<measure>-<unit>-<facet>`; no `__`; no grain prefix (`state-` / `district-` / `national-`) per ADR-0044 |
| `name` | string | no | citizen-facing label |
| `concept_id` | string | no (fk -> concepts.concept_id) | F6 one-indicator-per-concept |
| `unit` | string | no | human-readable unit; canonical unit lives on the concept |
| `derivation` | string | yes | F7 note (e.g. `per_capita`, `pct_of_gsdp`); null = direct observation |
| `topic` | string | yes (fk -> topics.topic) | one topic per row (M:N via separate index if needed) |
| `source_id` | string | yes (fk -> entities/source.csv.source_id) | catalogue-level default; per-row stamp still mandatory on datapoint rows |
| `update_period_days` | integer | no | publisher refresh cadence; never null per CLAUDE.md anti-pattern (`update_period_days` required) |
| `time_min` | integer | yes | min `time` across the indicator's datapoints; consumed by yen-ask grounding (plan section 20.10) |
| `time_max` | integer | yes | max `time`; same |
| `entity_kinds` | string | yes | pipe-separated subset of `entities/geo.csv.entity_kind` and/or `entities/electoral.csv.entity_kind`; yen-ask alias surface |

#### `datasets/data/concepts.csv`

| column | dtype | nullable | note |
| --- | --- | --- | --- |
| `concept_id` | string | no (pk) | kebab |
| `noun` | string | no | citizen-readable noun the indicator measures |
| `unit_canonical` | string | no | canonical SI / SI-derived unit (variants live on `variables.unit`) |
| `normalisation` | string | no | enum {`absolute`, `per_capita`, `share`, `rate`, `index`} |
| `entity_kinds` | string | no | pipe-separated set of admissible `entity_kind` values |
| `description` | string | yes | one-paragraph operational definition |

#### `datasets/data/topics.csv`

| column | dtype | nullable | note |
| --- | --- | --- | --- |
| `topic` | string | no (pk) | kebab; no `__` |
| `name` | string | no | citizen-facing label |
| `parent` | string | yes (fk -> topics.topic) | null = root topic (Gapminder parent-pointer shape) |

### 3.2 Entities (one row per identified thing)

#### `datasets/data/entities/geo.csv` (LGD administrative ladder)

| column | dtype | nullable | note |
| --- | --- | --- | --- |
| `entity_id` | string | no (pk) | issuing-authority id per [identifiers.md](../../reference/identifiers.md) |
| `name` | string | no | LGD citizen-readable name |
| `parent` | string | yes (fk -> entities/geo.csv.entity_id) | null for `india` root |
| `entity_kind` | string | no | enum {`country`, `state`, `district`, `sub-district`, `village`} (v1 freezes at state + district per F4) |
| `aliases` | string | yes | pipe-separated alternate names; yen-ask grounding surface |

#### `datasets/data/entities/electoral.csv` (ECI AC / PC, per delimitation cycle)

| column | dtype | nullable | note |
| --- | --- | --- | --- |
| `entity_id` | string | no (pk) | `IN-AC-<delim>-<state_code>-<ac_no>` or `IN-PC-<delim>-<state_code>-<pc_no>` |
| `name` | string | no | ECI constituency name |
| `entity_kind` | string | no | enum {`ac`, `pc`} |
| `delim_year` | integer | no | delimitation cycle anchor (e.g. 2008) |
| `state` | string | no (fk -> entities/geo.csv.entity_id) | LGD state id |
| `parent` | string | yes | null - electoral entities do NOT nest into LGD districts (F3); join via `electoral_lgd_xwalk.csv` |
| `reservation` | string | yes | enum {`GEN`, `SC`, `ST`} |

#### `datasets/data/entities/electoral_lgd_xwalk.csv` (versioned, NEVER an invariant)

| column | dtype | nullable | note |
| --- | --- | --- | --- |
| `electoral_id` | string | no (fk -> entities/electoral.csv.entity_id) | composite pk with delim_year |
| `lgd_district_id` | string | no (fk -> entities/geo.csv.entity_id) | composite pk |
| `delim_year` | integer | no | composite pk |
| `boundary_snapshot` | string | no | date or LGD snapshot id used to compute the overlap |
| `overlap_kind` | string | no | enum {`wholly_inside`, `majority`, `partial`} (F3) |

#### `datasets/data/entities/parties.csv`

| column | dtype | nullable | note |
| --- | --- | --- | --- |
| `party_id` | string | no (pk) | sole party key (plan section 20.3); no `eci_code` as PK |
| `short` | string | no | citizen-facing abbreviation |
| `full` | string | no | full registered name |
| `eci_codes` | string | yes | pipe-separated historical ECI codes |
| `brand_colour` | string | yes | hex `#RRGGBB` |
| `symbol_asset` | string | yes | path under `frontend/public/icons/party-symbols/` (plan section 21.10) |
| `wikipedia` | string | yes | URL |

#### `datasets/data/entities/source.csv` (provenance ledger, citation grain)

Exactly five columns per plan section 7 (O3). Only the PK is required; the four citation fields are ALL optional.

| column | dtype | nullable | note |
| --- | --- | --- | --- |
| `source_id` | string | no (pk) | derivable from `(owner, title, vintage)` but never hand-authored; built by the writer (plan section 12 / Holy Law #9) |
| `owner` | string | yes | producer / department / government / org name |
| `title` | string | yes | dataset / report title |
| `vintage` | string | yes | edition / year (ISO 8601 fragment when known) |
| `url` | string | yes | metadata only; may be blank |

NB `license`, `confidence_tier`, `is_issuing_authority`, `verification_method`, `notes`, `citation_full`, `content_hash` are explicitly dropped (plan section 7). The writer MUST NOT emit them; the validator MUST reject them.

### 3.3 Datapoints (long format - the row count lives here)

One file per `variable_id`. Filename exactly `<variable_id>.csv`. No `__`. Sorted deterministically by `(entity_id, time)`.

#### `datasets/data/datapoints/geo/<variable_id>.csv`

| column | dtype | nullable | note |
| --- | --- | --- | --- |
| `entity_id` | string | no (pk) | fk -> entities/geo.csv.entity_id; composite pk with `time` (+ any facet column) |
| `time` | integer | no (pk) | year (calendar or fiscal as declared by the concept); never a wall-clock |
| `value` | number | yes | null = labelled gap (F1); never BE/RE-filled |
| `source_id` | string | no | fk -> entities/source.csv.source_id; per-row stamp mandatory (Holy Law #9) |
| `<facet>` | string | yes | OPTIONAL additional column(s) declared per indicator (e.g. `sex`, `fuel_type`); part of pk when present (plan section 21.6) |

#### `datasets/data/datapoints/electoral/<variable_id>.csv`

Same shape as `datapoints/geo/`, but `entity_id` is fk -> `entities/electoral.csv.entity_id`.

### 3.4 Elections (per-election self-contained, NOT long format)

Source data is wide (one row per `constituency x candidate`) and does not fit `(entity, time, value)`; it keeps its own family. Each file is ONE election - delimitation merge/split is never reconciled in-file (plan section 21.3).

#### `datasets/elections/assembly/state=<lgd-slug>/election=<year>/candidacies.csv`

| column | dtype | nullable | note |
| --- | --- | --- | --- |
| `entity_id` | string | no | fk -> entities/electoral.csv.entity_id; `IN-AC-<delim>-<state_code>-<ac_no>` |
| `state` | string | no | LGD slug mirrored from the path partition |
| `election_year` | integer | no | mirrored from the path partition |
| `constituency_no` | integer | no | ECI ac_no |
| `constituency_name` | string | no | |
| `candidate_name` | string | no | |
| `party_id` | string | yes | fk -> entities/parties.csv.party_id; null for independents not in the party table |
| `votes` | integer | no | |
| `vote_share_pct` | number | yes | derived (F7) |
| `position` | integer | no | 1 = winner, 2 = runner-up, ... |
| `result` | string | no | enum {`won`, `lost`, `forfeit`} |
| `sex` | string | yes | enum {`M`, `F`, `O`, `U`} |
| `age` | integer | yes | |
| `education` | string | yes | |
| `profession` | string | yes | |
| `candidate_type` | string | yes | enum {`incumbent`, `challenger`, `crossover`} |
| `source_id` | string | no | fk -> entities/source.csv.source_id |

#### `datasets/elections/assembly/state=<lgd-slug>/election=<year>/summary.csv`

Derived projection of `candidacies.csv` (plan section 23.4). The parity oracle (gate `parity-oracle-CSV`, plan 22.6) asserts `summary == recompute(candidacies)`.

| column | dtype | nullable | note |
| --- | --- | --- | --- |
| `entity_id` | string | no (pk) | one row per AC |
| `state` | string | no | mirrored from path |
| `election_year` | integer | no | mirrored from path |
| `constituency_name` | string | no | |
| `electors` | integer | yes | |
| `votes_polled` | integer | yes | |
| `turnout_pct` | number | yes | derived (F7) |
| `winner_candidate` | string | no | |
| `winner_party_id` | string | yes | fk -> entities/parties.csv.party_id |
| `winner_votes` | integer | no | argmax votes ex-NOTA (plan section 23.4) |
| `winner_share_pct` | number | yes | derived; null for an unopposed return (TCPD records a non-numeric share) |
| `runnerup_candidate` | string | yes | null when the seat is uncontested (single candidate) |
| `runnerup_party_id` | string | yes | fk -> entities/parties.csv.party_id |
| `runnerup_votes` | integer | yes | null when uncontested |
| `margin_votes` | integer | yes | derived: `winner_votes - runnerup_votes`; null when uncontested |
| `margin_pct` | number | yes | derived (F7); null when uncontested or either share is non-numeric |
| `source_id` | string | no | fk -> entities/source.csv.source_id |

#### `datasets/elections/parliament/election=<year>/candidacies.csv`

Same column set as assembly `candidacies.csv` EXCEPT `constituency_no` is the ECI pc_no, `entity_id` follows `IN-PC-<delim>-<state_code>-<pc_no>`, and **`state` is a MANDATORY column even though the path has no `state=` partition** (plan section 23.4 - without it `constituency_no` is non-unique within the file and per-state joins break).

#### `datasets/elections/parliament/election=<year>/summary.csv`

Same column set as assembly `summary.csv` with `entity_id` keyed to PC and `state` as a mandatory column for the same reason.

### 3.5 Derived marts (route-shaped read models)

Derived marts are generated CSV read models, not new sources of truth. Their inputs remain the canonical CSVs listed in the generator module; the mart files are reproducible and guarded by a freshness receipt. The frontend may read these small marts directly when a route would otherwise need to scan a large canonical corpus in the browser.

#### `datasets/data/marts/party_pages/history.csv`

Generated by `python -m yen_gov derive-party-pages --root .` from `datasets/data/datapoints/electoral/*_election_results.csv`, `datasets/data/entities/parties.csv`, and supporting electoral entity lookup files. One row per `(party_id, body, period_label)`.

| column | dtype | nullable | note |
| --- | --- | --- | --- |
| `party_id` | string | no (pk, fk -> entities/parties.csv.party_id) | `parties.IN.<X>`; `parties.IN.UNK` is excluded because it has no citizen page |
| `body` | string | no (pk) | enum {`parliament`, `assembly`} |
| `period_label` | string | no (pk) | canonical election period label (`LsGenMay2024`, `AcGenApr2021`) |
| `year` | integer | no | polling year |
| `seats` | integer | no | party seats won in that body/event |
| `vote_share_pct` | number | yes | votes-weighted share: party votes divided by AC/PC votes polled when available; never an average of state percentages |
| `contested` | integer | yes | constituencies contested (`party-contested-pcs` or `party-contested-acs`) |
| `source_ids` | string | yes | pipe-delimited source ids from contributing canonical rows |
| `derivation` | string | no | derivation label, currently `computed_from_canonical_electoral_rows` |

#### `datasets/data/marts/party_pages/strongholds.csv`

Generated by the same command. One row per `(party_id, body, rank)` after taking the top 10 constituencies by wins, then win rate, then entity id.

| column | dtype | nullable | note |
| --- | --- | --- | --- |
| `party_id` | string | no (pk, fk -> entities/parties.csv.party_id) | party page owner |
| `body` | string | no (pk) | enum {`parliament`, `assembly`} |
| `rank` | integer | no (pk) | 1..10 per party/body |
| `entity_id` | string | no | peer election-results entity id (`IN-S22-AC-2008-167`, `IN-PC-2008-S22-25`) |
| `constituency_name` | string | yes | materialised from `entities/electoral.csv`; null only when lookup misses |
| `state` | string | yes | LGD state slug materialised for display/linking; null only when the peer id cannot be parsed |
| `wins` | integer | no | count of events where the party won this constituency |
| `contested` | integer | no | count of observed winner rows for this constituency/body |
| `results` | string | no | chronological W/L sparkline string, e.g. `WWL` |
| `source_ids` | string | yes | pipe-delimited source ids from contributing winner rows |
| `derivation` | string | no | derivation label, currently `computed_from_canonical_winner_rows` |

#### `datasets/data/marts/party_pages/manifest.csv`

Freshness receipt for the party-page mart.

| column | dtype | nullable | note |
| --- | --- | --- | --- |
| `surface` | string | no (pk) | currently `party_pages` |
| `input_signature` | string | no | sha256 over input relative paths + file-content hashes |
| `input_file_count` | integer | no | count of files included in the signature |
| `party_count` | integer | no | count of page-bearing parties in `parties.csv` |
| `history_rows` | integer | no | emitted history rows |
| `stronghold_rows` | integer | no | emitted stronghold rows |

Tier-B validation recomputes `input_signature` and fails when the mart is missing or stale. Any electoral ingest that changes the source CSVs must run `python -m yen_gov derive-party-pages --root .` before validation/commit.

## 4. Closed enums (single source)

The enums declared above (`entity_kind`, `normalisation`, `overlap_kind`, `result`, `sex`, `candidate_type`) live in `columns.json` as the sole source. The write-time validator enforces membership (plan gate `fk-validator`, 22.6). No second declaration anywhere in the codebase.

## 5. Determinism + provenance invariants

- Rows are sorted by the natural pk of each file class before write (deterministic byte output).
- No `datetime.now()` in any content column (CLAUDE.md anti-pattern; provenance lives on `entities/source.csv.vintage`).
- Every datapoint and candidacy row carries `source_id` (Holy Law #9; per CLAUDE.md section 12).
- `value` may be null; null = labelled gap, never a zero or BE/RE projection (F1).
- The writer is the **sole** writer to `datasets/data/` and `datasets/elections/` (Holy Law #2 + CLAUDE.md section 3 directory invariant).

## 6. Codegen + drift tripwire (consumer contract)

The frontend `read_csv(columns={...})` map is generated from `columns.json` (one map per file class). The exact codegen tool lands in chunk F1; this doc declares the rule. The drift test (F1) keeps the three surfaces in lockstep.

## 7. See also

- [canonical-store.md](canonical-store.md) - operational spec for the legacy Parquet store; being rewritten in B2b / X1b.
- [../../reference/identifiers.md](../../reference/identifiers.md) - issuing-authority id grammar.
- [../../concepts/indicator-naming.md](../../concepts/indicator-naming.md) - kebab id grammar + F2 facet-legitimacy gates.
- [../../concepts/data-provenance.md](../../concepts/data-provenance.md) - citation-ledger doctrine.
- [decision-index.md](../../reference/decision-index.md) - ADR-0047 redirect and the "one machine-readable contract" rule (alt F rejected).
- CLAUDE.md Holy Laws #3 (contracts), #9 (provenance), #10 (tests).
