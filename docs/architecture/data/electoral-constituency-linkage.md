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

**Result.** 316 of 382 gap ACs filled by the geometric pass (NULL-parent count `382 -> 66`); a logical single-PC-state rule then resolves 4 more (`66 -> 62`, section 6.1); a Survey-of-India composition backfill then resolves 34 more (`62 -> 28`, section 6.2); the 28 residual stay NULL (section 6). Regenerate with `python -m yen_gov seed-ac-pc-geometric-backfill` (prints the gate + coverage).

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

## 6. Residual coverage gap (28 ACs) + data needed to close it

After P0b, the single-PC-state rule (section 6.1), and the Survey-of-India composition backfill (section 6.2), 28 of the 382 gap ACs remain NULL. They fall into two buckets:

| Bucket | States (count) | Why these are still unresolved | Data needed to fix |
| --- | --- | --- | --- |
| Vintage mismatch | jammu-and-kashmir (13), andhra-pradesh (9), assam (3) | The electoral roster is the 2008 vintage but the seat set changed (J&K post-2022 90-seat re-delimitation; AP post-2014 bifurcation + rename/renumber; Assam post-2023 re-delimitation), so neither the seat number nor the name bridges cleanly. | The matching-vintage ECI Delimitation Order PC->AC composition for that state. |
| Name-spelling mismatch | uttar-pradesh (1), gujarat (2) | The seat resolves under the Survey-of-India composition (section 6.2) but its register name differs from the source label (e.g. SISAMAU; BAPUNAGAR), so the double-lock identity check abstains. | A name-reconciliation pass mapping the register names to the Survey-of-India / LGD seat names. |

The full residual seat list (for a follow-up pass), by state:

| State | Count | Residual ACs |
| --- | --- | --- |
| jammu-and-kashmir | 13 | Bishnah(SC), Channapora, Ganderbal, Habbakadal, Hazratbal, Inderwal, Kishtwar, Mendhar(ST), Padder - Nagseni, Pahalgam, Poonch Haveli, Suchetgarh(SC), Surankote(ST) |
| andhra-pradesh | 9 | Anakapalli, Bhimli, Elamanchili, Payakaraopeta, Rajamundry Rural, Sattenapalli, Unguturu, V.Madugula, Vijaywada West |
| assam | 3 | Amguri, Patacharkuchi, Thowra |
| gujarat | 2 | Bapunagar, Jamalpur-Khadia |
| uttar-pradesh | 1 | Sisamau |

**To close the gap:** acquire the ECI 2008 Delimitation Order PC-wise AC composition (the de-jure table) for the affected states, add the resolved pairs to `ac_pc_geometric_backfill.csv` (or a sibling de-jure crosswalk) with a `match_method` that records the de-jure source, re-run the surgical applier, and confirm the NULL-parent delim-2008 AC count drops below 28. Residuals that still cannot be sourced stay NULL -> "data pending". Never lower the 0.80 overlap bar or the 95% agreement gate to force coverage.

### 6.1 Autonomous-resolvability analysis (2026-06-25)

Of the original 66 residuals, **4 are resolvable with logical certainty and no geometry**: a state/UT with EXACTLY ONE Parliament constituency means every Assembly seat in it composes that one PC. This `single_pc_state` rule (section 3; `match_method=single_pc_state`, `overlap_frac=1.0`) closes Puducherry's 3 seats (Indira Nagar, Oupalam, Raj Bhavan -> `IN-PC-2008-puducherry-542`) and the non-territorial Sikkim Sangha seat (-> `IN-PC-2008-sikkim-192`), dropping the NULL-parent count `66 -> 62`.

A **centroid / interior-point-in-polygon** method (assign each straddling AC to the PC that contains its `representative_point()`) was evaluated for the remaining 62 and measured at **95.38% agreement** vs the LGD parent on the already-linked ACs - about equal to the area-overlap method, and above the 95% gate. It was nonetheless **REJECTED** for bulk-resolving the residual straddlers, because:

- The error does not spread evenly - it **concentrates on exactly these hard, near-PC-boundary dense-urban seats**, which are precisely the residuals. A 95% aggregate hides a much higher error rate on the specific seats that remain.
- The per-row name-match lock confirms an AC's **identity** (which seat it is), not its **parent** (which PC it belongs to), so a confident name match gives no assurance the centroid landed in the correct PC.
- A concrete wrong assignment was found: **BANKIPUR** (central Patna) resolves by centroid to the **Hajipur** PC instead of **Patna Sahib** - a real, citizen-visible error.

