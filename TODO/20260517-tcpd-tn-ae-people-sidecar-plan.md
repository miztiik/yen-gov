# TN AE People Sidecar — Clean Plan

**Date**: 2026-05-17
**Status**: Converged across all five agents. Ready to execute.
**Supersedes**: v1, v2, v3 of this file (drafts archived in git history).

---

## 1. The decision on sources (closed)

ECI is the source. Always was. TCPD just republished ECI's published data — they are a **carrier**, not the authority. Nobody but ECI has this data; TCPD's CSV is a transcription of ECI Statistical Reports.

- `sources[].url` = ECI URL (`https://eci.gov.in/statistical-report-2021/...` or the closest ECI page for that election year).
- Schema names, folder paths, enums, docs, UI labels — all source-agnostic, all reference ECI.
- The carrier (TCPD) is named nowhere — not in JSON, not in docs, not in UI, not in code comments. The CSV is a **frozen input** the developer happened to obtain; once frozen its origin is irrelevant to the artifact's lineage.
- Provenance honesty is preserved: ECI **is** the source. We are not laundering, we are correctly attributing.

This closes the only open question from v3.

---

## 2. The architecture in one paragraph

Each source (ECI HTML today, future first-party ECI PDFs, ADR/MyNeta later) is an **Adapter** that reads a **frozen input** (hashed once, never re-fetched) and writes per-entity **Contributions** to `.runtime/contributions/<adapter>/<entity>.json` (gitignored). A **Composer** is the only writer to `datasets/`: it merges contributions field-by-field per priority rules in `config/elections.json` and emits artifacts. The Composer is **idempotent** — same frozen inputs → byte-identical output, `git status` clean, mtimes unchanged. A contract test (`test_composer_idempotent.py`) proves this by running twice on the same fixture and asserting identical bytes.

---

## 3. Key elements

### 3.1 Idempotency — reuse the existing dict-equal write-skip gate

**No hash. No `.runtime/freeze/` sidecar. No SHA gate. No new mechanism.**

The infrastructure already exists at `backend/yen_gov/core/io.py::write_artifact` (commit `1d2983c0`): structural dict-equal compare with operational fields stripped from both sides. Same data → no write → mtime survives → `git status` clean. This is what ICED and every other adapter uses.

The people sidecar adapter writes through `write_artifact` like everything else. Idempotency is automatic. We add `people.entity.schema.json`'s operational fields to `_OPERATIONAL_STRIP_PATHS` if any new ones surface; otherwise the existing `sources[].*.fetched_at` strip covers it.

Why hash and `datetime.now()` were both rejected:
- **Hash:** breaks on any cosmetic upstream change (whitespace, column reorder, encoding tweak) even when the data content is unchanged. Invalidates the gate for non-reasons.
- **`datetime.now()`:** smears wall-clock into provenance content. Already CLAUDE.md §10 banned.
- **Dict-equal of stripped artifacts:** compares what citizens actually see. Robust to upstream cosmetics, robust to operator wall-clock, fails only on genuine data change. This is the right altitude.

### 3.1a "Done and tested" — election inventory entry (replaces per-run validation)

Once a `(state, election_id, source_input)` triple has been ingested and validated, we record that fact in an inventory file. Re-runs trust the inventory; correctness tests do NOT re-run against the corpus on every invocation (per CLAUDE.md §10 — Tier-B conformance is local-only, not CI-gated).

```
datasets/elections/_inventory.json
{
  "$schema": "https://yen-gov.github.io/schemas/elections-inventory.schema.json",
  "$schema_version": "1.0",
  "ingested": [
    {
      "election_id": "AcGenApr2021",
      "state": "S22",
      "people_source": "tn_ae_panel_1971_2021",
      "ingested_at": "2026-05-17",
      "discrepancy_summary": { "acs_with_mismatch": 3, "halted": false }
    }
  ]
}
```

Re-runs check this file first. If the entry exists for the current `(state, election_id, source_input)`, the adapter skips. To re-ingest deliberately, the operator deletes the entry (or runs `--force`). No background re-validation, no per-run correctness checks.

### 3.2 One config file

