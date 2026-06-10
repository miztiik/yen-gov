# Wikipedia Parties Snapshot - Vintage 2026-06

**Authored**: 2026-06-11 (PR-W-3 of [TODO/20260610-electoral-data-quality-and-party-catalogue-plan.md](../../../../TODO/20260610-electoral-data-quality-and-party-catalogue-plan.md))
**Vintage**: 2026-06 (operator snapshot window; per ADR-0042 publisher edition pin)
**Consumer**: [backend/yen_gov/canonical/recon/adapters/wikipedia_parties.py](../../../../backend/yen_gov/canonical/recon/adapters/wikipedia_parties.py)
**Curator**: [tools/recon_curate_wikipedia_parties/](../../../../tools/recon_curate_wikipedia_parties)

## Why hand-authored (not live scrape)

The plan section 3 (PR-W-3 brief) allowed two source paths:
(a) operator-committed snapshot at `datasets/ephemeral/wikipedia-parties/` (preferred); or
(b) live scrape once via httpx + beautifulsoup4, snapshot committed for audit trail.

This snapshot uses path (a), aligning with:

- **CLAUDE.md "Network-fetch code is deleted" doctrine** (TODO/20260603 §0 + ADR overrides). PR-W-2 set the precedent of hand-authoring the operator-committed snapshot rather than introducing a one-off live fetch; PR-W-3 follows the same shape.
- **Reproducibility**. A live scrape against Wikipedia would be non-deterministic across runs (revision drift) and would need rate-limit handling and HTML-structure assertions. A hand-authored snapshot is the audit trail.
- **Scope realism**. The snapshot covers the ~70-100 highest-confidence parties (national + major state-recognised + Q7 split factions + Hans-catalogue lineage rows), not the ~2,700 unrecognised-registered tail. The tail is out-of-scope of PR-W-3 per the brief; the major / national cohort is what enriches the most user-visible rows in the citizen UI.

## Provenance (citation order - primary first)

