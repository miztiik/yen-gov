# Assembly fan-out coverage (B2b.5.3, 2026-06-05)

Per-state DelimID-4 bind coverage for the assembly election-results
fan-out. `skipped_eci_no` counts (state-year, Constituency_No) pairs that
did not resolve to an `electoral.csv` entity - overwhelmingly
state-reorganisation artefacts (pre-2014 united-Andhra / Telangana ACs,
etc.) where the historical constituency has no current LGD entity, plus a
small LGD-spine gap (the same class as TN eci_no 17 / 192). Delhi is
deferred (no Delhi ACs in `electoral.csv`).

## Wave 1

| state | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- |
| andhra-pradesh | 7 | 3835 | 304 | 368 |
| arunachal-pradesh | 7 | 505 | 184 | 0 |
| assam | 7 | 2997 | 378 | 9 |
| bihar | 10 | 10889 | 753 | 6 |
| chhattisgarh | 9 | 3386 | 277 | 0 |
| goa | 5 | 776 | 122 | 3 |
| gujarat | 10 | 5527 | 578 | 12 |
| haryana | 7 | 3602 | 257 | 18 |
| himachal-pradesh | 6 | 1310 | 210 | 0 |
| jammu-and-kashmir | 4 | 1973 | 157 | 21 |
| **wave 1 total** | | 34800 | 3220 | |

## Wave 3

| state | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- |
| puducherry | 4 | 699 | 73 | 19 |
| punjab | 8 | 3589 | 358 | 3 |
| rajasthan | 8 | 6020 | 573 | 40 |
| sikkim | 4 | 406 | 88 | 9 |
| telangana | 6 | 3327 | 224 | 20 |
| tripura | 8 | 928 | 191 | 0 |
| uttar-pradesh | 10 | 15399 | 1171 | 83 |
| uttarakhand | 8 | 2069 | 214 | 3 |
| west-bengal | 10 | 5060 | 786 | 123 |
| **wave 3 total** | | 37497 | 3678 | |
