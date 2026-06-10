# Charts — Deferred Work

**Last Updated**: 2026-05-24

Forward-looking chart-renderer work that was scoped during the May 2026 charting modernisation but held out of v1 for specific, named reasons. Each item is shovel-ready the moment its gating condition flips. **Re-read this file before proposing anything sunburst-shaped, multi-state-composition-shaped, or alliance-shaped** — the work is already scoped and waiting for its trigger.

Historical context (rejected alternatives, R-rules, decision log, persona reviews) lives in the archived plan snapshot: [`docs/archive/20260518-frontend-charting-modernisation-plan-snapshot.md`](../../../archive/20260518-frontend-charting-modernisation-plan-snapshot.md).

## See also

- [`docs/architecture/frontend/charts/README.md`](README.md) — primitive index
- [`docs/architecture/data/elections-indicators.md`](../../data/elections-indicators.md) — election indicator contract
- [`docs/concepts/citizen-first.md`](../../../concepts/citizen-first.md) — Hans's "longitudinal default" + "never seat-share without vote-share" rules

---

## DEFERRED-A — Alliance rollups for election composition

**Status (2026-05-21)**: repromoted from "blocked on data" to active workstream per R-03.

**Citizen impact**: Indian state politics is alliance-led in most coalition-heavy states (TN, MH, BR, KA, KL, JH, partially MP/UP/WB). Showing only party-level composition (DMK+INC+VCK+CPI+CPM as five separate segments) instead of one DMK-led-alliance segment misframes the verdict; the citizen reads "no party won a majority" when the political reality is "the DMK-led alliance won 159 of 234." Party-only composition (Phase 3.6 v1) is correct for two-party-dominant states (GJ, HP, UK, KA, MP) and is the honest first slice given current data, but it is structurally incomplete for the coalition states.

**Schema work required**: promote `dim_party_alliances` to v2.0:

- Add `dim_alliances.parquet` (alliance dimension).
- Add `alliance_id` FK on observation rows.
- Add `alliance_status` enum: `in_alliance` (FK set) / `solo` (knowingly contesting alone, `alliance_id` NULL) / `unknown` (uncurated, `alliance_id` NULL). Today's NULL collapses all three; the schema bump separates them.
- Add `binding_type` enum.
- Backpopulate ALL events progressively (not gated on TN-only).

**Per-event alliance variant mount gate**: 95% vote-coverage (R-05), configured in `config/processing.json:alliance.coverage_pct_min`.

**Required indicators (none exist today)**:

- `alliance-seats-won` per `(state, election_event, alliance_id)`.
- `alliance-seat-share-pct` (trivially derived once `alliance-seats-won` exists).
- `alliance-vote-share-pct` per `(state, election_event, alliance_id)`.
- `state-winning-alliance-id` per `(state, election_event)`, NULL for hung verdicts.
- `state-effective-alliances-laakso` (parallel to `state-effective-parties-laakso`).

**What exists today**: `datasets/taxonomy/dim_party_alliances.parquet` (the alliance dimension table) — but **zero observation rows** keyed to alliances. The dimension is provisioned; the facts are missing.

**Likely data sources**: TCPD (Trivedi Centre for Political Data, Ashoka); Lokdhaba (same upstream as TCPD); ECI alliance affidavits filed pre-poll (per the symbol allocation order); manual curation per state × election; CSDS post-poll surveys.

**Re-entry trigger**: when an ingest commit lands observation rows for `alliance-seats-won` covering at least one state × election event (e.g. TN 2021 or MH 2019), reopen the equivalent of Phase 3.6 to add an alliance-binding adapter (`adapter-elections-alliance-seats.ts`) that swaps `dim_parties` for `dim_party_alliances` in the same `CompositionBar` renderer. The renderer needs zero changes — it is dimension-agnostic by design.

**Citizen UX when alliance data lands**: the elections card on the state hub renders both `CompositionBar`s — party composition on the left, alliance composition on the right, with a one-line caption explaining the relationship. For states with no alliance (single-party verdict like GJ 2022), the alliance bar degenerates to the party bar and the caption explains why.

**Documentation home when work resumes**: `docs/research/alliance-modelling.md` (schema design); `docs/architecture/data/elections-indicators.md` (rendering rule).

**Sequencing per Fowler**: expand–migrate–contract.

---

## DEFERRED-B — Multi-state composition

**Status**: blocked on (a) the multi-entity composition guard rules from the charting plan being satisfied by a real route, plus (b) a named comparative question existing in the page editorial.

