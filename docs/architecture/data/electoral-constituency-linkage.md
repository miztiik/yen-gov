# Electoral constituency linkage (AC <-> PC parent)

**Last Updated**: 2026-06-26

How `datasets/data/entities/electoral.csv` models the Assembly-constituency (AC) -> Parliament-constituency (PC) parent linkage, how the 2008-delimitation gap was backfilled by an in-repo geometric spatial join, the provenance rule (public-facing electoral data always cites ECI), the engineering shape of `electoral.csv`, and the residual coverage gap with the data needed to close it.

See also:

- [canonical-store.md](canonical-store.md) - the canonical CSV store.
- [boundaries.md](boundaries.md) - the boundary geometry layers the backfill reads.
- [../../concepts/data-provenance.md](../../concepts/data-provenance.md) - the citation-ledger doctrine (Holy Law #9).
- Plan-doc: [../../../TODO/20260625-election-constituency-list-redesign-plan.md](../../../TODO/20260625-election-constituency-list-redesign-plan.md) (Phase 0).

## 1. The model

`electoral.csv` carries one row per electoral entity. PC rows have `entity_kind=pc`; AC rows have `entity_kind=ac` and a `parent` column pointing at the `entity_id` of the PC the AC composes (a PC is, by delimitation, the union of whole ACs). `parent` is NULL only when the linkage is not yet known.

## 2. How `parent` is resolved (LGD-first, crosswalk-second, NULL-last)

1. **LGD** - the primary path. `backend/yen_gov/canonical/seed/electoral_csv_from_snapshot.py` reads `parent_pc_lgd_code` from the LGD constituency snapshot and resolves it to a PC `entity_id`.
2. **Geometric crosswalk** - the fallback (Row P0b). For ACs the LGD snapshot leaves NULL, the seed writer falls back to `datasets/data/entities/ac_pc_geometric_backfill.csv` (section 3).
3. **NULL** - if neither resolves, `parent` stays NULL and the citizen UI renders the AC honestly under "Parliament seat pending" / "data pending". No linkage is ever guessed.

## 3. The geometric AC->PC backfill (what + how)

The LGD snapshot lacks `parent_pc_lgd_code` for ~382 live-delim (2008) ACs across 26 states (Delhi is absent from the LGD AC roster entirely). These were backfilled from in-repo boundary geometry rather than by scraping ECI PDFs.

**Method.** `backend/yen_gov/canonical/seed/ac_pc_geometric_backfill.py` loads the AC polygons (`datasets/boundaries/electoral/delim=2024/ac/all.topojson`) and PC polygons (`datasets/boundaries/electoral/delim=2024/pc/all.geojson`) with shapely (an optional `[geo]` build-time extra; the committed pipeline that READS the crosswalk needs no geometry lib). For each AC it picks the PC with the maximum intersection area; `overlap_frac = intersection_area / AC_area` (lon/lat relative area - a relative comparison, so no reprojection).

**Safety - a hard validation gate.** Before emitting anything, the geometric parent of every AC that ALREADY has an LGD parent (~3,624 resolvable) is compared to that LGD parent. The run STOPS and writes nothing unless agreement `>= 95%`. Observed: **3443/3624 = 95.01%**, with a 99.57% per-row name-confirmed rate. This catches a broken decode/bridge before it can fabricate links.

**Safety - a per-row double-lock.** A gap AC is emitted only when `overlap_frac >= 0.80` AND the winning PC unambiguously beats the runner-up AND one of: (Tier A) the geometry's own seat name matches the electoral seat name, or (Tier B) the AC's state passed the per-state 95% LGD-agreement bar. Vintage-renumbered states (post-2014 AP/TG, post-2023 Assam) fail the number match but pass Tier-A name-lock. Anything satisfying neither lock is LEFT OUT.

**Result.** The geometric pass filled 316 of the 382 gap ACs; further passes (section 6) closed all but 3, leaving only the Assam vintage-mismatch seats NULL (`382 -> 3`). Regenerate with `python -m yen_gov seed-ac-pc-geometric-backfill` (prints the gate + coverage).

## 4. Provenance - electoral data always cites ECI

**Rule: the public-facing `source_id` for electoral data is always the Election Commission of India.**

The AC->PC linkage is a *de-jure delimitation fact* whose authority is the ECI 2008 Delimitation Order (`Delimitation of Parliamentary and Assembly Constituencies Order, 2008`, vintage `2008`, `source_id = src-7cd5269de2e7`). The in-repo geometric spatial join is the *recovery method*, not the origin - it is disclosed per-row on the crosswalk via `match_method=geometric_overlap` + `overlap_frac`, and in this doc. This honours Holy Law #9 by citing the source of the *fact* while keeping the method transparent.

The boundary geometry's own publishers remain cited on the boundary artifacts (see [boundaries.md](boundaries.md)); they are the provenance of the *polygons*, not of the *electoral linkage*. Where a state was re-delimited after 2008, the linkage's de-jure instrument is that state's own order (e.g. J&K = the 2022 J&K Delimitation Commission order, which the 2008 Order excluded); the crosswalk `source_id` keeps the standing ECI symbol and `match_method` + section 6 record the specific instrument.

## 5. Engineering notes - `electoral.csv` is a multi-source artifact

The next agent must know: **`electoral.csv` is NOT reproducible by a single writer.** It is assembled from:

- the LGD-snapshot base, emitted by `electoral_csv_from_snapshot.py` (LGD-keyed AC/PC rows), and
- a now-retired legacy backfill that appended ECI-keyed AC rows (`IN-AC-2008-<slug>-eci<N>`) for states absent from the LGD AC roster (e.g. all of Delhi), sourced from a since-deleted `dim_acs.parquet`.

Because the snapshot writer NEVER emits the ECI-keyed rows, **a naive full regen would DROP every ECI-keyed AC** (including all 316 backfilled seats). Consequently:

- The P0b backfill is applied by a **byte-preserving surgical applier** (`backend/yen_gov/canonical/seed/apply_ac_pc_backfill.py`, CLI `apply-ac-pc-geometric-backfill`) that sets `parent` for exactly the listed `ac_entity_id`s and rewrites only those lines - never a full regen.
- The seed writer is ALSO wired with the crosswalk fallback (`crosswalk_csv` arg) so any FUTURE full reconstruction stays correct.
- Editing `electoral.csv` staleness-invalidates downstream marts whose input-signature hashes it - notably `datasets/data/marts/party_pages/manifest.csv` - which must be regenerated in the same change (only its 1-line signature changes).

Before shipping any `electoral.csv` edit, diff it field-by-field against `origin/main` and confirm the change is confined to the intended cells.

## 6. How the 382-seat gap was closed + the residual

The 382 NULL-parent gap ACs were resolved in passes, each disclosed per-row on the crosswalk via `match_method` (+ `overlap_frac`). `source_id` is always the ECI delimitation authority (section 4); the recovery input is named by `match_method` and here, never cited as the source.

| `match_method` | Rows | What it is |
| --- | --- | --- |
| `geometric_overlap` | 316 | Spatial join: each AC -> the PC polygon it maximally overlaps (>= 0.80), double-locked by a per-row seat-name match or a per-state >= 95% LGD-agreement bar (section 3). |
| `single_pc_state` | 4 | A state/UT with exactly one PC: every Assembly seat composes that sole PC (Puducherry x3, Sikkim Sangha). `overlap_frac=1`. |
| `soi_composition` | 31 | The official `PC_NAME` AC->PC attribute on the Survey-of-India (datta07) Assembly shapefiles, double-locked against the AC's own centroid. `overlap_frac=1`. |
| `soi_centroid` | 3 | AP seats lacking that attribute, resolved by centroid-in-PC after the state validated >= 98% vs LGD. `overlap_frac=1`. |
| `composition_alias` | 10 | AP (9, satishvmadala open data) + UP (1, datta07): an official composition bridged by a verified name alias (e.g. `Sishamau` -> our SISAMAU; PC `Anakapalli` -> our Anakapalle). `overlap_frac=1`. |
| `eci_delimitation_order` | 15 | Read straight from the ECI delimitation order's PC-wise AC table: Gujarat (2, 2008 Order Part B p146 - Bapunagar/Jamalpur-Khadia -> Ahmedabad East/West) + J&K (13, 2022 J&K Delimitation Commission order). Names match verbatim. `overlap_frac=1`. |

**Doctrine.** Bare centroid inference is not used to bulk-resolve straddling seats: its error concentrates on exactly the hard, dense-urban, near-PC-boundary seats, and a name match confirms a seat's *identity*, not its *parent PC* (e.g. BANKIPUR centroids into Hajipur, not its true Patna Sahib). Such seats need an official de-jure composition. The 0.80 overlap bar and the 95% LGD-agreement gate are never lowered to force coverage (Holy Law #5). For a state re-delimited after 2008 the de-jure instrument is that state's own order (J&K = the 2022 J&K Delimitation Commission order; the 2008 Order excluded J&K); the crosswalk `source_id` keeps the standing ECI symbol while `match_method` + this section record the actual instrument (Holy Law #9).

### Residual: 3 Assam seats (delimitation-vintage mismatch)

| State | Residual ACs | Why still NULL | How to close |
| --- | --- | --- | --- |
| assam | Amguri, Thowra, Patacharkuchi | Our Assam AC roster is the pre-2023 (1976-era) delimitation, but the 2024 Lok Sabha PCs and the 2023 Assam re-delimitation renumbered and renamed every seat - so these three old-numbered seats bridge to no current PC by number or name. | Migrate the Assam Assembly roster to the 2023 re-delimitation (126 new seats, new numbering) - a deliberate data-model change - after which the 2023 PC->AC composition links them directly. |

Until then they stay NULL and the UI renders them honestly as "Parliament seat pending".

## 7. CLI

- `python -m yen_gov seed-ac-pc-geometric-backfill` - (re)build the crosswalk; prints the LGD-agreement gate + per-state coverage. Needs the `[geo]` extra (`pip install -e backend[geo]`).
- `python -m yen_gov apply-ac-pc-geometric-backfill` - apply the committed crosswalk to `electoral.csv` (byte-preserving, idempotent).
