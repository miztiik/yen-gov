// Canonical-Parquet → legacy-IndicatorArtifact adapter (Phase B of P.1.A C4.7).
//
// Given a CanonicalIndicatorDescriptor (from `indicator-allowlist.ts`),
// queries the canonical fact-table via DuckDB-WASM, joins the per-row
// `source_id` into `taxonomy/sources.parquet`, and returns the shape that
// IndicatorCard / IndicatorChoropleth / IndicatorRanked / IndicatorSmallMultiples
// already understand (`IndicatorArtifact` from `../indicators.ts`).
//
// The downstream renderers stay UNTOUCHED. This adapter is the single
// translation layer; the citizen-visible card looks pixel-identical to
// the legacy-shard path except where the canonical store now carries a
// longer time series (the sparkline becomes meaningful instead of a
// single 2025-04 dot).
//
// Doctrine notes
// --------------
// 1. Entity-id translation: canonical store uses ISO-3166-ish prefixed
//    ids (`IN`, `IN-S22`, `IN-U08`); the legacy indicator-row shape that
//    IndicatorCard.* helpers expect is the bare ECI code (`S22`, `U08`)
//    with `IN` reserved for the national aggregate row. We strip the
//    `IN-` prefix from sub-national ids and pass `IN` through unchanged.
// 2. Provenance: canonical `taxonomy.sources` is a citation ledger, not a
//    fetch ledger. The adapter carries those rows through `pills`
//    (deduped publisher pills) attached via a WeakMap side-channel for
//    the new `<SourceList pills={...} />` component in `$lib/sources`,
//    and leaves legacy `sources[]` empty so it never invents retired
//    fetch telemetry like `fetched_at`.
// 3. Coverage: derived from `MIN(period_label)` / `MAX(period_label)` of
//    the returned rows. No round-trip back to the legacy shard.
// 4. License / methodology: synthesised from constants + the descriptor's
//    `meta.methodology_vintage`. Canonical store does not yet model the
//    full `IndicatorMethodology` shape (`definition`, `publisher`,
//    `documentation_status`, etc.); we mirror the legacy "stub" status
//    until the Hans+Max+Gregor panel locks the canonical metadata
//    contract for these fields.

import { query, registerCsvAsTable, registerCsvFile } from "../duckdb";
import {
  fetchIndicator,
  type EntityKind,
  type IndicatorArtifact,
  type IndicatorMeta,
  type IndicatorMethodology,
  type IndicatorRow,
  type SeriesSpec,
} from "../indicators";
import { DATA_BASE } from "../paths";
import { dedupeToPills, type PublisherPill, type SourceRow } from "../sources";
import {
  buildTimeSeriesLineViewModel,
  type TimeSeriesSeriesVM,
} from "../charts/time-view-models";
import {
  loadCanonicalSlugToLegacyMap,
  translateCanonicalSlugToLegacy,
} from "./canonical-entity-translation";
import { csvColumnsClause } from "./csv-columns";
import {
  getCanonicalDescriptor,
  isCanonicalBacked,
  type CanonicalFacetMultiplexedDescriptor,
  type CanonicalIndicatorDescriptor,
  type CanonicalSingleIndicatorDescriptor,
} from "./indicator-allowlist";
import {
  CURRENT_INDICATOR_SCHEMA_ID,
  CURRENT_INDICATOR_SCHEMA_VERSION,
} from "./indicator-schema-policy";
/** Strip `IN-` prefix from canonical entity_ids; pass bare `IN` (national
 *  aggregate) and any unrecognised shape through unchanged. Works for
 *  every canonical entity shape currently in use:
 *   - `IN`              -> `IN`        (national aggregate)
 *   - `IN-S22`          -> `S22`       (state)
 *   - `IN-U03`          -> `U03`       (union territory)
 *   - `IN-S03-D280`     -> `S03-D280`  (district; the second-segment
 *                                       `D<lgd>` token is preserved
 *                                       as the legacy district code)
 *   - `IN-U05-D640`     -> `U05-D640`  (UT district; same shape)
 *  Note: PR B.02 added the explicit district documentation; no code
 *  change was needed because `slice(3)` already handles the longer
 *  district shape correctly. The legacy district code form
 *  `S<n>-D<lgd>` is what AboutThisData.svelte + the district
 *  choropleth boundary picker (PR B.03) consume downstream. */
export function canonicalEntityToLegacy(canonical_entity_id: string): string {
  if (canonical_entity_id === "IN") return "IN";
  if (canonical_entity_id.startsWith("IN-")) return canonical_entity_id.slice(3);
  return canonical_entity_id;
}

