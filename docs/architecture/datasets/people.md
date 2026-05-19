# People (candidate biographics) — RETIRED

**Last Updated**: 2026-05-20

> **Status: retired in PR-S.2 (canonical pivot, phase 1.8f).** This doc describes the per-candidate JSON sidecar (`datasets/people/<event>/<ac>/<slug>.json`) and the matching `people.entity.schema.json` v1.0. Both were deleted; biographic fields now ride as columns on the canonical store and there is no separate "people" surface anymore.
>
> **Where biographics live now:** the six citizen-readable fields ECI publishes (`sex`, `age`, `education`, `profession`, `constituency_type`, `party_type`) are nullable columns on `datasets/elections/dim_candidates.parquet` v1.2 (added in PR-S.1; backfilled from the retiring JSONs into 1,134 of 34,906 dim rows, covering Tamil Nadu AcGenApr2021). Canonical reference: [`docs/architecture/data/canonical-store.md` §11.5](../data/canonical-store.md).
>
> **Where the citizen reads them:** [`frontend/src/lib/view-models/constituency.ts`](../../../frontend/src/lib/view-models/constituency.ts) joins `dim_candidates` into the per-candidate result row and emits a `bio` object on `CandidateResult`. [`frontend/src/routes/Constituency.svelte`](../../../frontend/src/routes/Constituency.svelte) renders the chip under each candidate's name when `bio` is non-null. The 404-tolerant `fetchPersonEntity()` loader is gone; so is `slugifyCandidate()`.
>
> **Where the publisher fidelity lives:** the pure adapter [`backend/yen_gov/sources/eci/people_panel.py`](../../../backend/yen_gov/sources/eci/people_panel.py) still parses the TCPD-Ashoka panel CSV into `PersonRow` instances. The orchestrator [`backend/yen_gov/pipeline/people_ingest.py`](../../../backend/yen_gov/pipeline/people_ingest.py) now UPSERTs those rows onto `dim_candidates.parquet` via `_upsert_dim` in [`backend/yen_gov/canonical/writer.py`](../../../backend/yen_gov/canonical/writer.py) (additive `INSERT BY NAME`; sorted COPY emit for byte-idempotency). The `compare_winner_votes` discrepancy QA gate is preserved verbatim — it already reads the canonical Parquet (PR-O.3b-main).
>
> **What still lives in the original design (preserved for reference):**
>
> - The 4-tier provenance grade lexicon (`issuing_authority`, `sworn_declaration`, `third_party_curated`, `derived`) — still the right doctrine for "don't pretend self-declared fields are verified". Now expressed at the indicator / source level via `datasets/taxonomy/sources.parquet` rather than per-field on the artifact.
> - The 17-value `profession` enum preserving class distinctions (Agriculture vs Agricultural Labour, Business vs Small Business) — copied verbatim onto the `dim_candidates.profession` column, including the Hans rationale that "no rollup at the schema level".
> - The "Null is omitted, never `Unknown`" rule — same, expressed as `IS NULL` checks on the canonical columns.
> - The `_inventory.json` + halt/warn discrepancy doctrine (`>2% / >0.5pp` halt, `0.5% / 0.1pp` warn, per `(state, election_year)`) — unchanged; the orchestrator still writes it.
>
> **Why retired:** the JSON sidecar tree was 3,983 files across one election (TN 2021) on the way to ~100k+ if extended to every state × every year. Reading it forced one HTTP fetch per candidate from the citizen browser. Lifting bio onto `dim_candidates` collapsed that to a single Parquet HTTP range request alongside the result rows the page already loads (canonical pivot §0a/0b — OWID-style long-format wins on URL economy and on schema simplicity).
>
> **Inbound links:** [`TODO/20260517-tcpd-tn-ae-people-sidecar-plan.md`](../../../TODO/20260517-tcpd-tn-ae-people-sidecar-plan.md) (historical plan; do not implement). [`docs/architecture/canonical-pivot-deletion-manifest.md`](../canonical-pivot-deletion-manifest.md) row 1.8f marks the family ✅.