1. **Wikipedia**, "List of political parties in India" — primary index page (https://en.wikipedia.org/wiki/List_of_political_parties_in_India). Used to enumerate the major-party set.
2. **Wikipedia per-party infobox** — for each row in this snapshot, the canonical EN-Wikipedia page for the party. URL recorded in the `wikipedia_url` column. Per Q1 fact-class authority, Wikipedia infobox wins on `brand_colour`, `symbol_asset` URL, `wikipedia` URL, and `name_native_script`.
3. **MyNeta party pages** (https://www.myneta.info/) — secondary cross-reference for the major Lok Sabha 2024 cohort. URLs recorded in `myneta_url` column where the party has a MyNeta page. Per Q1, MyNeta data folded ONLY if Wikipedia is silent. Per Wave 0 / Hans section 10, MyNeta is NEVER used for vote counts (Wave 0 rule).
4. **PR-W-1 + PR-W-2 verdicts** — when this snapshot's brand_colour / native_script conflicts with a value PR-W-1 (TCPD) or PR-W-2 (ECI) already wrote, the parity flags DISPUTED; the curator hand-applies per Q1 tie-break.

## CSV schema

| Column | Type | Notes |
|---|---|---|
| `party_id_or_short` | string | Either the canonical `parties.IN.<SLUG>` id (preferred for direct mapping when curator knows the slug) OR the publisher's short abbreviation. The adapter dispatches by prefix: `parties.IN.` -> direct id; otherwise short. |
| `full_name` | string | Wikipedia infobox full registered name. |
| `native_script_name` | string (nullable) | Native-script name as printed by the Wikipedia infobox (Devanagari / Tamil / Bengali / Telugu / Kannada / Malayalam / Marathi / Punjabi / Urdu / Odia / Assamese). Per Q8, Wikipedia wins on this column. UI policy filters out on citizen elections surface per PR #874 No-Hindi rule; storage is additive (Q8 verdict). |
| `brand_colour_hex` | string (nullable) | `#RRGGBB` from the Wikipedia infobox swatch. Per Q1, Wikipedia wins. |
| `symbol_asset_url` | string (nullable) | Relative `party-symbols/<file>.{svg,png,jpg,webp}` path matching an asset under `frontend/public/party-symbols/`. Populated ONLY for parties where the canonical row already carries a matching `symbol_asset` value (the parity action becomes `match` -> VERIFIED, second oracle). New symbol-asset minting is OUT of scope for PR-W-3; a dedicated asset-ingest PR handles new symbols. |
| `wikipedia_url` | string (nullable) | Canonical EN-Wikipedia page URL. Per Q1, Wikipedia wins. URL-encoded characters preserved verbatim (e.g. `%27` for apostrophes). |
| `myneta_url` | string (nullable) | Secondary citation URL on https://www.myneta.info/. Cross-reference only; never auto-applied to a canonical column. |
| `recognition_blurb` | string | Free-text snapshot description used as a hint for the curator (recognition_scope + home_states + colour + symbol). NOT a canonical column. |
| `notes` | string (nullable) | Free-text adapter / curator note (lineage, Q7 disposition, etc.). |

## Scope limit

This snapshot covers ~70 of the ~620 canonical parties.csv rows:

- **6 national** parties (BJP, INC, BSP, CPIM, CPI now state, AAP, AITC, NPP — note CPI lost national 2024, AAP+AITC gained 2024).
- **All Q7 split factions** (AIADMK + AIADMK_OPS; SHS + SS_UBT; NCP + NCP_SP).
- **TN cohort** (DMK, AIADMK, AMMK, TVK, PMK, MDMK, VCK, PT, NTK, IUML, AINRC).
- **MH cohort** (SHS, SS_UBT, NCP, NCP_SP, MNS, RPI variants, PWP).
- **WB cohort** (AITC, CPIM, INC, BJP, AIFB, RSP).
- **UP cohort** (SP, BSP, RLD, JDU, AAPP, SBSP, INC).
- **BR cohort** (RJD, JDU, LJP, LJPRV, HAM_S, INC).
- **KA cohort** (JDS, INC, BJP).
- **AP/TG cohort** (TDP, YSRCP, BRS, JSP, AIMIM, INC).
- **OR cohort** (BJD, INC, BJP).
- **PB cohort** (SAD, AAP, INC).
- **NE cohort** (NPP, NPF, NDPP, MNF, ZPM, SKM, SDF, AIUDF, AGP).
- **GA cohort** (GFP, MGP).
- **JK cohort** (JKNC, JKPDP, JKPC).
- **HR cohort** (INLD, JJP, HJC).
- **KL cohort** (IUML, KEC, KEC_M, NCP_K).
- **Historic / lineage** (JD, JNP, JP, BJS, KEC, MUL) — for the predecessor / successor chain.

The ~550 long-tail unrecognised-registered parties (single-event or single-state) are left for a future PR-W-4 / curator backlog.

## Re-snapshot policy

When a new wave of Wikipedia infobox edits matters (e.g. a 2027 ECI-symbol-reallocation or a recognition flip), replace [registered.csv](registered.csv) with the updated rows and re-run:

```
python -m yen_gov parity --source wikipedia-parties --vintage 2026-06 --report datasets/ephemeral/party-parity/wikipedia-parties/2026-06/<sha>/verdict.csv
```

The adapter is pure; no code change needed. The `2026-06` vintage pin matches the operator snapshot window; bump the vintage string (e.g. `2027-03`) when a substantive resnapshot lands so the audit trail retains the prior snapshot in git history.

## Q1 fact-class authority (recap)

Per plan section 0.3, PR-W-3's enrichment leg writes ONLY these columns:

- `brand_colour` (Wikipedia infobox swatch)
- `symbol_asset` (fill-empty-only AND only when matching an asset under `frontend/public/party-symbols/`)
- `wikipedia` (canonical EN-Wikipedia URL)
- `name_native_script` (Wikipedia infobox native-script name)

NEVER writes TCPD-owned (full_name / short / aliases / lineage / founded_year / dissolved_year — those are PR-W-1) NEVER writes ECI-owned (eci_codes / recognition_scope / home_state_codes — those are PR-W-2).

When Wikipedia disagrees with a TCPD-owned or ECI-owned value, the parity flags DISPUTED and surfaces in the verdict.csv for hand-curation; PR-W-3 does NOT override PR-W-1 / PR-W-2 facts on those fact classes. (CLAUDE.md section 10 + Hans verdict.)

## Q7 split convention (option c, signed off 2026-06-10)

PR-W-2's `hans_mints.py` already applied:

- `parties.IN.AIADMK` (EPS faction): `claims_to_parent_name=true`, home_state_codes=IN-TN|IN-PY.
- `parties.IN.AIADMK_OPS` (OPS faction): NEW row minted with predecessor=AIADMK.
- `parties.IN.SHS` (Shinde faction): `claims_to_parent_name=true`, full=Shiv Sena, recognition_scope=state.
- `parties.IN.SS_UBT` (UBT faction): pre-existing row enriched with predecessor=SHS.
- `parties.IN.NCP` (Ajit faction): `claims_to_parent_name=true`, home_state_codes=IN-MH|IN-NL.
- `parties.IN.NCP_SP` (SP faction): pre-existing row enriched with predecessor=NCP.

PR-W-3 enriches these rows ONLY on Wikipedia-owned fields (brand_colour for NCP + SHS which lacked it; symbol-asset confirmation match for SS_UBT; name_native_script for all six).
