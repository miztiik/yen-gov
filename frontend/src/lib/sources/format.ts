// Pure helpers for the publisher-pill view-model. Zero DOM, zero Svelte
// imports, zero side effects. Unit-testable in isolation.
//
// The 4 exported helpers:
//   - publisherDisplay(producer)  -> compact publisher abbreviation
//   - seriesFamily(title)         -> leading clause of title before separator
//   - summarizeVintages(vintages) -> single string, range, "various", or ""
//   - dedupeToPills(rows)         -> SourceRow[] -> PublisherPill[]
//
// All helpers are pure functions (referentially transparent). The
// PUBLISHER_DISPLAY map is hand-authored: the 8 most common publishers
// in the yen-gov corpus get compact abbreviations; everything else falls
// back to the raw `producer` string. Adding a new publisher = one line
// in PUBLISHER_DISPLAY + one test row.
//
// See docs/concepts/data-provenance.md for the underlying citation
// contract; see frontend/src/lib/sources/README.md for the rendering
// rules and the soft 30-char label budget.

import type { PublisherPill, SourceRow } from "./types";

// Compact display names for the most common publishers. Hand-authored;
// fallback to the raw producer string for any unmapped entry.
//
// Rule when adding: the abbreviation must be a proper-noun an Indian
// citizen recognises (RBI, ECI, MoSPI). Avoid invented acronyms.
const PUBLISHER_DISPLAY: Record<string, string> = {
  "Reserve Bank of India": "RBI",
  "Election Commission of India": "ECI",
  "Ministry of Statistics and Programme Implementation": "MoSPI",
  "NITI Aayog India Climate & Energy Dashboard": "NITI ICED",
  "Central Electricity Authority": "CEA",
  "NITI Aayog": "NITI Aayog",
  "yen-gov": "yen-gov",
  Wikipedia: "Wikipedia",
};

// Soft cap on pill label length BEFORE the " (vintage)" suffix is
// appended. Pills exceeding this drop the series_family and render the
// publisher abbreviation alone.
const PILL_LABEL_BUDGET = 30;

/** Map a raw producer string to its compact display abbreviation.
 *  Falls back to the raw producer string when unmapped. */
export function publisherDisplay(producer: string): string {
  const trimmed = producer.trim();
  return PUBLISHER_DISPLAY[trimmed] ?? trimmed;
}

/** Extract the series-family name from a citation title.
 *
 *  Strips everything from the first colon, em-dash-with-spaces, or
 *  hyphen-with-spaces separator onward. Falls back to the trimmed
 *  whole title when no separator is present.
 *
 *  Examples:
 *    "State Finances: A Study of Budgets"
 *      -> "State Finances"
 *    "Statistical Report Section 10 (Detailed Results) -- Tamil Nadu AcGenMay2026"
 *      -> "Statistical Report Section 10 (Detailed Results)"
 *    "General Election to Lok Sabha 2009 - Constituency-wise candidate results"
 *      -> "General Election to Lok Sabha 2009"
 *    "Handbook of Statistics on the Indian Economy 2024-25"
 *      -> "Handbook of Statistics on the Indian Economy 2024-25"  (no separator) */
export function seriesFamily(title: string): string {
  const trimmed = title.trim();
  // Order matters: prefer em-dash-with-spaces / hyphen-with-spaces over
  // bare colon to avoid splitting on title-internal colons inside parens.
  const separators = [" \u2014 ", " - ", ":"];
  let earliest = trimmed.length;
  for (const sep of separators) {
    const idx = trimmed.indexOf(sep);
    if (idx > 0 && idx < earliest) {
      earliest = idx;
    }
  }
  return trimmed.slice(0, earliest).trim();
}

/** Summarise a set of vintage strings into one display string.
 *  Returns "" when input is empty or contains only empty/whitespace entries.
 *  Returns the single vintage when only one distinct non-empty vintage.
 *  Returns "<first> to <last>" when the sorted set forms a contiguous range
 *  (heuristic: 2+ entries, sorted ascending; we do not validate gap-free).
 *  Returns "various" when 2+ distinct non-contiguous vintages. */
