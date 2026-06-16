/**
 * Routes mount the shared `<Breadcrumb>` primitive.
 *
 * PR-12 (D12 of TODO/20260615-party-page-citizen-fixes-plan.md): the
 * `/parties/<slug>` page shipped with the `partyCrumbs` builder wired
 * in `main.ts` line 158 but never mounted `<Breadcrumb>` in
 * `routes/Party.svelte`. The defect surfaced as no breadcrumb chrome
 * on `/parties/bjp` while every state-event page rendered the
 * `Home -> Kerala -> Kerala elections -> assembly-2026` chain.
 *
 * This contract enforces the rule for every route file that the
 * router (`frontend/src/main.ts`) declares a `crumbs:` builder for:
 *   1. The route component MUST import `Breadcrumb` from
 *      `../lib/Breadcrumb.svelte` (relative path - vitest does not
 *      resolve SvelteKit-style `$lib` aliases per
 *      `/memories/lessons.md`).
 *   2. The route component MUST render `<Breadcrumb` somewhere in its
 *      markup.
 *   3. OR the component is listed in `ALLOWLIST_NO_MOUNT` below with
 *      a non-empty `reason` recording WHY the route is intentionally
 *      breadcrumb-less today.
 *
 * The allowlist captures the audit-state at the moment PR-12 landed.
 * PR-12 surgically:
 *   - mounted the shared component on `Party.svelte` (the one
 *     user-named gap that motivated the plan-doc row)
 *   - unified THREE bespoke `<nav aria-label="Breadcrumb">` holdouts
 *     onto the shared primitive (CompareIndicator.svelte,
 *     CountingMethodDoc.svelte, TopicLanding.svelte) - within the E5
 *     threshold (>3 holdouts triggers escalation; 3 is handled inline)
 *   - allowlisted the remaining no-mount routes pending follow-on
 *     plan-doc work
 *
 * No E5 escalation was needed: ZERO unified holdouts remain after
 * PR-12, and every allowlisted entry is a "no mount" gap (chrome
 * single-leaf, dev-only sandbox, or elections-landing family pending
 * a uniform mount sweep).
 *
 * Forward-defence: a NEW route added to `main.ts` with `crumbs:` MUST
 * either mount the shared `<Breadcrumb>` OR add an entry here with a
 * reason. A NEW route with bespoke `<nav aria-label="Breadcrumb">`
 * chrome will also trip the "no bespoke nav" assertion in this file.
 *
 * Per `/memories/lessons.md` and the existing contract files
 * (e.g. `topic-card-uniqueness.test.ts`, `app-tokens.test.ts`), this
 * suite reads source files from disk and asserts on textual
 * invariants. No Svelte mount, no jsdom.
 */

import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(
  fileURLToPath(new URL(".", import.meta.url)),
  "..",
  "..",
);
const mainPath = resolve(frontendRoot, "src", "main.ts");
const routesDir = resolve(frontendRoot, "src", "routes");

