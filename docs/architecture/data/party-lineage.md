# Party lineage catalogue

**Last Updated**: 2026-06-11

The lineage graph for Indian political parties as encoded in `datasets/data/entities/parties.csv` via `predecessor_party_ids[]` + `successor_party_ids[]` + `name_history[]`. This doc is a curator's quick-reference for the major lineage chains; the authoritative data is the CSV itself.

The catalogue was lifted from the Wave 0 / Hans 33-case identity catalogue produced for the [electoral-data quality + party-catalogue plan](../../archive/plans/20260610-electoral-data-quality-and-party-catalogue-plan.md) (closed 2026-06-11). Hans's analysis enumerated 33 distinct lineage events from 1962 to 2024 across the splits / mergers / rebrandings that an Indian electoral chart spanning multiple cycles MUST account for.

## See also

- [../../concepts/party-identity.md](../../concepts/party-identity.md) - the identity model and resolver rules; lineage is the data layer that backs the `predecessor_party_ids` / `successor_party_ids` columns documented there.
- [canonical-store.md](canonical-store.md) - section 5 (sources schema); every lineage row carries `source_id` provenance.
- [../backend/validator.md](../backend/validator.md) - section "Tier C - per-source parity"; the parity CLI surfaces lineage divergences as DISPUTED verdicts.
- [../../concepts/data-provenance.md](../../concepts/data-provenance.md) - ADR-0032; lineage facts are citation-anchored, never editorial.
- [../../concepts/owid-alignment.md](../../concepts/owid-alignment.md) - OWID's precedent on entity-history modelling.
- [CLAUDE.md](../../../CLAUDE.md) - Holy Law #5 (structural fixes only); Holy Law #9 (provenance mandatory).

## 1. Vocabulary

A lineage event is one of five shapes:

- **Founding.** New party comes into existence with no predecessor. `predecessor_party_ids = []`. Example: BJS 1951.
- **Merger.** Two or more parent rows fold into a new child. The child carries `predecessor_party_ids = [parent_a, parent_b, ...]`. Each parent carries `successor_party_ids = [child]`. The parents typically receive a `dissolved_year` matching the child's `founded_year`. Example: BJS + 5 other parties -> JNP 1977.
- **Split / breakaway.** One parent spawns one or more breakaway children. The parent does NOT receive `dissolved_year` (it continues to exist). The child carries `predecessor_party_ids = [parent]`; the parent carries `successor_party_ids = [child]`. Example: AIADMK -> AMMK 2018.
- **Rename / rebrand.** Same legal entity, new public name. Identity is preserved (`party_id` does NOT change). The rename is recorded in the `name_history[]` JSON blob on the same row. Example: TRS -> BRS 2022.
- **ECI-symbol award (post-split).** ECI rules which faction of a contested split retains the original name + registration symbol. The favoured side keeps the parent `party_id`; the breakaway gets a new id. See [../../concepts/party-identity.md](../../concepts/party-identity.md) §6 (the Q7 option-c hybrid model).

Two derived rules:

- **Splits mint NEW ids; the parent is NEVER retired.** Pre-split vote rows keep the parent's id forever. This is the Rosling rule applied to party identity: a methodology break (the split) does not retroactively change historical observations; a `methodology_breaks.parquet` row carries the citizen-facing annotation.
- **Pre-1980 votes are NEVER backtagged.** A vote cast for BJS in 1971 carries `party_id = parties.IN.BJS` (NOT `parties.IN.BJP`) forever, even though the BJP descended from BJS via the 1977-1980 JNP interlude. Citizens reading a chart of "BJP vote share over time" MUST see a discontinuity at 1980; backtagging the pre-1980 BJS votes onto BJP would be a citizen-trust failure. The same rule applies to JD-family chains: a 1977 JNP vote is `parties.IN.JNP`, never split-attributed to JD(U) / RJD / BJD / etc. that emerged from the post-1989 JD splits.

## 2. Anchor chains

The five chains that account for most multi-cycle electoral charts:

### 2.1 BJS -> JNP -> BJP (Right-wing Hindu nationalist lineage)

```
1951  parties.IN.BJS (Bharatiya Jana Sangh) founded
1977  parties.IN.BJS merges into parties.IN.JNP (Janata Party) along with SSP, BLD, Congress (O), and the Socialist Party
1980  parties.IN.BJP (Bharatiya Janata Party) founded; carries former BJS faction; predecessor_party_ids = [parties.IN.JNP]
```

The chain is `BJS -> JNP -> BJP` via two events: (a) BJS merger into JNP in 1977 (post-Emergency anti-Congress coalition), (b) BJS faction's exit from JNP in 1980 forming BJP. Pre-1980 BJS votes stay tagged to `parties.IN.BJS`. JNP's own 1977-1980 vote belongs to `parties.IN.JNP` and is NOT split-attributed to any successor (the merger was electorally coherent for one cycle and then dissolved).

### 2.2 JNP -> JD -> {JD(U), JD(S), RJD, BJD, LJP, SP} (Janata Dal family)

