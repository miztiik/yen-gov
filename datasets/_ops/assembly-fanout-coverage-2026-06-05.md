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

## Wave 2

| state | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- |
| jharkhand | 11 | 3879 | 247 | 9 |
| karnataka | 13 | 10196 | 874 | 64 |
| kerala | 7 | 3204 | 425 | 6 |
| madhya-pradesh | 13 | 9231 | 737 | 4 |
| maharashtra | 11 | 10153 | 810 | 68 |
| manipur | 6 | 838 | 188 | 0 |
| meghalaya | 6 | 1108 | 174 | 12 |
| mizoram | 7 | 474 | 101 | 24 |
| nagaland | 10 | 816 | 234 | 17 |
| odisha | 7 | 3841 | 442 | 3 |
| **wave 2 total** | | 43740 | 4232 | |

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

---

# Path A re-emit (2026-06-06, F1.3a)

Re-emitted by the same three waves AFTER:

1. **electoral.csv extension** landed in F1.1 #791 (324 LGD-spine gap-fill
   rows binding the previously-unbindable historical-cycle constituencies).
2. **party_lookup wiring** added to `assembly_results.emit_state_assembly`
   for F1.3a v1.1: TCPD `Party` shortcode -> `parties.IN.*` via
   `parties.csv.short` (case-insensitive). Long-tail shorts absent from
   `parties.csv` stay null per Holy Law #9 (no fabricated FKs).

Aggregate party_id resolution across all 31 emitted states: **112,950 of
140,041 rows (80.7%)** carry a non-null `party_id`; the remaining 27,091
rows are long-tail independents + niche parties not yet in
`parties.csv`. Provenance is 100% (every row carries `source_id`).

Row-count deltas vs the original block above are NOT a party_lookup
side-effect; they come from the LGD-spine extension picking up
previously-unbindable ACs (the previously-`skipped_eci_no` totals shrink
proportionally).

## Wave 1

| state | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- |
| andhra-pradesh | 9 | 8778 | 684 | 1 |
| arunachal-pradesh | 7 | 505 | 184 | 0 |
| assam | 7 | 3051 | 387 | 0 |
| bihar | 10 | 10990 | 759 | 0 |
| chhattisgarh | 9 | 3386 | 277 | 0 |
| goa | 5 | 797 | 125 | 0 |
| gujarat | 10 | 5683 | 590 | 0 |
| haryana | 7 | 3838 | 275 | 0 |
| himachal-pradesh | 6 | 1310 | 210 | 0 |
| jammu-and-kashmir | 4 | 1973 | 157 | 21 |
| **wave 1 total** | | 40311 | 3648 | |

## Wave 2

| state | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- |
| jharkhand | 11 | 4015 | 256 | 0 |
| karnataka | 13 | 11154 | 938 | 0 |
| kerala | 7 | 3254 | 431 | 0 |
| madhya-pradesh | 13 | 9231 | 737 | 4 |
| maharashtra | 11 | 10153 | 810 | 68 |
| manipur | 6 | 838 | 188 | 0 |
| meghalaya | 6 | 1175 | 186 | 0 |
| mizoram | 7 | 474 | 101 | 24 |
| nagaland | 11 | 876 | 252 | 0 |
| odisha | 7 | 3841 | 442 | 3 |
| **wave 2 total** | | 45011 | 4341 | |

## Wave 3

| state | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- |
| puducherry | 4 | 872 | 92 | 0 |
| punjab | 8 | 3615 | 361 | 0 |
| rajasthan | 8 | 6673 | 613 | 0 |
| sikkim | 4 | 406 | 88 | 9 |
| telangana | 6 | 3327 | 224 | 20 |
| tripura | 8 | 928 | 191 | 0 |
| uttar-pradesh | 10 | 16640 | 1254 | 0 |
| uttarakhand | 8 | 2095 | 217 | 0 |
| west-bengal | 10 | 6046 | 909 | 0 |
| **wave 3 total** | | 40602 | 3949 | |

