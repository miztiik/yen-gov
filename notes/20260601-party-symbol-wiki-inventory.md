# Party symbol inventory: Wikipedia scrape (PR-SYM-4a-redo)

Date: 2026-06-01. Source: <https://en.wikipedia.org/wiki/List_of_political_parties_in_India>.

Supersedes PR #543 (hand-drawn) and PR #545 (party-logo bytes mislabelled as election-symbol).
Per plan TODO/20260527-party-symbol-assets-plan.md: filenames use ECI symbol-noun (lotus, hand, elephant, broom...), kebab-case, English. Format = whatever Commons serves (SVG/PNG/JPG/WEBP).

## Pipeline

1. Fetch List_of_political_parties_in_India HTML.
2. Parse National + State tables; per row, identify party (cell[1]) + symbol image (first non-flag File:* reference).
3. Resolve Commons API for direct upload URL + mime.
4. Download bytes. SVG -> svgo normalise + strip xml:space/inkscape/sodipodi residue. PNG/JPG/WEBP -> pass-through.
5. Slug derived from filename: strip `Indian_Election_Symbol_` / `<X>_electoral_symbol` prefix, kebab-case, lowercase.
6. Slug collisions (same symbol-noun, different parties) suffix with party name.

## Inventory

| Tier | Party | Slug | Format | SHA-256 | Bytes | Commons source |
|---|---|---|---|---|---|---|
| National | Aam Aadmi Party | `broom` | PNG | `364b28bcf78e...` | 119750 | [AAP_Symbol.png](https://commons.wikimedia.org/wiki/File:AAP_Symbol.png) |
| National | Bahujan Samaj Party | `elephant` | SVG | `317a8e83e43c...` | 21655 | [Elephant_electoral_symbol.svg](https://commons.wikimedia.org/wiki/File:Elephant_electoral_symbol.svg) |
| National | Bharatiya Janata Party | `lotus` | SVG | `e7e7ce31e316...` | 6387 | [Lotus_flower_symbol.svg](https://commons.wikimedia.org/wiki/File:Lotus_flower_symbol.svg) |
| National | Communist Party of India (Marxist) | `hammer-sickle-and-star` | PNG | `6b6c153228cc...` | 243868 | [CPI(M)_Election_symbol.png](https://commons.wikimedia.org/wiki/File:CPI(M)_Election_symbol.png) |
| National | Indian National Congress | `hand` | SVG | `544bbcf55df9...` | 9778 | [Hand_INC.svg](https://commons.wikimedia.org/wiki/File:Hand_INC.svg) |
| State | All India Trinamool Congress | `flowers-and-grass` | SVG | `03c6ba196265...` | 4673 | [All_India_Trinamool_Congress_symbol_2021.svg](https://commons.wikimedia.org/wiki/File:All_India_Trinamool_Congress_symbol_2021.svg) |
| State | Communist Party of India | `ears-of-corn-and-sickle` | SVG | `7104159eed41...` | 11310 | [CPI_symbol.svg](https://commons.wikimedia.org/wiki/File:CPI_symbol.svg) |
| State | Janata Dal (Secular) | `female-farmer` | SVG | `5b01f4ef6de6...` | 144483 | [Indian_election_symbol_female_farmer.svg](https://commons.wikimedia.org/wiki/File:Indian_election_symbol_female_farmer.svg) |
| State | Janata Dal (United) | `arrow` | SVG | `c17dc7d11d43...` | 99288 | [Indian_Election_Symbol_Arrow.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Arrow.svg) |
| State | All India Anna Dravida Munnetra Kazhagam | `two-leaves` | SVG | `6f9a9828aa02...` | 37601 | [Indian_election_symbol_two_leaves.svg](https://commons.wikimedia.org/wiki/File:Indian_election_symbol_two_leaves.svg) |
| State | Dravida Munnetra Kazhagam | `rising-sun` | SVG | `5c72af23f15e...` | 12979 | [Indian_election_symbol_rising_sun.svg](https://commons.wikimedia.org/wiki/File:Indian_election_symbol_rising_sun.svg) |
| State | Nationalist Congress Party – Sharadchandra Pawar | `man-blowing-turha` | PNG | `e3d58da8155a...` | 220914 | [Indian_Election_Symbol_Man_Blowing_Turha.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Man_Blowing_Turha.png) |
| State | Rashtriya Janata Dal | `hurricane-lamp` | PNG | `56b95750ee11...` | 5515 | [Indian_Election_Symbol_Hurricane_Lamp.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Hurricane_Lamp.png) |
| State | Telugu Desam Party | `cycle` | PNG | `d91a897d738b...` | 13493 | [Indian_Election_Symbol_Cycle.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Cycle.png) |
| State | YSR Congress Party | `ceiling-fan` | SVG | `7ac7fd43afae...` | 2634 | [Indian_Election_Symbol_Ceiling_Fan.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Ceiling_Fan.svg) |
| State | All India Forward Bloc | `lion` | SVG | `6339dd459ece...` | 32692 | [Indian_Election_Symbol_Lion.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Lion.svg) |
| State | All India Majlis-e-Ittehadul Muslimeen | `kite` | SVG | `1471ac513070...` | 4444 | [Indian_Election_Symbol_Kite.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Kite.svg) |
| State | All India N.R. Congress | `all-india-nr-congress` | PNG | `a27a057bb050...` | 11428 | [All_India_N.R._Congress.png](https://commons.wikimedia.org/wiki/File:All_India_N.R._Congress.png) |
| State | All India United Democratic Front | `lock-and-key` | WEBP | `0950a75e1725...` | 23330 | [AIUDF_logo.webp](https://commons.wikimedia.org/wiki/File:AIUDF_logo.webp) |
| State | All Jharkhand Students Union | `banana` | SVG | `8b3be432e673...` | 5941 | [Indian_Election_Symbol_Banana.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Banana.svg) |
| State | Apna Dal (Soneylal) | `cup-and-saucer` | JPG | `43d89bd7d81a...` | 64017 | [Indian_Election_Symbol_Cup_and_Saucer.jpg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Cup_and_Saucer.jpg) |
| State | Asom Gana Parishad | `elephant-agp` | PNG | `bc69702c58a2...` | 159476 | [Indian_Election_Symbol_Elephant.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Elephant.png) |
| State | Bharat Rashtra Samithi | `car` | PNG | `f0669be72fa9...` | 6700 | [Indian_Election_Symbol_Car.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Car.png) |
| State | Biju Janata Dal | `conch` | SVG | `39077e1acd9a...` | 7041 | [Indian_Election_Symbol_Conch.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Conch.svg) |
| State | Desiya Murpokku Dravida Kazhagam | `nagara` | SVG | `70650817e9c6...` | 126733 | [Indian_Election_Symbol_Nagara.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Nagara.svg) |
| State | Goa Forward Party | `coconut` | SVG | `9b47d03825be...` | 28877 | [Indian_election_symbol_Coconut.svg](https://commons.wikimedia.org/wiki/File:Indian_election_symbol_Coconut.svg) |
| State | Indian National Lok Dal | `spectacles` | SVG | `f0dc7ee8f1ed...` | 3013 | [INLD1.svg](https://commons.wikimedia.org/wiki/File:INLD1.svg) |
| State | Indian Union Muslim League | `ladder` | SVG | `ea30c7d402a0...` | 9936 | [Indian_Election_Symbol_Lader.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Lader.svg) |
| State | Jammu & Kashmir National Conference | `plough` | PNG | `56dc5622eb8f...` | 22184 | [Indian_Election_Symbol_Plough.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Plough.png) |
| State | Jammu and Kashmir National Panthers Party | `cycle` | PNG | `d91a897d738b...` | 13493 | [Indian_Election_Symbol_Cycle.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Cycle.png) |
| State | Jammu and Kashmir Peoples Democratic Party | `ink-pot-and-pen` | PNG | `4e4d1752bb1c...` | 9134 | [Indian_Election_Symbol_Ink_Pot_and_Pen.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Ink_Pot_and_Pen.png) |
| State | Janasena Party | `glass-tumbler` | SVG | `2457d35cb263...` | 17342 | [Indian_election_symbol_glass_tumbler.svg](https://commons.wikimedia.org/wiki/File:Indian_election_symbol_glass_tumbler.svg) |
| State | Jannayak Janta Party | `key` | SVG | `c44f3c093292...` | 3911 | [Indian_election_symbol_Key.svg](https://commons.wikimedia.org/wiki/File:Indian_election_symbol_Key.svg) |
| State | Janta Congress Chhattisgarh | `farmer-ploughing-within-square` | JPG | `b5980e1a692e...` | 68282 | [Indian_Election_Symbol_Farmer_Ploughing_(within_Square).jpg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Farmer_Ploughing_(within_Square).jpg) |
| State | Jharkhand Mukti Morcha | `bow-and-arrow` | SVG | `b96f87239dc2...` | 22461 | [Indian_Election_Symbol_Bow_And_Arrow.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Bow_And_Arrow.svg) |
| State | Kerala Congress | `auto-rickshaw` | SVG | `38a9f5200acc...` | 18321 | [Auto_Rickshaw_Election_Symbol.svg](https://commons.wikimedia.org/wiki/File:Auto_Rickshaw_Election_Symbol.svg) |
| State | Kerala Congress (M) | `two-leaves` | SVG | `6f9a9828aa02...` | 37601 | [Indian_election_symbol_two_leaves.svg](https://commons.wikimedia.org/wiki/File:Indian_election_symbol_two_leaves.svg) |
| State | Lok Janshakti Party (Ram Vilas) | `helicopter` | JPG | `c5088cfa1ec9...` | 70124 | [Indian_Election_Symbol_Helicopter.jpg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Helicopter.jpg) |
| State | Maharashtra Navnirman Sena | `railway-engine` | PNG | `885bb2837784...` | 124348 | [Mns-symbol-railway-engine.png](https://commons.wikimedia.org/wiki/File:Mns-symbol-railway-engine.png) |
| State | Maharashtrawadi Gomantak Party | `lion` | SVG | `6339dd459ece...` | 32692 | [Indian_Election_Symbol_Lion.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Lion.svg) |
| State | Naam Tamilar Katchi | `farmer-carrying-plough` | JPG | `9a69d78ecfeb...` | 177126 | [NTK-EC-Symbol.jpg](https://commons.wikimedia.org/wiki/File:NTK-EC-Symbol.jpg) |
| State | Mizo National Front | `star` | SVG | `b6a24eef8cc9...` | 1302 | [Election_Symbol_Star.svg](https://commons.wikimedia.org/wiki/File:Election_Symbol_Star.svg) |
| State | Rashtriya Loktantrik Party | `bottle` | PNG | `9d22de5a0c38...` | 98138 | [Logo_Rashtriya_Loktantrik_party.png](https://commons.wikimedia.org/wiki/File:Logo_Rashtriya_Loktantrik_party.png) |
| State | Revolutionary Goans Party | `football` | JPG | `ec62c747b3aa...` | 184193 | [Indian_Election_Symbol_football.jpg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_football.jpg) |
| State | Revolutionary Socialist Party (India) | `spade-and-stoker` | PNG | `a09990234e64...` | 12471 | [Indian_Election_Symbol_Spade_and_Stoker.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Spade_and_Stoker.png) |
| State | Samajwadi Party | `cycle` | PNG | `d91a897d738b...` | 13493 | [Indian_Election_Symbol_Cycle.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Cycle.png) |
| State | Shiromani Akali Dal | `scales` | SVG | `f5d8fee9245c...` | 3761 | [Shiromani_Akali_Dal_symbol.svg](https://commons.wikimedia.org/wiki/File:Shiromani_Akali_Dal_symbol.svg) |
| State | Sikkim Democratic Front | `umbrella` | PNG | `a8bc47f29cd7...` | 13440 | [Indian_Election_Symbol_Umberlla.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Umberlla.png) |
| State | Sikkim Krantikari Morcha | `table-lamp` | PNG | `d98947a33fd0...` | 17681 | [Symbol_SKM.png](https://commons.wikimedia.org/wiki/File:Symbol_SKM.png) |
| State | Shiv Sena (2022–present) | `bow-and-arrow` | SVG | `b96f87239dc2...` | 22461 | [Indian_Election_Symbol_Bow_And_Arrow.svg](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Bow_And_Arrow.svg) |
| State | Shiv Sena (UBT) | `flaming-torch` | PNG | `a6faa72fff58...` | 5395 | [Indian_Election_Symbol_Flaming_Torch.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Flaming_Torch.png) |
| State | Tipra Motha Party | `tipra-logo` | JPG | `a368b9a6bcea...` | 6119 | [Tipra_Logo.jpg](https://commons.wikimedia.org/wiki/File:Tipra_Logo.jpg) |
| State | United Democratic Party (Meghalaya) | `drums` | PNG | `6fcaf1580d58...` | 50463 | [Indian_Election_Symbol_Drums.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Drums.png) |
| State | Voice of the People Party (Meghalaya) | `winnower` | PNG | `5e1ec3535875...` | 187032 | [Winnower_Symbol.png](https://commons.wikimedia.org/wiki/File:Winnower_Symbol.png) |
| State | Zoram Nationalist Party | `sun-without-rays` | PNG | `08e1f30b476d...` | 21694 | [Indian_Election_Symbol_Sun_without_Rays.png](https://commons.wikimedia.org/wiki/File:Indian_Election_Symbol_Sun_without_Rays.png) |

## Failed / missing: 0
None.

## Format breakdown
- `.jpg`: 6
- `.png`: 21
- `.svg`: 27
- `.webp`: 1

## Notes for PR-SYM-4b (parties.json population)

- `asset_path` is `party-symbols/<slug>.<ext>` (relative to `frontend/public/`).
- `asset_source_kind`: `"commons"` for all rows in this batch.
- `license_label`: verify per Commons file page; most ECI election-symbol SVGs are PD-shape; party-uploaded marks may be CC-BY-SA-4.0.
- `mime_type` will need a schema bump (v2.2 -> v2.3) since current schema implicitly assumes SVG.
- `symbol_status`: `"verified"` for files named `Indian_Election_Symbol_*` (ECI-canonical); others (e.g. `Tipra_Logo.jpg`) get `"party_supplied"`.
- `asset_sha256`: re-verify from committed bytes after LF normalisation via `Get-FileHash <file> -Algorithm SHA256`.
- Shared symbols (e.g. `two-leaves` shared by AIADMK + Kerala Congress(M); `cycle` shared by TDP + JKNPP + Samajwadi) reuse the same file path; multiple `parties.json` rows reference the same `asset_path`.
## Slug rename pass (post-merge fixup)

Renames applied to align filenames with ECI-symbol-noun (per plan-doc):

- `aap` → `broom`: AAP ECI symbol = broom (jhadu)
- `hand-inc` → `hand`: INC ECI symbol = hand; INC is sole holder
- `cpim` → `hammer-sickle-and-star`: CPI(M) ECI symbol = Hammer, Sickle and Star
- `cpi` → `ears-of-corn-and-sickle`: CPI ECI symbol = Ears of Corn and Sickle
- `aiudf-logo` → `lock-and-key`: AIUDF ECI symbol = Lock and Key
- `inld1` → `spectacles`: INLD ECI symbol = Spectacles
- `shiromani-akali-dal` → `scales`: SAD ECI symbol = Scales
- `mns-symbol-railway-engine` → `railway-engine`: MNS ECI symbol = Railway Engine
- `lotus-flower` → `lotus`: BJP ECI symbol = Lotus (drop redundant -flower suffix)
- `symbol-skm` → `table-lamp`: SKM ECI symbol = Table Lamp
- `ntk-ec-symbol` → `farmer-carrying-plough`: NTK ECI symbol (allotted May 2025) = Farmer Carrying Plough
- `all-india-trinamool-congress-symbol-2021` → `flowers-and-grass`: TMC ECI symbol = Flowers and Grass
- `logo-rashtriya-loktantrik-party` → `bottle`: RLP ECI symbol = Bottle
- `elephant-asom-gana-parishad` → `elephant-agp`: Shorten party suffix; ECI noun unchanged
- `lader` → `ladder`: Typo fix in upstream filename: Lader -> Ladder (IUML symbol)
- `umberlla` → `umbrella`: Typo fix in upstream filename

### Unresolved (party-named upstream filename, ECI symbol noun unverified)

- `all-india-nr-congress`: AINRC: party-named upload; ECI symbol noun not in filename. Manual lookup needed (probable: 'jug')
- `tipra-logo`: Tipra Motha: party-named upload; ECI symbol noun not in filename. Manual lookup needed

## Gap tracker (as of slug-rename pass)

| Metric | Count |
|---|---|
| Total parties in `datasets/taxonomy/parties.json` | 620 |
| Parties with `election_symbol` populated | 0 (PR-SYM-4b will wire 55 of them) |
| Symbol files in `frontend/public/party-symbols/` (excl placeholder) | 50 |
| Parties this batch covers (national + state, via shared symbols) | 55 |
| Estimated coverage of parties.json after PR-SYM-4b | 55 / 620 = 8.9% |
| Estimated coverage of seat-winners (per top-60 SQL in `notes/20260601-party-symbol-roster.md`) | ~50 / 60 = 83% |

### Symbol-file count per ECI tier

| Tier | Parties covered | Symbol files (shared = 1 file, N parties) |
|---|---|---|
| National | 5 (BJP/INC/BSP/CPI(M)/AAP - NPP missing) | 5 |
| State | 50 | 45 (5 shared: cycle x3, two-leaves x2, bow-and-arrow x2, lion x2, elephant x2) |
| Unrecognised | 0 (out of scope per 80/20) | 0 |

### Confirmed gaps (next iterations)

1. **NPP** (National People's Party) — wiki row parser missed it; manual add. Symbol: book.
2. **all-india-nr-congress.png** — party-named file; ECI symbol noun = jug (needs verify).
3. **tipra-logo.jpg** — party-named file; ECI symbol noun unverified.
4. **Faction splits** (SHS / NCP / LJP) — need ECI freezing-order citation for which symbol belongs to which faction in the current ECI ruling.
5. **Unrecognised parties** with material seat counts in `elections_candidacies.parquet` — to be enumerated in PR-SYM-4a-rest if user opts in.
6. **Remaining ~565 parties in parties.json** — most are registered-unrecognised RUPPs without ECI-reserved symbols; defer until they appear in seat-winner queries.

### How to fill the gaps

- For each gap above, the same pipeline (Wikipedia / Commons API → svgo / pass-through → write to `party-symbols/<eci-noun>.<ext>`) applies. Re-run the throwaway scraper from PR #550 with an extended target list, or hand-add via the same naming convention.
- For ECI symbol-noun lookup when the wiki/Commons filename doesn't give it, the canonical source is the ECI "Symbols (Reservation and Allotment) Order, 1968" + any subsequent allotment notifications.
