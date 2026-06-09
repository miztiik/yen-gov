# Parliament (Lok Sabha) 2024 ingest coverage (G16, 2026-06-09)

Source: ECI Statement 33 raw CSV (`datasets/ephemeral/2024_india_loksabha_33-Constituency-Wise-Detailed-Result.csv`). Bound to the 2008-delim PC entities in `electoral.csv` (the 2024 delimitation order takes effect for the LS2029 cycle). `unbound` counts ECI PCs that did not resolve to an `electoral.csv` PC entity at delim=2008 (Delhi's 7 PCs + Chandigarh + A&N + a small name-spelling drift in Maharashtra / UP / WB) - documented spine gap, not a writer bug. NOTA rows are excluded (ballot option, not a candidate); Surat is absent from the raw (unopposed return; ECI excluded it from Statement 33).

| election | states | candidacies | summary PCs | unbound | raw rows |
| --- | --- | --- | --- | --- | --- |
| 2024 | 33 | 7511 | 492 | 50 | 8909 |

## Unbound (state_slug, ECI PC name)

- `andaman-and-nicobar-islands` / `Andaman & Nicobar Islands`
- `andhra-pradesh` / `Ananthapur`
- `andhra-pradesh` / `Kurnoolu`
- `andhra-pradesh` / `Narsaraopet`
- `andhra-pradesh` / `Thirupathi`
- `assam` / `Darrang-Udalguri`
- `assam` / `Diphu`
- `assam` / `Guwahati`
- `bihar` / `Patliputra`
- `chandigarh` / `Chandigarh`
- `chhattisgarh` / `JANJGIR-CHAMPA`
- `dadra-and-nagar-haveli-and-daman-and-diu` / `Dadar & Nagar Haveli`
- `delhi` / `Chandni Chowk`
- `delhi` / `East Delhi`
- `delhi` / `New Delhi`
- `delhi` / `North-East Delhi`
- `delhi` / `North-West Delhi`
- `delhi` / `South Delhi`
- `delhi` / `West Delhi`
- `jammu-and-kashmir` / `ANANTNAG-RAJOURI`
- `jharkhand` / `Palamu`
- `karnataka` / `Bangalore North`
- `karnataka` / `Bangalore Rural`
- `karnataka` / `Bangalore South`
- `karnataka` / `Bangalore central`
- `karnataka` / `Belgaum`
- `karnataka` / `Bellary`
- `karnataka` / `Bijapur`
- `karnataka` / `Gulbarga`
- `karnataka` / `Mysore`
- `karnataka` / `Shimoga`
- `karnataka` / `Tumkur`
- `karnataka` / `Udupi Chikmagalur`
- `maharashtra` / `Bhandara Gondiya`
- `maharashtra` / `Gadchiroli - Chimur`
- `maharashtra` / `Hatkanangale`
- `maharashtra` / `Mumbai North Central`
- `maharashtra` / `Mumbai North East`
- `maharashtra` / `Mumbai North West`
- `maharashtra` / `Mumbai South`
- `maharashtra` / `Mumbai South Central`
- `maharashtra` / `Ratnagiri- Sindhudurg`
- `maharashtra` / `Yavatmal- Washim`
- `telangana` / `Mahbubnagar`
- `uttar-pradesh` / `Baharaich`
- `uttar-pradesh` / `Lucknow`
- `uttarakhand` / `Haridwar`
- `west-bengal` / `Bardhaman-Durgapur`
- `west-bengal` / `Kolkata Dakshin`
- `west-bengal` / `Kolkata Uttar`

