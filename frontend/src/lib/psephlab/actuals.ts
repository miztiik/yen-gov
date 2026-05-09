// Loaders that turn datasets/ JSON into the Tallies shape the engine expects.
//
// Reads from `results.sqlite` via the cached `getDb` (lib/sql.ts) — one query
// returns every AC and candidate for a state. Faster than parsing 234 per-AC
// JSON files, and we already incurred the wasm cost on the Explore page.
//
// Tallies are cached per (event, state) at module scope: they're frozen once
// loaded (actuals never change) so giving the same object reference back on
// repeat calls is safe and lets downstream `$derived` skip work.

import { getDb } from "../sql";
import type { AcTally, CandidateTally, Tallies } from "./types";

const cache = new Map<string, Promise<Tallies>>();

function key(event: string, state: string): string {
  return `${event}/${state}`;
}

export function loadActuals(event: string, state: string): Promise<Tallies> {
  const k = key(event, state);
  const hit = cache.get(k);
  if (hit) return hit;

  const p = (async (): Promise<Tallies> => {
    const db = await getDb(event, state);
    // Pull constituencies and candidates in two queries — cheaper than one
    // join with redundant constituency rows multiplied by candidate count.
    const cs = db.exec(
      `SELECT eci_no, name, votes_polled FROM constituencies ORDER BY eci_no;`,
    );
    const cands = db.exec(
      `SELECT constituency_eci_no, name, party_eci_code, party_short, votes, is_nota
       FROM candidates ORDER BY constituency_eci_no, rank;`,
    );

    const acs: AcTally[] = [];
    const ac_index = new Map<number, AcTally>();
    if (cs[0]) {
      for (const row of cs[0].values) {
        const ac: AcTally = {
          eci_no: Number(row[0]),
          name: String(row[1] ?? ""),
          // votes_polled doubles as our electorate proxy until we ship a
          // separate electors column. Turnout-uplift mutations (deferred to
          // v2 per psephlab.md) will need a real value here.
          electorate: Number(row[2] ?? 0),
          candidates: [],
        };
        acs.push(ac);
        ac_index.set(ac.eci_no, ac);
      }
    }

    if (cands[0]) {
      for (const row of cands[0].values) {
        const eci_no = Number(row[0]);
        const ac = ac_index.get(eci_no);
        if (!ac) continue;
        const name = String(row[1] ?? "");
        const party_code = row[2] == null ? null : String(row[2]);
        const party_short = String(row[3] ?? "");
        const votes = Number(row[4] ?? 0);
        const is_nota = Number(row[5] ?? 0) === 1;
        const c: CandidateTally = {
          party_eci_code: is_nota
            ? "NOTA"
            : party_code ?? "IND",
          party_short: party_short || (is_nota ? "NOTA" : "IND"),
          name,
          votes,
        };
        ac.candidates.push(c);
      }
    }

    const tallies: Tallies = {
      scope: { country: "IN", state, election: event },
      acs,
    };
    Object.freeze(tallies);
    Object.freeze(tallies.acs);
    return tallies;
  })();

  cache.set(k, p);
  p.catch(() => cache.delete(k));
  return p;
}