const SHARED_IMPORT = `import Breadcrumb from "../lib/Breadcrumb.svelte"`;
const SHARED_MOUNT_RE = /<Breadcrumb\b/;
const BESPOKE_NAV_RE = /<nav[^>]*aria-label\s*=\s*["']Breadcrumb["']/i;

/**
 * Route components in `main.ts` that DECLARE `crumbs:` but do NOT yet
 * mount the shared `<Breadcrumb>` primitive. Each entry records the
 * audit-state reason; a future plan-doc closes each gap by mounting
 * the shared component and removing the entry from this allowlist.
 *
 * The audit at PR-12 (2026-06-15) found THREE bespoke
 * `<nav aria-label="Breadcrumb">` holdouts (CompareIndicator,
 * CountingMethodDoc, TopicLanding); PR-12 unified all three onto the
 * shared primitive (within the E5 threshold of 3). Every entry below
 * is therefore a "no mount" gap, not a "wrong mount" gap.
 *
 * Adopters that DO NOT appear here (and therefore MUST mount the
 * shared component):
 *   - Home.svelte, StateOverview.svelte, StateTopic.svelte,
 *     StateElection.svelte, Constituency.svelte, District.svelte,
 *     CompareElections.svelte (the 7 pre-PR-12 adopters)
 *   - Party.svelte (the PR-12 mount)
 *   - CompareIndicator.svelte, CountingMethodDoc.svelte,
 *     TopicLanding.svelte (the 3 PR-12 unifications)
 */
const ALLOWLIST_NO_MOUNT: ReadonlyArray<{
  component: string;
  reason: string;
}> = [
  {
    component: "About.svelte",
    reason:
      "Single-leaf chrome route - the shared component self-suppresses chains of length <= 1 today, so mounting is a no-op. Pending follow-on plan-doc to either mount uniformly or formalise the chrome-suppression rule.",
  },
  {
    component: "Disclaimer.svelte",
    reason: "Single-leaf chrome route; same disposition as About.svelte.",
  },
  {
    component: "Settings.svelte",
    reason: "Single-leaf chrome route; same disposition as About.svelte.",
  },
  {
    component: "NotFound.svelte",
    reason:
      "404 surface; same disposition as About.svelte (the leaf carries 'Not found').",
  },
  {
    component: "TopicIndex.svelte",
    reason:
      "Single-leaf chrome route ('Home -> Topics'); pending follow-on plan-doc to mount uniformly across the chrome family.",
  },
  {
    component: "DataCompleteness.svelte",
    reason:
      "Single-leaf chrome route ('Home -> Data completeness'); same disposition.",
  },
  {
    component: "PartiesIndex.svelte",
    reason:
      "Single-leaf chrome route ('Home -> Parties'); same disposition.",
  },
  {
    component: "DevChartsSandbox.svelte",
    reason:
      "Dev-only sandbox, not citizen-discoverable; breadcrumb chrome is not a priority for this surface.",
  },
  {
    component: "Yenask.svelte",
    reason:
      "Dev-only LLM-OS lab surface, not citizen-discoverable; same disposition as DevChartsSandbox.",
  },
  {
    component: "AssemblyElections.svelte",
    reason:
      "Elections landing route; pending follow-on plan-doc to mount uniformly across the elections-landing family (AssemblyElections + GeneralElections + NationalElection + TopicLanding).",
  },
  {
    component: "GeneralElections.svelte",
    reason: "Elections landing route; same disposition as AssemblyElections.svelte.",
  },
  {
    component: "NationalElection.svelte",
    reason:
      "National event landing route ('Home -> Topics -> Elections -> general-YYYY'); pending follow-on plan-doc, same family disposition.",
  },
  {
    component: "Psephlab.svelte",
    reason:
      "Analyst lab surface, not the citizen permalink; pending follow-on plan-doc to confirm whether the lab carries crumbs.",
  },
  {
    component: "IndicatorDoc.svelte",
    reason:
      "Per-indicator doc route ('Home -> Docs -> Indicator -> <topic>/<id>'); pending follow-on plan-doc to mount uniformly across the docs family.",
  },
  {
    component: "Explore.svelte",
    reason:
      "Per-state explorer route ('Home -> <State> -> Explore'); pending follow-on plan-doc.",
  },
  {
    component: "StateSubRouter.svelte",
    reason:
      "Depth-2 dispatcher that mounts District / Constituency / NotFound at runtime; the breadcrumb chrome comes from the inner mounted component, not from the dispatcher itself.",
  },
];

interface RouteDecl {
  /** Component identifier as it appears in `main.ts` (e.g. `Party`). */
  componentName: string;
  /** Path of the route file under `src/routes/` (e.g. `Party.svelte`). */
  componentFile: string;
  /** The crumbs builder name (e.g. `partyCrumbs`). */
  crumbsName: string;
}

/**
 * Parse `main.ts` and extract every route object that declares both
 * `component:` and `crumbs:` keys. The `notFound:` entry is parsed
 * with the same rules.
 *
 * The parser is intentionally line-based (not a full TS AST) per the
 * existing contract-file precedent (`topic-card-uniqueness.test.ts`,
 * `app-tokens.test.ts`). A brace-balanced block extractor was tried
 * first but tripped on inner `({ ... }) => ({ ... })` arrow bodies in
 * route entries carrying a `parse:` key (e.g. IndicatorDoc,
 * CountingMethodDoc, Party). The line-window approach below is
 * resilient to inner brace nesting because it scans a fixed window of
 * lines after every `component:` declaration looking for the
 * matching `crumbs:` key on a sibling line.
 *
 * Strategy: walk lines of `main.ts` linearly; when a line carries
 * `component: <Ident>`, look forward up to LOOKAHEAD lines for a sibling
 * `crumbs: <ident>` declaration. The route table never separates a
 * route's `component:` and `crumbs:` keys by more than a handful of
 * lines (the longest entry today has the `component:` and `crumbs:`
 * separated by 5 lines), so 12 is a comfortable safety margin.
 */
function parseRouteComponents(mainSource: string): RouteDecl[] {
  // Snip out any block-comment payload so a commented-out route entry
  // does not register. Block comments inside `main.ts` are well-formed
  // (the file is generated by hand and svelte-check would reject a
  // dangling `/*`).
  const stripped = mainSource.replace(/\/\*[\s\S]*?\*\//g, "");
  const lines = stripped.split(/\r?\n/);
  const LOOKAHEAD = 12;

  const componentRe = /\bcomponent\s*:\s*([A-Z][A-Za-z0-9_]*)/;
  const crumbsRe = /\bcrumbs\s*:\s*([a-z][A-Za-z0-9_]*)/;

  const out: RouteDecl[] = [];
  for (let i = 0; i < lines.length; i++) {
    const componentMatch = componentRe.exec(lines[i]!);
    if (!componentMatch) continue;
    const componentName = componentMatch[1]!;
    // Look on the SAME line first (single-line route entries like
    // `{ pattern: "/", component: Home, crumbs: homeCrumbs }`), then
    // walk forward up to LOOKAHEAD lines.
    let crumbsName: string | null = null;
    for (let j = 0; j <= LOOKAHEAD && i + j < lines.length; j++) {
      const crumbsMatch = crumbsRe.exec(lines[i + j]!);
      if (crumbsMatch) {
        crumbsName = crumbsMatch[1]!;
        break;
      }
    }
    if (!crumbsName) continue;
    out.push({
      componentName,
      componentFile: `${componentName}.svelte`,
      crumbsName,
    });
  }
  // Deduplicate by component+crumbs pair (Constituency.svelte appears
  // three times under different crumbs builders; Psephlab.svelte
  // appears twice under the same crumbs builder).
  const seen = new Set<string>();
  return out.filter((r) => {
    const key = `${r.componentFile}::${r.crumbsName}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

describe("routes mount the shared <Breadcrumb> primitive", () => {
  const mainSource = readFileSync(mainPath, "utf-8");
  const routedDecls = parseRouteComponents(mainSource);
  const uniqueComponents = new Set(routedDecls.map((d) => d.componentFile));

  it("main.ts parser finds at least one routed component with crumbs", () => {
    // Sanity check: regression-proof the parser against a future
    // refactor of `main.ts` that drops the `crumbs:` literal (in which
    // case every other assertion in this suite would vacuously pass).
    expect(uniqueComponents.size).toBeGreaterThan(5);
  });

  it("every entry in ALLOWLIST_NO_MOUNT names a real routed component", () => {
    const offenders: string[] = [];
    for (const entry of ALLOWLIST_NO_MOUNT) {
      if (!uniqueComponents.has(entry.component)) {
        offenders.push(entry.component);
      }
    }
    expect(
      offenders,
      `Allowlist references components not present in main.ts route table: ${offenders.join(", ")}. Remove these entries; they are stale.`,
    ).toEqual([]);
  });

  it("every entry in ALLOWLIST_NO_MOUNT carries a non-empty reason", () => {
    const offenders: string[] = [];
    for (const entry of ALLOWLIST_NO_MOUNT) {
      if (!entry.reason || entry.reason.trim().length < 20) {
        offenders.push(entry.component);
      }
    }
    expect(
      offenders,
      `Allowlist entries must carry a substantive reason (>=20 chars): ${offenders.join(", ")}.`,
    ).toEqual([]);
  });

  it("no allowlisted component sneaks in a bespoke <nav aria-label='Breadcrumb'> implementation", () => {
    // A component on the allowlist is granted "no breadcrumb today";
    // a bespoke nav would still be a holdout (the E5 escalation
    // condition). Catch it on the allowlist path too.
    const offenders: string[] = [];
    for (const entry of ALLOWLIST_NO_MOUNT) {
      const filePath = resolve(routesDir, entry.component);
      let source: string;
      try {
        source = readFileSync(filePath, "utf-8");
      } catch {
        continue; // Stale-entry check covers existence.
      }
      if (BESPOKE_NAV_RE.test(source)) offenders.push(entry.component);
    }
    expect(
      offenders,
      `Allowlisted components must not carry a bespoke <nav aria-label="Breadcrumb"> block; replace with the shared component and remove from the allowlist: ${offenders.join(", ")}.`,
    ).toEqual([]);
  });

  const allowedSet = new Set(ALLOWLIST_NO_MOUNT.map((e) => e.component));
  const componentsToCheck = [...uniqueComponents].filter(
    (c) => !allowedSet.has(c),
  );

  // Per-component pin so a regression names the offending route.
  for (const component of componentsToCheck) {
    it(`route ${component} imports the shared Breadcrumb component`, () => {
      const filePath = resolve(routesDir, component);
      const source = readFileSync(filePath, "utf-8");
      expect(
        source.includes(SHARED_IMPORT),
        `${component} declares 'crumbs:' in main.ts but does not import '${SHARED_IMPORT}'. Either add the import + mount, or add the component to ALLOWLIST_NO_MOUNT with a reason.`,
      ).toBe(true);
    });

    it(`route ${component} renders the shared <Breadcrumb> mount`, () => {
      const filePath = resolve(routesDir, component);
      const source = readFileSync(filePath, "utf-8");
      expect(
        SHARED_MOUNT_RE.test(source),
        `${component} declares 'crumbs:' in main.ts and imports Breadcrumb, but does not render '<Breadcrumb' anywhere in its markup. Add the mount (typically '<Breadcrumb {crumbs} />' immediately before <main>).`,
      ).toBe(true);
    });

    it(`route ${component} does not carry a bespoke <nav aria-label='Breadcrumb'> block`, () => {
      const filePath = resolve(routesDir, component);
      const source = readFileSync(filePath, "utf-8");
      expect(
        BESPOKE_NAV_RE.test(source),
        `${component} carries a bespoke <nav aria-label="Breadcrumb"> block; replace it with the shared <Breadcrumb {crumbs} /> primitive.`,
      ).toBe(false);
    });
  }

  it("no route file in src/routes/ carries a bespoke <nav aria-label='Breadcrumb'> block", () => {
    // Whole-tree sweep - catches a future bespoke breadcrumb on a
    // route file the parser might miss (e.g. if main.ts ever uses
    // string-keyed component lookup instead of direct imports).
    const offenders: string[] = [];
    for (const entry of readdirSync(routesDir)) {
      if (!entry.endsWith(".svelte")) continue;
      const filePath = resolve(routesDir, entry);
      const source = readFileSync(filePath, "utf-8");
      if (BESPOKE_NAV_RE.test(source)) offenders.push(entry);
    }
    expect(
      offenders,
      `Bespoke <nav aria-label="Breadcrumb"> blocks found in routes/: ${offenders.join(", ")}. Replace with the shared <Breadcrumb {crumbs} /> primitive.`,
    ).toEqual([]);
  });
});
