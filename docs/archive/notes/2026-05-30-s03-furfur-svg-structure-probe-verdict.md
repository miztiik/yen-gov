# S03 Assam Furfur SVG structure probe verdict

**Last Updated**: 2026-05-30

**Source**: [File:Wahlkreise zur Vidhan Sabha von Assam (2023-).svg](https://commons.wikimedia.org/wiki/File:Wahlkreise_zur_Vidhan_Sabha_von_Assam_(2023-).svg) by Furfur (CC-BY-SA 4.0, 6.14 MB, 1326x919 viewBox, version 2 December 2025 "correction (constituencies 80/88)").

**Probe script**: `.tmp_probe_furfur_svg.py` (lxml-only; no external deps).

**Cited by**: [TODO/20260530-boundary-followups-execution-plan.md](../TODO/20260530-boundary-followups-execution-plan.md) Row 5.1.

---

## section 1. Probe findings

| Property | Value |
| --- | --- |
| viewBox | `0 0 1325.547 919.128` |
| File bytes | 6,439,856 |
| `<path>` element count | **20** |
| `<text>` element count | 132 |
| `<tspan>` element count | 132 |
| `<g>` element count | 265 (262 anonymous; 1 named `Nummern`; 2 named `text549`/`text551`) |
| `<title>` / `<desc>` elements | 0 / 0 |
| Total subpath-starts (`M` commands across all 20 paths) | **25** |
| Total subpath-closes (`Z` commands) | 24 |
| Path `d` length: min / avg / max | 745 / 27,053 / 148,600 chars |
| `d` command histogram | l=10038, h=6184, v=5366, c=1352, s=145, M=25, Z=24 |
| `<text>` content: pure-digits count | **129 of 132** (e.g. "1", "2", "3", ..., up to ~126 + corrections for 80/88) |
| `<text>` content: alpha (>1 char) count | 3 |

---

## section 2. Verdict (supersedes Row 5.1 optimistic estimate)

**The Furfur SVG is NOT directly extractable as 126 per-AC polygons via lxml path-parsing.**

The SVG is a **stylized cartographic composition**, not a per-feature vector source:

- Geometry: 20 `<path>` elements with **only 25 subpath-starts total**. These represent **district-fill or region-group polygons**, NOT individual ACs. Adobe Illustrator authoring style uses relative `l`/`h`/`v` line commands with occasional cubic beziers.
- Labels: 132 `<text>` elements, **129 of which are pure numeric AC numbers** (1-126 + a few corrections). The full AC name list ("GOSSAIGAON", "DOTMA (ST)", "KOKRAJHAR (ST)", ...) appears ONLY in the Wikimedia page _description_, NOT in the SVG itself.

Mathematically: 25 subpaths cannot represent 126 ACs. The mapping from SVG paths to ACs is many-to-one (one polygon contains multiple AC label-centroids).

## section 3. Implications for Row 5.1

The 8-step plan in the execution plan-doc assumed "lxml XPath `<path>` per AC -> polygon coordinates" (steps 1-2). That assumption is FALSE for this source.

**Three revised paths**:

### Path A - Voronoi tessellation around AC label centroids (L-XL, ~20-40h)

Extract the 126 numeric label positions; perform Voronoi tessellation in viewBox coordinates; clip each Voronoi cell to the union of the 20 district-fill polygons (Assam state outline); affine-warp to lat/lon. Produces 126 polygons that approximate AC boundaries.

- Pros: fully automated; produces 126-polygon output usable by frontend choropleth.
- Cons: **boundaries are approximations**, not the actual delimitation polygons. May materially misrepresent narrow / oddly-shaped ACs (urban areas especially). Requires `shapely` + `scipy.spatial.Voronoi` + `numpy` (none currently in `.venv`).
- Risk: shipping approximated boundaries to citizens labeled as "post-2023 delimitation" is misleading. Would need a very prominent caveat.

### Path B - Contact Furfur for source files (S effort, unknown timeline)

Open a discussion on https://commons.wikimedia.org/wiki/User_talk:Furfur asking for the source data used to author the SVG (Adobe Illustrator native file, georeferenced shapefile, KML, GeoJSON, etc.). Furfur cited the ECI 2023 Delimitation Order PDF as source - they likely traced manually from PDF.

- Pros: if Furfur shares a vector source, full pipeline becomes trivial.
- Cons: timeline depends on Furfur's response; may receive no reply.

### Path C - Reframe S03 expectation; keep T4 district fallback (S, ~0.5h)

The current S03 state-page uses a Tier-4 district-polygon fallback with a tooltip declaring "boundaries pending post-2023 delimitation; showing district outlines as interim." This is HONEST about the data gap. Reconsider whether spending 20-40h on Voronoi approximation buys enough citizen value over the current honest fallback.

- Pros: zero engineering cost; no misleading approximations.
- Cons: S03 stays the only major state without per-AC granularity until a real source ships.

## section 4. Recommendation

**Defer S03 per-AC geometry**. Pivot in this order:

1. **Open Path B** (Furfur outreach) - cheap, unbounded payoff. Costs ~30 min to author the talk-page message.
2. **Document the Path A approach** as a fallback in the execution plan-doc Row 5.1, BUT do not start it until either (a) Path B confirms-no-source AND (b) user explicitly accepts approximated-boundary tradeoff with a citizen-visible caveat ribbon.
3. **Keep T4 district fallback** as the current shipped experience. Update the tooltip copy to specifically credit the Furfur SVG as a visual reference linked from the state page, even though it can't be used as polygon source.

## section 5. Updates to plan-doc Row 5.1

After this PR merges, Row 5.1 in [TODO/20260530-boundary-followups-execution-plan.md](../TODO/20260530-boundary-followups-execution-plan.md) should:

- Drop the L `~10-11h` estimate. Replace with "BLOCKED on Path B (Furfur outreach) or user accepting Path A approximation."
- Move Row 5.1 from `PENDING-actionable` to `BLOCKED-on-trigger` until Path B verdict or user authorisation for Path A.
- Update `notes/2026-05-29-s03-pdf-probe-verdict.md` SUPERSEDED header to point at THIS verdict note + the structural finding.

This PR ships the probe + verdict + ALL three updates above.

---

## See also

- [TODO/20260530-boundary-followups-execution-plan.md](../TODO/20260530-boundary-followups-execution-plan.md) - Row 5.1.
- [notes/2026-05-29-s03-pdf-probe-verdict.md](2026-05-29-s03-pdf-probe-verdict.md) - prior verdict (now further superseded).
- [notes/2026-05-29-phase-b-verdict-correction.md](2026-05-29-phase-b-verdict-correction.md) - Phase B correction that surfaced the Furfur SVG.