export function summarizeVintages(vintages: readonly string[]): string {
  const distinct = Array.from(
    new Set(vintages.map((v) => (v ?? "").trim()).filter((v) => v.length > 0)),
  ).sort();
  if (distinct.length === 0) return "";
  if (distinct.length === 1) return distinct[0];
  // Two distinct vintages -> name the span.
  if (distinct.length === 2) return `${distinct[0]} to ${distinct[1]}`;
  // 3+ distinct -> "various" (a contiguous-range claim would over-promise;
  // citizen reading "2018-19 to 2025-26" assumes every FY in between).
  return "various";
}

/** Collapse SourceRow[] to PublisherPill[] grouped by (producer, series_family),
 *  then merge any groups that render to the same display label so a publisher
 *  whose series overflow the label budget shows once (not "ECI . ECI").
 *  Sorts output by count desc (most-cited first), then by label asc for stability. */
export function dedupeToPills(rows: readonly SourceRow[]): PublisherPill[] {
  if (rows.length === 0) return [];

  // Group by (producer, series_family) -> contributing rows.
  const groups = new Map<string, SourceRow[]>();
  for (const row of rows) {
    const key = `${row.producer}\u0000${seriesFamily(row.title)}`;
    const existing = groups.get(key);
    if (existing) {
      existing.push(row);
    } else {
      groups.set(key, [row]);
    }
  }

  // Build one provisional pill per (producer x series_family) group,
  // remembering the display label + every contributing row so that groups
  // which render to the SAME label can merge below.
  interface Provisional {
    label: string;
    family: string;
    rows: SourceRow[];
  }
  const provisional: Provisional[] = [];
  for (const contributing of groups.values()) {
    const producer = contributing[0].producer;
    const family = seriesFamily(contributing[0].title);
    const pub = publisherDisplay(producer);

    // Try producer + family; fall back to producer alone when over budget
    // OR when family duplicates the producer abbreviation.
    let label: string;
    if (family.length === 0 || family === pub) {
      label = pub;
    } else {
      const candidate = `${pub} ${family}`;
      label = candidate.length <= PILL_LABEL_BUDGET ? candidate : pub;
    }
    provisional.push({ label, family, rows: contributing });
  }

  // Second-level collapse by display label. Two distinct series from the
  // same publisher can BOTH overflow the label budget and shrink to the
  // bare publisher abbreviation (e.g. an ECI Lok-Dhaba series + an ECI
  // Report-33 series both render "ECI"). Showing "ECI . ECI" is redundant
  // noise to the citizen, so pills that share an identical label merge into
  // one. When the merge spans more than one distinct series_family the
  // vintage range would splice unrelated series, so the vintage is dropped
  // (the bare label already hides the per-series detail).
  const byLabel = new Map<string, Provisional[]>();
  for (const p of provisional) {
    const existing = byLabel.get(p.label);
    if (existing) {
      existing.push(p);
    } else {
      byLabel.set(p.label, [p]);
    }
  }

  const pills: PublisherPill[] = [];
  for (const [label, group] of byLabel) {
    const allRows = group.flatMap((p) => p.rows);
    const distinctFamilies = new Set(group.map((p) => p.family));
    const vintage_summary =
      distinctFamilies.size > 1
        ? ""
        : summarizeVintages(allRows.map((r) => r.vintage));

    // Click target: first non-empty url among contributing rows.
    const url =
      allRows.map((r) => (r.url ?? "").trim()).find((u) => u.length > 0) ?? null;

    pills.push({
      label,
      vintage_summary,
      url,
      count: allRows.length,
    });
  }

  // Sort: most-cited first, then alphabetical by label.
  pills.sort((a, b) => {
    if (b.count !== a.count) return b.count - a.count;
    return a.label.localeCompare(b.label);
  });

  return pills;
}