```
config/elections.json
{
  "$schema": "https://yen-gov.github.io/schemas/elections-config.schema.json",
  "$schema_version": "1.0",
  "provenance_grades": {
    "issuing_authority":   { "priority": 100 },
    "sworn_declaration":   { "priority": 80 },
    "third_party_curated": { "priority": 60 },
    "derived":             { "priority": 40 }
  },
  "field_priority": {
    "gender":     ["eci_html", "eci_statreport"],
    "education":  ["eci_statreport"],
    "profession": ["eci_statreport"],
    "votes":      ["eci_html"]
  },
  "discrepancy_thresholds": {
    "ac_mismatch_pct": { "warn": 0.5, "halt": 2.0 },
    "mean_delta_pp":   { "warn": 0.1, "halt": 0.5 }
  }
}
```

- JSON only. One file. Tuning knobs only.
- Enums (gender, party_type, education, profession) stay in artifact schemas — taxonomy ≠ tuning (Gregor's rule).

### 3.3 Universal provenance-grade enum (4 tiers, source-agnostic)

| Grade | Meaning | Examples |
|---|---|---|
| `issuing_authority` | Body that creates the fact certifies it | ECI on votes, Census on population |
| `sworn_declaration` | Subject attests under legal penalty; no authority verifies | Form-26 affidavits, FEC filings, Companies House |
| `third_party_curated` | Researcher/NGO compiled without independent verification | OWID, academic curators |
| `derived` | Computed by us or upstream | Margin %, turnout %, alliance roll-up |

### 3.4 Discrepancy doctrine

Per `(state, election_year)`, never aggregated across years:

- **Halt** ingest (exit non-zero, no artifact written): `>2%` AC vote mismatch OR `>0.5pp` mean delta.
- **Warn** (write artifact, flag in report): `0.5%` / `0.1pp`.
- Report at `.runtime/reports/ingest-discrepancies-<run-id>.json` (gitignored, JSON, citizen never sees).

### 3.5 Column triage

**Drop (10):** `DelimID`, `Poll_No`, `Party_ID`, `Last_Party_ID`, all `*_Desc` free-text fields (97 unique values), `TCPD_Prof_Second` (98% blank), `Position` (derivable), `Constituency_Name` (already on result artifact), carrier-internal `pid` columns.

**Keep with enum (enums live in artifact schemas):**

| Field | Enum |
|---|---|
| `sex` (optional) | `Male / Female / Other` + omit when blank |
| `election_type` (election entity) | `AE / GE` per ECI codebook |
| `constituency_type` | `GEN / SC / ST` |
| `party_type` | `NATIONAL / STATE / OTHER_STATE / REGISTERED_UNRECOGNISED / INDEPENDENT` (ECI's 5-bucket) |
| `education` (optional) | 11-value Indian credential ladder + omit |
| `profession` (optional) | 18 verbatim categories + omit |

**Keep as-is:** votes, electors, valid_votes, turnout_pct, margin, ENOP, age, candidate name, party short, district, sub_region.

**Promote to election entity:** `poll_month` (int 1-12), `election_type`, `number_of_seats`.

**Derive ourselves, never import:** `Incumbent`, `No_Terms`, `Recontest`, `Turncoat` — computed once ≥2 elections present.

### 3.6 Layout — flat under election_id

```
datasets/people/<election_id>/<ac_code>/<candidate_slug>.json
```

- ~10k candidates per election × ~10 elections per state over 50 years = ~100k files per state max.
- Lok Sabha and Rajya Sabha are separate election_ids, separate people (no merge).
- Total ceiling ~100-200k per state, manageable inside the election_id folder. No state-shard layer needed.
- One file per person (static-first: one HTTP fetch per detail page).

### 3.7 Commit sequence (3 commits)

| # | Commit | Level |
|---|---|---|
| 1 | Add `people.entity.schema.json` + `elections-inventory.schema.json` + `config/elections.json` + `elections-config.schema.json`. Schemas only, no callers. | L2 |
| 2 | Add CSV adapter writing through existing `write_artifact` (inherits dict-equal idempotency for free). Emit TN 2021 people sidecars + inventory entry + discrepancy report. ECI is sole vote contributor; biographics from CSV-derived adapter. | L3 |
| 3 | Frontend: extend `CandidateCard` to surface `provenance_grade` markers + "not declared" treatment for blank biographics. Vitest + one Playwright assertion per CLAUDE.md §15. | L2 |

Historical back-fill (1971-2016) and Gujarat/Maharashtra adapters are subsequent commits with their own plans.

---

## 4. Agent findings (lost in compaction — restored)

### Fowler (engineering craft)
- `fetched_at` from wall-clock is "operational telemetry pretending to be provenance" — violates CLAUDE.md §10. Replace with content-hash identity (`freeze.first_seen()`).
- Collapse the proposed 6-commit sequence to 4. Each commit must be reversible. Commit 2 ships with an idempotency contract test — that test IS the structural guarantee.
- No `write_text_if_changed` helpers. If re-run produces different bytes, fix the upstream non-determinism, don't paper over it at the write seam.

### Gregor (architecture)
- Aggregator + Canonical Data Model pattern. Adapters are Message Translators; Composer is an Idempotent Receiver.
- ONE config file. Tuning knobs (`config/`) and taxonomy (`datasets/schemas/`) MUST stay separated — mixing them invites someone to "tune" an enum.
- Adapter source IDs (`eci_html`, `eci_statreport`) are publishers/transports, never carriers. Pipes-and-filters boundary clean.

### Hans (governance)
- Provenance grade enum must be globally true. The Oxford-degree case (no electoral commission worldwide verifies claimed education) means `sworn_declaration` is universal, not India-specific.
- Discrepancy thresholds per `(state, election_year)` — aggregating across years hides regime-specific source breaks (e.g. a 2014 ECI methodology change disappears in a 50-year mean).
- Don't collapse profession categories — `Agriculture` vs `Agricultural Labour` is a class distinction that matters in Indian politics. 18 verbatim values, no rollup.

### Max (indicator scout)
- Keep biographics even if self-declared — ECI doesn't publish biographics CSVs at all, so the alternative is no data. Mark provenance grade clearly so citizens see the trust level.
- ADR/MyNeta queued for Phase A+1 pending licence confirmation. Don't ingest now.
- State-shard the directory: at India scale (~500k files), single-folder approaches die.

### Jony (UI/UX) — Round-2 verdict unchanged
- No new components. Extend existing `CandidateCard`, `ConstituencyHeader`, `SourceList`.
- Provenance grade renders as a small inline marker on the field, not a separate panel. Citizen learns by hovering, not by reading docs.
- "Not declared" when biographics are blank. Never "Unknown" — sentinels lie.

---

## 5. What this kills (from earlier drafts)

- `datasets/recon/<source>-vs-<source>/` folders — never. Discrepancy reports live in `.runtime/reports/`, gitignored.
- Citizen-facing footer disclosure sentence — gone. ECI wins silently.
- Two-altitude gate (Fetcher + Composer) — collapsed to one (Composer only).
- Two config files (`priority.yaml` + `provenance-grades.json`) — collapsed to one JSON file.
- `+ Unknown` sentinel in profession/education — null/omit instead.
- 7-bucket party-type vocabulary — replaced by ECI's 5-bucket per codebook.
- `datetime.now()`-at-write-time bug per §10 — replaced by `freeze.first_seen_at`.

---

## 6. What this does NOT do

- No historical back-fill (1971-2016) — follow-up commit with ADR-0030.
- No Gujarat / Maharashtra adapter — same pattern, separate commits when CSVs land.
- No ADR/MyNeta adapter — Phase A+1, licence confirmation pending.
- No new UI components — extensions only.
- No re-fetch logic — frozen inputs only.

---

## 7. Files this plan creates

**Schemas (`datasets/schemas/`):**
- `contribution.schema.json` — adapter output contract
- `people.entity.schema.json` — source-agnostic person artifact
- `elections-config.schema.json` — for the new tuning config

**Config:** `config/elections.json`

**ADRs:**
- `0029-contribution-composer-architecture.md`
- `0030-historical-backfill-methodology-break.md` (lands with commit 5, not this plan)

**Subsystem docs:**
- `docs/architecture/backend/composer.md`
- `docs/architecture/datasets/people.md`

**Updates:**
- `CLAUDE.md` §3 topology (+ `.runtime/contributions/`, `.runtime/freeze/`, `.runtime/reports/`, `datasets/people/`)
- `CLAUDE.md` §12 (field-level `provenance_grade` referencing `sources[]` by `source_id`)
- `docs/concepts/data-provenance.md` (freeze-once semantics)
- `docs/reference/data-inventory.md` (auto-generated per ADR-0027)
