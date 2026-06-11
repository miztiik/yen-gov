# IndiaVotes snapshot - Rajasthan Vidhan Sabha 2023

**Scrape date**: 2026-06-11 (snapshot operator window).
**Vintage tag**: 2023-11 (Nov 2023 polling event; matches the source.csv vintage column).
**Source URLs**:
- Master: <https://www.indiavotes.com/vidhan-sabha/rajasthan/2023>
- Per-AC: <https://www.indiavotes.com/vidhan-sabha/rajasthan/2023/<slug>/> x 200

**Politeness compliance**: 1 req/sec single-threaded; citizen UA
(`yen-gov-electoral-corpus/0.1 (one-shot citizen audit; contact via github.com/yen-gov/yen-gov)`); no cookies / Referer / yen-gov-tagged headers; cache-first
(re-runs incur zero network traffic). Producer (citation grain):
IndiaVotes (compilation publisher; original data sourced from ECI).

## Why this snapshot exists

TCPD compilation cutoff is 2021 and the upstream thecont1 Nov 2023 cohort
is missing MP/CG/RJ/TG (only KA/ML/NL/TR present). The 200 Rajasthan ACs
therefore have no canonical source after the PR-S-MP-AE2023 PR collapsed
on precondition-fail (2026-06-10). This snapshot promotes IndiaVotes from
secondary parity-oracle source to primary ingest source for the Nov 2023
Rajasthan cohort.

User signoff (2026-06-11): "A - fix all UNK and rajasthan". Recorded as
Scope-change ledger row SCL-03 in the PR body per CLAUDE.md section 10.

## Files

- `master.html` + `master.json` - state-year landing page (party tally +
  total-seats + turnout, extracted from the Astro v5 `iv-page-context`
  script tag).
- `ac/<slug>.html` + `ac/<slug>.json` x 200 - per-AC candidate
  tables + summary.
- `results.csv` - flat candidate-grain CSV (1875 rows; one per
  (AC, candidate); NOTA excluded because IndiaVotes records it on the
  summary `nota_votes` field, not as a candidate row).
- `summary.csv` - flat AC-grain CSV (200 rows; winner +
  runnerup + margin).

## Downstream consumer

`tools/elections_rj_ae2023_ingest/` maps these flat CSV rows to the
canonical `datasets/elections/assembly/state=rajasthan/election=2023/`
candidacies.csv + summary.csv (Holy Law #6, OWID one-format-per-tier).

Re-run with `--force-refetch` to bypass the cache and re-fetch every
page; the cache files are byte-stable across re-runs because the
IndiaVotes pages are SSR'd and the JSON blobs are deterministic.
