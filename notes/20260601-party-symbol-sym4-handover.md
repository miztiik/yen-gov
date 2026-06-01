# Party Symbol PR-SYM-4 Handover

**Created**: 2026-06-01
**Status**: PR-SYM-4a STOPPED at user-supervised boundary. PR-SYM-4b and PR-SYM-5 BLOCKED until SYM-4a completes.
**Plan**: [TODO/20260527-party-symbol-assets-plan.md](../TODO/20260527-party-symbol-assets-plan.md)

## What is shipped on `main` as of `a92a2906`

| PR | What landed |
| --- | --- |
| #524 | Plan-doc with Status Reckoner + Gregor sequencing (PR-SYM-0). |
| #526 | `taxonomy-parties.schema.json` v2.1 -> v2.2 + 13 schema-fixture tests (PR-SYM-1). |
| #527 | `notes/20260601-party-symbol-roster.md` (Tier 0..3 target list + DuckDB query + alias-trap rules) (PR-SYM-2). |
| #528 | `frontend/src/lib/party-symbols/sanitizer.ts` + 18 vitest cases + `frontend/public/party-symbols/placeholder.svg` (PR-SYM-3). |

What this means in citizen terms: nothing renders yet. The schema, the target list, the sanitizer, and the placeholder glyph all exist. No party-row has `recognition` or `election_symbol` populated. No real ECI ballot-symbol SVGs are committed.

## Why the autonomous agent stopped before PR-SYM-4a

PR-SYM-4a needs to commit ~40 real ECI ballot-symbol SVG files (Lotus, Hand, Hammer-Sickle-Star, Rising Sun, Two Leaves, Bicycle, Elephant, Cycle, Clock, Lantern, Bow-and-Arrow, etc.) alongside corresponding `datasets/taxonomy/sources.parquet` rows per producer.

The autonomous agent halted here per the Citizen verdict on 2026-06-01:

> Symbols are identity. Shipping 40 grey placeholders or a half-populated set damages citizen trust more than waiting does. Document the boundary, let a human do the supervised SVG pass.

The reasoning, in three points:

1. **Each SVG needs human-eyes verification.** Wikimedia Commons hosts SVGs of varying provenance (some are byte-exact ECI source material, some are fan re-traces with wrong proportions, some are dated to the wrong faction in a post-split party). The sanitizer guarantees the bytes are safe to render; it cannot confirm "this glyph IS the ECI-allotted symbol for BJP today". Auto-attaching the first hit from a search would propagate any error to every citizen-facing surface.
2. **Faction-split disputes are live.** Shiv Sena (UBT vs Shinde), NCP (Sharad Pawar vs Ajit Pawar), and LJP (Paswan vs Pashupati) each have an ECI freezing order that hands the reserved symbol to one faction and a new symbol to the other. Picking the wrong holder is a political-perception bug, not a technical bug.
3. **Half-populated coverage is worse than no coverage.** If BJP shows a Lotus but DMK shows a placeholder, a citizen will read political intent into the asymmetry even if there is none. The right batch shape is "all current Tier 0 parties verified" or "none".

## What a human operator needs to do for PR-SYM-4a

