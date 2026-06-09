# AcGenMay2026 fan-out coverage (TN / KL / WB / AS / PY)

Per-state DelimID-2008 bind coverage for the AcGenMay2026 ECI Section 10
Detailed Results emit. `skipped_eci_no` counts ECI Constituency_No values
that did not resolve to a current `electoral.csv` AC entity for the state
(typically an LGD-spine gap). Source XLSXes are hand-downloaded from
old.eci.gov.in and held in `datasets/ephemeral/` for the legacy
`eci-statreport-emit-local` parse; the partitioned candidacies+summary
CSVs are pivoted by `assembly_results_from_eci.py`.

| state | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- |
| tamil-nadu | 1170 | 234 | 0 |
| kerala | 670 | 140 | 0 |
| west-bengal | 1470 | 294 | 0 |
| assam | 546 | 126 | 0 |
| puducherry | 150 | 30 | 0 |
| **total** | 4006 | 824 | |