```
1977  parties.IN.JNP (Janata Party) formed (see 2.1)
1988  parties.IN.JD (Janata Dal) formed as merger of JNP factions + Lok Dal + Congress (S) and others
1997  parties.IN.JDU (Janata Dal (United)) splits from JD
1999  parties.IN.JDS (Janata Dal (Secular)) splits from JD (Karnataka-focused, H.D. Deve Gowda)
1997  parties.IN.RJD (Rashtriya Janata Dal) splits from JD (Bihar-focused, Lalu Prasad Yadav)
1997  parties.IN.BJD (Biju Janata Dal) splits from JD (Odisha-focused, Naveen Patnaik)
2000  parties.IN.LJP (Lok Janshakti Party) splits from JD (Bihar, Ram Vilas Paswan)
1992  parties.IN.SP (Samajwadi Party) splits from JD (Uttar Pradesh, Mulayam Singh Yadav)
```

The JD parent (`parties.IN.JD`) is the source of all major regional Hindi-belt + Karnataka + Odisha parties. Pre-1988 votes belong upstream (JNP / Lok Dal); 1988-1997 votes belong to JD; post-split votes belong to the respective successor. The JD parent row continues to exist in `parties.csv` (no `dissolved_year`) because the parent's late-stage votes still carry `parties.IN.JD`.

### 2.3 Indian National Congress chains

The INC itself is single-rooted (1885-present, opaque slug `parties.IN.INC`) but spawns several splinters relevant to electoral data since 1962:

```
1969  parties.IN.INC(O) Congress (Organisation) splits from INC (Indira-vs-Syndicate)
1978  parties.IN.INC(I) Congress (Indira) splits from INC, but this is the dominant faction; ECI later restores parties.IN.INC continuity to this branch
1999  parties.IN.NCP (Nationalist Congress Party) splits from INC (Sharad Pawar)
2011  parties.IN.AITC (All India Trinamool Congress) splits from INC in 1998 actually (Mamata Banerjee); the alias 'TMC' is registered on the AITC row
```

The INC <-> INC(O) <-> INC(I) chain is a historical complication: the 1978 INC(I) faction was retroactively absorbed back into `parties.IN.INC` by ECI ruling; the parent `parties.IN.INC` therefore carries continuous votes from 1962 onward, with the brief INC(O) breakaway holding its own opaque slug for the 1969-1977 cycle.

### 2.4 AIADMK family (Dravidian movement, Tamil Nadu)

```
1949  parties.IN.DK (Dravidar Kazhagam) founded (E.V. Ramasamy / Periyar)
1949  parties.IN.DMK (Dravida Munnetra Kazhagam) splits from DK (C.N. Annadurai)
1972  parties.IN.AIADMK (All India Anna Dravida Munnetra Kazhagam) splits from DMK (M.G. Ramachandran)
2018  parties.IN.AMMK (Amma Makkal Munnetra Kazhagam) splits from AIADMK (T.T.V. Dhinakaran / Sasikala wing)
2022  parties.IN.AIADMK_OPS (AIADMK O. Panneerselvam faction) splits from AIADMK
2024  parties.IN.AIADMK continues as ECI-favoured (E. Palaniswami / EPS faction); claims_to_parent_name = true
2024  parties.IN.TVK (Tamilaga Vettri Kazhagam) founded (Vijay; Feb 2024); no DMK/AIADMK lineage despite Dravidian framing
```

The 2022 OPS-EPS factional war is the second split (after the 2018 AMMK breakaway). ECI's Feb 2024 ruling awarded the original name + symbol to the EPS faction; the OPS faction gets `parties.IN.AIADMK_OPS`. AMMK (Sasikala wing, 2018) is a SEPARATE breakaway from the 2022 OPS split and carries its own opaque slug. See [../../concepts/party-identity.md](../../concepts/party-identity.md) §6 for the citizen-UI break-annotation contract.

### 2.5 Shiv Sena + NCP 2022-2024 splits (Maharashtra)

```
1966  parties.IN.SHS (Shiv Sena) founded (Bal Thackeray)
2022  parties.IN.SHS_UBT (Shiv Sena Uddhav Balasaheb Thackeray) splits from SHS
2023  parties.IN.SHS continues as ECI-favoured (Eknath Shinde faction); claims_to_parent_name = true (Feb 2023 ECI ruling)

1999  parties.IN.NCP (Nationalist Congress Party) splits from INC (Sharad Pawar)
2023  parties.IN.NCP_SP (Nationalist Congress Party - Sharadchandra Pawar) splits from NCP
2024  parties.IN.NCP continues as ECI-favoured (Ajit Pawar faction); claims_to_parent_name = true (Feb 2024 ECI ruling)
```

Both 2022-2024 splits follow the same Q7 option-c hybrid model as AIADMK. The ECI-favoured side keeps the parent id + carries `claims_to_parent_name = true`; the breakaway gets a new opaque slug. Citizen UI MUST annotate the break on the breakaway's first appearance; the continuous side renders without annotation. See [../../concepts/party-identity.md](../../concepts/party-identity.md) §6.

