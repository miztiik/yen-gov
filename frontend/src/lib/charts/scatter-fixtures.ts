// Fixture data for Scatter.test.ts + the dev sandbox (PR-W4c, 2026-06-10).
//
// 50 hand-authored ScatterDatum rows spanning multiple states / parties /
// reservations / body types / margin bands, so the model tests can prove:
//   1. Unfiltered: 50 rows surface.
//   2. Filter narrowing: e.g. reservation=ST narrows to the 8 ST rows;
//      margin_band=lt2 narrows to the 6 close-fight rows.
//   3. Mixed parties + states exercise the colour resolver fallover.
//
// Numbers are not drawn from any specific year — these are mock rows.
// Do NOT cross-cite them as real election outcomes.

import type { ScatterDatum } from "./scatter-model";

interface FixtureSpec {
  entity_id: string;
  state_slug: string;
  constituency_slug: string;
  constituency_name: string;
  event_id: string;
  turnout_pct: number;
  margin_pct: number;
  electors: number;
  winner_party_id: string;
  winner_party_short: string;
  reservation: "GEN" | "SC" | "ST";
  body: "parliament" | "assembly";
}

const SPECS: ReadonlyArray<FixtureSpec> = [
  // 25 PCs (parliament). Distributed across 6 states + 6 parties.
  // 16 GEN / 5 SC / 4 ST. 3 close (<2%), 5 narrow (2-5%), 8 moderate
  // (5-10%), 9 wide (>10%).
  { entity_id: "PC-1",  state_slug: "tamil-nadu", constituency_slug: "chennai-south", constituency_name: "Chennai South", event_id: "general-2024", turnout_pct: 58.3, margin_pct: 12.4, electors: 1_843_211, winner_party_id: "parties.IN.DMK", winner_party_short: "DMK", reservation: "GEN", body: "parliament" },
  { entity_id: "PC-2",  state_slug: "tamil-nadu", constituency_slug: "chennai-north", constituency_name: "Chennai North", event_id: "general-2024", turnout_pct: 53.1, margin_pct: 18.2, electors: 1_710_443, winner_party_id: "parties.IN.DMK", winner_party_short: "DMK", reservation: "GEN", body: "parliament" },
  { entity_id: "PC-3",  state_slug: "tamil-nadu", constituency_slug: "thiruvallur",   constituency_name: "Thiruvallur",   event_id: "general-2024", turnout_pct: 66.4, margin_pct:  6.7, electors: 1_614_002, winner_party_id: "parties.IN.DMK", winner_party_short: "DMK", reservation: "SC",  body: "parliament" },
  { entity_id: "PC-4",  state_slug: "tamil-nadu", constituency_slug: "kanyakumari",   constituency_name: "Kanyakumari",   event_id: "general-2024", turnout_pct: 72.8, margin_pct:  1.4, electors: 1_499_810, winner_party_id: "parties.IN.INC", winner_party_short: "INC", reservation: "GEN", body: "parliament" },
  { entity_id: "PC-5",  state_slug: "tamil-nadu", constituency_slug: "salem",         constituency_name: "Salem",         event_id: "general-2024", turnout_pct: 70.2, margin_pct: 22.6, electors: 1_734_220, winner_party_id: "parties.IN.DMK", winner_party_short: "DMK", reservation: "GEN", body: "parliament" },

  { entity_id: "PC-6",  state_slug: "karnataka",  constituency_slug: "bangalore-south",constituency_name: "Bangalore South",event_id: "general-2024", turnout_pct: 55.5, margin_pct: 14.9, electors: 2_410_315, winner_party_id: "parties.IN.BJP", winner_party_short: "BJP", reservation: "GEN", body: "parliament" },
  { entity_id: "PC-7",  state_slug: "karnataka",  constituency_slug: "bangalore-north",constituency_name: "Bangalore North",event_id: "general-2024", turnout_pct: 54.1, margin_pct:  3.2, electors: 2_322_103, winner_party_id: "parties.IN.INC", winner_party_short: "INC", reservation: "GEN", body: "parliament" },
  { entity_id: "PC-8",  state_slug: "karnataka",  constituency_slug: "mysuru",         constituency_name: "Mysuru",         event_id: "general-2024", turnout_pct: 68.7, margin_pct:  8.6, electors: 1_805_410, winner_party_id: "parties.IN.BJP", winner_party_short: "BJP", reservation: "GEN", body: "parliament" },
  { entity_id: "PC-9",  state_slug: "karnataka",  constituency_slug: "chitradurga",    constituency_name: "Chitradurga",    event_id: "general-2024", turnout_pct: 71.9, margin_pct:  9.8, electors: 1_602_988, winner_party_id: "parties.IN.INC", winner_party_short: "INC", reservation: "SC",  body: "parliament" },
  { entity_id: "PC-10", state_slug: "karnataka",  constituency_slug: "uttara-kannada", constituency_name: "Uttara Kannada", event_id: "general-2024", turnout_pct: 70.2, margin_pct: 16.5, electors: 1_456_701, winner_party_id: "parties.IN.BJP", winner_party_short: "BJP", reservation: "GEN", body: "parliament" },

  { entity_id: "PC-11", state_slug: "west-bengal",constituency_slug: "kolkata-dakshin",constituency_name: "Kolkata Dakshin",event_id: "general-2024", turnout_pct: 60.4, margin_pct: 21.1, electors: 1_588_213, winner_party_id: "parties.IN.AITC", winner_party_short: "AITC", reservation: "GEN", body: "parliament" },
  { entity_id: "PC-12", state_slug: "west-bengal",constituency_slug: "darjeeling",     constituency_name: "Darjeeling",     event_id: "general-2024", turnout_pct: 76.5, margin_pct:  4.3, electors: 1_402_889, winner_party_id: "parties.IN.BJP",  winner_party_short: "BJP",  reservation: "GEN", body: "parliament" },
  { entity_id: "PC-13", state_slug: "west-bengal",constituency_slug: "alipurduars",    constituency_name: "Alipurduars",    event_id: "general-2024", turnout_pct: 79.8, margin_pct: 12.0, electors: 1_512_644, winner_party_id: "parties.IN.AITC", winner_party_short: "AITC", reservation: "ST",  body: "parliament" },
  { entity_id: "PC-14", state_slug: "west-bengal",constituency_slug: "purulia",        constituency_name: "Purulia",        event_id: "general-2024", turnout_pct: 81.1, margin_pct: 26.8, electors: 1_660_421, winner_party_id: "parties.IN.BJP",  winner_party_short: "BJP",  reservation: "GEN", body: "parliament" },
  { entity_id: "PC-15", state_slug: "west-bengal",constituency_slug: "bishnupur",      constituency_name: "Bishnupur",      event_id: "general-2024", turnout_pct: 83.6, margin_pct:  0.6, electors: 1_473_902, winner_party_id: "parties.IN.AITC", winner_party_short: "AITC", reservation: "SC",  body: "parliament" },

  { entity_id: "PC-16", state_slug: "assam",      constituency_slug: "guwahati",       constituency_name: "Guwahati",       event_id: "general-2024", turnout_pct: 71.5, margin_pct: 11.2, electors: 1_801_044, winner_party_id: "parties.IN.BJP", winner_party_short: "BJP", reservation: "GEN", body: "parliament" },
  { entity_id: "PC-17", state_slug: "assam",      constituency_slug: "dibrugarh",      constituency_name: "Dibrugarh",      event_id: "general-2024", turnout_pct: 73.4, margin_pct: 22.0, electors: 1_722_315, winner_party_id: "parties.IN.AGP", winner_party_short: "AGP", reservation: "GEN", body: "parliament" },
  { entity_id: "PC-18", state_slug: "assam",      constituency_slug: "kokrajhar",      constituency_name: "Kokrajhar",      event_id: "general-2024", turnout_pct: 86.1, margin_pct: 17.4, electors: 1_345_990, winner_party_id: "parties.IN.BJP", winner_party_short: "BJP", reservation: "ST",  body: "parliament" },

  { entity_id: "PC-19", state_slug: "lakshadweep",constituency_slug: "lakshadweep",    constituency_name: "Lakshadweep",    event_id: "general-2024", turnout_pct: 84.2, margin_pct:  2.5, electors:    57_804, winner_party_id: "parties.IN.INC", winner_party_short: "INC", reservation: "ST",  body: "parliament" },

  { entity_id: "PC-20", state_slug: "kerala",     constituency_slug: "wayanad",        constituency_name: "Wayanad",        event_id: "general-2024", turnout_pct: 73.6, margin_pct: 23.1, electors: 1_469_661, winner_party_id: "parties.IN.INC",  winner_party_short: "INC",  reservation: "GEN", body: "parliament" },
  { entity_id: "PC-21", state_slug: "kerala",     constituency_slug: "thiruvananthapuram", constituency_name: "Thiruvananthapuram", event_id: "general-2024", turnout_pct: 67.0, margin_pct:  3.8, electors: 1_481_303, winner_party_id: "parties.IN.INC",  winner_party_short: "INC",  reservation: "GEN", body: "parliament" },
  { entity_id: "PC-22", state_slug: "kerala",     constituency_slug: "kollam",         constituency_name: "Kollam",         event_id: "general-2024", turnout_pct: 67.4, margin_pct: 16.2, electors: 1_336_915, winner_party_id: "parties.IN.CPI",  winner_party_short: "CPI",  reservation: "GEN", body: "parliament" },
  { entity_id: "PC-23", state_slug: "kerala",     constituency_slug: "alappuzha",      constituency_name: "Alappuzha",      event_id: "general-2024", turnout_pct: 74.3, margin_pct:  1.2, electors: 1_376_002, winner_party_id: "parties.IN.CPIM", winner_party_short: "CPIM", reservation: "GEN", body: "parliament" },
  { entity_id: "PC-24", state_slug: "kerala",     constituency_slug: "palakkad",       constituency_name: "Palakkad",       event_id: "general-2024", turnout_pct: 72.1, margin_pct:  8.4, electors: 1_388_044, winner_party_id: "parties.IN.INC",  winner_party_short: "INC",  reservation: "SC",  body: "parliament" },

  { entity_id: "PC-25", state_slug: "maharashtra",constituency_slug: "mumbai-south",   constituency_name: "Mumbai South",   event_id: "general-2024", turnout_pct: 50.3, margin_pct:  4.7, electors: 1_523_011, winner_party_id: "parties.IN.INC",  winner_party_short: "INC",  reservation: "GEN", body: "parliament" },

  // 25 ACs (assembly). Distributed across the same 6 states. Smaller
  // electors (AC scale is typically 200k..400k). 19 GEN / 4 SC / 2 ST.
  { entity_id: "AC-1",  state_slug: "tamil-nadu", constituency_slug: "mylapore",       constituency_name: "Mylapore",       event_id: "assembly-2021", turnout_pct: 64.5, margin_pct: 12.1, electors:   286_022, winner_party_id: "parties.IN.DMK", winner_party_short: "DMK", reservation: "GEN", body: "assembly" },
  { entity_id: "AC-2",  state_slug: "tamil-nadu", constituency_slug: "thousand-lights",constituency_name: "Thousand Lights",event_id: "assembly-2021", turnout_pct: 66.0, margin_pct:  6.4, electors:   240_517, winner_party_id: "parties.IN.DMK", winner_party_short: "DMK", reservation: "GEN", body: "assembly" },
  { entity_id: "AC-3",  state_slug: "tamil-nadu", constituency_slug: "tiruchengode",   constituency_name: "Tiruchengode",   event_id: "assembly-2021", turnout_pct: 78.4, margin_pct:  3.2, electors:   261_344, winner_party_id: "parties.IN.AIADMK", winner_party_short: "AIADMK", reservation: "GEN", body: "assembly" },
  { entity_id: "AC-4",  state_slug: "tamil-nadu", constituency_slug: "harur",          constituency_name: "Harur",          event_id: "assembly-2021", turnout_pct: 82.3, margin_pct: 10.5, electors:   228_710, winner_party_id: "parties.IN.AIADMK", winner_party_short: "AIADMK", reservation: "SC",  body: "assembly" },
  { entity_id: "AC-5",  state_slug: "tamil-nadu", constituency_slug: "papanasam",      constituency_name: "Papanasam",      event_id: "assembly-2021", turnout_pct: 77.9, margin_pct:  1.8, electors:   234_811, winner_party_id: "parties.IN.DMK", winner_party_short: "DMK", reservation: "GEN", body: "assembly" },

  { entity_id: "AC-6",  state_slug: "karnataka",  constituency_slug: "shivajinagar",   constituency_name: "Shivajinagar",   event_id: "assembly-2023", turnout_pct: 53.4, margin_pct: 11.0, electors:   206_310, winner_party_id: "parties.IN.INC", winner_party_short: "INC", reservation: "GEN", body: "assembly" },
  { entity_id: "AC-7",  state_slug: "karnataka",  constituency_slug: "chickpet",       constituency_name: "Chickpet",       event_id: "assembly-2023", turnout_pct: 58.8, margin_pct:  9.4, electors:   188_415, winner_party_id: "parties.IN.BJP", winner_party_short: "BJP", reservation: "GEN", body: "assembly" },
  { entity_id: "AC-8",  state_slug: "karnataka",  constituency_slug: "hubli-dharwad",  constituency_name: "Hubli-Dharwad",  event_id: "assembly-2023", turnout_pct: 70.1, margin_pct: 17.2, electors:   241_812, winner_party_id: "parties.IN.BJP", winner_party_short: "BJP", reservation: "GEN", body: "assembly" },
  { entity_id: "AC-9",  state_slug: "karnataka",  constituency_slug: "humnabad",       constituency_name: "Humnabad",       event_id: "assembly-2023", turnout_pct: 73.2, margin_pct:  4.1, electors:   217_400, winner_party_id: "parties.IN.INC", winner_party_short: "INC", reservation: "GEN", body: "assembly" },
  { entity_id: "AC-10", state_slug: "karnataka",  constituency_slug: "chamarajanagar", constituency_name: "Chamarajanagar", event_id: "assembly-2023", turnout_pct: 77.5, margin_pct: 14.8, electors:   201_004, winner_party_id: "parties.IN.INC", winner_party_short: "INC", reservation: "ST",  body: "assembly" },

  { entity_id: "AC-11", state_slug: "west-bengal",constituency_slug: "kolkata-port",   constituency_name: "Kolkata Port",   event_id: "assembly-2021", turnout_pct: 61.0, margin_pct: 26.5, electors:   210_220, winner_party_id: "parties.IN.AITC", winner_party_short: "AITC", reservation: "GEN", body: "assembly" },
  { entity_id: "AC-12", state_slug: "west-bengal",constituency_slug: "haringhata",     constituency_name: "Haringhata",     event_id: "assembly-2021", turnout_pct: 84.6, margin_pct:  2.3, electors:   235_311, winner_party_id: "parties.IN.AITC", winner_party_short: "AITC", reservation: "SC",  body: "assembly" },
  { entity_id: "AC-13", state_slug: "west-bengal",constituency_slug: "ranibandh",      constituency_name: "Ranibandh",      event_id: "assembly-2021", turnout_pct: 81.9, margin_pct:  6.4, electors:   188_990, winner_party_id: "parties.IN.AITC", winner_party_short: "AITC", reservation: "ST",  body: "assembly" },
  { entity_id: "AC-14", state_slug: "west-bengal",constituency_slug: "khargram",       constituency_name: "Khargram",       event_id: "assembly-2021", turnout_pct: 82.4, margin_pct:  8.2, electors:   197_311, winner_party_id: "parties.IN.AITC", winner_party_short: "AITC", reservation: "SC",  body: "assembly" },
  { entity_id: "AC-15", state_slug: "west-bengal",constituency_slug: "siliguri",       constituency_name: "Siliguri",       event_id: "assembly-2021", turnout_pct: 80.1, margin_pct: 12.6, electors:   251_240, winner_party_id: "parties.IN.BJP", winner_party_short: "BJP", reservation: "GEN", body: "assembly" },

  { entity_id: "AC-16", state_slug: "assam",      constituency_slug: "dispur",         constituency_name: "Dispur",         event_id: "assembly-2021", turnout_pct: 72.8, margin_pct: 18.5, electors:   213_551, winner_party_id: "parties.IN.BJP", winner_party_short: "BJP", reservation: "GEN", body: "assembly" },
  { entity_id: "AC-17", state_slug: "assam",      constituency_slug: "dhakuakhana",    constituency_name: "Dhakuakhana",    event_id: "assembly-2021", turnout_pct: 79.4, margin_pct: 13.0, electors:   192_006, winner_party_id: "parties.IN.AGP", winner_party_short: "AGP", reservation: "SC",  body: "assembly" },

  { entity_id: "AC-18", state_slug: "kerala",     constituency_slug: "vattiyoorkavu",  constituency_name: "Vattiyoorkavu",  event_id: "assembly-2021", turnout_pct: 70.8, margin_pct:  5.9, electors:   209_445, winner_party_id: "parties.IN.CPIM", winner_party_short: "CPIM", reservation: "GEN", body: "assembly" },
  { entity_id: "AC-19", state_slug: "kerala",     constituency_slug: "manjeri",        constituency_name: "Manjeri",        event_id: "assembly-2021", turnout_pct: 76.3, margin_pct: 15.1, electors:   235_812, winner_party_id: "parties.IN.IUML", winner_party_short: "IUML", reservation: "GEN", body: "assembly" },
  { entity_id: "AC-20", state_slug: "kerala",     constituency_slug: "tirur",          constituency_name: "Tirur",          event_id: "assembly-2021", turnout_pct: 76.8, margin_pct:  9.0, electors:   222_113, winner_party_id: "parties.IN.IUML", winner_party_short: "IUML", reservation: "GEN", body: "assembly" },
  { entity_id: "AC-21", state_slug: "kerala",     constituency_slug: "thrissur",       constituency_name: "Thrissur",       event_id: "assembly-2021", turnout_pct: 71.4, margin_pct:  7.2, electors:   211_980, winner_party_id: "parties.IN.CPIM", winner_party_short: "CPIM", reservation: "GEN", body: "assembly" },
  { entity_id: "AC-22", state_slug: "kerala",     constituency_slug: "alappuzha-ac",   constituency_name: "Alappuzha",      event_id: "assembly-2021", turnout_pct: 79.4, margin_pct:  1.5, electors:   215_604, winner_party_id: "parties.IN.INC", winner_party_short: "INC", reservation: "GEN", body: "assembly" },

  { entity_id: "AC-23", state_slug: "maharashtra",constituency_slug: "worli",          constituency_name: "Worli",          event_id: "assembly-2024", turnout_pct: 49.4, margin_pct: 13.6, electors:   272_011, winner_party_id: "parties.IN.AITC", winner_party_short: "AITC", reservation: "GEN", body: "assembly" },
  { entity_id: "AC-24", state_slug: "maharashtra",constituency_slug: "pune-cantonment",constituency_name: "Pune Cantonment",event_id: "assembly-2024", turnout_pct: 53.9, margin_pct:  5.8, electors:   258_022, winner_party_id: "parties.IN.BJP", winner_party_short: "BJP", reservation: "GEN", body: "assembly" },
  { entity_id: "AC-25", state_slug: "maharashtra",constituency_slug: "kolhapur-north", constituency_name: "Kolhapur North", event_id: "assembly-2024", turnout_pct: 67.1, margin_pct: 19.8, electors:   234_330, winner_party_id: "parties.IN.INC", winner_party_short: "INC", reservation: "GEN", body: "assembly" },
];

/** 50 hand-authored rows used by both the unit tests and the dev sandbox.
 *  Distribution recorded here so brief test 4 (filter narrowing) can
 *  hand-verify the expected counts:
 *    - 25 parliament + 25 assembly
 *    - 8 SC + 5 ST + 37 GEN
 *    - 5 close (<2%) + 8 narrow (2-5%) + 12 moderate (5-10%) + 25 wide (>=10%)
 *  Update these counts if you mutate SPECS. */
export const SCATTER_FIXTURES: ReadonlyArray<ScatterDatum> = SPECS.map((s) => ({
  ...s,
}));
