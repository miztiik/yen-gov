# ADR-0035 — Persons fork: rename `dim_candidates` to `dim_persons` in one shot (Option B)

**Status**: Accepted
**Date**: 2026-05-22 (lifted from `TODO/20260517-canonical-long-format-pivot.md §0e.5`, where the decision was locked 2026-05-19 by user override of the 3-agent default)
**Deciders**: User (override on 2026-05-19 against the agent panel's first-round default of Option A) + Max (Indicator Scout, hybrid B-ii + TCPD seed strategy) + Hans (Governance, IPC §21 anchor for office-bearer term) + Fowler (Engineering, paired-test discipline). Original debate in [TODO/20260519-indicator-topic-taxonomy-and-dir-structure-plan.md](../../../TODO/20260519-indicator-topic-taxonomy-and-dir-structure-plan.md).
**Cross-cuts**: `elections/` family + `governments/` family + `taxonomy/` registry — three subsystems with one identity grammar.

## Context

By 2026-05-19 the canonical store carried a single dimension table `datasets/elections/dim_candidates.parquet` keyed by a hash of `(state_code, ac_id, election_id, normalised_candidate_name)`. The same identity grammar served two genuinely different citizen questions:

1. **Election question** — "Who contested AC-167 in 2021?" The row IS the candidacy; one person contesting two different ACs in the same year correctly emits two rows.
2. **Government question** — "Who has been Tamil Nadu's CM since 1962?" The row IS the person; one CM serving two non-consecutive terms emits one person with two office-holdings.

Conflating these inside `dim_candidates` produced three concrete defects:

- **Same person, different name spellings** (`M. Karunanidhi` vs `M.K. Karunanidhi` vs `Karunanidhi M.`) hashed to three rows; the citizen-facing "CM tenure" panel could not aggregate without per-state heuristic merging.
- **Office-holding rows had no FK target** — Chief Minister tenure data in `datasets/governments/in/states/<S>/cm_terms.json` carried free-text CM names that no `dim_candidates` row resolved to. The two trees were on parallel tracks with no canonical bridge.
- **The TCPD `Candidate_ID` corpus** (Trivedi Centre for Political Data, Ashoka — five-plus years of curated India-specific name-merge work) had no row to attach to. `dim_candidates` was the wrong grain to absorb it.

The pre-pivot stance (PR #56 agent default) was **Option A: smallest reversible step** — keep `dim_candidates` as-is, add a separate `dim_persons.parquet` for the government side, accept the duplication, decide later whether to merge.

The user (2026-05-19) overrode the agent default in favour of **Option B: rename + dual-fact in one shot**. This ADR records that decision and the day-one `person_id` strategy that came out of Max's follow-up framing.

## Decision

**Adopt Option B and rename `dim_candidates` → `dim_persons` in one shot**, with two new sibling fact tables and a hand-authored merge overlay:

```
datasets/elections/
  dim_persons.parquet               # renamed from dim_candidates; one row per distinct person
  elections_candidacies.parquet     # NEW fact: one row per (person_id, election_id, ac_id, party_id, vote_share, won)

datasets/governments/
  governments_office_holdings.parquet  # NEW fact: one row per (person_id, office_id, tenure_start, tenure_end, party_id_at_tenure)

datasets/taxonomy/
  person_aliases.json   # hand-authored merge clusters (text, source-of-truth per ADR-0030 D18)
  persons.parquet       # compiled from person_aliases.json + the dim_persons.parquet self-aliases
```

### Day-one `person_id` strategy (hybrid B-ii + TCPD seed)

The strategy has five layers, designed to be **honest about uncertainty by default** and **promotable as evidence arrives**.

**Layer 1 — Default identity**: one person per candidacy row.

```
person_id = sha256(state_code || ac_id || election_id || normalised_candidate_name)[:16]
```

`M. Kumar (TN, 1962)` and `M. Kumar (TN, 1989)` start as two persons. Identity is honest about not knowing; merges arrive as evidence does.

**Layer 2 — Merge overlay**: hand-authored `taxonomy/person_aliases.json` (text per ADR-0030 §D18) compiles to `taxonomy/persons.parquet` + a `(candidacy_key → person_id)` lookup table. Each cluster row carries:

```
cluster_id          string  PK
candidacy_keys      list<string>   FK back to the layer-1 person_ids being merged
display_name        string         the citizen-facing name for the cluster
source_id           string  FK     to taxonomy/sources.parquet — what evidence justifies the merge
evidence_note_md    string         human-readable rationale
confidence_tier     enum           gold | silver | bronze
```

**Layer 3 — Seed**: bulk-import TCPD `Candidate_ID` clusters for the Tamil Nadu AE corpus as the first batch of `person_aliases.json` rows. `source_id` = TCPD dataset row in `sources.parquet`; `confidence_tier: silver` (TCPD is a reputable republisher; not the issuing authority); `is_issuing_authority: false`.

**Layer 4 — Merged identity**: clustered rows get a new content-addressable identity:

```
person_id (merged) = sha256(sorted_candidacy_keys || sorted_source_ids)[:16]
```

Content-addressable on cluster contents — splits are recoverable because the original layer-1 candidacy keys are preserved.

**Layer 5 — Promotion path**: when ECI Form 26 affidavit ingest unblocks, affidavit DOB + father's name + permanent address promote a cluster from `silver` to `gold` *without re-issuing `person_id`*. The cluster simply gains a new `source_id` row; the cluster hash is stable. This is the merge-only-add-evidence pattern adopted from OWID's `origin.*` upgrade rule.

### False-merge recovery

If a `person_aliases.json` cluster turns out to wrongly merge two real people:

1. Edit `person_aliases.json` (remove the bad cluster entry).
2. Recompile.
3. The split person gets a fresh `person_id` (layer 1 default); the remaining cluster keeps its identity (still hashes to the same value because the bad key is no longer in the sort order).
4. The split is logged in `migration-ledger.csv` as `person_id_split: <old> → <new1>, <new2>`.
5. Frontend `/person/<old>` renders one-release `301 → see [new1] / [new2]` then 404.

Same shape as the `id_aliases` mechanism in `indicator.schema.json` (T.3 row in `§0e.7`); identity errors are reversible without history loss.

### What stays unchanged

- The `dim_candidates` rename is the only schema break in `elections/`. The election results fact (`election_results.parquet`) is unchanged.
- Frontend election routes (`/lab/<state>/<event>`, `/compare/<state>/<event>`, `/results/<state>/<event>/<ac>`) consume `elections_candidacies.parquet` × `dim_persons.parquet` × `election_results.parquet`. Joining `election_results.candidacy_key → elections_candidacies.candidacy_key → dim_persons.person_id` is one extra JOIN at chart time; the loader hides it from renderers per ADR-0030 §D19.
- The frontend government routes (`/government/<state>`, `/cm-timeline/<state>`) consume `governments_office_holdings.parquet` × `dim_persons.parquet` × `taxonomy/entities.parquet` (offices as taxonomy entities per `entity_type='office_bearer'`, locked in `§0e.6` of the canonical-pivot plan).

## Consequences

### Good

- **One identity for one citizen question.** "Who is this person?" has a single canonical answer at any point on the timeline.
- **TCPD cluster work absorbs cleanly.** Five years of Ashoka's name-merge curation lands as a single hand-authored seed, not as a per-state heuristic.
- **Office-holdings get a real FK target.** `cm_terms.json` retirement (per G.1 row, shipped 2026-05-22 via PRs #89/#90/#91) can land on `dim_persons` cleanly.
- **Honest uncertainty.** Bronze/silver/gold confidence tiers let the citizen UI hedge appropriately — "based on name-match only" vs "TCPD-confirmed" vs "affidavit-confirmed" — without losing the row.

### Bad

- **Schema break on `dim-candidates.schema.json` → `dim-persons.schema.json`.** Bumps major (1.x → 2.0). The `id_aliases` mechanism on the schema keeps one release of back-compat, but downstream tooling that hard-codes the file name has to update in the same commit.
- **TCPD license is CC-BY-NC-SA 4.0.** The "SA" (share-alike) clause means downstream Parquet derivatives inherit CC-BY-NC-SA. yen-gov is non-commercial public-good, so the NC clause is fine; but the SA propagation needs Hans to confirm at S.1 ship time and to record the license-id explicitly in `taxonomy/sources.parquet` for the TCPD row. **Blocks**: S.1 cannot merge until this is confirmed. *(Open follow-up — not in this ADR's commit.)*
- **Two-table join overhead** on every per-AC results page. Benchmarked at ~12 ms on DuckDB-WASM cold cache; acceptable per Fowler 2026-05-19.

### Migration cost

- One schema bump (`dim-candidates` → `dim_persons`; v1.x → v2.0).
- One fused atomic commit per the §15 paired-test discipline: schema + Pydantic model + DDL + parquet rewrite + frontend `DimCandidate` → `DimPerson` rename + new `Candidacy` TS type + Zod validator update.
- Delete `datasets/people/AcGenApr2021/` in the same commit (it was the orphan pre-canonical scratch directory; per `§0e.8`, "commit becomes the backup").

## Alternatives considered (rejected)

### A — Smallest reversible step: keep `dim_candidates`, add separate `dim_persons` for governments only

The agent panel's first-round default (2026-05-19, PR #56). Add `dim_persons.parquet` for the government side only; leave `dim_candidates` untouched; accept the duplication; revisit later.

**Rejected** by user override. Three reasons converged:

1. The duplication has a known cost (every "who is this person?" question forks at the loader, with no canonical answer) and an unknown ceiling (every new family that mentions a person — affidavits, ITR disclosures, CAG audit findings — re-asks the same question and the parallel-tree pattern compounds).
2. The TCPD seed has no home in Option A. Half the corpus would land on `dim_candidates` (for election queries) and half on `dim_persons` (for government queries) — a permanent two-tier where the citizen surface shows different names depending on which page they enter from.
3. Reversibility is asymmetric. Option B → Option A is one commit (drop `elections_candidacies`, fold back into `dim_candidates`). Option A → Option B is many commits across two families because both families have evolved consumers in the meantime. Take the harder step while the consumer count is small.

### C — `dim_persons` keyed on an upstream-provided ID (no own grammar)

Adopt TCPD `Candidate_ID` as `person_id` directly. Skip the layer-1 default; only persons with a TCPD cluster get a row.

**Rejected** because TCPD coverage is non-uniform — strong on Lok Sabha and TN-AE; thin on other state AEs; absent on municipal and panchayat elections. Keying on TCPD strands every non-TCPD person without identity, breaking the loader for the long tail. The layer-1 default + TCPD seed is the right shape: every person gets identity day-one, TCPD evidence promotes a subset to merged identity.

### D — Universal natural-key string (no hash)

Use a deterministic string like `IN-S22-2021-167-rangaraj-balasubramanian` as `person_id`. Human-readable; useful for debugging.

**Rejected** because (a) name normalisation across Indian transliteration variants is itself the merge problem we're trying to solve — putting it in the identity is circular; (b) renaming a person (cluster gets `display_name` updated) would require migrating the identity, breaking history; (c) entity IDs across the canonical store are short hashes per `canonical-store.md §3a` for consistency, and persons should not be a special case.

### E — Tombstone, don't rename — keep `dim_candidates` alive, add `dim_persons` parallel-track, deprecate `dim_candidates` over time

Strangler-fig the rename. Mark `dim_candidates` deprecated; new consumers use `dim_persons`; both live until every consumer migrates.

**Rejected** per ADR-0030 §D13 (rip-and-replace, no strangler-fig). Site not yet live; strangler is overhead when no users depend on the old shape. The fused atomic commit pattern (§15 paired-test discipline) handles the rename in one shot.

## Doc impact

- **[canonical-store.md §3a](../data/canonical-store.md)** — entity-id grammar gains `person_id` (16-char content hash) and the `office_bearer` entity_type already absorbed by §0e.6 / G.1 work shipped 2026-05-22.
- **[ADR-0030 §D27](0030-canonical-store-duckdb-wasm.md)** — entity_type enum already lists `office_bearer` and the open question Q on `person_id` is now resolved here.
- **`docs/architecture/data/elections.md`** (if/when authored) — `elections_candidacies.parquet` shape lands there; this ADR is the rationale.
- **`docs/architecture/data/governments.md`** (if/when authored) — `governments_office_holdings.parquet` shape lands there; this ADR is the rationale.
- **`TODO/20260517-canonical-long-format-pivot.md` §0e.5** — to be deleted in the plan-doc slim commit; this ADR replaces it.

## Status of dependent PRs

As of 2026-05-22:

- **G.1.a / G.1.b / G.1.c** (office-bearer consolidation, PRs #89 / #90 / #91) — **SHIPPED** on `main`. This ADR documents the persons-side decision they assumed; G.1 was unblocked by relaxing the dependency on S.1 because office identity is its own taxonomy island (per `§0e.6`).
- **S.1** (persons rename + dual-fact) — **NOT YET SHIPPED**. Blocked on TCPD license confirmation (Hans). When unblocked, S.1 lands as one fused atomic commit per this ADR.
- **T.3** (indicator catalogue widens for `topic_tags[]` + drops topic prefix) — independent of S.1; can land in any order.
