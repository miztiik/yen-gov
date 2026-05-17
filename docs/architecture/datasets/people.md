# People (candidate biographics) sidecar

**Last Updated**: 2026-05-17

A per-person, source-agnostic record of candidates who appeared on the ballot in a given election. ECI publishes vote facts in machine-readable form (Section 10 HTML) but biographics (sex, age, education, profession, party_type) only in PDF Statistical Reports — this sidecar carries those fields without forcing every consumer to parse PDFs.

See also: [`docs/concepts/data-provenance.md`](../../concepts/data-provenance.md), [`backend/yen_gov/core/io.py`](../../../backend/yen_gov/core/io.py), `datasets/schemas/people.entity.schema.json`.

## Identity and layout

Files live at `datasets/people/<election_id>/<ac_code>/<candidate_slug>.json`. The triple `(election_id, ac_code, candidate_slug)` is the natural key; vote facts on `result.constituency.json` are joined by `(election, eci_no, name)`.

State is on the record (`state: "S22"`) but does not appear in the path — single-folder per election scales fine to the ~100-200k-per-state ceiling we expect. Lok Sabha and Rajya Sabha are separate election_ids carrying separate people; no merge.

## Why a sidecar, not fields on result.constituency

Vote facts and biographics have different provenance grades, different update cadences (biographics are static after declaration; votes can be revised in long counts), and different consumers (turnout pages want vote totals only; candidate-detail pages want biographics). Folding biographics into the result artifact would force every reader to load both and bloat the JSON the citizen pages over the wire. Per-person files = one HTTP fetch per detail page (static-first).

## Per-field provenance

The `field_provenance` map carries the universal 4-tier grade for each biographic field plus the adapter id that contributed it:

```json
"field_provenance": {
  "sex":        { "grade": "issuing_authority",   "source_id": "eci_html" },
  "age":        { "grade": "sworn_declaration",   "source_id": "eci_statreport" },
  "education":  { "grade": "sworn_declaration",   "source_id": "eci_statreport" },
  "profession": { "grade": "sworn_declaration",   "source_id": "eci_statreport" },
  "party_type": { "grade": "issuing_authority",   "source_id": "eci_html" }
}
```

- `issuing_authority` — the body creating the fact certifies it (ECI on vote-related fields and party classification).
- `sworn_declaration` — subject attests under legal penalty; no authority verifies. Globally true (no electoral commission worldwide verifies claimed education or profession).
- `third_party_curated` — researcher compiled without independent verification.
- `derived` — computed by us or upstream.

Citizens see a small marker on each field; hovering reveals the grade. Doctrine: don't pretend self-declared fields are verified.

## Enum choices

All enums live in the schema, not in `config/elections.json` (taxonomy ≠ tuning):

| Field | Source | Values |
|---|---|---|
| `sex` | ECI codebook | `Male / Female / Other` + null |
| `party_type` | ECI codebook (5-bucket) | `NATIONAL / STATE / OTHER_STATE / REGISTERED_UNRECOGNISED / INDEPENDENT` + null |
| `constituency_type` | ECI | `GEN / SC / ST` + null |
| `education` | Indian credential ladder | 11 verbatim values + null |
| `profession` | ECI Statistical Report categories | 17 verbatim values + null |

Blank values are represented as `null`/omitted, never as `"Unknown"` or other sentinels (sentinels lie about whether a value was recorded). UI says "not declared".

The 17-value profession enum preserves class distinctions (Agriculture vs Agricultural Labour, Business vs Small Business or Self-employed, Labourer vs Liberal Profession) that matter in Indian political analysis (Hans). No rollup at the schema level.

## Idempotency

Reuses the existing `write_artifact` dict-equal write-skip gate (`backend/yen_gov/core/io.py`, commit `1d2983c0`). No new mechanism, no hash sidecar. Operational fields stripped from both sides before compare; same data → no write → `git status` clean.

## "Done and tested" — elections inventory

`datasets/elections/_inventory.json` records each `(election_id, state, source_input)` triple that has been ingested and validated. Re-runs check the inventory and skip; operators delete an entry or pass `--force` to re-ingest deliberately. Replaces per-run corpus validation per CLAUDE.md §10 (Tier-B is local pre-emit, not CI-gated).

The `discrepancy_summary` block on each entry carries headline numbers (ACs total, ACs with mismatch, halt/warn flags) so a human scanning the inventory can spot regressions without opening the full report at `.runtime/reports/ingest-discrepancies-<run-id>.json`.

## Discrepancy doctrine

Per `(state, election_year)`, never aggregated across years (Hans: aggregation hides regime-specific methodology breaks):

- **Halt** ingest (exit non-zero, no artifact written) at `>2%` AC vote mismatch OR `>0.5pp` mean delta.
- **Warn** (write artifact, flag in report) at `0.5%` / `0.1pp`.

When biographic adapters (e.g. a future CSV-derived adapter) ship vote columns too, those are compared against ECI HTML; ECI wins, the discrepancy is reported, biographics survive the merge.

## Frontend rendering

The constituency route (`frontend/src/routes/Constituency.svelte`) fetches the per-candidate sidecar via `fetchPersonEntity(event, ac_code, slugifyCandidate(name))` in `frontend/src/lib/data.ts`. The loader is 404-tolerant — most (election, AC, candidate) triples have no sidecar yet (only TN AE 2021 is ingested at time of writing), and absence renders as `Not declared` rather than as an error.

`slugifyCandidate` is a verbatim mirror of the backend's `yen_gov.sources.eci.people_panel.slugify` (ASCII-fold → lowercase → collapse non-alphanumerics to hyphens). Both sides MUST stay in lockstep — the slug is the join key between the result.constituency `candidates[].name` field and the people sidecar filename. The vitest suite (`frontend/src/lib/data.test.ts`) covers the same fixtures as the pytest suite (`backend/tests/test_people_panel.py::test_slugify_*`) so drift is caught at unit-test tier.

The biographic line under each candidate name shows only fields that are populated (`Male · age 60 · 10th Pass · Business`), in field order matching the schema. Null fields are omitted entirely from the join — no "Unknown" sentinel, no per-field `Not declared` label — and the whole line collapses to `Not declared` only when ALL biographic fields are absent. This is the citizen-honest treatment Hans asked for: don't manufacture a value where the candidate didn't declare one.