/** Translate a canonical `IndicatorMeta.entity_kind` into the legacy
 *  `IndicatorCoverage.admin_level` string consumed by AboutThisData.svelte
 *  and the choropleth boundary picker.
 *
 *  The legacy `admin_level` field is `string | null` (see
 *  `IndicatorCoverage` in [../indicators.ts](../indicators.ts)); on-disk
 *  artifacts populate it with `"country"`, `"national"`, `"state"`, or
 *  `null`. The canonical pivot uses the typed `EntityKind` union
 *  (`country | state | district | subdistrict | constituency | city |
 *  ward`); this dispatch is the single seam that maps the typed canonical
 *  enum onto the legacy string surface so downstream readers stay
 *  unchanged. Per ADR-0043, sub-state-grain adapters now emit BOTH grains
 *  (district source-of-truth + state SUM rollup); each grain reaches the
 *  renderer through its own allowlist descriptor whose `meta.entity_kind`
 *  decides its `admin_level` via this helper.
 *
 *  Returns `null` for `constituency` / `city` / `ward` (no canonical
 *  consumer yet); pass-through downstream is unchanged from the legacy
 *  "unspecified" treatment.
 */
export function entityKindToAdminLevel(kind: EntityKind | undefined): string | null {
  if (kind === undefined) return null;
  switch (kind) {
    case "country":
      return "country";
    case "state":
      return "state";
    case "district":
      return "district";
    case "subdistrict":
      return "subdistrict";
    case "constituency":
    case "city":
    case "ward":
      return null;
  }
}

interface CanonicalObsRow {
  entity_id: string;
  period_label: string;
  value_numeric: number | null;
  source_id: string;
}

/** Observation row carrying its source indicator_id — used by the
 *  facet-multiplexed path which fans N children into one fused artifact
 *  and needs to know which child each row came from. */
interface CanonicalFacetObsRow extends CanonicalObsRow {
  indicator_id: string;
}

interface CanonicalSourceRow {
  source_id: string;
  producer: string;
  title: string;
  vintage: string;
  url: string | null;
}

type IndicatorMetaWithRetiredRenderFields = IndicatorMeta & {
  renderer_rules?: unknown;
  default_mode?: unknown;
  facet_labels?: unknown;
};

const artifactPills = new WeakMap<IndicatorArtifact, readonly PublisherPill[]>();

function attachPills<T extends IndicatorArtifact>(
  artifact: T,
  pills: readonly PublisherPill[],
): T {
  artifactPills.set(artifact, Object.freeze([...pills]));
  return artifact;
}

/** Read the deduped publisher pills attached to a canonical-backed
 *  IndicatorArtifact. Returns the array (possibly empty) when present,
 *  or `undefined` when the artifact was not produced by this adapter
 *  (legacy on-disk JSON path). */
export function indicatorArtifactPills(
  artifact: IndicatorArtifact,
): readonly PublisherPill[] | undefined {
  return artifactPills.get(artifact);
}

/** One observation row from a `<canonical_indicator_id>-national.csv`
 *  sibling file (G31a / parent plan section 20.11). The shape matches
 *  the long-format canonical CSV (`entity_id`, `time`, `value`,
 *  `source_id`) - the only differences vs the base indicator are
 *  (a) `entity_id` is one of the reserved pseudo-entities
 *  `"IN-pop-weighted"` / `"IN-median"`, and (b) `source_id` is the
 *  reserved `yen-gov (derived)` ledger row per Holy Law #9 (NOT a
 *  publisher's source_id). `time` and `value` carry their CSV-typed
 *  shapes (BIGINT/DOUBLE per columns.json); the loader does not
 *  re-stringify `time` so consumers can compute on it directly. */
export interface NationalReferenceRow {
  readonly entity_id: string;
  readonly time: number;
  readonly value: number | null;
  readonly source_id: string;
}

/** WeakMap side-channel mirroring `artifactPills`. Carries the
 *  pop-weighted national-reference rows for indicators that opt in via
 *  `descriptor.has_national_reference === true`. Keeping the data off
 *  the on-disk IndicatorArtifact shape avoids a JSON Schema bump
 *  (CLAUDE.md section 11) for what is a runtime-only enrichment - the
 *  artifact body still validates against the current indicator schema
 *  unchanged. Discovery is via the exported accessor below. */
const artifactNationalReference = new WeakMap<
  IndicatorArtifact,
  readonly NationalReferenceRow[]
>();

function attachNationalReference<T extends IndicatorArtifact>(
  artifact: T,
  rows: readonly NationalReferenceRow[],
): T {
  artifactNationalReference.set(artifact, Object.freeze([...rows]));
  return artifact;
}