## 3. Other significant lineage events

The 33-case catalogue also covers these less-frequently-traversed chains. A full enumeration with `source_id` provenance lives on the rows of `datasets/data/entities/parties.csv` itself; this section names the chains so curators know where to look.

- **AIFB(S) -> AIFB.** All India Forward Bloc (Subhasist) merged back into the parent AIFB. `predecessor_party_ids = ['parties.IN.AIFB']` on the splinter row.
- **TDP family.** Telugu Desam Party (TDP, 1982, N.T. Rama Rao) -> no major splits since founding; the YSR Congress Party (parties.IN.YSRCP, 2011) is independent of TDP (Y.S. Jagan Mohan Reddy, a 2011 INC breakaway, not a TDP breakaway).
- **TRS -> BRS rebrand (2022).** Telangana Rashtra Samithi renamed to Bharat Rashtra Samithi without legal-entity change. SAME `party_id` (`parties.IN.BRS` post-rename), with the previous name "TRS" preserved in the `name_history[]` blob on that row. The 2014-2022 vote rows still display "TRS" via the historical name segment; the post-2022 rows display "BRS". No `predecessor_party_ids` needed because no entity change occurred.
- **CPI / CPI(M) / CPI(ML).** Three distinct opaque slugs: parties.IN.CPI (1925, original), parties.IN.CPM (1964 split from CPI on Sino-Soviet alignment), parties.IN.CPIML (1969 Naxalite breakaway from CPM; later split into multiple factions). Each carries the others in `predecessor_party_ids` where applicable.
- **AAP (founding only).** Aam Aadmi Party founded 2012 as outgrowth of India Against Corruption movement; no party predecessor (the movement was not an electoral entity). `predecessor_party_ids = []`. National recognition gained 2024 (ECI ruling), reflected in `recognition_scope = "national"` on the row.
- **AGP family (Assam).** Asom Gana Parishad (1985) descended from the Assam Movement (similar to AAP - not an electoral predecessor). The 2005 split into AGP and AGP(P) is captured as parties.IN.AGP + parties.IN.AGPP with appropriate predecessor links.
- **PMK, MDMK (Tamil Nadu Dravidian satellites).** Pattali Makkal Katchi (founded 1989, Dr. S. Ramadoss) and Marumalarchi Dravida Munnetra Kazhagam (1994, V. Gopalswamy / Vaiko, splinter from DMK) are independent slugs; MDMK carries `predecessor_party_ids = ['parties.IN.DMK']`.

## 4. The "no backtag" rule in practice

The hardest curator decision is what to do when a multi-decade chart spans a lineage event. Hans's verdict (Wave 0 / section 10, ratified by user 2026-06-10):

- **Pre-event votes stay on the pre-event id forever.** A 1971 BJS vote is `parties.IN.BJS`. A 1985 JD vote is `parties.IN.JD`. A 2019 AIADMK vote is `parties.IN.AIADMK` (which, post-2024, points to the EPS faction's continuous id).
- **Citizen UI carries a methodology-break annotation across the event.** When a chart of "BJP vote share" or "BJP seats" spans pre-1980 years, the renderer MUST surface the BJS->JNP->BJP transition as a visible break, NOT silently sum BJS + BJP totals.
- **Auto-merge is BANNED.** No tool, no script, no curator note may auto-rewrite historical `party_id` values when a lineage event is added to the catalogue. Lineage is documentation, not retroactive normalisation.

This is the Rosling rule applied to party identity: the methodology break (the split) is a visible structural fact in the citizen-facing chart, not a hidden inference at query time. The chart MAY offer a "Show combined" toggle that aggregates parent + child via the `predecessor_party_ids` walk, but the default render preserves the break.

## 5. How lineage is enriched

New lineage rows enter `parties.csv` via the parity-CLI VERIFIED loop (see [../backend/validator.md](../backend/validator.md) section "Tier C - per-source parity"). The two primary external sources for lineage are:

1. **TCPD-PoliticalPartiesIndia_1962_2021** (already on disk under `datasets/ephemeral/`). Primary authority on `full_name`, `short`, `aliases`, founded/dissolved years, and `predecessor_party_ids` chains per Q1 fact-class table (electoral-quality plan section 0.3).
2. **Wikipedia per-party infobox + List of political parties in India**. Cross-check on founded year; primary source for native-script names and Wikipedia URL.

The parity workflow is: a curator runs `python -m yen_gov parity --source tcpd-parties --vintage 2021 --report <path>`, the CLI emits a verdict.csv naming the proposed mint / enrich / alias-add action per row; the curator applies VERIFIED rows directly to `parties.csv` (CSV column edits); DISPUTED rows stay in the verdict.csv ledger as a permanent audit trail. Auto-correct is BANNED; every lineage row landed via the parity loop carries a `source_id` FK to a row in `datasets/data/entities/source.csv`.