## Wave 1

| state | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- |
| andhra-pradesh | 9 | 8778 | 684 | 1 |
| arunachal-pradesh | 7 | 505 | 184 | 0 |
| assam | 7 | 3051 | 387 | 0 |
| bihar | 10 | 10990 | 759 | 0 |
| chhattisgarh | 9 | 3386 | 277 | 0 |
| goa | 5 | 797 | 125 | 0 |
| gujarat | 10 | 5683 | 590 | 0 |
| haryana | 7 | 3838 | 275 | 0 |
| himachal-pradesh | 6 | 1310 | 210 | 0 |
| jammu-and-kashmir | 4 | 1973 | 157 | 21 |
| **wave 1 total** | | 40311 | 3648 | |

## Wave 2

| state | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- |
| jharkhand | 11 | 4015 | 256 | 0 |
| karnataka | 13 | 11154 | 938 | 0 |
| kerala | 7 | 3254 | 431 | 0 |
| madhya-pradesh | 13 | 9231 | 737 | 4 |
| maharashtra | 11 | 10153 | 810 | 68 |
| manipur | 6 | 838 | 188 | 0 |
| meghalaya | 6 | 1175 | 186 | 0 |
| mizoram | 7 | 474 | 101 | 24 |
| nagaland | 11 | 876 | 252 | 0 |
| odisha | 7 | 3841 | 442 | 3 |
| **wave 2 total** | | 45011 | 4341 | |

## Wave 3

| state | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- |
| puducherry | 4 | 872 | 92 | 0 |
| punjab | 8 | 3615 | 361 | 0 |
| rajasthan | 8 | 6673 | 613 | 0 |
| sikkim | 4 | 406 | 88 | 9 |
| telangana | 6 | 3327 | 224 | 20 |
| tripura | 8 | 928 | 191 | 0 |
| uttar-pradesh | 10 | 16640 | 1254 | 0 |
| uttarakhand | 8 | 2095 | 217 | 0 |
| west-bengal | 10 | 6046 | 909 | 0 |
| **wave 3 total** | | 40602 | 3949 | |

## Wave 1

| state | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- |
| andhra-pradesh | 9 | 8778 | 684 | 1 |
| arunachal-pradesh | 7 | 505 | 184 | 0 |
| assam | 7 | 3051 | 387 | 0 |
| bihar | 10 | 10990 | 759 | 0 |
| chhattisgarh | 9 | 3386 | 277 | 0 |
| goa | 5 | 797 | 125 | 0 |
| gujarat | 10 | 5501 | 590 | 0 |
| haryana | 7 | 3838 | 275 | 0 |
| himachal-pradesh | 6 | 1242 | 210 | 0 |
| jammu-and-kashmir | 4 | 1973 | 157 | 21 |
| **wave 1 total** | | 40061 | 3648 | |

## Wave 2

| state | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- |
| jharkhand | 11 | 4015 | 256 | 0 |
| karnataka | 13 | 10930 | 938 | 0 |
| kerala | 7 | 3254 | 431 | 0 |
| madhya-pradesh | 13 | 9231 | 737 | 4 |
| maharashtra | 11 | 10153 | 810 | 68 |
| manipur | 6 | 838 | 188 | 0 |
| meghalaya | 6 | 1116 | 186 | 0 |
| mizoram | 7 | 474 | 101 | 24 |
| nagaland | 11 | 817 | 252 | 0 |
| odisha | 7 | 3841 | 442 | 3 |
| **wave 2 total** | | 44669 | 4341 | |

## Wave 3

| state | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- |
| puducherry | 4 | 872 | 92 | 0 |
| punjab | 8 | 3615 | 361 | 0 |
| rajasthan | 8 | 6673 | 613 | 0 |
| sikkim | 4 | 406 | 88 | 9 |
| telangana | 6 | 3327 | 224 | 20 |
| tripura | 8 | 868 | 191 | 0 |
| uttar-pradesh | 10 | 16640 | 1254 | 0 |
| uttarakhand | 8 | 2095 | 217 | 0 |
| west-bengal | 10 | 6046 | 909 | 0 |
| **wave 3 total** | | 40542 | 3949 | |