/** Read the pop-weighted national-reference rows attached to a
 *  canonical-backed IndicatorArtifact, or `undefined` if the indicator
 *  did not opt in / the sibling CSV was absent / the sibling carried
 *  no pop-weighted rows. Returning `undefined` (rather than an empty
 *  array) is the structural "no reference line" signal renderer
 *  wrappers consume to decide whether to mount `<TimeSeriesLine
 *  reference_series=...>` per plan section 20.11. */
export function indicatorArtifactNationalReference(
  artifact: IndicatorArtifact,
): readonly NationalReferenceRow[] | undefined {
  return artifactNationalReference.get(artifact);
}

function requireRows(rows: readonly IndicatorRow[], indicatorId: string): void {
  if (rows.length === 0) {
    throw new Error(
      `canonical indicator ${indicatorId} returned zero rows; current indicator schema requires at least one row`,
    );
  }
}

/** Quote a string literal for embedding in a SQL `IN (...)` list. */
function sqlString(s: string): string {
  return `'${s.replace(/'/g, "''")}'`;
}

/** Synthetic methodology block — matches the legacy shard's "stub" shape
 *  so AboutThisData.svelte renders an identical surface. The optional
 *  `descriptor.caveats` field (allowlist-authored, citizen-readable) is
 *  surfaced verbatim as `known_caveats[]`; see PR-E (AboutThisData RPO
 *  caveat surfacing) for the doctrine and the RPO seed entry. */
function buildMethodology(
  descriptor: CanonicalIndicatorDescriptor,
  source_rows: ReadonlyArray<CanonicalSourceRow>,
): IndicatorMethodology {
  // "Who publishes it" must be the actual citation producer (e.g.
  // "Reserve Bank of India"), NOT the `implementing_authority` enum value
  // (which is one of "state" / "centre" / "joint" / "local_body" /
  // "parastatal" - a coarse responsibility tag, useless as a publisher
  // label). Pre-fix the renderer surfaced "Who publishes it: state" for
  // every state-administered indicator. The first source row's `producer`
  // is the canonical citation per ADR-0032 (identity = producer + title +
  // vintage); fall back to the implementing-authority humanised form if
  // the canonical sources table has nothing.
  const first_source = source_rows.length > 0 ? source_rows[0] : null;
  const publisher =
    first_source?.producer ?? humanisePublisherFallback(descriptor.meta.implementing_authority);
  return {
    definition: descriptor.meta.description ?? descriptor.meta.title,
    publisher,
    publisher_methodology_url: null,
    documentation_status: "stub",
    methodology_breaks: [],
    known_caveats: descriptor.caveats ? [...descriptor.caveats] : [],
    notes: [],
  };
}

function humanisePublisherFallback(
  implementing_authority: IndicatorMeta["implementing_authority"] | undefined,
): string {
  // Citizen-readable fallback when the indicator's source ledger is empty.
  // The enum values are administrative bucket labels; render them as
  // descriptive phrases that read like a publisher description rather than
  // a bare bucket tag.
  switch (implementing_authority) {
    case "state":
      return "State governments";
    case "centre":
      return "Government of India";
    case "joint":
      return "Joint centre + state programme";
    case "local_body":
      return "Local bodies";
    case "parastatal":
      return "Parastatal body";
    default:
      return "Publisher not on file";
  }
}

function buildSeriesSpec(descriptor: CanonicalIndicatorDescriptor): SeriesSpec {
  return {
    description:
      descriptor.meta.description ??
      descriptor.meta.description_short ??
      `Canonical series for ${descriptor.meta.title}`,
  };
}

/** Build deduped publisher pills from the canonical sources table rows.
 *  One pill per (producer x series_family). Wraps the canonical
 *  `dedupeToPills` helper from `$lib/sources` per the sources-
 *  simplification PR-1 (2026-06-11). */
function buildPills(rows: ReadonlyArray<CanonicalSourceRow>): PublisherPill[] {
  return dedupeToPills(
    rows.map<SourceRow>((s) => ({
      source_id: s.source_id,
      producer: s.producer,
      title: s.title,
      vintage: s.vintage,
      url: s.url,
    })),
  );
}

function buildCanonicalIndicatorMeta(
  meta: IndicatorMeta,
  idOverride?: string,
): IndicatorMeta {
  const {
    renderer_rules: _rendererRules,
    default_mode: _defaultMode,
    facet_labels: _facetLabels,
    ...schemaMeta
  } = meta as IndicatorMetaWithRetiredRenderFields;
  return idOverride === undefined
    ? { ...schemaMeta }
    : { ...schemaMeta, id: idOverride };
}

