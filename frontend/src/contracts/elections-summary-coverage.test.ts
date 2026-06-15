// Tier-A contract test for the event_summary mart (PR-E3 of
// TODO/20260615-elections-redesign-plan.md).
//
// Reads the SHIPPED `datasets/data/marts/elections/event_summary.csv`
// + `datasets/taxonomy/election_events.json` from disk (Node-side; no
// DuckDB-WASM). Enforces the four invariants Hans + Fowler + Gregor
// signed off on in plan Section 0:
//
//   1. Composite PK uniqueness: `(event_id, state_code)` is unique
//      across all rows (state_code is empty-string for scope=national
//      after CSV serialisation; that maps to the SQL NULL value).
//   2. FK to election_events.json: every (event_id, state_code) row
//      references an event_id that exists in the catalogue for the
//      matching state (or any state for scope=national).
//   3. Turnout sanity: `0 <= turnout_pct <= 100` when not null.
//   4. Seat sanity: `seats_won + (runner_up_seats or 0) <= seats_contested`.
//
// This file is intentionally small — the per-row coverage matrix
// belongs in the writer's pytest (PR-E2); this contract enforces only
// the shape invariants the view-models depend on.

import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// `frontend/src/contracts/<this>.test.ts` -> 3 hops up to `frontend/`,
// 1 more up to repo root. Matches the pattern in
// `datasets-conform.test.ts`.
const REPO_ROOT = resolve(
  fileURLToPath(new URL(".", import.meta.url)),
  "..",
  "..",
  "..",
);
const MART_PATH = resolve(
  REPO_ROOT,
  "datasets/data/marts/elections/event_summary.csv",
);
const CATALOGUE_PATH = resolve(
  REPO_ROOT,
  "datasets/taxonomy/election_events.json",
);

interface MartRow {
  event_id: string;
  state_code: string; // empty string in CSV when SQL NULL
  scope: string;
  kind: string;
  polled_on: string;
  leading_party_id: string;
  seats_won: number;
  seats_contested: number;
  turnout_pct: number | null;
  runner_up_party_id: string;
  runner_up_seats: number | null;
  source_id: string;
}

function parseRows(): MartRow[] {
  const text = readFileSync(MART_PATH, "utf-8");
  const lines = text.split("\n").filter((l) => l.length > 0);
  const header = lines[0].split(",");
  const out: MartRow[] = [];
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split(",");
    const get = (n: string): string => {
      const idx = header.indexOf(n);
      return idx >= 0 ? cols[idx] ?? "" : "";
    };
    const num = (n: string): number => {
      const v = get(n);
      return v === "" ? 0 : Number(v);
    };
    const numOrNull = (n: string): number | null => {
      const v = get(n);
      return v === "" ? null : Number(v);
    };
    out.push({
      event_id: get("event_id"),
      state_code: get("state_code"),
      scope: get("scope"),
      kind: get("kind"),
      polled_on: get("polled_on"),
      leading_party_id: get("leading_party_id"),
      seats_won: num("seats_won"),
      seats_contested: num("seats_contested"),
      turnout_pct: numOrNull("turnout_pct"),
      runner_up_party_id: get("runner_up_party_id"),
      runner_up_seats: numOrNull("runner_up_seats"),
      source_id: get("source_id"),
    });
  }
  return out;
}

interface CatalogueEvent {
  event_id: string;
  kind: string;
  polled_on: string;
}

interface CatalogueShape {
  states: Record<string, CatalogueEvent[]>;
}

function parseCatalogue(): CatalogueShape {
  const text = readFileSync(CATALOGUE_PATH, "utf-8");
  return JSON.parse(text) as CatalogueShape;
}

describe("event_summary.csv contract", () => {
  it("ships at the canonical mart path", () => {
    expect(existsSync(MART_PATH)).toBe(true);
  });

  it("carries the expected 12-column header", () => {
    const text = readFileSync(MART_PATH, "utf-8");
    const header = text.split("\n")[0];
    expect(header).toBe(
      "event_id,state_code,scope,kind,polled_on,leading_party_id,seats_won,seats_contested,turnout_pct,runner_up_party_id,runner_up_seats,source_id",
    );
  });

  it("has unique composite PK (event_id, state_code)", () => {
    const rows = parseRows();
    const keys = rows.map((r) => `${r.event_id}|${r.state_code}`);
    const dupes = keys.filter((k, i) => keys.indexOf(k) !== i);
    expect(dupes).toEqual([]);
  });

  it("every (event_id, state_code) row FKs into election_events.json", () => {
    const rows = parseRows();
    const catalogue = parseCatalogue();
    // Build (state_code -> Set<event_id>) and a global set for national.
    const byState = new Map<string, Set<string>>();
    const allParliament = new Set<string>();
    for (const [code, evts] of Object.entries(catalogue.states)) {
      const set = new Set<string>();
      for (const e of evts) {
        set.add(e.event_id);
        if (e.kind === "parliament") allParliament.add(e.event_id);
      }
      byState.set(code, set);
    }
    const missing: string[] = [];
    for (const r of rows) {
      if (r.scope === "national") {
        if (!allParliament.has(r.event_id)) {
          missing.push(`${r.event_id}|national`);
        }
        continue;
      }
      const set = byState.get(r.state_code);
      if (!set || !set.has(r.event_id)) {
        missing.push(`${r.event_id}|${r.state_code}`);
      }
    }
    expect(missing).toEqual([]);
  });

  it("turnout_pct is in [0, 100] when not null", () => {
    const rows = parseRows();
    const offenders = rows.filter(
      (r) =>
        r.turnout_pct !== null &&
        (r.turnout_pct < 0 || r.turnout_pct > 100),
    );
    expect(offenders).toEqual([]);
  });

  it("seats_won + runner_up_seats <= seats_contested", () => {
    const rows = parseRows();
    const offenders = rows.filter((r) => {
      const ru = r.runner_up_seats ?? 0;
      return r.seats_won + ru > r.seats_contested;
    });
    expect(offenders).toEqual([]);
  });

  it("scope is one of {national, state}", () => {
    const rows = parseRows();
    const bad = rows.filter((r) => r.scope !== "national" && r.scope !== "state");
    expect(bad).toEqual([]);
  });

  it("national rows have empty state_code; state rows have non-empty state_code", () => {
    const rows = parseRows();
    const inconsistent = rows.filter((r) => {
      if (r.scope === "national") return r.state_code !== "";
      if (r.scope === "state") return r.state_code === "";
      return true;
    });
    expect(inconsistent).toEqual([]);
  });
});