## Wave 1

| state | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- |
| andhra-pradesh | 9 | 8777 | 684 | 1 |
| arunachal-pradesh | 7 | 504 | 184 | 0 |
| assam | 7 | 3043 | 387 | 0 |
| bihar | 10 | 10977 | 759 | 0 |
| chhattisgarh | 9 | 3383 | 277 | 0 |
| delhi | 6 | 3068 | 284 | 0 |
| goa | 5 | 793 | 125 | 0 |
| gujarat | 10 | 5481 | 590 | 0 |
| haryana | 7 | 3835 | 275 | 0 |
| himachal-pradesh | 6 | 1237 | 210 | 0 |
| jammu-and-kashmir | 4 | 1973 | 157 | 21 |
| **wave 1 total** | | 43071 | 3932 | |

## Wave 2

| state | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- |
| jharkhand | 11 | 4009 | 256 | 0 |
| karnataka | 13 | 10906 | 938 | 0 |
| kerala | 7 | 3247 | 431 | 0 |
| madhya-pradesh | 13 | 9196 | 737 | 4 |
| maharashtra | 11 | 10150 | 810 | 68 |
| manipur | 6 | 833 | 188 | 0 |
| meghalaya | 6 | 1107 | 186 | 0 |
| mizoram | 7 | 471 | 101 | 24 |
| nagaland | 11 | 811 | 252 | 0 |
| odisha | 7 | 3837 | 442 | 3 |
| **wave 2 total** | | 44567 | 4341 | |

## Wave 3

| state | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- |
| puducherry | 4 | 870 | 92 | 0 |
| punjab | 8 | 3610 | 361 | 0 |
| rajasthan | 8 | 6665 | 613 | 0 |
| sikkim | 4 | 404 | 88 | 9 |
| telangana | 6 | 3323 | 224 | 20 |
| tripura | 8 | 863 | 191 | 0 |
| uttar-pradesh | 10 | 16618 | 1254 | 0 |
| uttarakhand | 8 | 2092 | 217 | 0 |
| west-bengal | 10 | 6030 | 909 | 0 |
| **wave 3 total** | | 40475 | 3949 | |

## Wave 1

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| andhra-pradesh | 3 | 26 | 14740 | 2145 | 0 |
| arunachal-pradesh | 3 | 11 | 985 | 331 | 0 |
| assam | 3 | 15 | 7431 | 876 | 0 |
| bihar | 3 | 23 | 35365 | 2273 | 0 |
| chhattisgarh | 3 | 4 | 886 | 95 | 0 |
| delhi | 3 | 7 | 3633 | 327 | 0 |
| goa | 3 | 9 | 1216 | 208 | 0 |
| gujarat | 3 | 24 | 11189 | 1496 | 0 |
| haryana | 3 | 21 | 9653 | 654 | 0 |
| himachal-pradesh | 3 | 16 | 3087 | 556 | 0 |
| jammu-and-kashmir | 3 | 14 | 2832 | 419 | 0 |
| **wave 1 delim=3 total** | | | 91017 | 9380 | |

## Wave 1

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| andhra-pradesh | 1 | 3 | 1010 | 309 | 0 |
| arunachal-pradesh | 1 | 0 | 0 | 0 | 0 |
| assam | 1 | 4 | 422 | 109 | 0 |
| bihar | 1 | 3 | 1534 | 320 | 0 |
| chhattisgarh | 1 | 0 | 0 | 0 | 0 |
| delhi | 1 | 0 | 0 | 0 | 0 |
| goa | 1 | 0 | 0 | 0 | 0 |
| gujarat | 1 | 2 | 526 | 156 | 0 |
| haryana | 1 | 0 | 0 | 0 | 0 |
| himachal-pradesh | 1 | 0 | 0 | 0 | 0 |
| jammu-and-kashmir | 1 | 1 | 174 | 75 | 0 |
| **wave 1 delim=1 total** | | | 3666 | 969 | |

