# ECI Registered & Recognised Parties Snapshot — Vintage 2024

**Authored**: 2026-06-11 (PR-W-2 of [TODO/20260610-electoral-data-quality-and-party-catalogue-plan.md](../../../../TODO/20260610-electoral-data-quality-and-party-catalogue-plan.md))
**Vintage**: 2024 (operator snapshot window; per ADR-0042 publisher edition pin)
**Consumer**: [backend/yen_gov/canonical/recon/adapters/eci_registered.py](../../../../backend/yen_gov/canonical/recon/adapters/eci_registered.py)
**Curator**: [tools/recon_curate_eci_registered/](../../../../tools/recon_curate_eci_registered)

## Provenance (citation order — primary first)

1. **Election Commission of India**, "List of Political Parties & Symbol main Notification dated 23.04.2024" (Apr 2024 quarterly update, in force through subsequent quarterly amendments).
   - https://www.eci.gov.in/political-parties/
   - https://www.eci.gov.in/files/file/16487-notification-of-the-election-symbols-reservation-and-allotment-order-1968-as-amended-up-to-date/
2. **Wikipedia**, "List of political parties in India" (cites the same ECI notification; used as a structured tabular mirror of ECI's PDF).
   - https://en.wikipedia.org/wiki/List_of_political_parties_in_India
3. **ECI orders on Q7-relevant 2022-2024 splits**:
   - Order on AIADMK symbol (1 Apr 2022) — ECI restored "Two Leaves" symbol to AIADMK after E. Madhusudhanan succession dispute; OPS faction subsequently lost claim.
   - Order on Shiv Sena symbol (17 Feb 2023) — bow-and-arrow + name "Shiv Sena" allotted to Eknath Shinde faction; Uddhav Thackeray faction allotted "Shiv Sena (Uddhav Balasaheb Thackeray)" + flaming torch symbol.
   - Order on NCP symbol (6 Feb 2024) — clock symbol + "Nationalist Congress Party" allotted to Ajit Pawar faction; Sharad Pawar faction allotted "Nationalist Congress Party - Sharadchandra Pawar" + man-blowing-turha symbol.

## CSV schema

| Column | Type | Notes |
|---|---|---|
| `eci_code` | string (nullable) | ECI numeric or string registration code where published; empty when ECI publishes by symbol-allotment only (common for state-recognised parties). |
| `short` | string | ECI-published abbreviation (canonical short form). |
| `full` | string | ECI-published full registered name. |
| `recognition_scope` | enum | `national` / `state` / `unrecognised_registered`. Per Q1 fact-class authority table (plan section 0.3), ECI wins on this column. |
| `home_state_codes` | string (pipe-list) | Pipe-list of ISO 3166-2 IN-XX codes where the party holds state-recognised status (empty for national). |
| `gained_year` | integer | Year ECI granted the CURRENT recognition_scope (dates the 6 known 2024 flips cited in PR-W-2 brief section 5). |
| `notes` | string (nullable) | Disambiguation hint (Q7 split context, etc.). |

## Scope limit

This snapshot covers ALL national + the well-known state-recognised parties (the ~50 parties cited in Hans 33-case catalogue Wave 0 + the active state cohorts for the 2024-2026 election cycle). It does NOT include the ~2,700+ unrecognised_registered tail; that tier lives in the ECI's quarterly amendment PDFs and is covered by PR-W-3's Wikipedia per-party-infobox scrape lane.

## Re-snapshot policy

When a new ECI notification lands, replace [registered.csv](registered.csv) verbatim and re-run:

```sh
python -m yen_gov parity --source eci-registered --vintage 2024 --report datasets/ephemeral/party-parity/eci-registered/2024/<sha>/verdict.csv
```

The adapter is pure; no code change needed.

## Q7 split convention (option c, signed off 2026-06-10)

For each of the three 2022-2024 ECI symbol-rulings, the snapshot carries TWO rows:

- **ECI-favoured side keeps the parent canonical id** (e.g. `parties.IN.AIADMK`, `parties.IN.SHS`, `parties.IN.NCP`). The curator sets `claims_to_parent_name=true` on the canonical row.
- **Breakaway gets a new id** (e.g. `parties.IN.AIADMK_OPS`, `parties.IN.SHS_UBT`, `parties.IN.NCP_SP`). The curator mints the row with `predecessor_party_ids=parties.IN.<parent>`.

Faction abbreviations in this snapshot follow the citizen-facing convention (AIADMK_OPS, SHS_UBT, NCPSP — matching the canonical `parties.IN.<slug>` after slug normalisation).
