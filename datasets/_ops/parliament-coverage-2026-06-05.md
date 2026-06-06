# Parliament (Lok Sabha) coverage (B2b.5.4, 2026-06-05)

Per-cycle PC bind coverage for the in-force (2008) delimitation. `unbound` counts (state, pc_no) pairs that did not resolve to an `electoral.csv` PC entity - state-reorganisation artefacts + the small LGD-spine gap + Delhi's PCs (Delhi has no `electoral.csv` constituencies; deferred with the assembly Delhi gap).

Per-cycle totals below are reproduced by `_write_coverage` on every run; re-emitted unchanged on 2026-06-06 (F1.3a Path A) AFTER party_lookup wiring was added to `emit_parliament`. Aggregate party_id resolution: **15,929 of 19,336 rows (82.4%)** carry a non-null `party_id`; the remaining 3,407 rows are long-tail independents + niche parties not in `parties.csv`. Provenance is 100% (every row carries `source_id`). Per Holy Law #9 no party_ids are fabricated.

| election | states | candidacies | summary PCs | unbound |
| --- | --- | --- | --- | --- |
| 2009 | 29 | 6380 | 428 | 115 |
| 2011 | 3 | 68 | 3 | 2 |
| 2012 | 4 | 40 | 4 | 1 |
| 2013 | 3 | 32 | 4 | 3 |
| 2014 | 29 | 6455 | 428 | 115 |
| 2015 | 3 | 42 | 3 | 0 |
| 2016 | 4 | 41 | 5 | 0 |
| 2017 | 3 | 14 | 3 | 0 |
| 2018 | 7 | 140 | 12 | 1 |
| 2019 | 29 | 6100 | 426 | 117 |
| 2021 | 3 | 24 | 3 | 4 |
