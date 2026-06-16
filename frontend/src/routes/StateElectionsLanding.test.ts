// Contract test for StateElectionsLanding.svelte (R2 of
// TODO/20260615-state-election-event-page-redesign-plan.md).
//
// Why a static-source test, not a DOM-mount test:
//   `@testing-library/svelte` is NOT a project dep; vitest runs node-env;
//   the route renders behind DuckDB-WASM + an async fetchElectionEvents
//   loader, both of which would dominate test time. The four
//   conditional-rendering invariants from the plan-doc are template-
//   author-time facts (Svelte 5 syntax visible in the source), so a
//   readFileSync + grep test catches a regression in <10 ms with
//   precise failure messages — strictly stronger than a DOM mount.
//   See user-memory lessons-2026-06-12 "static-source contract tests
//   beat DOM-mount tests for 'this string must not appear' gates".
//
// The invariants we lock in here are the four conditional-rendering
// cases the plan-doc names (TODO/20260615-state-election-event-page-
// redesign-plan.md Section 3 row R2):
//   1. Two parallel tables (Vidhan Sabha / Lok Sabha) — each table
//      guarded by `length > 0` so empty arms render no table chrome.
//   2. Single empty-state block guarded by BOTH arms empty.
//   3. Last-viewed badge guarded by isLastViewed(ev) AND carrying the
//      stable testid prefix the e2e + admin smoke can latch on to.
//   4. Year-cell renders an <a href={link.stateElection(...)}> link
//      (per-event detail page is the citizen's onward path).
// And the connector wiring:
//   5. readLastEvent(params.state) called at mount (the read-pass for
//      the localStorage memory the StateElection write-pass writes).

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const HERE = fileURLToPath(new URL(".", import.meta.url));
const SOURCE_PATH = resolve(HERE, "StateElectionsLanding.svelte");
const SOURCE = readFileSync(SOURCE_PATH, "utf8");
// Split off the instance-script comment block so post-mortem prose in
// the script header can't trip the template grep.
const TEMPLATE = SOURCE.slice(SOURCE.lastIndexOf("</script>"));

describe("StateElectionsLanding contract (static source)", () => {
  it("imports readLastEvent from the canonical last-event-memory module", () => {
    expect(
      SOURCE.includes(
        'import { readLastEvent, type LastEventMemory } from "../lib/elections/last-event-memory";',
      ),
      "readLastEvent + LastEventMemory must come from the canonical helper module; do not inline another localStorage call. See last-event-memory.ts.",
    ).toBe(true);
  });

  it("calls readLastEvent(params.state) at mount (the read-pass)", () => {
    expect(
      SOURCE.includes("readLastEvent(params.state)"),
      "The landing must read the per-state last-viewed memo at mount so the badge can render on the matching year-link.",
    ).toBe(true);
  });

  it("renders the assembly table ONLY when assembly_events.length > 0 (Vidhan Sabha guard + testid)", () => {
    expect(
      TEMPLATE.includes("{#if assembly_events.length > 0}"),
      "Assembly table must be guarded by `assembly_events.length > 0`; an empty arm must render no table chrome at all.",
    ).toBe(true);
    expect(
      TEMPLATE.includes('data-testid="state-elections-landing-assembly-table"'),
      "Assembly section must carry the stable testid `state-elections-landing-assembly-table`.",
    ).toBe(true);
  });

  it("renders the parliament table ONLY when parliament_events.length > 0 (Lok Sabha guard + testid)", () => {
    expect(
      TEMPLATE.includes("{#if parliament_events.length > 0}"),
      "Parliament table must be guarded by `parliament_events.length > 0`; an empty arm must render no table chrome at all.",
    ).toBe(true);
    expect(
      TEMPLATE.includes(
        'data-testid="state-elections-landing-parliament-table"',
      ),
      "Parliament section must carry the stable testid `state-elections-landing-parliament-table`.",
    ).toBe(true);
  });

  it("renders the empty-state block ONLY when BOTH arms are empty", () => {
    expect(
      TEMPLATE.includes(
        "{#if assembly_events.length === 0 && parliament_events.length === 0}",
      ),
      "Empty-state must be guarded by BOTH arms empty; a state with parliament-only or assembly-only events must show the populated table, not the empty-state copy.",
    ).toBe(true);
    expect(
      TEMPLATE.includes('data-testid="state-elections-landing-empty"'),
      "Empty-state must carry the stable testid `state-elections-landing-empty`.",
    ).toBe(true);
  });

  it("renders the Last viewed badge guarded by isLastViewed(ev), with stable testid prefix and exact copy", () => {
    expect(
      TEMPLATE.includes("{#if isLastViewed(ev)}"),
      "Badge must be guarded by `isLastViewed(ev)`; otherwise every row would render the badge.",
    ).toBe(true);
    expect(
      TEMPLATE.includes(
        "data-testid={`state-elections-landing-last-viewed-${ev.event_id}`}",
      ),
      "Badge must carry the per-event testid `state-elections-landing-last-viewed-<event_id>` so the e2e + browser smoke can target the exact row.",
    ).toBe(true);
    expect(
      TEMPLATE.includes(">Last viewed</span>"),
      'Badge copy is the literal English string "Last viewed" (No-Hindi citizen-chrome policy, see ADR-0037).',
    ).toBe(true);
  });

  it("isLastViewed matches on event_id (not body, not year)", () => {
    expect(
      SOURCE.includes("return last_viewed?.event_id === ev.event_id;"),
      "isLastViewed must compare event_id specifically; comparing on body would badge every event of the same body, year would alias across bodies.",
    ).toBe(true);
  });

  it("year cells link to the per-event detail page via link.stateElection(...)", () => {
    expect(
      TEMPLATE.includes("href={link.stateElection(params.state, ev.event_id)}"),
      "Year cells must use the link helper `link.stateElection(state, event_id)` so the URL grammar stays the route registration's single source of truth (ADR-0028 / url-grammar.md).",
    ).toBe(true);
  });
});