## Wave 1

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| andhra-pradesh | 2 | 4 | 2095 | 581 | 0 |
| arunachal-pradesh | 2 | 0 | 0 | 0 | 0 |
| assam | 2 | 3 | 977 | 241 | 0 |
| bihar | 2 | 4 | 6182 | 958 | 0 |
| chhattisgarh | 2 | 0 | 0 | 0 | 0 |
| delhi | 2 | 1 | 270 | 56 | 0 |
| goa | 2 | 0 | 0 | 0 | 0 |
| gujarat | 2 | 3 | 1437 | 337 | 0 |
| haryana | 2 | 4 | 1275 | 248 | 0 |
| himachal-pradesh | 2 | 2 | 566 | 128 | 0 |
| jammu-and-kashmir | 2 | 2 | 548 | 150 | 0 |
| **wave 1 delim=2 total** | | | 13350 | 2699 | |

## Wave 2

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| jharkhand | 3 | 3 | 1428 | 83 | 0 |
| karnataka | 3 | 25 | 12269 | 1616 | 0 |
| kerala | 3 | 21 | 6933 | 1147 | 0 |
| madhya-pradesh | 3 | 25 | 19466 | 2202 | 0 |
| maharashtra | 3 | 22 | 19101 | 2067 | 0 |
| manipur | 3 | 16 | 2760 | 487 | 0 |
| meghalaya | 3 | 15 | 2180 | 431 | 0 |
| mizoram | 3 | 12 | 1307 | 299 | 0 |
| nagaland | 3 | 17 | 1538 | 492 | 0 |
| odisha | 3 | 20 | 7002 | 1201 | 0 |
| **wave 2 delim=3 total** | | | 73984 | 10025 | |

## Wave 2

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| jharkhand | 1 | 0 | 0 | 0 | 0 |
| karnataka | 1 | 0 | 0 | 0 | 0 |
| kerala | 1 | 0 | 0 | 0 | 0 |
| madhya-pradesh | 1 | 4 | 1361 | 295 | 0 |
| maharashtra | 1 | 4 | 1182 | 271 | 0 |
| manipur | 1 | 0 | 0 | 0 | 0 |
| meghalaya | 1 | 0 | 0 | 0 | 0 |
| mizoram | 1 | 0 | 0 | 0 | 0 |
| nagaland | 1 | 0 | 0 | 0 | 0 |
| odisha | 1 | 1 | 535 | 140 | 0 |
| **wave 2 delim=1 total** | | | 3078 | 706 | |

## Wave 2

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| jharkhand | 2 | 0 | 0 | 0 | 0 |
| karnataka | 2 | 0 | 0 | 0 | 0 |
| kerala | 2 | 4 | 1494 | 400 | 0 |
| madhya-pradesh | 2 | 4 | 3022 | 601 | 0 |
| maharashtra | 2 | 4 | 2449 | 543 | 0 |
| manipur | 2 | 2 | 418 | 90 | 0 |
| meghalaya | 2 | 1 | 198 | 60 | 0 |
| mizoram | 2 | 1 | 155 | 30 | 0 |
| nagaland | 2 | 4 | 244 | 96 | 0 |
| odisha | 2 | 3 | 1434 | 281 | 0 |
| **wave 2 delim=2 total** | | | 9414 | 2101 | |

## Wave 3

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| puducherry | 3 | 12 | 1607 | 273 | 0 |
| punjab | 3 | 18 | 5610 | 835 | 0 |
| rajasthan | 3 | 22 | 12763 | 1430 | 0 |
| sikkim | 3 | 7 | 938 | 189 | 0 |
| tamil-nadu | 3 | 23 | 18319 | 1904 | 0 |
| telangana | 3 | 0 | 0 | 0 | 0 |
| tripura | 3 | 14 | 2044 | 431 | 0 |
| uttar-pradesh | 3 | 31 | 58539 | 4297 | 0 |
| uttarakhand | 3 | 5 | 1732 | 143 | 0 |
| west-bengal | 3 | 23 | 11891 | 2127 | 0 |
| **wave 3 delim=3 total** | | | 113443 | 11629 | |