/** Map observation + source rows into the legacy IndicatorArtifact shape. */
export function buildIndicatorArtifact(
  descriptor: CanonicalIndicatorDescriptor,
  obs_rows: ReadonlyArray<CanonicalObsRow>,
  source_rows: ReadonlyArray<CanonicalSourceRow>,
): IndicatorArtifact {
  const rows: IndicatorRow[] = obs_rows.map((r) => ({
    entity_id: canonicalEntityToLegacy(r.entity_id),
    time: r.period_label,
    value: r.value_numeric,
  }));
  requireRows(rows, descriptor.meta.id);

  // Coverage temporal — derived from the actual rows so this stays in
  // lockstep with the canonical fact-table (no manual maintenance).
  const times = rows
    .map((r) => r.time)
    .filter((t): t is string => typeof t === "string" && t.length > 0)
    .sort();
  const temporal =
    times.length === 0
      ? ""
      : times[0] === times[times.length - 1]
        ? times[0]
        : `${times[0]} to ${times[times.length - 1]}`;

  return attachPills({
    $schema: CURRENT_INDICATOR_SCHEMA_ID,
    $schema_version: CURRENT_INDICATOR_SCHEMA_VERSION,
    sources: [],
    license: {
      id: "OGL-IN-1.0",
      name: "India Government Open Data License (OGL-IN-1.0)",
      url: "https://www.data.gov.in/government-open-data-license-india",
      redistributable: true,
    },
    coverage: {
      spatial: "India (states + UTs)",
      temporal,
      admin_level: entityKindToAdminLevel(descriptor.meta.entity_kind),
    },
    indicator: buildCanonicalIndicatorMeta(descriptor.meta),
    rows,
    series_spec: buildSeriesSpec(descriptor),
    methodology: buildMethodology(descriptor, source_rows),
    divergence: null,
  }, buildPills(source_rows));
}

/** Run the DuckDB-WASM JOIN and return the assembled `IndicatorArtifact`.
 *  Throws on missing manifest entries / SQL errors — caller catches in
 *  the same `.catch()` arm as the legacy `fetchIndicator()` path.
 *
 *  Dispatches on `descriptor.kind` (PR 7c.5):
 *   - `"single"`           → one SQL `WHERE indicator_id = '<id>'`, 1:1 row mapping.
 *   - `"facet-multiplexed"` → one SQL `WHERE indicator_id IN (<children>)`,
 *                             rows fused into one artifact with
 *                             `rows[].facet = <legacy_facet_label>` and
 *                             `indicator.id = canonical_parent_indicator_id`. */
export async function loadIndicatorFromCanonical(
  descriptor: CanonicalIndicatorDescriptor,
): Promise<IndicatorArtifact> {
  if (descriptor.kind === "facet-multiplexed") {
    return loadFacetMultiplexedFromCanonical(descriptor);
  }
  return loadSingleFromCanonical(descriptor);
}

async function loadSingleFromCanonical(
  descriptor: CanonicalSingleIndicatorDescriptor,
): Promise<IndicatorArtifact> {
  // Phase C/D (2026-06-07): the energy + livestock parquet writers were
  // retired in the same commit that deleted the parquet files. Every
  // production descriptor in the allowlist now carries `csv_path` and
  // reads via the long-format per-indicator CSV at
  // `data/datapoints/geo/<canonical_indicator_id>.csv`. The CSV has
  // shape `entity_id, time, value, source_id` (no `indicator_id` column —
  // it's encoded by the filename per csv-column-contract.md section 3.3).
  // Entity_ids are LGD-name slugs ("tamil-nadu", "andhra-pradesh/visakhapatnam");
  // translate to the legacy ECI shape ("S22", "S01-D744") via the canonical
  // entity-translation seam so downstream renderers stay unchanged.
  //
  // A missing `csv_path` is a contract violation (the allowlist invariant
  // test in indicator-from-canonical.test.ts pins this): fail loud at
  // the boundary rather than silently falling back to a code path the
  // dispatch no longer has.
  if (descriptor.csv_path === undefined) {
    throw new Error(
      `canonical descriptor missing csv_path: ${descriptor.legacy_artifact_id} ` +
        `(canonical=${descriptor.canonical_indicator_id}). The parquet back-compat ` +
        `branch retired 2026-06-07 in Phase C/D; every descriptor must declare csv_path.`,
    );
  }
  return loadSingleFromCsv(descriptor, descriptor.csv_path);
}

/** Raw row shape returned by `read_csv` against a `data/datapoints/geo/*.csv`
 *  file class. `time` is INTEGER per columns.json; `value` is DOUBLE. */
interface CanonicalCsvRow {
  entity_id: string;
  time: number;
  value: number | null;
  source_id: string;
}

/** Same shape as `CanonicalCsvRow` plus the synth `indicator_id` literal
 *  the facet-multiplexed UNION ALL injects so per-row facet dispatch
 *  still works after the CSV flip. */
