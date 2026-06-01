/**
 * Contract test (CLAUDE.md §11): every JSON artifact under datasets/ that
 * is reachable by the frontend MUST validate against its declared $schema,
 * AND its $schema_version MUST be accepted by the shared json-corpus
 * compatibility contract.
 *
 * This closes the consumer-side half of the §11 loop. The backend tests
 * (backend/tests/test_validate.py) cover the producer side; this test
 * makes the frontend's bet that "the data conforms to the contract"
 * verifiable in CI rather than left to convention.
 *
 * Why a glob over the workspace's datasets/ rather than fixtures: the
 * point of the contract is that the *real* shipped artifacts are valid.
 * A fixture would test our test, not our data.
 */
import { describe, it, expect } from "vitest";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { globSync } from "glob";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const datasetsDir = resolve(repoRoot, "datasets");
const schemasDir = resolve(datasetsDir, "schemas");
const schemaCompatibilityPath = resolve(datasetsDir, "schema-compatibility.json");

interface SchemaMeta {
  path: string;
  id: string;
  basename: string;
  version: string;
  raw: Record<string, unknown>;
}

interface CompatibilityOverride {
  surface: string;
  schema: string;
  accepted_versions: string[];
  validation: string;
}

interface CompatibilityRegistry {
  overrides: CompatibilityOverride[];
}

function readJson<T>(path: string): T {
  return JSON.parse(readFileSync(path, "utf-8")) as T;
}

/** Build a (basename + $id) → schema map by scanning datasets/schemas/.
 *
 * Canonical pivot schemas use a local relative $id (`./entity.schema.json`),
 * while data files reference them via a path relative to themselves
 * (`../schemas/entity.schema.json`). Both must resolve to the same schema
 * — we index by basename so either form lands the right validator.
 */
function loadSchemas(): Map<string, SchemaMeta> {
  const out = new Map<string, SchemaMeta>();
  for (const file of globSync("*.schema.json", { cwd: schemasDir, absolute: true })) {
    const raw = readJson<Record<string, unknown>>(file);
    const id = String(raw["$id"] ?? "");
    const version = String(raw["x-version"] ?? "");
    const basename = file.split(/[\\/]/).pop()!;
    if (!id || !version) {
      throw new Error(`schema ${file} missing $id or x-version`);
    }
    const meta: SchemaMeta = { path: file, id, basename, version, raw };
    out.set(id, meta);
    out.set(basename, meta);
  }
  return out;
}

function uniqueSchemasByBasename(schemas: Map<string, SchemaMeta>): SchemaMeta[] {
  const seen = new Set<string>();
  const out: SchemaMeta[] = [];
  for (const meta of schemas.values()) {
    if (seen.has(meta.basename)) continue;
    seen.add(meta.basename);
    out.push(meta);
  }
  return out;
}

/** Resolve a data file's $schema string against the loaded schemas, accepting
 * the full $id form or the basename form. */
function resolveSchema(declared: string): SchemaMeta | undefined {
  if (SCHEMAS.has(declared)) return SCHEMAS.get(declared);
  const basename = declared.split(/[\\/]/).pop()!;
  return SCHEMAS.get(basename);
}

function versionTuple(version: string): [number, number] | undefined {
  const match = /^(\d+)\.(\d+)$/.exec(version);
  if (!match) return undefined;
  return [Number(match[1]), Number(match[2])];
}

function schemaChangelogVersions(schema: SchemaMeta): Set<string> {
  const changelog = schema.raw["x-changelog"];
  if (!Array.isArray(changelog)) return new Set();
  return new Set(
    changelog
      .map(entry => (entry && typeof entry === "object" ? (entry as Record<string, unknown>).version : undefined))
      .filter((version): version is string => typeof version === "string"),
  );
}

function currentSchemaCanValidateDeclaredVersion(schema: SchemaMeta, version: string): boolean {
  const current = versionTuple(schema.version);
  const declared = versionTuple(version);
  if (!current || !declared) return false;
  if (declared[0] !== current[0] || declared[1] > current[1]) return false;
  return schemaChangelogVersions(schema).has(version);
}

function buildJsonCorpusAcceptedVersions(
  registry: CompatibilityRegistry,
  schemas: SchemaMeta[],
): Map<string, ReadonlySet<string>> {
  const byBasename = new Map(schemas.map(schema => [schema.basename, schema]));
  const accepted = new Map<string, Set<string>>(
    schemas.map(schema => [schema.basename, new Set([schema.version])]),
  );

  for (const override of registry.overrides) {
    if (override.surface !== "json-corpus" || override.validation !== "current_schema") continue;
    const schema = byBasename.get(override.schema);
    if (!schema) continue;
    const versions = accepted.get(schema.basename)!;
    for (const version of override.accepted_versions) {
      if (currentSchemaCanValidateDeclaredVersion(schema, version)) {
        versions.add(version);
      }
    }
  }

  return new Map([...accepted.entries()].map(([schema, versions]) => [schema, versions as ReadonlySet<string>]));
}