## Wave 3

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| puducherry | 1 | 0 | 0 | 0 | 0 |
| punjab | 1 | 3 | 773 | 160 | 0 |
| rajasthan | 1 | 3 | 904 | 181 | 0 |
| sikkim | 1 | 0 | 0 | 0 | 0 |
| tamil-nadu | 1 | 0 | 0 | 0 | 0 |
| telangana | 1 | 0 | 0 | 0 | 0 |
| tripura | 1 | 0 | 0 | 0 | 0 |
| uttar-pradesh | 1 | 3 | 2641 | 435 | 0 |
| uttarakhand | 1 | 0 | 0 | 0 | 0 |
| west-bengal | 1 | 3 | 980 | 258 | 0 |
| **wave 3 delim=1 total** | | | 5298 | 1034 | |

## Wave 3

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| puducherry | 2 | 2 | 161 | 60 | 0 |
| punjab | 2 | 4 | 1557 | 315 | 0 |
| rajasthan | 2 | 3 | 1772 | 370 | 0 |
| sikkim | 2 | 0 | 0 | 0 | 0 |
| tamil-nadu | 2 | 1 | 750 | 234 | 0 |
| telangana | 2 | 0 | 0 | 0 | 0 |
| tripura | 2 | 2 | 321 | 90 | 0 |
| uttar-pradesh | 2 | 6 | 5966 | 863 | 0 |
| uttarakhand | 2 | 0 | 0 | 0 | 0 |
| west-bengal | 2 | 4 | 4319 | 1119 | 0 |
| **wave 3 delim=2 total** | | | 14846 | 3051 | |

## Wave 1

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| andhra-pradesh | 1 | 3 | 1010 | 309 | 0 |
| arunachal-pradesh | 1 | 0 | 0 | 0 | 0 |
| assam | 1 | 4 | 422 | 109 | 0 |
| bihar | 1 | 3 | 1534 | 320 | 0 |
| chhattisgarh | 1 | 0 | 0 | 0 | 0 |
| delhi | 1 | 0 | 0 | 0 | 0 |
| goa | 1 | 0 | 0 | 0 | 0 |
| gujarat | 1 | 2 | 526 | 156 | 0 |
| haryana | 1 | 0 | 0 | 0 | 0 |
| himachal-pradesh | 1 | 0 | 0 | 0 | 0 |
| jammu-and-kashmir | 1 | 1 | 174 | 75 | 0 |
| **wave 1 delim=1 total** | | | 3666 | 969 | |

## Wave 1

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| andhra-pradesh | 2 | 4 | 2095 | 581 | 0 |
| arunachal-pradesh | 2 | 0 | 0 | 0 | 0 |
| assam | 2 | 3 | 977 | 241 | 0 |
| bihar | 2 | 4 | 6182 | 958 | 0 |
| chhattisgarh | 2 | 0 | 0 | 0 | 0 |
| delhi | 2 | 1 | 270 | 56 | 0 |
| goa | 2 | 0 | 0 | 0 | 0 |
| gujarat | 2 | 3 | 1437 | 337 | 0 |
| haryana | 2 | 4 | 1275 | 248 | 0 |
| himachal-pradesh | 2 | 2 | 566 | 128 | 0 |
| jammu-and-kashmir | 2 | 2 | 548 | 150 | 0 |
| **wave 1 delim=2 total** | | | 13350 | 2699 | |