interface CanonicalCsvFacetRow extends CanonicalCsvRow {
  indicator_id: string;
}

/** Build the absolute URL for a `data/datapoints/geo/<id>.csv` repo path. */
function canonicalCsvUrl(repoRelPath: string): string {
  return `${DATA_BASE}/${repoRelPath}`;
}

/** Filter rows whose slug entity_id is admissible for the descriptor's
 *  declared grain. A single per-indicator CSV may carry MULTIPLE grains
 *  (e.g. `pashu-aadhaar-count-cattle.csv` ships both state slugs and
 *  `state/district` district slugs because of the ADR-0043 auto-rollup
 *  writer); the descriptor chooses the slice it wants.
 *
 *  Note: the national-aggregate row `"IN"` is admissible at BOTH country
 *  and state grain. State-grain renderers consume it as the national
 *  centroid value alongside the 36 state slugs. */
function rowMatchesEntityKind(slug: string, kind: EntityKind | undefined): boolean {
  if (kind === undefined) return true;
  if (kind === "country") return slug === "IN";
  if (kind === "state") return !slug.includes("/");
  if (kind === "district") return slug.includes("/");
  // Other grains (subdistrict / constituency / city / ward) currently
  // have no CSV consumers in the 9 family migration; pass-through.
  return true;
}

async function loadSingleFromCsv(
  descriptor: CanonicalSingleIndicatorDescriptor,
  csvRelPath: string,
): Promise<IndicatorArtifact> {
  const url = canonicalCsvUrl(csvRelPath);
  const [columnsClause, slugToLegacy] = await Promise.all([
    csvColumnsClause(`datasets/${csvRelPath}`),
    loadCanonicalSlugToLegacyMap(),
    registerCsvAsTable("taxonomy.sources"),
    registerCsvFile(url),
  ]);

  const obsSql = `
    SELECT entity_id, time, value, source_id
    FROM read_csv('${url.replace(/'/g, "''")}', ${columnsClause}, header=true)
    ORDER BY entity_id, time
  `;
  const obsRows = await query<CanonicalCsvRow>(obsSql);

  const filteredRows = obsRows.filter((r) =>
    rowMatchesEntityKind(r.entity_id, descriptor.meta.entity_kind),
  );

  // Adapt to the parquet-shaped `CanonicalObsRow` buildIndicatorArtifact
  // consumes so the downstream construction stays unchanged. The slug →
  // legacy ECI translation lifts the existing canonicalEntityToLegacy
  // call: by the time buildIndicatorArtifact runs, entity_id is ALREADY
  // legacy-shaped, so its own canonicalEntityToLegacy pass is a no-op.
  const adapted: CanonicalObsRow[] = filteredRows.map((r) => ({
    entity_id: translateCanonicalSlugToLegacy(slugToLegacy, r.entity_id),
    period_label: String(r.time),
    value_numeric: r.value,
    source_id: r.source_id,
  }));

  const distinctSourceIds = [...new Set(adapted.map((r) => r.source_id))].filter(
    (s): s is string => typeof s === "string" && s.length > 0,
  );
  let sourceRows: CanonicalSourceRow[] = [];
  if (distinctSourceIds.length > 0) {
    const idList = distinctSourceIds.map(sqlString).join(", ");
    const srcSql = `
      SELECT source_id, producer, title, vintage, url
      FROM sources
      WHERE source_id IN (${idList})
      ORDER BY title
    `;
    sourceRows = await query<CanonicalSourceRow>(srcSql);
  }

  const artifact = buildIndicatorArtifact(descriptor, adapted, sourceRows);

  // G31b (plan section 20.11): opportunistic sibling-CSV load for the
  // pop-weighted national reference line. Only when the descriptor opts
  // in via `has_national_reference: true`. Failures are graceful - the
  // base artifact ships unchanged and the accessor returns `undefined`,
  // which the renderer wrapper reads as "no reference line for this
  // indicator". No console output on the miss path (anti-pattern: a
  // log per indicator without a sibling would be noise on every page).
  if (descriptor.has_national_reference === true) {
    const refRows = await loadNationalReferenceRows(csvRelPath);
    if (refRows !== undefined && refRows.length > 0) {
      attachNationalReference(artifact, refRows);
    }
  }

  return artifact;
}

/** Compute the sibling URL: `data/datapoints/geo/<canonical-id>.csv`
 *  -> `data/datapoints/geo/<canonical-id>-national.csv`. Only handles
 *  the `.csv` extension because the canonical store's geo datapoint
 *  file class is csv-only (no manifest indirection). Returns the
 *  base path unchanged for any non-csv extension; the caller's CSV
 *  reader will then fail loud, surfacing a contract violation rather
 *  than silently falling through. */