function loadJsonCorpusAcceptedVersions(): Map<string, ReadonlySet<string>> {
  return buildJsonCorpusAcceptedVersions(
    readJson<CompatibilityRegistry>(schemaCompatibilityPath),
    uniqueSchemasByBasename(SCHEMAS),
  );
}

function formatVersions(versions: Iterable<string>): string {
  return [...versions]
    .sort((left, right) => {
      const leftTuple = versionTuple(left) ?? [Number.MAX_SAFE_INTEGER, Number.MAX_SAFE_INTEGER];
      const rightTuple = versionTuple(right) ?? [Number.MAX_SAFE_INTEGER, Number.MAX_SAFE_INTEGER];
      return leftTuple[0] - rightTuple[0] || leftTuple[1] - rightTuple[1];
    })
    .join(", ");
}

/** Schemas whose row shape carries per-row source_id (FK to taxonomy/sources)
 * rather than a top-level `sources` array. Per the canonical pivot
 * (CLAUDE.md §12.1, D18), reference taxonomy files don't carry a legacy
 * sources[] — provenance moves onto each row via source_id. */
const PER_ROW_PROVENANCE_SCHEMAS = new Set<string>([
  "entity.schema.json",
  "indicator-catalogue.schema.json",
  "source.schema.json",
  "observation.schema.json",
  "caveat.schema.json",
  "methodology-break.schema.json",
  "operator-state.schema.json",
  "manifest.schema.json",
  // concepts.json (PR-Z3a) is a hand-authored taxonomy of nouns, not a
  // dataset of observed series. Schema description: "sources[] left empty
  // (concepts are nouns, not series)". Provenance lives on each
  // indicator row's source_id FK, not on the concept registry itself.
  "concepts.schema.json",
  // office_holdings.json (G.1.c 2026-05-22) carries per-row references[]
  // (hand-authored Wikipedia/upstream citations) instead of a top-level
  // sources[] array. office_citations is a per-office map of canonical
  // url_main. Compiled Parquet rows (dim_offices, governments_office_holdings)
  // carry source_id FK; the authoring JSON is taxonomy-shaped.
  "office-holdings.schema.json",
  // Grapher render catalogues (ADR-0045) are frontend-owned UI hints — they
  // carry no observational data and no provenance; they're authored by the
  // frontend layer and validated against grapher-*-render.schema.json. They
  // are not subject to §12 sources[] (same logic as manifest.schema.json).
  "grapher-indicator-render.schema.json",
  "grapher-topic-render.schema.json",
  // Election tile-cartogram layouts (ADR-0048, PR-B1) are the same class of
  // frontend-owned grapher catalogue: each tile carries a per-row source_id
  // FK to the boundary geojson it was hexbinned from, so provenance lives on
  // the row (§12.1), not in a top-level sources[] (§12.2).
  "grapher-election-tile-layout.schema.json",
  // Schema compatibility is a control-plane policy registry, not observed
  // data. It is validated by its own schema and by schema-compatibility.test.ts.
  "schema-compatibility.schema.json",
  // Schema evolution is also control-plane release metadata: it records
  // schema releases, retained historical schema paths, and value-change
  // receipts. It is not an observed series and carries no sources[].
  "schema-evolution.schema.json",
]);

const SCHEMAS = loadSchemas();
const UNIQUE_SCHEMAS = uniqueSchemasByBasename(SCHEMAS);
const JSON_CORPUS_ACCEPTED_VERSIONS = loadJsonCorpusAcceptedVersions();

// One Ajv instance per process — shared across data-file checks.
const ajv = new Ajv2020({ strict: false, allErrors: true, allowUnionTypes: true });
addFormats(ajv);
for (const meta of SCHEMAS.values()) {
  // Register under both keys (full $id and basename) so ajv.getSchema resolves
  // either form. addSchema is idempotent by content but throws on duplicate id;
  // skip if already added.
  if (!ajv.getSchema(meta.id)) ajv.addSchema(meta.raw, meta.id);
  if (meta.basename !== meta.id && !ajv.getSchema(meta.basename)) {
    ajv.addSchema(meta.raw, meta.basename);
  }
}

interface DataFileRef {
  path: string;
  rel: string;
}

interface DataFile extends DataFileRef {
  schema: string | undefined;
  schemaVersion: string | undefined;
  body: Record<string, unknown>;
}

/**
 * Enumerate every JSON file under datasets/ (cheap — glob only, no parse).
 * Parsing happens lazily inside each `it()` so the I/O runs in the test
 * phase (parallelisable) rather than at collect time (single-threaded).
 * Before this split, collect dominated wall time (~39s collect vs ~6s tests
 * across ~7,500 files); after, collect drops to ~2s and total run halves.
 */
function listDataFiles(): DataFileRef[] {
  const files = globSync("**/*.json", { cwd: datasetsDir, absolute: true, ignore: ["schemas/**"] });
  return files.map(path => ({
    path,
    rel: path.slice(datasetsDir.length + 1).replaceAll("\\", "/"),
  }));
}

