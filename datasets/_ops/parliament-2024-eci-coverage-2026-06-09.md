# Parliament (Lok Sabha) 2024 ingest coverage (G16, 2026-06-09)

Source: ECI Statement 33 raw CSV (`datasets/ephemeral/2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv`). Bound to the 2008-delim PC entities in `electoral.csv` (the 2024 delimitation order takes effect for the LS2029 cycle). `unbound` counts ECI PCs that did not resolve to an `electoral.csv` PC entity at delim=2008 (Delhi's 7 PCs + Chandigarh + A&N + a small name-spelling drift in Maharashtra / UP / WB) - documented spine gap, not a writer bug. NOTA rows are excluded (ballot option, not a candidate); Surat is absent from the raw (unopposed return; ECI excluded it from Statement 33).

| election | states | candidacies | summary PCs | unbound | raw rows |
| --- | --- | --- | --- | --- | --- |
| 2024 | 33 | 8105 | 528 | 14 | 8909 |

## Unbound (state_slug, ECI PC name)

- `andaman-and-nicobar-islands` / `Andaman & Nicobar Islands`
- `chandigarh` / `Chandigarh`
- `dadra-and-nagar-haveli-and-daman-and-diu` / `Dadar & Nagar Haveli`
- `delhi` / `Chandni Chowk`
- `delhi` / `East Delhi`
- `delhi` / `New Delhi`
- `delhi` / `North-East Delhi`
- `delhi` / `North-West Delhi`
- `delhi` / `South Delhi`
- `delhi` / `West Delhi`
- `maharashtra` / `Mumbai South`
- `uttar-pradesh` / `Lucknow`
- `west-bengal` / `Kolkata Dakshin`
- `west-bengal` / `Kolkata Uttar`

