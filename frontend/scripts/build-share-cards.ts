/**
 * Build-time share-card generator for R7 of
 * TODO/20260615-state-election-event-page-redesign-plan.md
 * (J-elevated-14).
 *
 * Runs as part of `bun run build`. Reads:
 *   - datasets/data/marts/elections/event_summary.csv (one row per
 *     (event_id, state_code) - 313 rows as of 2026-06-15)
 *   - datasets/data/entities/parties.csv (party_id -> short, brand_colour)
 *   - datasets/data/entities/geo.csv (slug, name, aliases - S## codes
 *     are pipe-separated inside the aliases column)
 *   - datasets/data/entities/state_codes.csv (lgd_state_id -> slug + name)
 *   - datasets/data/entities/source.csv (source_id -> producer)
 *
 * Produces one 1200x630 PNG per row at
 *   frontend/public/share/{state-slug}/{event_id}.png
 * (national-scope rows write to share/national/).
 *
 * The PNGs ship as static assets the OG-card unfurl uses (WhatsApp,
 * Twitter, LinkedIn, Signal). The pure SVG composition lives in
 * `frontend/src/lib/share-cards/build-svg.ts` (testable); the
 * per-row projection in `plan.ts` (testable); this file is the I/O
 * + rasterisation orchestrator.
 *
 * Idempotent: re-running overwrites the same PNGs. Parallelised by
 * the @resvg/resvg-js internal worker pool; we just iterate.
 *
 * Why @resvg/resvg-js over @vercel/og: pure-WASM, no native binary
 * deps; @vercel/og bundles satori (a TSX-to-SVG renderer) we don't
 * need - we write SVG directly via build-svg.ts.
 *
 * Failure mode: any row that can't resolve (state_code missing,
 * etc.) is logged + skipped; the build continues. The final report
 * counts written + skipped + errors; non-zero error count fails the
 * build so a regression surfaces at CI.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { Resvg } from "@resvg/resvg-js";

import { buildShareCardSvg } from "../src/lib/share-cards/build-svg";
import {
  buildCardPlan,
  type EventSummaryRowForCard,
  type PartyRowForCard,
  type SourceRowForCard,
  type StateRowForCard,
} from "../src/lib/share-cards/plan";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(SCRIPT_DIR, "../..");
const MART_PATH = join(REPO_ROOT, "datasets/data/marts/elections/event_summary.csv");
const PARTIES_PATH = join(REPO_ROOT, "datasets/data/entities/parties.csv");
const GEO_PATH = join(REPO_ROOT, "datasets/data/entities/geo.csv");
const STATE_CODES_PATH = join(REPO_ROOT, "datasets/data/entities/state_codes.csv");
const SOURCE_PATH = join(REPO_ROOT, "datasets/data/entities/source.csv");
const OUTPUT_ROOT = resolve(SCRIPT_DIR, "../public");

interface CsvRow {
  [column: string]: string;
}

/** Minimal RFC-4180 CSV parser: supports quoted fields with embedded
 *  commas and doubled quotes. The on-disk yen-gov CSVs are all
 *  RFC-4180-compliant per the writer contract. */
function parseCsv(text: string): { headers: string[]; rows: CsvRow[] } {
  const lines: string[][] = [];
  let row: string[] = [];
  let field = "";
  let in_quotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (in_quotes) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          in_quotes = false;
        }
      } else {
        field += c;
      }
    } else {
      if (c === '"') {
        in_quotes = true;
      } else if (c === ",") {
        row.push(field);
        field = "";
      } else if (c === "\n") {
        row.push(field);
        lines.push(row);
        row = [];
        field = "";
      } else if (c === "\r") {
        // skip
      } else {
        field += c;
      }
    }
  }
  if (field.length > 0 || row.length > 0) {
    row.push(field);
    lines.push(row);
  }
  if (lines.length === 0) return { headers: [], rows: [] };
  const headers = lines[0];
  const rows: CsvRow[] = [];
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].length === 1 && lines[i][0] === "") continue;
    const r: CsvRow = {};
    for (let j = 0; j < headers.length; j++) {
      r[headers[j]] = lines[i][j] ?? "";
    }
    rows.push(r);
  }
  return { headers, rows };
}