function nationalSiblingCsvPath(baseCsvRelPath: string): string {
  if (baseCsvRelPath.endsWith(".csv")) {
    return `${baseCsvRelPath.slice(0, -".csv".length)}-national.csv`;
  }
  return baseCsvRelPath;
}

/** Fetch + parse the sibling `<base>-national.csv`. Filters to
 *  `entity_id === "IN-pop-weighted"` (median rows are reserved for a
 *  future toggle), sorts by `time`. Returns `undefined` when the
 *  sibling file is absent OR a network error fires OR the file
 *  parses to zero pop-weighted rows - all graceful, all silent. The
 *  caller MUST distinguish `undefined` (no reference attached) from
 *  `[]` (which would currently NOT be returned, since `[]` collapses
 *  to `undefined` via the length check; the consumer surface is
 *  therefore "either >=1 row or absent"). */
async function loadNationalReferenceRows(
  baseCsvRelPath: string,
): Promise<readonly NationalReferenceRow[] | undefined> {
  const siblingRelPath = nationalSiblingCsvPath(baseCsvRelPath);
  const siblingUrl = canonicalCsvUrl(siblingRelPath);
  try {
    // The sibling file class is the same as the base
    // (`data/datapoints/geo/*.csv`); reuse the shared columns clause
    // resolver so the typed read contract stays single-source.
    const siblingColumnsClause = await csvColumnsClause(`datasets/${siblingRelPath}`);
    await registerCsvFile(siblingUrl);
    const sql = `
      SELECT entity_id, time, value, source_id
      FROM read_csv('${siblingUrl.replace(/'/g, "''")}', ${siblingColumnsClause}, header=true)
      WHERE entity_id = 'IN-pop-weighted'
      ORDER BY time
    `;
    const rows = await query<NationalReferenceRow>(sql);
    return rows;
  } catch {
    // Sibling absent / fetch failed / DuckDB rejected the file: the
    // descriptor's `has_national_reference: true` is INERT until the
    // backend writer emits the file. Graceful pass-through is the
    // plan-section-20.11 contract (no broken charts; no `[error]`).
    return undefined;
  }
}

/** Facet-multiplexed adapter — fuses N canonical child indicators into a
 *  single IndicatorArtifact carrying `indicator.id =
 *  canonical_parent_indicator_id` and `rows[].facet =
 *  <legacy_facet_label>` (the legacy hyphenated display form the
 *  IndicatorCard's facet-picker expects).
 *
 *  Issues ONE SQL query against the fact-table with `indicator_id IN
 *  (<child_1>, <child_2>, …)`. The per-row `indicator_id` is consulted
 *  client-side against `descriptor.facet_values` to assign the
 *  citizen-facing facet label. Provenance is aggregated from the
 *  observed rows (children carry `source_id`, parent does not). */
async function loadFacetMultiplexedFromCanonical(
  descriptor: CanonicalFacetMultiplexedDescriptor,
): Promise<IndicatorArtifact> {
  // Phase C/D (2026-06-07): every facet child in the energy + livestock
  // allowlist now carries `csv_path`; the parquet UNION-on-fact-table
  // back-compat branch retired in the same commit that deleted the
  // parquet files. Fan out via UNION ALL with a synth `'<child_id>' AS
  // indicator_id` literal per branch so per-row facet dispatch stays
  // unchanged. A missing `csv_path` on any child is a contract violation;
  // fail loud at the boundary.
  const childrenMissingCsv = descriptor.facet_values.filter(
    (fv) => fv.csv_path === undefined,
  );
  if (childrenMissingCsv.length > 0) {
    const ids = childrenMissingCsv.map((fv) => fv.canonical_child_id).join(", ");
    throw new Error(
      `facet-multiplexed descriptor ${descriptor.legacy_artifact_id} has ` +
        `${childrenMissingCsv.length} child(ren) missing csv_path: ${ids}. ` +
        `The parquet back-compat branch retired 2026-06-07 in Phase C/D; ` +
        `every facet child must declare csv_path.`,
    );
  }
  return loadFacetMultiplexedFromCsv(descriptor);
}