Working from the [Tier 0 list in the roster note](20260601-party-symbol-roster.md#tier-0-target-list-pr-sym-4a-authors-svgs-for-these) (~43 parties), for each party:

1. **Identify the current reserved/allotted ECI symbol.** Source order from section 4 of the plan-doc: ECI list-of-political-parties notification > ECI recognition/de-recognition orders > ECI election-symbol detail pages > State CEO Form 7A.
2. **Find an SVG of that glyph.** First check whether the Commons category https://commons.wikimedia.org/wiki/Category:Symbols_of_political_parties_in_India has a clean, monochrome, accurately-shaped file. If not, hand-trace from the ECI PDF source (the placeholder.svg under `frontend/public/party-symbols/` shows the path/line/circle/currentColor style the allowlist permits).
3. **Sanitise and hash.** Use `frontend/src/lib/party-symbols/sanitizer.ts` from PR-SYM-3. Author a small CLI wrapper if useful (`tools/party-symbols/sanitise.ts` is a fine new home; not yet built).
4. **Commit the SVG bytes** under `frontend/public/party-symbols/<kebab-case-symbol>.svg`.
5. **Add a `sources.parquet` row** per distinct producer (one for Commons-as-a-mirror, one for ECI-as-primary-authority, one per State CEO order as needed). Use `backend.yen_gov.canonical.citation.derive_source_id` per ADR-0032; never hand-author `source_id`.
6. **Record the inventory in the PR body** as a table: `party_short | symbol_name | asset_path | asset_sha256 | source_id | render_mode | license_label | sanitizer_pass`.

For faction-split parties, the operator MUST cite the specific ECI freezing or restoration order for the symbol attachment, and put the OTHER faction at `symbol_status: "deferred_historical"` in PR-SYM-4b's parties.json edits.

## What a human operator needs to do for PR-SYM-4b

Once PR-SYM-4a is merged (SVGs + sources.parquet exist on main):

1. Edit `datasets/taxonomy/parties.json`. For each party with a verified SVG, add the `election_symbol` block (per the [schema v2.2 contract](../datasets/schemas/taxonomy-parties.schema.json)) plus the `recognition` value cross-checked against the ECI national/state notification.
2. For each Tier 0 party that did NOT get a verified SVG in PR-SYM-4a (none, if SYM-4a covered the full Tier 0), write `symbol_status: "placeholder"` with `source_id: null` and `asset_path: "party-symbols/placeholder.svg"`.
3. For the 16 alias-trap rows listed in the roster note, write `recognition: "unknown"` and NO `election_symbol` block. Add a `notes` line citing the roster note.
4. Recompile `datasets/elections/dim_parties.parquet` (`python -m yen_gov.cli emit-...`; the writer already carries `recognition`, no compiler edit needed).
5. Run Tier-A validate: it will enforce every non-placeholder `asset_path` exists, every `asset_sha256` matches, every `source_id` resolves to `sources.parquet`.

## What PR-SYM-5 looks like after both 4a and 4b land

1. Bump `datasets/schemas/dim-parties.schema.json` v1.0 -> v1.1 (additive `election_symbol` mirror).
2. Update `backend/yen_gov/canonical/writer.py` to copy `election_symbol` from `parties.json` into `dim_parties.parquet`.
3. Add `frontend/src/lib/parties/symbol-url.ts`: pure function deriving `${base}/party-symbols/${assetPath}` from a `dim_parties` row. Returns the placeholder path when `symbol_status === "placeholder"`; returns null when no `election_symbol` block.
4. Wire one or two Svelte consumers (candidate row, party badge). NO party-id-to-path map in any `.svelte` or `.ts` file - the contract test (also in PR-SYM-5) greps `frontend/src/**` for literal party-ids from the top-40 roster and fails on hit.
5. Browser smoke per CLAUDE.md section 13 on one state route: verify the Lotus renders next to BJP, the placeholder renders next to a placeholder-status party, no console errors, no 404.

## Why this is a clean stop, not an incomplete plan

Every PR shipped so far has a closed contract: the schema enforces every later step; the sanitizer rejects every malicious byte; the placeholder is the only asset that needs to exist for the renderer to test its fallback path; the roster note pins the target list reproducibly. A reviewer in three months can pick up PR-SYM-4a without re-deriving any of those decisions.

The only thing missing is the operator-judgment-bound batch of bytes. That bound was always going to be a user surface, regardless of automation level - the plan-doc anticipated this in section 2 ("No symbol is better than a guessed symbol") and section 4 ("Wikipedia and the corpus winners list are NOT recognition sources by themselves").

## Pick-up checklist for the next agent or operator

- [ ] Read this note + [the plan-doc](../TODO/20260527-party-symbol-assets-plan.md) + [the roster note](20260601-party-symbol-roster.md) end-to-end.
- [ ] Confirm the current ECI national-party + state-recognised-party notification dates; record in the PR-SYM-4b body.
- [ ] Start the SVG collection pass for Tier 0; commit in batches of 10-15 SVGs at a time if 40+ in one PR is too review-heavy (per the plan, PR-SYM-4a may itself split into 4a.i / 4a.ii / 4a.iii without renaming the plan rows).
- [ ] Land PR-SYM-4b once all Tier 0 SVGs are on main.
- [ ] Land PR-SYM-5; deploy and verify a citizen route renders the lotus next to BJP.