function loadEventSummary(): EventSummaryRowForCard[] {
  const text = readFileSync(MART_PATH, "utf8");
  const { rows } = parseCsv(text);
  return rows.map((r): EventSummaryRowForCard => ({
    event_id: r.event_id,
    state_code: r.state_code === "" ? null : r.state_code,
    scope: r.scope as EventSummaryRowForCard["scope"],
    kind: r.kind as EventSummaryRowForCard["kind"],
    polled_on: r.polled_on,
    leading_party_id: r.leading_party_id === "" ? null : r.leading_party_id,
    seats_won: Number.parseInt(r.seats_won, 10) || 0,
    seats_contested: Number.parseInt(r.seats_contested, 10) || 0,
    source_id: r.source_id,
  }));
}

function loadParties(): Map<string, PartyRowForCard> {
  const text = readFileSync(PARTIES_PATH, "utf8");
  const { rows } = parseCsv(text);
  const out = new Map<string, PartyRowForCard>();
  for (const r of rows) {
    if (!r.party_id || !r.short) continue;
    out.set(r.party_id, {
      party_id: r.party_id,
      short: r.short,
      brand_colour: r.brand_colour || "",
    });
  }
  return out;
}

function loadStates(): Map<string, StateRowForCard> {
  // The ECI state code (e.g. "S13") is pipe-separated inside the
  // geo.csv `aliases` column for every row with entity_kind=state.
  // state_codes.csv has the canonical (lgd, slug, name) tuple; we
  // join the two so the lookup map is keyed by ECI code.
  const geo_text = readFileSync(GEO_PATH, "utf8");
  const { rows: geo_rows } = parseCsv(geo_text);
  const slug_to_eci = new Map<string, string>();
  for (const r of geo_rows) {
    if (r.entity_kind !== "state") continue;
    const aliases = r.aliases.split("|").map((s) => s.trim());
    for (const a of aliases) {
      if (/^[SU]\d{2}$/.test(a)) {
        slug_to_eci.set(r.entity_id, a);
        break;
      }
    }
  }

  const codes_text = readFileSync(STATE_CODES_PATH, "utf8");
  const { rows: codes_rows } = parseCsv(codes_text);
  const out = new Map<string, StateRowForCard>();
  for (const r of codes_rows) {
    const eci = slug_to_eci.get(r.slug);
    if (!eci) continue;
    out.set(eci, {
      state_code: eci,
      state_name: r.lgd_name,
      state_slug: r.slug,
    });
  }
  return out;
}

function loadSources(): Map<string, SourceRowForCard> {
  const text = readFileSync(SOURCE_PATH, "utf8");
  const { rows } = parseCsv(text);
  const out = new Map<string, SourceRowForCard>();
  for (const r of rows) {
    if (!r.source_id) continue;
    out.set(r.source_id, {
      source_id: r.source_id,
      producer: r.producer || "Election Commission of India",
    });
  }
  return out;
}

function main(): void {
  // eslint-disable-next-line no-console
  console.log("[share-cards] reading datasets...");
  const mart = loadEventSummary();
  const parties = loadParties();
  const states = loadStates();
  const sources = loadSources();

  // eslint-disable-next-line no-console
  console.log(
    `[share-cards] inputs: ${mart.length} mart rows, ${parties.size} parties, ${states.size} states, ${sources.size} sources`,
  );

  let written = 0;
  let skipped = 0;
  let errors = 0;

  for (const row of mart) {
    const plan = buildCardPlan({
      row,
      parties_by_id: parties,
      states_by_code: states,
      sources_by_id: sources,
    });
    if (!plan) {
      skipped++;
      continue;
    }
    try {
      const svg = buildShareCardSvg(plan.card);
      const resvg = new Resvg(svg, {
        fitTo: { mode: "width", value: 1200 },
        background: "#ffffff",
      });
      const png = resvg.render().asPng();
      const out_path = join(OUTPUT_ROOT, plan.output_rel_path);
      const out_dir = dirname(out_path);
      if (!existsSync(out_dir)) mkdirSync(out_dir, { recursive: true });
      writeFileSync(out_path, png);
      written++;
    } catch (e: unknown) {
      errors++;
      // eslint-disable-next-line no-console
      console.error(
        `[share-cards] failed to render ${plan.output_rel_path}:`,
        e instanceof Error ? e.message : e,
      );
    }
  }

  // eslint-disable-next-line no-console
  console.log(
    `[share-cards] done: ${written} written, ${skipped} skipped (unresolvable), ${errors} errors`,
  );

  if (errors > 0) {
    // eslint-disable-next-line no-console
    console.error("[share-cards] non-zero error count; failing the build");
    process.exit(1);
  }
}

main();