async function loadFacetMultiplexedFromCsv(
  descriptor: CanonicalFacetMultiplexedDescriptor,
): Promise<IndicatorArtifact> {
  const slugToLegacy = await loadCanonicalSlugToLegacyMap();
  // Resolve column clauses + register each child CSV in parallel. All
  // file_classes share the `datasets/data/datapoints/geo/*.csv` glob so
  // a single columnsClause is reused across all branches.
  const sampleChild = descriptor.facet_values[0];
  if (!sampleChild?.csv_path) {
    throw new Error(
      `facet-multiplexed CSV path missing for ${descriptor.canonical_parent_indicator_id}`,
    );
  }
  const columnsClause = await csvColumnsClause(`datasets/${sampleChild.csv_path}`);
  await Promise.all([
    registerCsvAsTable("taxonomy.sources"),
    ...descriptor.facet_values.map((fv) =>
      registerCsvFile(canonicalCsvUrl(fv.csv_path!)),
    ),
  ]);

  // UNION ALL across children. Per-branch synth column carries the
  // child indicator_id so the existing per-row facet dispatch (driven
  // by `facetLabelByChildId.get(r.indicator_id)`) keeps working.
  const branches = descriptor.facet_values.map((fv) => {
    const url = canonicalCsvUrl(fv.csv_path!).replace(/'/g, "''");
    return `
      SELECT ${sqlString(fv.canonical_child_id)} AS indicator_id,
             entity_id, time, value, source_id
      FROM read_csv('${url}', ${columnsClause}, header=true)
    `;
  });
  const obsSql = `${branches.join(" UNION ALL ")} ORDER BY indicator_id, entity_id, time`;

  const csvRows = await query<CanonicalCsvFacetRow>(obsSql);

  // Adapt CSV rows into the parquet-shaped CanonicalFacetObsRow shape,
  // filtering each branch's rows by the descriptor's declared grain.
  const adapted: CanonicalFacetObsRow[] = csvRows
    .filter((r) => rowMatchesEntityKind(r.entity_id, descriptor.meta.entity_kind))
    .map((r) => ({
      entity_id: translateCanonicalSlugToLegacy(slugToLegacy, r.entity_id),
      period_label: String(r.time),
      value_numeric: r.value,
      source_id: r.source_id,
      indicator_id: r.indicator_id,
    }));

  return buildFacetMultiplexedArtifact(descriptor, adapted);
}

/** Shared construction step extracted so the parquet + CSV branches of
 *  `loadFacetMultiplexedFromCanonical` build the IndicatorArtifact from
 *  the same code path. Refactored from the inline pre-R2 body so the
 *  per-branch readers only have to produce a uniform `CanonicalFacetObsRow[]`
 *  before this finisher runs. */
async function buildFacetMultiplexedArtifact(
  descriptor: CanonicalFacetMultiplexedDescriptor,
  obsRows: ReadonlyArray<CanonicalFacetObsRow>,
): Promise<IndicatorArtifact> {
  // Map child indicator_id → citizen-facing facet label.
  const facetLabelByChildId = new Map(
    descriptor.facet_values.map((fv) => [fv.canonical_child_id, fv.legacy_facet_label]),
  );

  // Fuse rows: assign facet label per-row, derive coverage temporal as the
  // UNION across children (handled by buildIndicatorArtifact's existing
  // min/max-of-times calculation).
  const rows: IndicatorRow[] = obsRows.map((r) => ({
    entity_id: canonicalEntityToLegacy(r.entity_id),
    time: r.period_label,
    value: r.value_numeric,
    facet: facetLabelByChildId.get(r.indicator_id) ?? null,
  }));
  requireRows(rows, descriptor.canonical_parent_indicator_id);

  // Sources from CHILDREN (parent's source_id is null per indicator-naming.md D29).
  const distinctSourceIds = [...new Set(obsRows.map((r) => r.source_id))].filter(
    (s): s is string => typeof s === "string" && s.length > 0,
  );
  let sourceRows: CanonicalSourceRow[] = [];
  if (distinctSourceIds.length > 0) {
    const idList = distinctSourceIds.map(sqlString).join(", ");
    const srcSql = `
      SELECT source_id, producer, title, vintage, url
      FROM sources
      WHERE source_id IN (${idList})
      ORDER BY title
    `;
    sourceRows = await query<CanonicalSourceRow>(srcSql);
  }

  // Coverage temporal = MIN/MAX across the fused rows (UNION of all
  // children's coverage). buildIndicatorArtifact derives it from rows[]
  // directly; we already populated those above.
  const times = rows
    .map((r) => r.time)
    .filter((t): t is string => typeof t === "string" && t.length > 0)
    .sort();
  const temporal =
    times.length === 0
      ? ""
      : times[0] === times[times.length - 1]
        ? times[0]
        : `${times[0]} to ${times[times.length - 1]}`;

  return attachPills({
    $schema: CURRENT_INDICATOR_SCHEMA_ID,
    $schema_version: CURRENT_INDICATOR_SCHEMA_VERSION,
    sources: [],
    license: {
      id: "OGL-IN-1.0",
      name: "India Government Open Data License (OGL-IN-1.0)",
      url: "https://www.data.gov.in/government-open-data-license-india",
      redistributable: true,
    },
    coverage: {
      spatial: "India (states + UTs)",
      temporal,
      admin_level: entityKindToAdminLevel(descriptor.meta.entity_kind),
    },
    indicator: buildCanonicalIndicatorMeta(
      descriptor.meta,
      descriptor.canonical_parent_indicator_id,
    ),
    rows,
    series_spec: buildSeriesSpec(descriptor),
    methodology: buildMethodology(descriptor, sourceRows),
    divergence: null,
  }, buildPills(sourceRows));
}

/** Single dispatch entry-point used by IndicatorCard.svelte: branches on the
 *  allowlist and delegates either to canonical or to the legacy fetcher.
 *  Returns `null` for the canonical-backed flag so the caller knows to use
 *  its existing legacy path; returns the artifact when canonical-backed. */
export async function loadIndicatorIfCanonical(
  legacy_artifact_id: string,
): Promise<IndicatorArtifact | null> {
  if (!isCanonicalBacked(legacy_artifact_id)) return null;
  const descriptor = getCanonicalDescriptor(legacy_artifact_id)!;
  return loadIndicatorFromCanonical(descriptor);
}

/** Derive the catalogue artifact id (e.g. ``energy/state_peak_electricity_demand_mw``)
 *  from a DATA_BASE-relative path of the form ``/indicators/in/<topic>/<id>.json``.
 *  Returns the empty string for paths that don't match the legacy shape — the
 *  caller will then short-circuit straight to the legacy fetcher. */
export function legacyArtifactIdFromPath(path: string): string {
  const m = path.match(/^\/indicators\/in\/(.+)\.json$/);
  return m ? m[1] : "";
}

/** Universal indicator loader (Phase B-extension of P.1.A C4.7). Derives the
 *  legacy artifact id from ``path``, consults the canonical allowlist, and
 *  returns either the canonical-backed artifact or the legacy-shard fetch
 *  result. Drop-in replacement for ``fetchIndicator(path)`` — non-allowlisted
 *  paths take the legacy fetch path with zero behavioural change.
 *
 *  Use this from every IndicatorCard / IndicatorChoropleth / IndicatorRanked /
 *  IndicatorSmallMultiples call site so that allowlist-routed artifacts never
 *  trigger a 404 against a deleted legacy shard. */
export async function loadIndicator(path: string): Promise<IndicatorArtifact> {
  const legacy_id = legacyArtifactIdFromPath(path);
  if (legacy_id !== "") {
    const canonical = await loadIndicatorIfCanonical(legacy_id);
    if (canonical !== null) return canonical;
  }
  return fetchIndicator(path);
}

/** Default label used by `buildNationalReferenceSeries` when the caller
 *  omits one. Plan section 20.11 mandates that "national" never appear
 *  unqualified - "pop-weighted" is the qualifier for the only series
 *  this PR ships (the median variant lands in a follow-on toggle PR). */
export const NATIONAL_REFERENCE_LABEL_DEFAULT = "National (pop-weighted)";

/** Project `NationalReferenceRow[]` (from
 *  `indicatorArtifactNationalReference(artifact)`) into a
 *  `TimeSeriesSeriesVM<NationalReferenceRow>` the F3
 *  `<TimeSeriesLine reference_series=...>` prop consumes directly
 *  (parent plan section 20.11, PR #779).
 *
 *  Wraps `buildTimeSeriesLineViewModel` rather than constructing the VM
 *  by hand so the per-point shape (`is_missing`, `is_break_start`,
 *  `period_id`/`period_label` derivation) stays in lockstep with the
 *  state-side series; this is the same builder the state's primary
 *  line uses. The returned series's `.series_id` is the reserved
 *  pseudo-entity `"IN-pop-weighted"`; `.series_label` defaults to
 *  `NATIONAL_REFERENCE_LABEL_DEFAULT` and is overridable per chart.
 *
 *  Returns `null` when `rows.length === 0` so the renderer can keep
 *  the same conditional shape it already uses for
 *  `indicatorArtifactNationalReference(artifact)` (undefined-or-array)
 *  - both signal "no reference line" identically. */
export function buildNationalReferenceSeries(
  rows: readonly NationalReferenceRow[],
  options?: { label?: string },
): TimeSeriesSeriesVM<NationalReferenceRow> | null {
  if (rows.length === 0) return null;
  const label = options?.label ?? NATIONAL_REFERENCE_LABEL_DEFAULT;
  const vm = buildTimeSeriesLineViewModel<NationalReferenceRow>({
    rows: [...rows],
    toPoint: (r) => ({
      series_id: r.entity_id,
      series_label: label,
      period_id: String(r.time),
      period_label: String(r.time),
      value: r.value,
    }),
    policy: "value_desc",
  });
  return vm.series[0] ?? null;
}
