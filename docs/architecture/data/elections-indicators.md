# Elections Indicator Catalogue (Phase 1.1)

**Last Updated**: 2026-05-18

Authoritative list of `elections.*` indicators yen-gov emits into the canonical store. Phase 1.1 scope: AC-level legislative-assembly results for the 28 backfilled elections. Lok Sabha follows in Phase 2; PRI/ULB later.

Decided 2026-05-18 by Max (indicator-scout pass) + Hans (governance pass), user-approved with Max's "aggressive materialisation" stance. Sibling doc: [canonical-store.md §3a](canonical-store.md#3a-election-entity-identity-d-elections-phase-11) for entity IDs, [§11.4](canonical-store.md#114-materialisation-rule-d-elections-phase-11) for the materialisation contract.

## Naming

`elections.<scope>.<measure>` per [canonical-store.md §7](canonical-store.md#7-indicator-naming-convention-d30). Scopes used here:

| Scope | Entity it attaches to | Example entity_id |
| --- | --- | --- |
| `candidate` | per-contest candidate | `IN-S22-AC-2008-167-AcGenMay2026-C03` |
| `ac` | AC × election | `IN-S22-AC-2008-167` observed at `AcGenMay2026` |
| `party` | party × state × election rollup | `IN-S22-AcGenMay2026-PARTY-DMK` |
| `state` | state × election rollup | `IN-S22-AcGenMay2026` |

`year` is the calendar year the contest was held (integer, OWID convention). `period_label` is the ECI event ID (`AcGenMay2026`). `period_seq` orders multiple events within a year monotonically.

## Catalogue

### Candidate scope (raw ingest from ECI per-AC PDFs)

| indicator_id | unit | value column | notes |
| --- | --- | --- | --- |
| `elections.candidate.votes_polled` | votes | `value_numeric` | absolute count |
| `elections.candidate.vote_share_pct` | % of valid votes in contest | `value_numeric` | 0–100, 2 dp |
| `elections.candidate.rank` | ordinal | `value_numeric` | 1 = winner |

Candidate dim attributes (name, party_id, gender, age, education, profession, criminal_cases) live on `candidates.parquet`, not as observations. Reason: they don't change over the lifetime of the candidate within a contest, so they're dim-table facts, not time-keyed observations.

### AC scope (materialised per-AC contest summaries)

| indicator_id | unit | derivation | notes |
| --- | --- | --- | --- |
| `elections.ac.total_electors` | persons | raw from ECI PDF | enrolled voters |
| `elections.ac.votes_polled` | votes | `sum(candidate.votes_polled)` | including NOTA |
| `elections.ac.turnout_pct` | % | `votes_polled / total_electors * 100` | 2 dp |
| `elections.ac.nota_votes` | votes | raw from ECI PDF | absolute count |
| `elections.ac.nota_pct` | % | `nota_votes / votes_polled * 100` | 2 dp |
| `elections.ac.winner_candidate_id` | entity_id | `argmax(candidate.votes_polled)` | `value_text` |
| `elections.ac.winner_party_id` | entity_id | join(winner_candidate, candidates.party_id) | `value_text`, e.g. `parties.IN.DMK` |
| `elections.ac.margin_votes` | votes | `winner.votes - runner_up.votes` | absolute |
| `elections.ac.margin_pct` | % of votes_polled | `margin_votes / votes_polled * 100` | 2 dp |
| `elections.ac.effective_candidates` | count | Laakso-Taagepera N | `1 / sum(share^2)` |

### Party scope (materialised per-state-per-election rollups)

| indicator_id | unit | derivation | notes |
| --- | --- | --- | --- |
| `elections.party.contested` | ACs | `count(distinct ac) where candidate.party_id = P` | denominator for strike rate |
| `elections.party.seats_won` | ACs | `count where winner_party_id = P` | |
| `elections.party.strike_rate_pct` | % | `seats_won / contested * 100` | 2 dp |
| `elections.party.votes_polled` | votes | `sum(candidate.votes_polled) where party = P` | across state |
| `elections.party.vote_share_pct` | % of state valid votes | `party.votes_polled / state.votes_polled * 100` | 2 dp |
| `elections.party.forfeitures` | ACs | `count where candidate.vote_share_pct < 16.67 and party = P` | one-sixth-deposit rule |

### State scope (materialised per-election rollups)

| indicator_id | unit | derivation | notes |
| --- | --- | --- | --- |
| `elections.state.total_electors` | persons | `sum(ac.total_electors)` | |
| `elections.state.votes_polled` | votes | `sum(ac.votes_polled)` | |
| `elections.state.turnout_pct` | % | `votes_polled / total_electors * 100` | 2 dp |
| `elections.state.nota_pct` | % | `sum(ac.nota_votes) / votes_polled * 100` | 2 dp |
| `elections.state.effective_parties` | count | Laakso-Taagepera on seat shares | governance health signal |
| `elections.state.winning_party_id` | entity_id | `argmax(party.seats_won)` | `value_text`; null if hung |
| `elections.state.winning_party_seats` | ACs | max seats_won | |
| `elections.state.majority_threshold` | ACs | `floor(total_acs / 2) + 1` | constant per state per delim cycle, but emitted for the citizen who shouldn't have to look it up |

## What is NOT materialised (query-time only)

- Per-AC top-N candidate cutoffs ("top 5 + NOTA + others"). The cutoff is a UX concern (§14 open question), not a fact. Frontend computes it from `candidate.*` rows on demand.
- Demographic cross-tabs ("votes by candidate age band"). Open-ended; combinatorial explosion.
- Cross-election personal histories ("every contest candidate X ran"). Blocked by candidate-identity being per-contest only (§3a).
- Geographic aggregates above state (regional, all-India party shares from AC data). Phase 2 once Lok Sabha is in.

## Comparability traps (citizen-facing)

1. **Delimitation breaks**: `elections.ac.*` rows pre- and post-redraw belong to different entities (§3a). Charts spanning a delim year MUST render a vertical break, not interpolate.
2. **State reorganisations** (Telangana 2014): an AC's `entity_valid_from` predates Telangana → it's an Andhra AC for those years, a Telangana AC after. Roll-ups to `state` scope follow whichever state the AC was in on election day. Pre-existence outside the state's life: **null**, not zero ([canonical-store.md §3a](canonical-store.md#3a-election-entity-identity-d-elections-phase-11)).
3. **NOTA was introduced in 2013.** Pre-2013 `elections.ac.nota_*` = null, not zero. The validator MUST reject zero.
4. **Party splits/mergers**: `parties.IN.<slug>` carries `predecessor_of` / `successor_of`. Charts comparing "DMK vote share over time" should declare whether they're following the legal party or the political lineage. yen-gov emits the legal party; the lineage walker is a frontend concern.

## See also

- [canonical-store.md §3a — Election entity identity](canonical-store.md#3a-election-entity-identity-d-elections-phase-11)
- [canonical-store.md §11.4 — Materialisation rule](canonical-store.md#114-materialisation-rule-d-elections-phase-11)
- [canonical-store.md §6 — Indicator catalogue](canonical-store.md#6-indicator-catalogue-d15--d29)
- [canonical-store.md §7 — Indicator naming convention](canonical-store.md#7-indicator-naming-convention-d30)
