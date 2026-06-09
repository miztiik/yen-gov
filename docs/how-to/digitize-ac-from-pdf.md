# How to digitize AC boundaries from a Delimitation Order PDF (T3 workflow)

**Last Updated**: 2026-05-30
**Status**: scaffold (v0 framework; full QGIS step-by-step with
screenshots is a follow-up). Use this doc to scope a T3 sprint and
understand the deliverable shape; the operational mechanics are
captured here at the level needed to estimate effort and avoid
common traps.

When an upstream publisher (ramSeraph, Delimitation Commission, state
EC) does NOT ship machine-readable AC boundaries for a state, the
fallback ladder is:

```
T1  machine-readable shapefile / geojson    <- PREFERRED
T2  Voronoi from polling-station points     <- BLOCKED (no PS points pre-poll)
T3  PDF digitization of Delimitation Order  <- THIS DOC (40-60 hours)
T4  parent-district fallback (interim)      <- visual placeholder only
```

This doc covers T3. The currently-open T3 candidate is **S03 Assam**
post-2023 delimitation (A.1.b of the closed boundary plan); future T3
work would target any state whose machine-readable source lags a delim
cycle.

## Scope: what T3 delivers

A T3 sprint produces:

1. Per-AC polygon geometry for ALL ACs in the state at the target
   delim vintage (e.g. Assam 2023 = 126 ACs).
2. Topological soundness: no gaps between adjacent ACs, no overlaps,
   coastline + state-border alignment with the existing state polygon
   to within ~50 metres.
3. LGD `ac_id` + ECI `eci_no` properties on every feature, ready for
   the existing election-results join pipeline.
4. A `datasets/boundaries/electoral/delim=<year>/ac/state=<slug>/all.geojson` shard
   that drops in alongside the other 30 state shards with no
   schema change.
5. A verdict note + a lift ledger entry recording: source PDF URL,
   digitization date, QGIS project file location, vintage,
   topological-check pass/fail.

## Why T3 is expensive (40-60 hours)

The Delimitation Order PDF is a 200-500 page document published by the
Delimitation Commission (or the equivalent body for a delim cycle).
For each AC, it specifies the constituent revenue villages,
municipal wards, and street-level cut-offs in TEXT FORM ("AC 12
comprises blocks A, B, C; wards 1-15 of municipality X; villages
listed in Annexure II..."). There is NO machine-readable boundary
table -- the geometry must be RECONSTRUCTED by selecting the
constituent unit polygons (villages + wards) from existing layers and
dissolving them into AC polygons.

Time goes to:

- Reading 200-500 pages of legal text and extracting the unit lists
  per AC (~10-15 hours).
- Joining each AC's unit list to the underlying village + ward
  geometry (~10-15 hours; villages may be in LGD, Bhuvan, or
  state-published cadastrals; wards may be SBM or state-AMRUT).
- Dissolving in QGIS and resolving topology errors per AC (~10-15
  hours; coastline + inter-AC gap reconciliation is the slow part).
- Spot-check + sign-off pass (~5-10 hours; compare 5-10 ACs to the
  ECI's published polling-station coordinates as ground truth).

Estimates vary by state. A state with ~50 ACs at clean unit-list
coverage is ~25-30 hours. Assam (126 ACs + uneven village coverage in
the Barak Valley + tribal autonomous councils) is the upper bound at
~50-60 hours.

## Prerequisites before starting a T3 sprint

1. The state's Delimitation Order PDF (machine-readable text layer,
   NOT a scan -- if scanned, OCR adds another ~10 hours).
2. Underlying unit layers: villages (LGD or Bhuvan), wards (SBM),
   municipalities (LGD ULBs). Run the corresponding `lift_*` to
   confirm coverage before committing to T3.
3. The state polygon from the existing state-boundary shard
   (`datasets/boundaries/in/states/state=in_<lc>/all.geojson`) for
   topological alignment.
4. ECI's published list of ACs for the delim cycle (ac_no + name +
   reservation), as the cross-check against the PDF's enumeration.
5. QGIS 3.34 LTS or newer. Plugins: QuickWKT, MMQGIS (for batch
   dissolve), Topology Checker.

## Outline workflow (operational details captured at sprint-time)

1. **Extract per-AC unit lists from the PDF.** Use `pdftotext -layout`
   then regex per Annexure. For Assam 2023, the Annexure II structure
   is `AC <n>: <name> (<reservation>) - <village list>`. Parse into
   a CSV `ac_no, ac_name, units[]`.
