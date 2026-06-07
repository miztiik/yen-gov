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
//    fetch ledger. The adapter carries those rows through `sources_v2`
//    for SourceListV2 and leaves legacy `sources[]` empty so it never
//    invents retired fetch telemetry like `fetched_at`.
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
import type { SourceV2Row } from "../source-list-v2";
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
  license: SourceV2Row["license"];
  confidence_tier: SourceV2Row["confidence_tier"];
  is_issuing_authority: boolean | number;
  verification_method: SourceV2Row["verification_method"];
  url_main: string | null;
  citation_full: string | null;
  notes: string | null;
}

type IndicatorMetaWithRetiredRenderFields = IndicatorMeta & {
  renderer_rules?: unknown;
  default_mode?: unknown;
  facet_labels?: unknown;
};

const artifactSourcesV2 = new WeakMap<IndicatorArtifact, readonly SourceV2Row[]>();

function attachSourcesV2<T extends IndicatorArtifact>(
  artifact: T,
  sources: readonly SourceV2Row[],
): T {
  artifactSourcesV2.set(artifact, Object.freeze([...sources]));
  return artifact;
}

export function indicatorArtifactSourcesV2(
  artifact: IndicatorArtifact,
): readonly SourceV2Row[] | undefined {
  return artifactSourcesV2.get(artifact) ?? artifact.sources_v2;
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
function buildMethodology(descriptor: CanonicalIndicatorDescriptor): IndicatorMethodology {
  return {
    definition: descriptor.meta.description ?? descriptor.meta.title,
    publisher: descriptor.meta.implementing_authority ?? "joint",
    publisher_methodology_url: null,
    documentation_status: "stub",
    methodology_breaks: [],
    known_caveats: descriptor.caveats ? [...descriptor.caveats] : [],
    notes: [],
  };
}

function buildSeriesSpec(descriptor: CanonicalIndicatorDescriptor): SeriesSpec {
  return {
    description:
      descriptor.meta.description ??
      descriptor.meta.description_short ??
      `Canonical series for ${descriptor.meta.title}`,
  };
}

/** Build `SourceV2Row[]` from the canonical sources table rows. */
function buildSourcesV2(rows: ReadonlyArray<CanonicalSourceRow>): SourceV2Row[] {
  return rows.map((s) => ({
    source_id: s.source_id,
    producer: s.producer,
    title: s.title,
    vintage: s.vintage,
    license: s.license,
    confidence_tier: s.confidence_tier,
    is_issuing_authority: Boolean(s.is_issuing_authority),
    verification_method: s.verification_method,
    url_main: s.url_main,
    citation_full: s.citation_full,
    notes: s.notes,
  }));
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

  return attachSourcesV2({
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
    methodology: buildMethodology(descriptor),
    divergence: null,
  }, buildSourcesV2(source_rows));
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
          SELECT source_id, producer, title, vintage, license, confidence_tier,
           is_issuing_authority, verification_method, url_main,
           citation_full, notes
      FROM sources
      WHERE source_id IN (${idList})
      ORDER BY title
    `;
    sourceRows = await query<CanonicalSourceRow>(srcSql);
  }

  return buildIndicatorArtifact(descriptor, adapted, sourceRows);
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
          SELECT source_id, producer, title, vintage, license, confidence_tier,
           is_issuing_authority, verification_method, url_main,
           citation_full, notes
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

  return attachSourcesV2({
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
    methodology: buildMethodology(descriptor),
    divergence: null,
  }, buildSourcesV2(sourceRows));
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