/** Parse one file on demand. Returns a DataFile with a __parseError sentinel on failure. */
function parseDataFile(ref: DataFileRef): DataFile {
  let body: Record<string, unknown>;
  try {
    body = JSON.parse(readFileSync(ref.path, "utf-8"));
  } catch (e) {
    return { ...ref, schema: undefined, schemaVersion: undefined, body: { __parseError: String(e) } };
  }
  return {
    ...ref,
    schema: typeof body["$schema"] === "string" ? (body["$schema"] as string) : undefined,
    schemaVersion: typeof body["$schema_version"] === "string" ? (body["$schema_version"] as string) : undefined,
    body,
  };
}

const DATA_FILE_REFS = listDataFiles();

describe("contract — schema registry sanity", () => {
  it("loads every *.schema.json in datasets/schemas/", () => {
    expect(SCHEMAS.size).toBeGreaterThan(0);
  });

  it("every schema has a non-empty $id and x-version", () => {
    for (const meta of SCHEMAS.values()) {
      expect(meta.id, meta.path).toBeTruthy();
      expect(meta.version, meta.path).toMatch(/^\d+\.\d+$/);
    }
  });

  it("workspace contains at least one shipped data artifact", () => {
    expect(DATA_FILE_REFS.length).toBeGreaterThan(0);
  });

  it("accepts current schema versions by default", () => {
    for (const schema of UNIQUE_SCHEMAS) {
      expect(JSON_CORPUS_ACCEPTED_VERSIONS.get(schema.basename), schema.basename).toContain(schema.version);
    }
  });

  it("accepts json-corpus additive minors but filters future and old-major overrides", () => {
    const processing = SCHEMAS.get("processing.schema.json");
    expect(processing).toBeDefined();

    const accepted = buildJsonCorpusAcceptedVersions({
      overrides: [{
        surface: "json-corpus",
        schema: "processing.schema.json",
        accepted_versions: ["2.0", "3.0", "3.1", "3.9"],
        validation: "current_schema",
      }],
    }, [processing!]);

    expect(accepted.get("processing.schema.json")).toEqual(new Set(["3.0", "3.1"]));
  });
});

// Per-file conformance. Each data file becomes one test so a failure
// names the offending file directly in the test output.
describe("contract — every datasets/*.json validates against its declared $schema", () => {
  for (const ref of DATA_FILE_REFS) {
    it(ref.rel, () => {
      const f = parseDataFile(ref);
      // Files that don't declare a $schema are out of scope for the contract
      // (e.g. raw_ephemeral_datasets/ snapshots, internal manifests).
      if (!f.schema) {
        return;
      }
      const schema = resolveSchema(f.schema);
      expect(schema, `unknown $schema ${f.schema} in ${f.rel}`).toBeDefined();
      // CLAUDE.md section 11: $schema_version MUST be accepted by the json-corpus contract.
      expect(f.schemaVersion, `${f.rel} missing $schema_version`).toBeDefined();
      const acceptedVersions = JSON_CORPUS_ACCEPTED_VERSIONS.get(schema!.basename) ?? new Set<string>();
      expect(
        acceptedVersions.has(f.schemaVersion!),
        `${f.rel}: $schema_version=${f.schemaVersion} not accepted for ${schema!.basename}; `
          + `accepted versions: ${formatVersions(acceptedVersions)}`,
      ).toBe(true);

      const validate = ajv.getSchema(f.schema) ?? ajv.getSchema(schema!.basename) ?? ajv.getSchema(schema!.id);
      expect(validate, `compiled validator missing for ${f.schema}`).toBeDefined();
      const ok = validate!(f.body);
      if (!ok) {
        const errors = (validate!.errors ?? []).map(
          e => `  ${e.instancePath || "/"} ${e.message} ${JSON.stringify(e.params)}`,
        ).join("\n");
        throw new Error(`${f.rel} fails ${f.schema}:\n${errors}`);
      }
    });
  }
});

describe("contract — provenance (CLAUDE.md §12)", () => {
  // Every file that declares a legacy schema MUST carry a `sources` array
  // (§12.2 — legacy JSON shape). Canonical-pivot files use per-row source_id
  // FK instead (§12.1, D18) — those are skipped here; their provenance is
  // checked downstream by the writer's FK gate (D22) and by Tier-A schema
  // sanity on the `source_id` field itself.
  for (const ref of DATA_FILE_REFS) {
    it(`${ref.rel} has a sources array (if it declares $schema)`, () => {
      const f = parseDataFile(ref);
      if (!f.schema) return;
      const schemaBasename = f.schema.split(/[\\/]/).pop()!;
      if (PER_ROW_PROVENANCE_SCHEMAS.has(schemaBasename)) return;
      expect(Array.isArray(f.body.sources), `${f.rel} missing sources[]`).toBe(true);
    });
  }
});

// Sanity check that the workspace layout is what we expected.
describe("contract — workspace layout", () => {
  it("datasets/schemas/ exists at the resolved repo root", () => {
    expect(existsSync(schemasDir)).toBe(true);
  });
});