Therefore those straddlers require an official **de-jure PC-wise AC composition** (the 2008 Delimitation Order assignment table, or an equivalent published composition) for safe resolution rather than bare centroid inference. The Survey-of-India composition backfill in section 6.2 supplies exactly such an official composition and safely resolves 34 of the 62 (BANKIPUR among them, correctly). Geometry alone must not assert the rest, and lowering the 0.80 overlap bar or the 95% agreement gate to force coverage is forbidden (Holy Law #5 - structural fix, not a band-aid).

### 6.2 Survey-of-India composition backfill (2026-06-25)

The user supplied the `datta07/INDIAN-SHAPEFILES` corpus (Survey-of-India-derived state constituency shapefiles). For most states the ASSEMBLY-constituency file carries the OFFICIAL AC->PC composition as a `PC_NAME` attribute on each AC feature - a de-jure composition table, not merely polygons. Reading that attribute (rather than inferring it from geometry) resolved 34 of the 62 residuals and corrected two earlier geometric errors, dropping the NULL-parent delim-2008 AC count `62 -> 28`.

**Method (double-locked).** A seat was admitted only when BOTH (a) the official `PC_NAME` attribute named a PC AND (b) the AC's own-geometry centroid fell inside that same PC polygon - the attribute and the geometry had to agree. 31 resolved this way (`match_method=soi_composition`). For Andhra Pradesh, 3 seats whose composition attribute was absent were resolved by centroid-in-PC alone (`match_method=soi_centroid`). All 34 carry `overlap_frac=1.0` (serialized `1`) to denote "wholly attributed by the Survey-of-India composition / containment", not a measured straddle fraction. The public `source_id` stays the ECI 2008 Delimitation Order (section 4): the linkage is a de-jure delimitation fact and electoral data always cites ECI; the Survey-of-India shapefiles are the recovery INPUT, credited via `match_method` and this section.

**Per-state LGD validation.** Where an LGD ground-truth existed, the Survey-of-India composition was cross-checked against it before any seat in that state was admitted: Maharashtra 100%, Jharkhand 100%, Goa 100%, Uttar Pradesh 99.7%, Bihar 99.1%, West Bengal 98.9%, Rajasthan 97.5%. Delhi has no LGD AC ground-truth at all, so its 13 seats relied on the attribute-plus-centroid double-lock alone. Andhra Pradesh's 3 centroid seats validated at 98.3%.

**Two earlier geometric errors corrected.** The official composition overturned two assignments bare geometry had gotten wrong: BANKIPUR (central Patna) -> Patna Sahib, not Hajipur; KALKAJI (Delhi) -> South Delhi, not East Delhi. This is exactly why the de-jure attribute, not centroid inference, is authoritative for these dense-urban seats (section 6.1).

**The remaining 28 - why these sources do not resolve them.**

- **Jammu & Kashmir (13)** - our roster is the CURRENT 2022 delimitation (90 ACs / 5 PCs). The current-vintage AC geometry (shijithpk 2024) carries NO AC->PC composition; the shijithpk LS file is only a partial supplement (changed borders plus a "Rest of J&K" residual); and datta07's J&K is the SUPERSEDED old delimitation (107 ACs). No source provides the complete current-2024 J&K AC->PC composition.
- **Andhra Pradesh (9)** - our roster is the undivided pre-2014 AP (293 rows of the ~294-seat assembly), but datta07's AP is the current post-bifurcation 175-seat assembly, so the remaining 9 fail to bridge on vintage plus name-spelling (e.g. our `VIJAYWADA WEST` vs the source's `VIJAYAWADA WEST`).
- **Assam (3)** - datta07's Assam agrees with LGD at only 92.3% (post-2023 re-delimitation), below the 95% gate, so it is excluded as vintage-suspect.
- **Uttar Pradesh (1: Sisamau) + Gujarat (2: Bapunagar, Jamalpur-Khadia)** - name-spelling mismatches between the register and the Survey-of-India label; recoverable with a name-reconciliation pass (no new source needed).

These 28 stay NULL -> "data pending". The 0.80 overlap bar and the 95% agreement gate are not lowered to force coverage (Holy Law #5).

## 7. CLI

- `python -m yen_gov seed-ac-pc-geometric-backfill` - (re)build the crosswalk; prints the LGD-agreement gate + per-state coverage. Needs the `[geo]` extra (`pip install -e backend[geo]`).
- `python -m yen_gov apply-ac-pc-geometric-backfill` - apply the committed crosswalk to `electoral.csv` (byte-preserving, idempotent).