2. **Confirm unit coverage.** Each village/ward name in the CSV must
   resolve to a polygon in the underlying layer. Mismatches surface as
   "AC X has unit `Y` but no village/ward named `Y` in the layer".
   These ALWAYS happen at 1-2% rate; mitigate by name-fuzzy-match
   (Levenshtein <= 2) + manual reconciliation.
3. **Dissolve in QGIS.** Per AC, select the matched unit polygons and
   dissolve. Output: 126 (Assam) candidate AC polygons.
4. **Topology pass.** Run Topology Checker for: gaps between adjacent
   ACs (must be zero -- ACs partition the state); overlaps (must be
   zero -- no AC shares territory); state-border slivers (must be
   <50m sliver tolerance).
5. **Coastline + state-border snapping.** Snap exterior boundary to
   the state polygon's vertices to eliminate slivers.
6. **Property attachment.** Add `ac_no`, `ac_name`, `eci_no`,
   `lgd_ac_id` (where LGD has issued them; otherwise NULL with a
   stamp), `delim_vintage` to each feature.
7. **Export to GeoJSON.** Use a fixed coordinate-precision matching
   the rest of the AC layer (`coord_precision=5` per the boundary
   byte-budget rule).
8. **Lift into yen-gov.** Place under
   `datasets/boundaries/electoral/delim=<year>/ac/state=<slug>/all.geojson`, run
   `tools/boundaries/lift_ac_<state>_t3.py` (if a wrapper exists)
   OR commit the shard directly + record the parquet ledger row.
9. **Smoke + sign-off.** Run the standard 5-gate DoD; spot-check 5
   ACs by overlaying ECI's polling-station coordinates from the most
   recent election.
10. **Document the vintage**: add a verdict note recording the source
    PDF URL, digitization date, QGIS project location, topology pass
    summary, and a per-AC matched-unit-count table.

## When to authorise a T3 sprint (decision filter)

T3 is genuinely expensive. The trigger conditions:

1. The state has indicator demand at AC grain (election results +
   AC-level indicators) AND
2. T1 (machine-readable upstream) is unavailable AND has no published
   timeline AND
3. T4 (district-fallback interim) is in place and citizen-visible
   AND has been pinged by at least one user complaint OR is blocking
   a citizen-facing election event (e.g. an LS poll cycle) AND
4. A staff or contractor day-rate budget is approved for the
   estimated 40-60 hour sprint.

Without ALL of 1-4, the state stays on T4 (district fallback) and is
documented in the boundary-plan followups inventory under "carve-outs
shipped with quality compromise".

The current open T3 candidate (Assam 2023) sits at YES on 1+2+3 but
NO on 4 (no budget authorised); deferred until either Lok Sabha
election cycle pings it OR ramSeraph / Delimitation Commission
publishes the machine-readable shapefile.

## What NOT to do

- **Do NOT attempt T3 from a scanned PDF without OCR sign-off.** OCR
  on legal-text Annexures introduces transcription errors that
  cascade into AC-misattribution. Confirm the PDF has a text layer
  before committing the sprint.
- **Do NOT skip the topology pass.** Gaps and slivers cause renderer
  artefacts (transparent slivers on the choropleth) and election-result
  join failures (orphan polling stations falling between AC polygons).
- **Do NOT dissolve unit polygons without first reconciling the
  unit-name mismatches.** Unmatched units default-fall to the wrong
  AC and silently mis-attribute election results.
- **Do NOT ship T3 without comparing 5-10 ACs to ECI polling-station
  coordinates.** This is the only ground-truth available without a
  T1 reference.

## See also

- [`docs/concepts/boundary-data-philosophy.md`](../concepts/boundary-data-philosophy.md)
- [`docs/concepts/admin-level-sourcing.md`](../concepts/admin-level-sourcing.md)
- [`docs/how-to/add-new-boundary-layer.md`](add-new-boundary-layer.md)
- [docs/archive/plans/20260530-boundary-plan-followups.md](../../docs/archive/plans/20260530-boundary-plan-followups.md) Category 2 (carve-outs)
- Closed plan-doc: [docs/archive/plans/20260527-state-ac-map-universal-coverage-plan.md](../archive/plans/20260527-state-ac-map-universal-coverage-plan.md) row A.1.b
- Verdict correction: [docs/archive/notes/2026-05-29-phase-b-verdict-correction.md](../../docs/archive/notes/2026-05-29-phase-b-verdict-correction.md)
