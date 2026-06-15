// Source-level regression pin for RecognitionStrip.svelte (PR-5 D2).
//
// Plan-doc: TODO/20260615-party-page-citizen-fixes-plan.md PR-5.
//
// Why source-level (read-from-disk) instead of a rendered-component
// vitest: the existing test surface for this component is the helper
// `recognition-strip.test.ts` (pure functions). PR-5 D2 is template-
// level only - it adds a leading `<img>` glyph when `symbol_url` is
// non-null and falls back to the existing TopicIcon info-glyph when
// null. The two branches are easy and deterministic to assert by
// grepping the .svelte source, and that pin survives a Svelte
// version bump that would otherwise force us to thread a real
// Svelte-runtime test rig just for this one component.
//
// What this test pins:
//   1. The Props interface carries `symbol_url?: string | null` -
//      otherwise the prop reaches the destructure as `undefined` and
//      Svelte 5 throws.
//   2. The template carries BOTH the `<img>` branch (with the canonical
//      data-testid that the PR-5 section-13 smoke queries) AND the
//      TopicIcon `name="info"` fallback - so a future agent cannot
//      silently drop one branch without going red here.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { describe, expect, it } from "vitest";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SRC = readFileSync(
  path.join(__dirname, "RecognitionStrip.svelte"),
  "utf8",
);

describe("RecognitionStrip.svelte - PR-5 D2 template-level pins", () => {
  it("Props interface declares the optional symbol_url prop", () => {
    // Either form is acceptable; the union must allow null.
    const hasSymbolUrlProp =
      /symbol_url\??\s*:\s*string\s*\|\s*null/.test(SRC);
    expect(hasSymbolUrlProp).toBe(true);
  });

  it("destructures symbol_url from $props with a null default", () => {
    // `let { party_id, symbol_url = null } = $props();` shape -
    // protects callers that omit the prop from triggering the truthy
    // `{#if symbol_url}` branch with an `undefined` value.
    const hasDefaultedDestructure =
      /symbol_url\s*=\s*null/.test(SRC) && /\$props\(\)/.test(SRC);
    expect(hasDefaultedDestructure).toBe(true);
  });

  it("renders the <img> branch with the canonical data-testid when symbol_url is non-null", () => {
    // The section-13 browser smoke queries
    // `[data-testid="party-recognition-symbol-img"]`; this pin keeps
    // the testid from drifting silently.
    expect(SRC).toMatch(/\{#if symbol_url\}/);
    expect(SRC).toMatch(
      /data-testid="party-recognition-symbol-img"/,
    );
    // Render-as-img check: the img tag carries the resolved URL and
    // an empty alt (decorative; the citizen text already labels it).
    expect(SRC).toMatch(/<img\b[\s\S]*?src=\{symbol_url\}/);
    expect(SRC).toMatch(/alt=""/);
  });

  it("falls back to the TopicIcon info-glyph when symbol_url is null", () => {
    // `{:else} <TopicIcon name="info" .../> {/if}` shape - keeps the
    // pre-PR-5 visual exactly for special parties without a
    // symbol_asset (e.g. NCP).
    expect(SRC).toMatch(/\{:else\}/);
    expect(SRC).toMatch(/<TopicIcon\b[\s\S]*?name="info"/);
  });

  it("preserves the outer render-nothing guard on the strip helper", () => {
    // `{#if strip}` survives - non-special parties still render
    // nothing at all, even with `symbol_url` set.
    expect(SRC).toMatch(/\{#if strip\}/);
  });
});