## Wave 1

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| andhra-pradesh | 3 | 26 | 14740 | 2145 | 0 |
| arunachal-pradesh | 3 | 11 | 985 | 331 | 0 |
| assam | 3 | 15 | 7431 | 876 | 0 |
| bihar | 3 | 23 | 35365 | 2273 | 0 |
| chhattisgarh | 3 | 4 | 886 | 95 | 0 |
| delhi | 3 | 7 | 3633 | 327 | 0 |
| goa | 3 | 9 | 1216 | 208 | 0 |
| gujarat | 3 | 24 | 11189 | 1496 | 0 |
| haryana | 3 | 21 | 9653 | 654 | 0 |
| himachal-pradesh | 3 | 16 | 3087 | 556 | 0 |
| jammu-and-kashmir | 3 | 14 | 2832 | 419 | 0 |
| **wave 1 delim=3 total** | | | 91017 | 9380 | |

## Wave 1

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| andhra-pradesh | 4 | 9 | 8777 | 684 | 1 |
| arunachal-pradesh | 4 | 7 | 504 | 184 | 0 |
| assam | 4 | 7 | 3043 | 387 | 0 |
| bihar | 4 | 10 | 10977 | 759 | 0 |
| chhattisgarh | 4 | 9 | 3383 | 277 | 0 |
| delhi | 4 | 6 | 3068 | 284 | 0 |
| goa | 4 | 5 | 793 | 125 | 0 |
| gujarat | 4 | 10 | 5481 | 590 | 0 |
| haryana | 4 | 7 | 3835 | 275 | 0 |
| himachal-pradesh | 4 | 6 | 1237 | 210 | 0 |
| jammu-and-kashmir | 4 | 4 | 1973 | 157 | 21 |
| **wave 1 delim=4 total** | | | 43071 | 3932 | |

## Wave 2

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| jharkhand | 1 | 0 | 0 | 0 | 0 |
| karnataka | 1 | 0 | 0 | 0 | 0 |
| kerala | 1 | 0 | 0 | 0 | 0 |
| madhya-pradesh | 1 | 4 | 1361 | 295 | 0 |
| maharashtra | 1 | 4 | 1182 | 271 | 0 |
| manipur | 1 | 0 | 0 | 0 | 0 |
| meghalaya | 1 | 0 | 0 | 0 | 0 |
| mizoram | 1 | 0 | 0 | 0 | 0 |
| nagaland | 1 | 0 | 0 | 0 | 0 |
| odisha | 1 | 1 | 535 | 140 | 0 |
| **wave 2 delim=1 total** | | | 3078 | 706 | |

## Wave 2

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| jharkhand | 2 | 0 | 0 | 0 | 0 |
| karnataka | 2 | 0 | 0 | 0 | 0 |
| kerala | 2 | 4 | 1494 | 400 | 0 |
| madhya-pradesh | 2 | 4 | 3022 | 601 | 0 |
| maharashtra | 2 | 4 | 2449 | 543 | 0 |
| manipur | 2 | 2 | 418 | 90 | 0 |
| meghalaya | 2 | 1 | 198 | 60 | 0 |
| mizoram | 2 | 1 | 155 | 30 | 0 |
| nagaland | 2 | 4 | 244 | 96 | 0 |
| odisha | 2 | 3 | 1434 | 281 | 0 |
| **wave 2 delim=2 total** | | | 9414 | 2101 | |

## Wave 2

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| jharkhand | 3 | 3 | 1428 | 83 | 0 |
| karnataka | 3 | 25 | 12269 | 1616 | 0 |
| kerala | 3 | 21 | 6933 | 1147 | 0 |
| madhya-pradesh | 3 | 25 | 19466 | 2202 | 0 |
| maharashtra | 3 | 22 | 19101 | 2067 | 0 |
| manipur | 3 | 16 | 2760 | 487 | 0 |
| meghalaya | 3 | 15 | 2180 | 431 | 0 |
| mizoram | 3 | 12 | 1307 | 299 | 0 |
| nagaland | 3 | 17 | 1538 | 492 | 0 |
| odisha | 3 | 20 | 7002 | 1201 | 0 |
| **wave 2 delim=3 total** | | | 73984 | 10025 | |

