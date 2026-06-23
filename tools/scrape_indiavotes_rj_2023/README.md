# scrape_indiavotes_rj_2023

One-shot IndiaVotes scraper for the Rajasthan Vidhan Sabha 2023 cohort
(200 ACs). Sister tool to [`tools/elections_parity_indiavotes/`](../elections_parity_indiavotes/);
the two share politeness invariants but target different IndiaVotes
frontends — this one handles the Astro v5 `iv-page-context` JSON layout
that the older parity scraper does not understand.

## Why this exists

TCPD compilation cutoff is 2021 and the upstream `thecont1` Nov 2023
cohort is missing MP/CG/RJ/TG (only KA/ML/NL/TR present). The 200
Rajasthan ACs therefore have no canonical source after the
PR-S-MP-AE2023 PR collapsed on precondition-fail (2026-06-10). User
signoff (2026-06-11): "A - fix all UNK and rajasthan" promotes
IndiaVotes from secondary parity-oracle source to primary ingest source
for the Nov 2023 RJ cohort. Recorded as Scope-change ledger row SCL-03
in the PR body per CLAUDE.md section 10.

## Politeness invariants

- 1 req/sec strictly serialised single-threaded.
- Citizen UA (`yen-gov-electoral-corpus/0.1`).
- No Cookie / Referer / yen-gov-tagged headers.
- Cache-first; re-runs are zero network traffic.
- `--no-fetch` skips network entirely (emit CSVs from existing cache).
- Total wall-clock for a cold scrape: ~3.5 min (201 pages * 1 sec/req +
  latency). Warm scrape: seconds.

## Usage

```powershell
# Cold scrape (uses or seeds the cache):
python tools/scrape_indiavotes_rj_2023/__main__.py

# Re-run CSV emit from existing cache (no network):
python tools/scrape_indiavotes_rj_2023/__main__.py --no-fetch

# Force re-fetch every page (bypass cache):
python tools/scrape_indiavotes_rj_2023/__main__.py --force-refetch
```

## Outputs

All under `datasets/ephemeral/indiavotes-rj-ae2023/2023-11/`:

- `master.html` + `master.json` — state-year landing page (party tally +
  total-seats + turnout).
- `ac/<slug>.html` + `ac/<slug>.json` × 200 — per-AC candidate tables.
- `results.csv` — flat candidate-grain CSV.
- `summary.csv` — flat AC-grain CSV.
- `README.md` — citation + scrape date + politeness compliance note.

## Downstream

The `tools/elections_rj_ae2023_ingest/` tool consumes `results.csv` +
`summary.csv` and emits the canonical
`datasets/elections/assembly/state=rajasthan/election=2023/candidacies.csv`
+ `summary.csv`. The provenance source row lands in
`datasets/data/entities/source.csv` keyed by the
`(producer="Election Commission of India", title="Rajasthan Vidhan Sabha 2023", vintage="2023-11")`
triple per ADR-0032 (ECI is the issuing authority; IndiaVotes is the
redistribution channel scraped here - user directive 2026-06-23).

## Why a sibling tool and not an extension of `elections_parity_indiavotes/`

The older parity scraper targets the legacy HTML-table layout
(`find_all('table')` + party-in-parens extraction). IndiaVotes migrated
to Astro v5 in early 2026 and now ships the data inside
`<script type="application/json" id="iv-page-context">{...}</script>`.
A unified scraper would need a layout-detection switch and would be
harder to retire when the parity oracle moves to the new JSON layout in
a future PR. Sibling tools is the strangler-fig pattern: the new layout
ships clean, the old layout retires independently. The two scrapers
coexist (the older one is still wired into the parity CLI per
`tests/test_elections_parity_indiavotes.py`).
