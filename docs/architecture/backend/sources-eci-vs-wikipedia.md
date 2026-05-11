# Why ECI is the canonical source for the AC catalogue (not Wikipedia)

**Last updated**: 2026-05-11
**Audience**: contributors adding new states or wondering why
`tools/bootstrap_constituencies_from_results.py` exists alongside
`python -m yen_gov reference`.

## TL;DR

When ECI election results have been ingested for a state, **bootstrap the
state's `constituencies.json` from those result files** — not from
Wikipedia. ECI's own per-AC result files are the authoritative source
for `eci_no`, `constituency_name`, and `reservation`. Wikipedia is only
needed for states where we have no ingested results (genuinely new
states the pipeline has never touched).

| Source | What it gives us | Provenance | Stability |
|---|---|---|---|
| **ECI Statistical Report Section 10** (per-AC `result.<n>.json` we already ingest) | `eci_no`, `constituency_name` (with `(SC)`/`(ST)` suffix), candidate-level results | Direct — every record carries the original ECI XLSX URL in `sources[]` | Frozen — election results don't change after the report is published |
| Wikipedia "List of constituencies of the X Legislative Assembly" | Same fields, plus often a district mapping | Indirect — Wikipedia editors may transcribe ECI inconsistently | Drifts — anyone can edit; column headings and table shapes vary by state |
| ECI Delimitation Order PDFs | Authoritative AC↔PC↔district hierarchy | Direct (PDF, hard to parse) | Frozen until the next Delimitation (next due ~2026 post-census) |
| LGD (Local Government Directory) | Authoritative district codes | Direct (HTML/REST) | Drifts — districts are split/renamed routinely |

## How we got here (the lesson)

The original `python -m yen_gov reference <state>` command, written when
yen-gov only knew Tamil Nadu and Kerala, scrapes Wikipedia for AC names
and reservation. That was the only freely available machine-readable
list at the time — the ECI Statistical Reports were not yet ingested.

After Phase 6 / N2 (commit `29da524`, 2026-05-11) we ingested ECI
Statistical Reports for **14 states/UTs** covering 1,846 assembly
constituencies. Every per-AC result file
(`datasets/elections/<event>/<state>/results/<eci_no>.json`) carries:

- `eci_no` — the integer constituency number
- `constituency_name` — e.g. `"Palakonda (ST)"` or `"Yerragondapalem (SC) (SC)"`
  (the duplicated `(SC)` is an upstream ECI artefact in the 2024 reports;
  the bootstrapper's regex strips both)
- `sources[]` — the ECI Statistical Report XLSX URL the row was scraped from

**That is the canonical authoring source for `constituencies.json`.**
Wikipedia adds nothing the ECI files don't already have, *and* introduces
two failure modes:

1. **State-by-state table-shape drift.** "List of districts of Andhra
   Pradesh" uses different column headings than "List of districts of
   Bihar". Maintaining a Wikipedia parser per state is whack-a-mole; we
   hit this in this very session when extending `_ECI_TO_WIKI_STATE` to
   9 more states broke immediately on the very first state (`S01`).
2. **Editor drift.** Wikipedia content can change at any moment.
   ECI Statistical Reports are immutable once published.

## The current rule

1. **Have ingested election results?** Bootstrap from disk:
   ```
   python tools/bootstrap_constituencies_from_results.py <STATE_CODE>
   # or for all states with data_status=complete in election-events.json:
   python tools/bootstrap_constituencies_from_results.py --all
   ```
   The output is `status: "provisional"` (per
   [constituency.schema.json](../../datasets/schemas/constituency.schema.json))
   because it lacks `district_id` and `pc_id`. That's by design — see
   "What `provisional` means" below. The bootstrapper refuses to
   overwrite an existing file.

2. **Don't have ingested results?** Two valid paths:
   - **Preferred**: ingest the most recent ECI Statistical Report for that
     state (this is what the rest of the pipeline does), then bootstrap.
     Election results are frozen-in-stone after the SR is published, so
     the data is one-shot work that doesn't go stale.
   - **Fallback**: hand-author from the ECI Delimitation Order PDF. Use
     `status: "provisional"` until district/PC mapping is added.

3. **Wikipedia path** (`python -m yen_gov reference <state>`) is kept
   alive only for the existing TN/KL files we authored before the ECI
   ingest path matured. Do not extend `_ECI_TO_WIKI_STATE` for new
   states — bootstrap from results instead. The Wikipedia pipeline will
   be retired or repurposed in a future cleanup once districts.json has
   a non-Wikipedia path (LGD codes, see ADR-0015).

## What `provisional` means

`constituency.schema.json` defines two lifecycle tiers (added in v4.0):

- `status: "provisional"` — only `eci_no`, `name`, `reservation` required
  per item. Suitable for bootstrapping from any single source. The UI
  renders the AC directory and constituency pages without the by-district
  grouping.
- `status: "complete"` — additionally requires `district_id` and `pc_id`
  per item, cross-checked against an ECI Delimitation Order or a verified
  LGD/Wikipedia mapping. The UI then groups ACs by district on the
  StateOverview page.

The five originally hand-authored / Wikipedia-scraped files (S03, S11,
S22, S25, U07) are `provisional` too — district mappings exist for them
in `districts.json` but the AC `district_id` is a Wikipedia slug, not an
LGD code. Promoting them to `complete` is gated on the LGD migration
([ADR-0015](architecture/decisions/0015-data-model-rules.md) districts);
no immediate work needed.

## Coverage as of 2026-05-11

After running `python tools/bootstrap_constituencies_from_results.py --all`:

| State / UT | ECI code | ACs | Source |
|---|---|---:|---|
| Andhra Pradesh | S01 | 175 | ECI bootstrap |
| Arunachal Pradesh | S02 | 50 | ECI bootstrap |
| Assam | S03 | 126 | Wikipedia (legacy) |
| Haryana | S07 | 90 | ECI bootstrap |
| Kerala | S11 | 140 | Wikipedia (legacy) |
| Maharashtra | S13 | 288 | ECI bootstrap |
| Odisha | S18 | 147 | ECI bootstrap |
| Sikkim | S21 | 32 | ECI bootstrap |
| Tamil Nadu | S22 | 234 | Wikipedia (legacy) |
| West Bengal | S25 | 293 | Wikipedia (legacy) |
| Jharkhand | S27 | 81 | ECI bootstrap |
| NCT of Delhi | U05 | 70 | ECI bootstrap |
| Puducherry | U07 | 30 | Wikipedia (legacy) |
| Jammu and Kashmir | U08 | 90 | ECI bootstrap |

**Total: 14 of 36 states/UTs.** The other 22 (Bihar pending; UP, MP,
Karnataka, Gujarat, Rajasthan, Punjab, Telangana, Chhattisgarh, MP,
Goa, HP, Tripura, Mizoram, Meghalaya, Nagaland, Manipur, Uttarakhand,
the remaining UTs) need either ECI Statistical Report ingest *or*
hand-authored bootstrap from the Delimitation Order. This is tracked as
[IA-RESET §P2.8](../../TODO/IA-RESET-PLACE-FIRST-WITH-TOPIC-FRONT-DOOR.md).
