# Result aggregation

**Last Updated**: 2026-05-09

How yen-gov turns ECI's per-page output into the artifacts the frontend reads.

## Inputs and outputs

```
results.eci.gov.in pages           →   datasets/elections/<event>/<state>/
─────────────────────────────────      ─────────────────────────────────────
partywiseresult-<state>.htm        →   parties.json
                                       result.summary.json (with constituencies)
Constituencywise<state><n>.htm     →   results/<n>.json (one per AC)
```

The pipeline is one-shot per `(event, state)`: results don't change after declaration. Re-runs overwrite.

## The two layers

**`sources/eci/`** parses one page at a time. Each parser is a pure function from `bytes` to an adapter-local dataclass (`PartywiseSnapshot`, `ConstituencywiseRaw`). They know nothing about the schema, the election, or each other. See [backend/sources-eci.md](../architecture/backend/sources-eci.md).

**`pipeline/compose.py`** combines those adapter outputs into schema-bound models:

- `party_lookup_from_partywise(snapshot)` — builds `{full_name → (short, eci_code)}`. The constituencywise pages carry only full party names; the lookup lets `to_constituency_result` fill `party_short` and `party_eci_code`.
- `compose_result_summary(...)` — aggregates per-AC results into a `ResultSummary` row per party.
- `reconcile_winners_against_partywise(...)` — sanity-checks per-AC winners against partywise seat counts before any artifact is written.

## Why the partywise table is the spine

`compose_result_summary` walks parties from the partywise table, not from the per-AC candidate lists. Reasoning:

1. Partywise is the only source of `seats_won + leading` and ECI numeric party codes within a state. Per-AC pages only know about candidates in that constituency.
2. Partywise enumerates every party with a non-zero seat count, which is the natural denominator for `party_totals`.

When a vote-bearing party shows up in per-AC candidates but **not** in partywise (a fringe party that won zero seats but fielded candidates in some ACs), the composer adds a synthetic row with `seats_won=0`, `party_eci_code=None`, and `party_full=None`. Without this, those votes would silently vanish from the summary even though they appear in per-AC results.

## The top-N trade-off

`processing.results.top_n_candidates` (default 5) controls how many candidates per AC are kept in `result.constituency.json`. The rest collapse into `OthersBucket{ candidate_count, votes, vote_share_pct }` when `collapse_others: true`.

`OthersBucket` loses per-party identity. Consequence: a small party whose candidate finishes 6th in many ACs has its votes counted in `OthersBucket.votes` (which is published) but **not** in `party_totals[that party].votes` (which the composer only sees via the kept top-N).

`totals.votes_polled` is always the true sum from each constituency's tfoot, so per-party `vote_share_pct` denominators are correct. It is the per-party numerators that may be slightly low for small parties when `top_n_candidates` is small. A consumer that needs exact party-level vote totals must run with `top_n_candidates >= max_candidates_per_AC` (~50 in practice).

## Reconciliation as a pre-write gate

After `compose_result_summary` builds the `ResultSummary` model — but before any file is written — `reconcile_winners_against_partywise` re-derives party seat counts from per-AC `winner.party_short` and asserts they match `partywise.parties[i].seats_won + leading`. Discrepancies raise with a per-party diff:

```
winner reconciliation failed:
  AIADMK: per-AC winners=65, partywise=66
  DMK:    per-AC winners=130, partywise=129
```

Either source could be wrong; what matters is that we don't ship artifacts the two disagree on. Per CLAUDE.md §10 fail-loud, the run aborts. The operator inspects, identifies the upstream cause (ECI page edit mid-run? parser drift? our reservation table?), and re-runs.

A winning party absent from partywise (`X: per-AC winners=N, absent from partywise`) is treated as an integrity red flag, not a fringe-party edge case — distinct from the *vote-bearing-but-not-winning* path above. A party that won at least one seat MUST appear in the partywise table.

## Provenance

Every emitted file carries the URLs it derives from in `sources` (per CLAUDE.md §12 / ADR-0002):

- `results/<n>.json` cites one URL — its constituencywise page.
- `parties.json` cites one URL — the partywise page.
- `result.summary.json` cites every URL that contributed: partywise + every constituencywise page it aggregated.

`fetched_at` is stamped per URL, so a re-run of one AC updates that AC's row and `result.summary.json`'s corresponding entry; the partywise entry is unchanged.

## See also

- [backend/sources-eci.md](../architecture/backend/sources-eci.md) — ECI source adapter conventions (URL builders, two-step parsing, party-name resolution).
- [backend/pipeline.md](../architecture/backend/pipeline.md) — pipeline orchestration (composers, fail-loud, top-N trade-off, parallelism rejected).
- `docs/concepts/data-provenance.md` — what the `sources` field means.
- `docs/how-to/run-the-pipeline.md` — operator commands.
