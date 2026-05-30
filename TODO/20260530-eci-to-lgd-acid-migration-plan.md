# Level-5 plan: `eci_no` -> LGD `AC_ID` corpus migration

**Last Updated**: 2026-05-30

**Predecessor plan-doc**: [TODO/20260530-boundary-followups-execution-plan.md](20260530-boundary-followups-execution-plan.md) Row 4.4 (was Row 5.2 pre-PR #471 cleanup; this plan-doc opens that row's research-only first PR).

**Status**: RESEARCH-ONLY first PR shipped via #469. Subsequent migration rows ESCALATE per CLAUDE.md §6 Level-5 ("Design consultation only - pause work"). Agent does NOT execute beyond R1 without explicit user design sign-off + this plan-doc being amended in the same commit as the sign-off.

---

## section 0. Operating contract

### 0.1 Why this plan-doc exists

The "LGD-golden" doctrine (per [docs/concepts/admin-level-sourcing.md](../docs/concepts/admin-level-sourcing.md) + Phase A.1 of the 20260530 plan-doc) made LGD the authoritative spine for Assembly Constituency identity. Boundary shards now key on `lgd_ac_id` (numeric LGD identifier) while election-results parquets + indicator-family tables + SoT files + frontend join logic still key on `eci_no` (ECI's per-state 1-to-N enumeration). The two-spine state is workable for the current citizen surfaces but creates ongoing translation cost on every cross-cut and blocks any future "national AC-level indicator" that needs a single primary key.

This plan-doc opens the migration arc. It does NOT start migrating; it commissions the audit that tells the user how big the rewrite is + which surfaces would have to change + what the user-experience-visible risk is for each surface.

### 0.2 Hard-coded scope of the FIRST PR (this PR via _pending_)

ONLY R1 — write a research-note auditing all `eci_no` read + write sites. No data rewrite. No frontend join changes. No schema changes. No code execution beyond the audit walk.

### 0.3 ESCALATE triggers (everything beyond R1)

The migration rows (R2 onwards: data rewrite, schema changes, join-key refactor, frontend join logic, contract-test updates, distillation) ALL ESCALATE. Agent does NOT execute any of them without:

1. User reading the R1 research-note + explicitly approving migration strategy
2. This plan-doc amended with the chosen strategy + per-row acceptance gates IN THE SAME COMMIT as the approval

This is the CLAUDE.md §6 Level-5 contract verbatim: "Core design / data model / runtime — Design consultation only — pause work".

---

## section 1. Status Reckoner

| Row | Title | Status | PR | Effort |
| --- | --- | --- | --- | --- |
| R1 | Audit all `eci_no` read + write sites; produce research-note + migration-surface map | [ ] PENDING | #469 | S (~2-4h next session) |
| R2 | Migration strategy (chosen by user from R1's options) | [!] ESCALATED | n/a | TBD |
| R3+ | Per-surface migration PRs (data rewrite, schema, frontend, tests) | [!] ESCALATED | n/a | XL |

---

## section 2. Row R1 — Audit + research-note (THIS PR's deliverable)

### R1 acceptance

This PR (#469) ships:

1. THIS plan-doc with the operating contract + Row R1 spec.
2. R1 acceptance is bounded — actual research-note authoring happens in a future PR; this PR opens the docket.

The research-note (separate PR) will be at `notes/<YYYYMMDD>-eci-to-acid-migration-surface-audit.md` and MUST list, exhaustively:

- **Read sites** in `frontend/`: every `.ts` / `.svelte` file that reads `eci_no` from any data source (parquet via DuckDB, JSON sidecar, URL parameter, contract test fixture). For each site: file:line, what it reads `eci_no` FOR, what it would key on POST-migration.
- **Read sites** in `backend/`: every Python module that reads `eci_no` from any source.
- **Write sites** in `backend/`: every parquet / JSON emit that carries `eci_no` as a column or key.
- **SoT files**: every `datasets/reference/in/states/<state>/constituencies.json` that lists `eci_no` as the citizen-recognizable enumeration.
- **Election-results parquets**: per-election manifests that key results to `eci_no`.
- **Indicator-family tables**: any AC-grain indicator parquet that uses `eci_no` as the grain dimension.
- **Frontend join logic**: every `maplibre` boundary -> data join that does `properties.eci_no === row.eci_no`.
- **Contract tests**: every `frontend/src/contracts/*.test.ts` + `backend/tests/test_*.py` that asserts on `eci_no` as the key.

### R1 deliverable structure (for the future PR)

The research-note will tabulate sites in 8 sections (one per surface above) + a "migration-surface map" diagram showing the dependency order (which sites are downstream of which) + 3-5 candidate migration strategies (e.g. (a) big-bang corpus rewrite, (b) dual-key co-existence with adapter layer, (c) read-side translation table + lazy migration, (d) keep ECI as citizen-display + LGD as internal-only, (e) just-the-bits-that-need-national-spine).

R1 explicitly does NOT recommend a strategy. The user picks from the 3-5 options + the agent's R1 estimated effort/risk per option.

### R1 NOT-in-scope

- Implementing any of the migration strategies
- Modifying any data file
- Modifying any frontend / backend code (except possibly adding a `// TODO: migration audit captured in <note>` marker, which is itself ESCALATE-able)
- Touching schemas
- Touching contract tests

---

## section 3. ESCALATE triggers (rows R2+)

R2 ("migration strategy chosen + per-row acceptance gates amended into this plan-doc") requires user reading R1 + naming the strategy. Until then, R2 ESCALATES.

R3+ (per-surface migration PRs) each require:

1. R2 strategy chosen + this plan-doc amended
2. Per-row acceptance gates + per-row blast-radius documented in this plan-doc BEFORE the row's PR opens
3. Each row's PR is its own Level-3 or Level-4 work (4+ files, structural)

---

## See also

- [TODO/20260530-boundary-followups-execution-plan.md](20260530-boundary-followups-execution-plan.md) Row 4.4 (was Row 5.2; this plan-doc opens that row)
- [docs/concepts/admin-level-sourcing.md](../docs/concepts/admin-level-sourcing.md) (LGD-golden doctrine + 3-convention rule)
- [docs/architecture/decisions/0029-unmapped-region-chips.md](../docs/architecture/decisions/0029-unmapped-region-chips.md) (D.1.A user-mandate + retirement context)
- [CLAUDE.md](../CLAUDE.md) §6 Level-5 ("Core design / data model / runtime - Design consultation only - pause work")