**Citizen impact**: There are legitimate multi-state composition questions ("How did BJP's seat share evolve across the Hindi belt 2017→2022?", "Which southern states gave a majority to a Dravidian-party-led alliance in each election?"). The guard rule is what makes such a view honest: the question is named, the encoding is ratio-only (so chamber-size differences across states do not visually distort), the peer set is principled (Hindi belt, Dravidian states, etc. — NOT "two states that happened to vote in the same calendar year").

**Why deferred**: Phase 3.6 v1 ships single-entity composition because (a) the v1 goal is shipping ONE new chart side-by-side with the existing one for visual A/B; (b) routes that host election composition (state hub elections card) are single-state by construction — they answer "what did this state decide?", not "how did the Hindi belt vote?"; (c) no compare route exists today that frames a named multi-state question.

**Re-entry trigger**: when a route ships that has a named multi-state question in its editorial copy AND the data is ratio-only — typical example would be `/elections/compare/?states=GJ,HP,UP&year=2017` with a written framing like "How did BJP's seat share compare across these three BJP-vs-INC states in 2017?". Mount `<FacetPanelGrid>` containing one `<CompositionBar>` per state, with **state identity in the panel title** and **party identity in the segment fill** (multi-entity composition guard sub-rule).

**Forbidden re-entry shape**: do NOT re-introduce the sunburst / nested-radial shape rejected on 2026-05-19. The guard rule explicitly says ratio-only encoding and named comparative question; it does NOT say "use a composite circle with two centres." Re-read the rejected-alternatives section of the archived plan before revisiting.

---

## DEFERRED-C — `categorical_choropleth` projection

**Status**: blocked on a separate scoping pass with Hans (hung-verdict labelling) and Jony (swatch-grid legend visual design).

**Citizen impact**: "Who won where" maps are a foundational election visualisation. The existing `choropleth` projection is sequential (low→high ramp); a categorical choropleth uses nominal fills (party-anchor palette) with a swatch-grid legend (not a ramp). It is distinct from sequential `choropleth` at the renderer level (legend semantics differ, colour interpolation is forbidden, the dark=more-of-thing rule does NOT apply) and warrants its own projection enum.

**Why deferred**: structurally separate from the composition question. Composition answers "what did one state decide?"; categorical choropleth answers "who won where across the country/state map?" Bundling them would force premature decisions on hung-verdict treatment (striped fill, outline, separate swatch, no fill?) and on swatch-legend density (8 parties? 15? collapse to "Other"?). Both are non-trivial design questions that deserve dedicated debate.

**Re-entry trigger**: when there is a route that needs a "largest party by state" map view — typically a post-election results page (`/elections/<event>/map`) or a historical-trajectory page (`/elections/trajectory/parliament`) with a time stepper. Spec must cover:

- nominal fill from the party-anchor palette;
- hung-verdict treatment (Hans);
- swatch-grid legend with collapsed "Other parties" bucket (Jony);
- a time-stepped variant for trajectory views (with frame-to-frame fill continuity rules);
- a `state-largest-party-id` derived field if not already in the canonical store (currently `state-winning-party-id` is NULL for hung verdicts — may or may not be the right shape for a map).

---

## DEFERRED-D — Vote-share twin alongside seat-share on the composition card

**Status (2026-05-21)**: **promoted into Phase 3.6 v1 scope** per R-02 and shipped. Retained here as a historical record of the original deferral and Hans's rationale.

**Hans's rule (non-negotiable)**: never show seat-share without vote-share when discussing FPTP outcomes. The gap between them IS the FPTP distortion story (49% vote share → 54% seat share in Gujarat 2017; the citizen needs both numbers to read the result honestly).

**Caption shipped**: *"Seats won (left) vs vote share (right); the gap is the FPTP distortion."*

---

## DEFERRED-E — Longitudinal seat-share + vote-share twin

**Status**: blocked on time-series renderer + temporal-viewport primitive (shipped as Phase 1.5).

**Citizen impact**: Hans's "citizen-default ought to be longitudinal" principle. A single-election composition bar is a snapshot; a multi-election trajectory is the political-shift story. For the state hub elections card, the citizen-honest default is "how has this state voted across the last N elections?" not "how did it vote in 2017?"

**Why deferred**: Phase 1.5 (temporal viewport interaction primitive) ships before this is buildable. The trajectory shape is `stacked_trend` (already exists, already adapter-fed for elections) — not `composition_bar`. So this entry is really "after Phase 1.5 ships, re-evaluate whether the state hub elections card should default to a `stacked_trend` longitudinal view with the `composition_bar` snapshot as a secondary read."

**Re-entry trigger**: after Phase 1.5 ships (done). Outstanding decision: pick up the longitudinal default-on-state-hub decision in the next chart-plan cycle.
