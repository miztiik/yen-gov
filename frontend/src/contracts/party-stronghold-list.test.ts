/**
 * Row E of TODO/20260617-party-page-polish-and-cdn-config-plan.md
 * (Jony P1 + Citizen) - the strongholds lists on /parties/<slug>.
 *
 * The two inline strongholds `<ul>` blocks (a dense run-on
 * `formatStrongholdTally` sentence per row inside a heavy bordered
 * box) are replaced by the shared `StrongholdList.svelte` component:
 * a two-line row hierarchy + a colour-coded strike-rate badge, capped
 * to the top-5 with a "Show all" disclosure, sorted best-to-least by
 * strike-rate.
 *
 * The project does NOT install `@testing-library/svelte`, so - exactly
 * like `party-meta-wikipedia.test.ts` and every other Tier-A contract
 * test under `frontend/src/contracts/` - the contract is enforced on
 * the source text of the components directly (the runtime is also
 * covered by the e2e spec + the CLAUDE.md section 13 in-browser smoke).
 *
 * Regression guards (each a separate `it` so one failure names the
 * exact rollback that needs fixing).
 */
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const PARTY_SVELTE = resolve(here, "..", "routes", "Party.svelte");
const STRONGHOLD_LIST = resolve(
  here,
  "..",
  "lib",
  "parties",
  "StrongholdList.svelte",
);

const PARTY_SOURCE = readFileSync(PARTY_SVELTE, "utf-8");
const LIST_SOURCE = readFileSync(STRONGHOLD_LIST, "utf-8");

// The strongholds <section ...>...</section> block, anchored on its
// data-testid so a regression elsewhere in Party.svelte does not
// poison these assertions. No nested <section> exists inside it, so
// the lazy `[\s\S]*?</section>` stops at the section's own close.
const STRONGHOLDS_SECTION = PARTY_SOURCE.match(
  /data-testid="party-strongholds"[\s\S]*?<\/section>/,
)?.[0];

describe("Party.svelte strongholds section (Row E - StrongholdList)", () => {
  it("finds the party-strongholds section block", () => {
    expect(
      STRONGHOLDS_SECTION,
      'strongholds <section data-testid="party-strongholds"> not found in Party.svelte',
    ).toBeTruthy();
  });

  it("no longer renders an inline <ul> in the strongholds section", () => {
    const section = STRONGHOLDS_SECTION as string;
    expect(section).not.toMatch(/<ul[\s>]/);
  });

  it("no longer calls the retired formatStrongholdTally one-liner", () => {
    expect(PARTY_SOURCE).not.toMatch(/formatStrongholdTally/);
  });

  it("mounts <StrongholdList> exactly twice (Parliament + State Assembly)", () => {
    const mounts = PARTY_SOURCE.match(/<StrongholdList\b/g) ?? [];
    expect(mounts).toHaveLength(2);
    // ...fed by the two view-model arrays.
    expect(PARTY_SOURCE).toMatch(
      /<StrongholdList\s+rows=\{view_model\.ls_strongholds\}/,
    );
    expect(PARTY_SOURCE).toMatch(
      /<StrongholdList\s+rows=\{view_model\.vs_strongholds\}/,
    );
  });
});

describe("StrongholdList.svelte (Row E)", () => {
  it("defaults max_visible to 5", () => {
    expect(LIST_SOURCE).toMatch(/max_visible\s*=\s*5\b/);
  });

  it("drops the heavy outer box for a divide-y row separator", () => {
    expect(LIST_SOURCE).toMatch(/divide-y/);
    // The retired box chrome (border + rounded + bg-white) is gone.
    expect(LIST_SOURCE).not.toMatch(/border border-slate-200 rounded bg-white/);
  });

  it("renders the constituency as an <a href={s.href}> when href is set", () => {
    expect(LIST_SOURCE).toMatch(/\{#if s\.href\}[\s\S]*?<a\s+href=\{s\.href\}/);
  });

  it("renders a strike-rate badge with the wins/contested + percent format", () => {
    // Compact tabular-nums "{wins}/{contested} . {rate}%".
    expect(LIST_SOURCE).toMatch(/tabular-nums/);
    expect(LIST_SOURCE).toMatch(
      /\{s\.wins\}\/\{s\.contested\}\s*&middot;\s*\{rate\}%/,
    );
  });

  it("colour-codes the badge with the sanctioned emerald/amber/rose tiers", () => {
    expect(LIST_SOURCE).toMatch(/bg-emerald-100 text-emerald-900 border-emerald-300/);
    expect(LIST_SOURCE).toMatch(/bg-amber-100 text-amber-900 border-amber-300/);
    expect(LIST_SOURCE).toMatch(/bg-rose-100 text-rose-900 border-rose-300/);
  });

  it("caps with an inline 'Show all N' disclosure toggling a $state boolean", () => {
    expect(LIST_SOURCE).toMatch(/let show_all = \$state\(false\)/);
    expect(LIST_SOURCE).toMatch(/Show all \{rows\.length\}/);
  });
});
