# Electoral constituency linkage (AC <-> PC parent)

**Last Updated**: 2026-06-25

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

**Result.** 316 of 382 gap ACs filled (NULL-parent count `382 -> 66`); the 66 residual stay NULL (section 6). Regenerate with `python -m yen_gov seed-ac-pc-geometric-backfill` (prints the gate + coverage).

## 4. Provenance - electoral data always cites ECI

**Rule: the public-facing `source_id` for electoral data is always the Election Commission of India.**

The AC->PC linkage is a *de-jure delimitation fact* whose authority is the ECI 2008 Delimitation Order (`Delimitation of Parliamentary and Assembly Constituencies Order, 2008`, vintage `2008`, `source_id = src-7cd5269de2e7`). The in-repo geometric spatial join is the *recovery method*, not the origin - it is disclosed per-row on the crosswalk via `match_method=geometric_overlap` + `overlap_frac`, and in this doc. This honours Holy Law #9 by citing the source of the *fact* while keeping the method transparent.

The boundary geometry's own publishers remain cited on the boundary artifacts (see [boundaries.md](boundaries.md)); they are the provenance of the *polygons*, not of the *electoral linkage*. An earlier iteration cited the crosswalk to a `yen-gov` "geometric inference" source; that was corrected to ECI on 2026-06-25 because the linkage is a delimitation fact ECI is the authority for, and electoral data must cite ECI uniformly.

## 5. Engineering notes - `electoral.csv` is a multi-source artifact

The next agent must know: **`electoral.csv` is NOT reproducible by a single writer.** It is assembled from:

- the LGD-snapshot base, emitted by `electoral_csv_from_snapshot.py` (LGD-keyed AC/PC rows), and
- a now-retired legacy backfill that appended ECI-keyed AC rows (`IN-AC-2008-<slug>-eci<N>`) for states absent from the LGD AC roster (e.g. all of Delhi), sourced from a since-deleted `dim_acs.parquet`.

Because the snapshot writer NEVER emits the ECI-keyed rows, **a naive full regen would DROP every ECI-keyed AC** (including all 316 backfilled seats). Consequently:

- The P0b backfill is applied by a **byte-preserving surgical applier** (`backend/yen_gov/canonical/seed/apply_ac_pc_backfill.py`, CLI `apply-ac-pc-geometric-backfill`) that sets `parent` for exactly the listed `ac_entity_id`s and rewrites only those lines - never a full regen.
- The seed writer is ALSO wired with the crosswalk fallback (`crosswalk_csv` arg) so any FUTURE full reconstruction stays correct.
- Editing `electoral.csv` staleness-invalidates downstream marts whose input-signature hashes it - notably `datasets/data/marts/party_pages/manifest.csv` - which must be regenerated in the same change (only its 1-line signature changes).

Before shipping any `electoral.csv` edit, diff it field-by-field against `origin/main` and confirm the change is confined to the intended cells.

## 6. Residual coverage gap (66 ACs) + data needed to close it

After P0b, 66 of the 382 gap ACs remain NULL. They fall into three buckets:

| Bucket | States (count) | Why geometry cannot resolve them | Data needed to fix |
| --- | --- | --- | --- |
| Vintage mismatch | jammu-and-kashmir (13), andhra-pradesh (12), assam (3) | The electoral roster is the 2008 vintage but the seat set changed (J&K post-2022 90-seat re-delimitation; AP post-2014 bifurcation + rename/renumber; Assam post-2023 re-delimitation), so neither the seat number nor the name bridges cleanly. | The matching-vintage ECI Delimitation Order PC->AC composition for that state. |
| Dense-urban straddle | delhi (13), maharashtra (6), west-bengal (5), uttar-pradesh (4), puducherry (3), gujarat (2), bihar (1), goa (1), jharkhand (1), rajasthan (1) | Metro-core ACs straddle two PCs under the simplified PC boundary, so no PC clears the 0.80 dominant-overlap bar (and Delhi has no LGD fallback at all). | The ECI 2008 Delimitation Order PC-wise AC composition table (de-jure assignment), OR unsimplified PC boundary geometry. |
| Non-territorial seat | sikkim (1) | The Sangha seat is elected by monasteries state-wide and has no contiguous geography, so spatial containment is undefined. | Manual assignment to the Sikkim PC per the Delimitation Order. |

The full residual seat list (for a follow-up pass), by state:

| State | Count | Residual ACs |
| --- | --- | --- |
| jammu-and-kashmir | 13 | Bishnah(SC), Channapora, Ganderbal, Habbakadal, Hazratbal, Inderwal, Kishtwar, Mendhar(ST), Padder - Nagseni, Pahalgam, Poonch Haveli, Suchetgarh(SC), Surankote(ST) |
| andhra-pradesh | 12 | Anakapalli, Bhimli, Elamanchili, Gajuwaka, Gurazala, Payakaraopeta, Rajamundry Rural, Sattenapalli, Unguturu, V.Madugula, Vijayawada East, Vijaywada West |
| delhi | 13 | Adarsh Nagar, Badarpur, Chandni Chowk, Gandhi Nagar, Jangpura, Kalkaji, Karawal Nagar, Madipur, Model Town, Moti Nagar, Mustafabad, Patel Nagar, Shalimar Bagh |
| maharashtra | 6 | Colaba, Ghatkopar West, Mankhurd Shivaji Nagar, Mumbadevi, Shivadi, Worli |
| west-bengal | 5 | Barrackpur, Bhatpara, Bijpur, Howrah Madhya, Jadavpur |
| uttar-pradesh | 4 | Allahabad South, Lucknow North, Lucknow West, Sisamau |
| assam | 3 | Amguri, Patacharkuchi, Thowra |
| puducherry | 3 | Indira Nagar, Oupalam, Raj Bhavan |
| gujarat | 2 | Bapunagar, Jamalpur-Khadia |
| bihar | 1 | Bankipur |
| goa | 1 | Mormugao |
| jharkhand | 1 | Jamshedpur West |
| rajasthan | 1 | Hawamahal |
| sikkim | 1 | Sangha |

**To close the gap:** acquire the ECI 2008 Delimitation Order PC-wise AC composition (the de-jure table) for the affected states, add the resolved pairs to `ac_pc_geometric_backfill.csv` (or a sibling de-jure crosswalk) with a `match_method` that records the de-jure source, re-run the surgical applier, and confirm the NULL-parent delim-2008 AC count drops below 66. Residuals that still cannot be sourced stay NULL -> "data pending". Never lower the 0.80 overlap bar or the 95% agreement gate to force coverage.

## 7. CLI

- `python -m yen_gov seed-ac-pc-geometric-backfill` - (re)build the crosswalk; prints the LGD-agreement gate + per-state coverage. Needs the `[geo]` extra (`pip install -e backend[geo]`).
- `python -m yen_gov apply-ac-pc-geometric-backfill` - apply the committed crosswalk to `electoral.csv` (byte-preserving, idempotent).
