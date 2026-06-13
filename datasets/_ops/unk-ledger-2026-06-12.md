# UNK ledger (2026-06-12)

**Last Updated**: 2026-06-12

## What this is

A worklist of every remaining publisher label that the TCPD per-party catalogue
correlator (PR-Q2 / PR-Q8) could not bind to a real `party_id`, with enough
context that the next correlation pass (ECI statreports + Wikipedia + press)
can pay down the debt without re-discovering each label from scratch.

One row per `(body, state_slug, year, event_id, publisher_label)` bucket.
Sorted by `(body, state_slug, year, publisher_label)` — stable and easy to
diff across re-emissions.

An "UNK" entry here is **publisher-side debt, not TCPD-side ignorance**. The
TCPD per-party catalogue covers ~2,700 distinct Indian parties across
1962-2021; for many of the remaining UNK labels TCPD HAS a real `Party_Name`
(carried in this ledger's `tcpd_party_name` column), but the correlator could
not bind it - the cases are enumerated by the `skip_reason` column. The
ledger preserves TCPD's recognition so the next pass starts where the last
one stopped.

## How to use it

1. Filter to one `skip_reason` at a time (the residuals are heterogenous;
   `not-in-tcpd-catalogue` calls for a Wikipedia / press search, while
   `tcpd-state-year-collision` calls for tightening the disambiguator).
2. For each bucket, the `next_lookup_source` column suggests the realistic
   next step: `eci-statreport-<year>` when the ECI publishes a comprehensive
   statistical report for that year (post-1977 general elections), else
   `wikipedia-and-press` (older / smaller parties).
3. When the next pass produces a verdict (alias-add, mint-new, or "leave
   UNK with citizen-visible footnote"), update `parties.csv` via the
   existing `tools.correlate_unk_apply` tool, re-emit the corpus via the
   reingest drivers (`_run_assembly_fanout` / `_run_parliament_results`),
   and re-emit THIS ledger to confirm the bucket is gone. Iterate.

## How it was generated

- Source script: [`tools/emit_unk_ledger`](../../tools/emit_unk_ledger).
- Corpus: every `candidacies.csv` under `datasets/elections/assembly/` and
  `datasets/elections/parliament/` (post-rebind state at PR-Q8 commit).
- TCPD context: joined against `datasets/ephemeral/TCPD-PoliticalPartiesIndia_1962_2021.csv`
  (the TCPD per-party catalogue, the same file PR-Q2's correlator reads).
- Skip-reason context: the most-recent `skipped.csv` under
  `datasets/ephemeral/party-parity/tcpd-catalogue/<run-sha>/` (the
  correlator's per-label rejection log).

## How to re-emit

From the repo root:

```powershell
$env:PYTHONPATH = "$pwd\backend"
python -m tools.emit_unk_ledger
```

The output is byte-deterministic given the same corpus + TCPD catalogue inputs.

## Schema

| column | meaning |
| --- | --- |
| `body` | `assembly` or `parliament`. |
| `state_slug` | LGD state slug for the bucket. Every PC row carries a state too. |
| `year` | 4-digit election year (parsed from the event-id partition value). |
| `event_id` | full event identifier verbatim (e.g. `AeMar2003`, `LsGenJun2024`). |
| `publisher_label` | `UPPER(party_short_raw)` - the raw publisher label that resolved to `parties.IN.UNK`. |
| `n_rows` | count of candidacy rows in this bucket. |
| `tcpd_party_id` | TCPD `Party_ID` when the publisher label appears in the catalogue (full-name B1 or abbreviation B2); empty when the label is not in the catalogue. Placeholder rows (`NA'S` / `EXPANDED PARTY NAME NOT RELEASED BY THE ECI`) are filtered out of the match so the column never carries a placeholder. |
| `tcpd_party_name` | TCPD `Party_Name` for that pid. |
| `tcpd_party_type` | TCPD `Party_Type` (`National Party` / `State-based Party` / `Local Party`). |
| `tcpd_start_year` | min TCPD `Start_Year` across the pid's rows. |
| `tcpd_last_year` | max TCPD `Last_Year` across the pid's rows. |
| `tcpd_state_name` | TCPD `State_Name` for the canonical (most-recent) catalogue row of that pid. `All_States` for nationwide parties. |
| `skip_reason` | Correlator's reason for not binding this label - sourced from the most-recent `skipped.csv`. One of `not-in-tcpd-catalogue` / `tcpd-state-year-collision` / `tcpd-no-year-coverage` / `tcpd-placeholder-only` / `tcpd-state-disambig-contradiction` / `multiple-tcpd-candidates-unresolved`. Empty when the correlator did not have an entry for this label (rare; would mean the correlator resolved it in some buckets but apply collisions prevented landing in others). |
| `next_lookup_source` | Hint for the next pass: `eci-statreport-<year>` when `year >= 1977` (when ECI began publishing comprehensive statistical reports for general elections), else `wikipedia-and-press`. Informational, not binding. |

## See also

- [`docs/concepts/party-identity.md`](../../docs/concepts/party-identity.md) -
  identity contract for `party_id`; the resolver that produces the UNK
  sentinel when an alias is missing.
- [`tools/correlate_unk_via_tcpd_catalogue`](../../tools/correlate_unk_via_tcpd_catalogue) -
  the per-party catalogue correlator (PR-Q2 / PR-Q8). The B1/B2 buckets
  documented in its package docstring are the same buckets this ledger's
  TCPD-context columns reflect.
- [`tools/correlate_unk_apply`](../../tools/correlate_unk_apply) - the
  curator script that turns a verdict.csv into `parties.csv` alias / mint
  mutations.
- [`CLAUDE.md`](../../CLAUDE.md) section 12 - provenance contract for the
  citation row attached to every applied mint (the TCPD per-party
  catalogue is `src-4040a970f10c`).
