# Elections Indicator Catalogue (Phase 1.1)

**Last Updated**: 2026-05-18

Authoritative list of indicators yen-gov emits in `family: "elections"` into the canonical store. Phase 1.1 scope: AC-level legislative-assembly results for the 28 backfilled elections. Parliament follows in Phase 2; PRI/ULB later.

Decided 2026-05-18 by Max (indicator-scout pass) + Hans (governance pass), user-approved with Max's "aggressive materialisation" stance. Sibling doc: [canonical-store.md §3a](canonical-store.md#3a-election-entity-identity-d-elections-phase-11) for entity IDs, [§11.4](canonical-store.md#114-materialisation-rule-d-elections-phase-11) for the materialisation contract.

## Naming

All indicator IDs follow [D30](canonical-store.md#7-indicator-naming-convention-d30): kebab-case single segment, max 60 chars. The first token names the **entity-type the indicator attaches to** (matches the entity_id prefix used in §3a).

| First token | Entity it attaches to | Example entity_id |
| --- | --- | --- |
| `candidate-*` | per-contest candidate | `IN-S22-AC-2008-167-AcGenMay2026-C03` |
| `ac-*` | AC × election | `IN-S22-AC-2008-167` observed at `AcGenMay2026` |
| `party-*` | party × state × election rollup | `IN-S22-AcGenMay2026-PARTY-DMK` |
| `state-*` | state × election rollup | `IN-S22-AcGenMay2026` |

All rows carry `family: "elections"` so the catalogue browser can scope to elections-domain indicators without name-collision concern with socio-economic series (e.g. socio-economic `state-` rows are disambiguated by `family`).

`year` = calendar year the contest was held (integer, OWID convention). `period_label` = ECI event ID (`AcGenMay2026`). `period_seq` orders multiple events within a year monotonically.

## Catalogue

### Candidate scope (raw ingest from ECI per-AC PDFs)

| indicator_id | unit | value column | notes |
| --- | --- | --- | --- |
| `candidate-votes-polled` | votes | `value_numeric` | absolute count |
| `candidate-vote-share-pct` | % of valid votes in contest | `value_numeric` | 0–100, 2 dp |
| `candidate-rank` | ordinal | `value_numeric` | 1 = winner |

Candidate dim attributes (name, party_id, gender, age, education, profession, criminal_cases) live on `candidates.parquet`, not as observations. Reason: they don't change over the lifetime of the candidate within a contest, so they're dim-table facts, not time-keyed observations.

### AC scope (materialised per-AC contest summaries)

| indicator_id | unit | derivation | notes |
| --- | --- | --- | --- |
| `ac-total-electors` | persons | raw from ECI PDF | enrolled voters |
| `ac-votes-polled` | votes | `sum(candidate-votes-polled)` | including NOTA |
| `ac-turnout-pct` | % | `votes_polled / total_electors * 100` | 2 dp |
| `ac-nota-votes` | votes | raw from ECI PDF | absolute count; null pre-2013 |
| `ac-nota-pct` | % | `nota_votes / votes_polled * 100` | 2 dp; null pre-2013 |
| `ac-winner-candidate-id` | entity_id | `argmax(candidate-votes-polled)` | `value_text` |
| `ac-winner-party-id` | entity_id | join(winner candidate, `candidates.party_id`) | `value_text`, e.g. `parties.IN.DMK` |
| `ac-margin-votes` | votes | `winner.votes - runner_up.votes` | absolute |
| `ac-margin-pct` | % of votes_polled | `margin_votes / votes_polled * 100` | 2 dp |
| `ac-effective-candidates-laakso` | count | Laakso-Taagepera N | `1 / sum(share^2)` |
| `ac-candidates-total` | candidates | `len(kept) + len(others)` | full field size; emitted even when no tail |
| `ac-others-votes` | votes | `sum(votes) of tail` | absent when no tail |
| `ac-others-pct` | % of votes_polled | `sum(share_pct) of tail` | 2 dp; absent when no tail |

### Party scope (materialised per-state-per-election rollups)

| indicator_id | unit | derivation | notes |
| --- | --- | --- | --- |
| `party-contested-acs` | ACs | `count(distinct ac) where candidate.party_id = P` | denominator for strike rate |
| `party-seats-won` | ACs | `count where ac-winner-party-id = P` | |
| `party-strike-rate-pct` | % | `seats_won / contested * 100` | 2 dp |
| `party-votes-polled` | votes | `sum(candidate-votes-polled) where party = P` | across state |
| `party-vote-share-pct` | % of state valid votes | `party.votes_polled / state.votes_polled * 100` | 2 dp |
| `party-forfeitures-count` | ACs | `count where candidate-vote-share-pct < 16.67 and party = P` | one-sixth-deposit rule |

### State scope (materialised per-election rollups)

| indicator_id | unit | derivation | notes |
| --- | --- | --- | --- |
| `electors-total` | persons | `sum(ac-total-electors)` | |
| `votes-polled` | votes | `sum(ac-votes-polled)` | |
| `turnout-pct` | % | `votes_polled / electors_total * 100` | 2 dp |
| `nota-pct` | % | `sum(ac-nota-votes) / votes_polled * 100` | 2 dp; null pre-2013 |
| `effective-parties-laakso` | count | Laakso-Taagepera on seat shares | governance health signal |
| `winning-party-id` | entity_id | `argmax(party-seats-won)` | `value_text`; null if hung |
| `winning-party-seats` | ACs | max `party-seats-won` | |
| `majority-threshold-acs` | ACs | `floor(total_acs / 2) + 1` | constant per state per delim cycle, but emitted so the citizen doesn't have to look it up |

## Parliament / PC scope (Phase 2)

Parliament (parliamentary-constituency, PC) results mirror the AC catalogue at PC grain. Per [ADR-0048](../../reference/decision-index.md) and [ADR-0044](../../reference/decision-index.md), `pc-*` indicators are a sanctioned fact-grain prefix (the grain gate `^(state|district|national)-` never matches `pc-`). PC observation rows share the `elections` family and the existing `datasets/elections/state=<key>/election_results.parquet`, discriminated by `entity_id` prefix (`IN-PC-<delim_year>-<state_code>-<pc_no>`, globally unique because ECI `pc_no` is per-state) and `indicator_id` (`pc-*`). The national query is `WHERE indicator_id='pc-winner-party-id' AND entity_id LIKE 'IN-PC-%'`.

Every `pc-*` measure that also exists at AC grain shares ONE `concept_id` (in `datasets/taxonomy/concepts.json`) whose `entity_kinds` lists both `ac` and `pc` (Option B concept-binding). The candidate-scope and party/state rollup indicators are grain-neutral and are reused as-is.

### PC scope (materialised per-PC contest summaries)

| indicator_id | unit | derivation | notes | shared concept_id |
| --- | --- | --- | --- | --- |
| `pc-total-electors` | persons | raw from ECI | enrolled voters | `total-electors` |
| `pc-votes-polled` | votes | `sum(candidate-votes-polled)` | including NOTA | `votes-polled-constituency` |
| `pc-turnout-pct` | % | `votes_polled / total_electors * 100` | 2 dp | `turnout-pct` |
| `pc-nota-votes` | votes | raw from ECI | absolute count; null pre-2013 | `nota-votes` |
| `pc-nota-pct` | % | `nota_votes / votes_polled * 100` | 2 dp; null pre-2013 | `nota-pct` |
| `pc-winner-candidate-id` | entity_id | `argmax(candidate-votes-polled)` | `value_text` | `winner-candidate-id` |
| `pc-winner-party-id` | entity_id | join(winner candidate, party_id) | `value_text` | `winner-party-id` |
| `pc-margin-votes` | votes | `winner.votes - runner_up.votes` | absolute | `margin-votes` |
| `pc-margin-pct` | % of votes_polled | `margin_votes / votes_polled * 100` | 2 dp | `margin-pct` |
| `pc-effective-candidates-laakso` | count | Laakso-Taagepera N | `1 / sum(share^2)` | `effective-candidates-laakso` |
| `pc-candidates-total` | candidates | `len(kept) + len(others)` | full field size | `candidates-total` |
| `pc-others-votes` | votes | `sum(votes) of tail` | absent when no tail | `others-votes` |
| `pc-others-pct` | % of votes_polled | `sum(share_pct) of tail` | 2 dp; absent when no tail | `others-pct` |

Party-scope rollups for Parliament reuse `party-seats-won` / `party-vote-share-pct` / `party-strike-rate-pct` (the entity_id event token `LsGen...` discriminates the contest), with `party-contested-pcs` as the PC denominator analogue of `party-contested-acs`. PC events carry `kind: "parliament"` in `datasets/taxonomy/election_events.json`.

## Dimension tables (Phase 1.2b — denormalised strings, not observations)

Per [canonical-store §11.5](canonical-store.md#115-dimension-tables-phase-12b): citizen-facing strings (person name, AC name, party labels) live in sibling Parquets, NOT in `observations.parquet`. `elections_candidacies.candidacy_key` is byte-equal to candidate-scope `observations.entity_id`, so the frontend reconstructs the citizen shape through `election_results → elections_candidacies → dim_persons`.

| Table | PK | Columns | Source |
| --- | --- | --- | --- |
| `elections.dim_persons` | `person_id` | `display_name`, `source_id`, nullable `sex`, `age`, `education`, `profession` | per-AC ECI source |
| `elections.elections_candidacies` | `candidacy_key` (= per-contest `entity_id`) | `person_id`, `ac_id`, `election_id`, `ballot_serial`, `party_id`, `rank`, `votes_polled`, `vote_share_pct`, `won`, `source_id`, `party_short_raw`, nullable `constituency_type`, `party_type` | per-AC ECI source |
| `elections.dim_acs` | `ac_id` | `state_code`, `delim_year`, `eci_no`, `name`, `source_id` | per-AC ECI source |
| `elections.dim_parties` | `party_id` | `eci_code`, `short_name`, `full_name`, `recognition`, `source_id` | `datasets/taxonomy/parties.json` registry |

## What is NOT materialised (query-time only)

- ~~Per-AC top-N candidate cutoffs ("top 5 + NOTA + others"). The cutoff is a UX concern (§14 open question), not a fact. Frontend computes it from `candidate-*` rows on demand.~~ **Resolved Phase 1.6 (2026-05-18)**: the cutoff is still a UX concern, but the *consequences* of the cutoff are facts. `ac-candidates-total` + `ac-others-{votes,pct}` are now materialised so the citizen can see field size and aggregate tail without the canonical store having to keep every losing candidate row.
- Demographic cross-tabs ("votes by candidate age band"). Open-ended; combinatorial explosion.
- Cross-election personal histories ("every contest candidate X ran"). Blocked by candidate-identity being per-contest only (§3a).
- Geographic aggregates above state (regional, all-India party shares from AC data). Phase 2 once Parliament is in.

## Comparability traps (citizen-facing)

1. **Delimitation breaks**: `ac-*` rows pre- and post-redraw belong to different entities (§3a). Charts spanning a delim year MUST render a vertical break, not interpolate.
2. **State reorganisations** (Telangana 2014): an AC's `entity_valid_from` predates Telangana → it's an Andhra AC for those years, a Telangana AC after. Roll-ups to `state` scope follow whichever state the AC was in on election day. Pre-existence outside the state's life: **null**, not zero ([§3a](canonical-store.md#3a-election-entity-identity-d-elections-phase-11)).
3. **NOTA was introduced in 2013.** Pre-2013 `ac-nota-*` and `nota-pct` = null, not zero. The validator MUST reject zero.
4. **Party splits/mergers**: `parties.IN.<slug>` carries `predecessor_of` / `successor_of`. Charts comparing "DMK vote share over time" should declare whether they're following the legal party or the political lineage. yen-gov emits the legal party; the lineage walker is a frontend concern.

## See also

- [canonical-store.md §3a — Election entity identity](canonical-store.md#3a-election-entity-identity-d-elections-phase-11)
- [canonical-store.md §11.4 — Materialisation rule](canonical-store.md#114-materialisation-rule-d-elections-phase-11)
- [canonical-store.md §6 — Indicator catalogue](canonical-store.md#6-indicator-catalogue-d15--d29)
- [canonical-store.md §7 — Indicator naming convention](canonical-store.md#7-indicator-naming-convention-d30)
