# Parliament coverage (B2b.5.4, 2026-06-05; PR-Q7c historical delims, 2026-06-12)

Per-cycle PC bind coverage. `unbound` counts (state, pc_no) pairs that did not resolve to an `electoral.csv` PC entity for the matching delim cohort - state-reorganisation artefacts + the small LGD-spine gap + historical state-name divergence. PR-Q7c (2026-06-12) extends the driver to DelimID 1/2/3 once `_run_historical_pc_entities` has minted the historical PC cohorts.

| delim_id | election | states | candidacies | summary PCs | unbound |
| --- | --- | --- | --- | --- | --- |
| 4 | 2009 | 32 | 6598 | 439 | 104 |
| 4 | 2011 | 4 | 73 | 4 | 1 |
| 4 | 2012 | 4 | 40 | 4 | 1 |
| 4 | 2013 | 3 | 32 | 4 | 3 |
| 4 | 2014 | 32 | 6672 | 439 | 104 |
| 4 | 2015 | 3 | 42 | 3 | 0 |
| 4 | 2016 | 4 | 41 | 5 | 0 |
| 4 | 2017 | 3 | 14 | 3 | 0 |
| 4 | 2018 | 7 | 129 | 12 | 1 |
| 4 | 2019 | 32 | 6339 | 437 | 106 |
| 4 | 2021 | 3 | 22 | 3 | 4 |
