# ADR-0016: ECI Statistical Reports as the canonical source for past-election enrichment

**Last Updated**: 2026-05-09
**Status**: accepted

## Context

ADR-0015 introduced the `status: provisional | complete` lifecycle on `constituency.schema.json` and required at least one ECI-domain URL in `sources[]` before promoting to `complete`. It listed the Delimitation Order 2008 (PDF), `results.eci.gov.in` (HTML), and CEO state portals (mixed) as the acceptable ECI sources, in that order.

Two facts changed the picture:

1. The user identified the [ECI Statistical Reports hub](https://www.eci.gov.in/statistical-reports) as a much richer resource than was previously catalogued. Per-election landing pages at `https://www.eci.gov.in/statistical-report/{ae|ge}/{year}/{display-state-code}` carry the **full official statistical report** for an election: constituency-wise results, candidate-wise results, party-wise summary, vote share, electors, turnout. Many of these are published as XLSX, which we can parse losslessly.
2. The user explicitly designated ECI as the canonical source for enrichment, asked to bootstrap West Bengal (S25) reference data from ECI rather than Wikipedia, and asked for an exploration pass against TN, Kerala, and WB across the last three assembly cycles.

This ADR codifies the policy before any tooling is written, so the recon and enrichment workstreams don't accumulate ad hoc decisions.

## Decision

### 1. ECI Statistical Reports are the canonical source for any past-election enrichment

For any past election (assembly or general), when filling out fields that are not pure constituency reference (boundary) data — i.e. results, vote counts, candidate counts, electors at poll-time, turnout — the ECI Statistical Report for that election is the source of truth. Wikipedia and MyNeta are downgraded to enrichment/cross-check roles for those fields.

Specifically:

- **Vote counts, candidate counts, party-wise totals, turnout** — ECI Statistical Report only. Wikipedia tables are not authoritative for these even when they appear correct.
- **Electors (poll-time snapshot)** — ECI Statistical Report (Form 20-equivalent tables) preferred; CEO electoral roll PDFs as fallback.
- **AC↔PC↔district mapping** — Delimitation Order 2008 remains the legal source. ECI Statistical Reports often *also* publish this mapping per election; we accept either, but if they disagree, the Delimitation Order wins.
- **Candidate affidavit data (assets, criminal cases)** — MyNeta. ECI does not publish this in a structured form.

Wikipedia is reduced to: a fast bootstrap for constituency *names* and *numbers* (provisional state), and a source of historical narrative fields (`established_year`, district lineage) that ECI does not publish.

### 2. URL grammar and persistence rules

**Persisted in `sources[]`** (the human-facing landing page):

```
https://www.eci.gov.in/statistical-report/{body}/{year}/{state-code}
```

**Never persisted in `sources[]`** (time-limited signed URLs from the "Download" buttons):

```
https://www.eci.gov.in/eci-backend/public/api/download?url=<base64-blob>
```

These signed URLs expire. We re-resolve them from the landing page on every fetch. The intermediate downloaded XLSX/PDF lives in `.runtime/raw/eci/statistical_report/{body}/{year}/{state-code}/<filename>` per ADR-0003 and ADR-0006 — not a contract surface, gitignored, throwaway.

The ECI URL grammar uses *display* state codes (e.g. `26` for Tamil Nadu), not the `S22`-style codes we use internally. The mapping must be empirically confirmed during the recon pass and recorded in [`docs/reference/identifiers.md`](../../reference/identifiers.md). Until the mapping for a state is confirmed, code MUST NOT silently assume it.

### 3. Two-phase rollout

The user asked for both reconnaissance and enrichment. We separate them:

**Phase A — Reconnaissance** (next change after this ADR lands):

- A standalone tool under `tools/eci_recon/` (per CLAUDE.md §3 / §4: tools are self-contained, no `backend/` imports).
- Inputs: a list of `(state_code, body, year)` tuples — initial scope is `{S22, S11, S25} × {AE} × {2021, 2016, 2011}` plus `{S22 × AE × 2026}`.
- For each tuple: fetch the landing page, extract every linked file (XLSX, PDF, CSV), record `(file_name, content_type, size_bytes, link_text, landing_url)`.
- Output: a markdown inventory written to `notes/eci-recon-<date>.md` — non-authoritative per CLAUDE.md §3, intended for human review.
- **No data is ingested into `datasets/` in this phase.** The recon's only artifact is the inventory.
- Recon is idempotent and re-runnable; no state in `datasets/` depends on it.

**Phase B — Enrichment** (separate, future change after we read the recon report together):

- Built around an XLSX parser tailored to the ECI report shapes the recon surfaces. Different ECI reports use different sheet structures; the parser must be schema-driven, not heuristic.
- Each parsed report becomes either (a) a new `datasets/elections/...` artifact, or (b) the ECI source that promotes a `constituencies.json` from `provisional` to `complete`.
- Phase B will require its own ADR(s) covering the parser shape, the per-report schema, and the result-aggregation rules already started in [`docs/concepts/result-aggregation.md`](../../concepts/result-aggregation.md).

### 4. WB (S25) bootstrap policy

West Bengal has no `datasets/reference/in/states/S25/` files yet. The user directed: "include WB; ECI is the official source; bootstrap from ECI and enrich with Wiki."

Operationally:

- **Recon pass includes WB** even without WB reference data — it costs nothing and tells us what's available.
- **Bootstrap order for new states is reversed from how TN/Kerala were bootstrapped.** Once recon confirms an ECI Statistical Report exists for WB-2021 in a parseable form (XLSX), we generate `S25/constituencies.json` directly from the ECI report (`status: complete` if the report carries district + PC mapping, otherwise `status: provisional` with ECI in `sources[]`). Wikipedia is then layered in for narrative fields only.
- The TN and Kerala files remain `status: provisional` until Phase B promotes them via the same ECI cross-check.

## Consequences

- **Good**: clear authority order ends ambiguity over "which source wins when they disagree" — ECI Statistical Reports do.
- **Good**: separating recon from enrichment prevents the "let me also write the parser while I'm here" sprawl. Recon's output is reviewed before parser work starts.
- **Good**: WB bootstrap from ECI rather than Wikipedia gives us a `complete`-grade reference file from day one for that state, not a `provisional` one.
- **Good**: signed-URL non-persistence is now in policy, not implicit. Tooling that violates it fails review, not validation-after-the-fact.
- **Cost**: recon discovers reality. If a state's report is published as a scanned PDF rather than XLSX, Phase B for that state is much harder. We accept this cost; pretending the data is uniformly XLSX would just defer the surprise.
- **Cost**: state-code mapping (`S22 ↔ 26`, etc.) is empirically confirmed, not assumed. Recon must record it explicitly.
- **Migration**: schemas unchanged. `docs/reference/data-sources.md` (added in this commit) carries the URL grammar; `tools/eci_recon/` arrives in the next change.

## Alternatives considered

- **Treat all ECI surfaces (Statistical Reports, Results portal, Delimitation Order, CEO sites) as one undifferentiated "ECI source".** Rejected: they differ in authority, freshness, and format. Saying "any ECI URL satisfies `status: complete`" loses meaning.
- **Combine recon and enrichment in one workstream.** Rejected: recon's purpose is to surface unknowns; tying it to a parser commits us to a parser shape before we know what we're parsing. CLAUDE.md §6 explicitly: "Level 4+ — propose breakdown first."
- **Bootstrap WB from Wikipedia like TN/Kerala for consistency, promote later.** Rejected by user direction. Also dispreferred because every `provisional` file is a future migration we'd rather not create when we can avoid it.
- **Persist signed download URLs in `sources[]` "for traceability".** Rejected: they expire. A `sources[]` entry that 404s in a week is worse than no entry — it implies traceability that does not exist.

## See also

- [`docs/reference/data-sources.md`](../../reference/data-sources.md) — the live catalogue of sources and URL grammars.
- [ADR-0015](0015-constituency-hierarchy-fields.md) — `status: complete` rule that this ADR refines.
- [ADR-0008](0008-eci-source-adapter.md), [ADR-0009](0009-wikipedia-source-adapter.md) — adapter-level conventions.
- [ADR-0003](0003-no-fetch-cache.md), [ADR-0006](0006-intermediate-raw-path-derivation.md) — `.runtime/raw/` placement for intermediate downloads.
- [`docs/concepts/data-provenance.md`](../../concepts/data-provenance.md), [`docs/concepts/electoral-hierarchy.md`](../../concepts/electoral-hierarchy.md).