## Wave 2

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| jharkhand | 4 | 11 | 4009 | 256 | 0 |
| karnataka | 4 | 13 | 10906 | 938 | 0 |
| kerala | 4 | 7 | 3247 | 431 | 0 |
| madhya-pradesh | 4 | 13 | 9196 | 737 | 4 |
| maharashtra | 4 | 11 | 10150 | 810 | 68 |
| manipur | 4 | 6 | 833 | 188 | 0 |
| meghalaya | 4 | 6 | 1107 | 186 | 0 |
| mizoram | 4 | 7 | 471 | 101 | 24 |
| nagaland | 4 | 11 | 811 | 252 | 0 |
| odisha | 4 | 7 | 3837 | 442 | 3 |
| **wave 2 delim=4 total** | | | 44567 | 4341 | |

## Wave 3

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| puducherry | 1 | 0 | 0 | 0 | 0 |
| punjab | 1 | 3 | 773 | 160 | 0 |
| rajasthan | 1 | 3 | 904 | 181 | 0 |
| sikkim | 1 | 0 | 0 | 0 | 0 |
| tamil-nadu | 1 | 0 | 0 | 0 | 0 |
| telangana | 1 | 0 | 0 | 0 | 0 |
| tripura | 1 | 0 | 0 | 0 | 0 |
| uttar-pradesh | 1 | 3 | 2641 | 435 | 0 |
| uttarakhand | 1 | 0 | 0 | 0 | 0 |
| west-bengal | 1 | 3 | 980 | 258 | 0 |
| **wave 3 delim=1 total** | | | 5298 | 1034 | |

## Wave 3

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| puducherry | 2 | 2 | 161 | 60 | 0 |
| punjab | 2 | 4 | 1557 | 315 | 0 |
| rajasthan | 2 | 3 | 1772 | 370 | 0 |
| sikkim | 2 | 0 | 0 | 0 | 0 |
| tamil-nadu | 2 | 1 | 750 | 234 | 0 |
| telangana | 2 | 0 | 0 | 0 | 0 |
| tripura | 2 | 2 | 321 | 90 | 0 |
| uttar-pradesh | 2 | 6 | 5966 | 863 | 0 |
| uttarakhand | 2 | 0 | 0 | 0 | 0 |
| west-bengal | 2 | 4 | 4319 | 1119 | 0 |
| **wave 3 delim=2 total** | | | 14846 | 3051 | |

## Wave 3

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| puducherry | 3 | 12 | 1607 | 273 | 0 |
| punjab | 3 | 18 | 5610 | 835 | 0 |
| rajasthan | 3 | 22 | 12763 | 1430 | 0 |
| sikkim | 3 | 7 | 938 | 189 | 0 |
| tamil-nadu | 3 | 23 | 18319 | 1904 | 0 |
| telangana | 3 | 0 | 0 | 0 | 0 |
| tripura | 3 | 14 | 2044 | 431 | 0 |
| uttar-pradesh | 3 | 31 | 58539 | 4297 | 0 |
| uttarakhand | 3 | 5 | 1732 | 143 | 0 |
| west-bengal | 3 | 23 | 11891 | 2127 | 0 |
| **wave 3 delim=3 total** | | | 113443 | 11629 | |

## Wave 3

| state | delim_id | years | candidacies | summary ACs | skipped_eci_no |
| --- | --- | --- | --- | --- | --- |
| puducherry | 4 | 4 | 870 | 92 | 0 |
| punjab | 4 | 8 | 3610 | 361 | 0 |
| rajasthan | 4 | 8 | 6665 | 613 | 0 |
| sikkim | 4 | 4 | 404 | 88 | 9 |
| telangana | 4 | 6 | 3323 | 224 | 20 |
| tripura | 4 | 8 | 863 | 191 | 0 |
| uttar-pradesh | 4 | 10 | 16618 | 1254 | 0 |
| uttarakhand | 4 | 8 | 2092 | 217 | 0 |
| west-bengal | 4 | 10 | 6030 | 909 | 0 |
| **wave 3 delim=4 total** | | | 40475 | 3949 | |
