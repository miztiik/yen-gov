/**
 * Contract test (CLAUDE.md §11): every JSON artifact under datasets/ that
 * is reachable by the frontend MUST validate against its declared $schema,
 * AND its $schema_version MUST match the schema's current x-version.
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

interface SchemaMeta {
  path: string;
  id: string;
  basename: string;
  version: string;
  raw: Record<string, unknown>;
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
    const raw = JSON.parse(readFileSync(file, "utf-8")) as Record<string, unknown>;
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

/** Resolve a data file's $schema string against the loaded schemas, accepting
 * the full $id form or the basename form. */
function resolveSchema(declared: string): SchemaMeta | undefined {
  if (SCHEMAS.has(declared)) return SCHEMAS.get(declared);
  const basename = declared.split(/[\\/]/).pop()!;
  return SCHEMAS.get(basename);
}

/** Schemas whose row shape carries per-row source_id (FK to taxonomy/sources)
 * rather than a top-level `sources` array. Per the canonical pivot
 * (CLAUDE.md §12.1, D18), reference taxonomy files don't carry a legacy
 * sources[] — provenance moves onto each row via source_id. */
const PER_ROW_PROVENANCE_SCHEMAS = new Set<string>([
  "entity.schema.json",
  "facet-axes.schema.json",
  "indicator-catalogue.schema.json",
  "source.schema.json",
  "observation.schema.json",
  "caveat.schema.json",
  "methodology-break.schema.json",
  "operator-state.schema.json",
  "manifest.schema.json",
]);

const SCHEMAS = loadSchemas();

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
      // §11: $schema_version MUST match the schema's current x-version.
      expect(f.schemaVersion, `${f.rel} missing $schema_version`).toBeDefined();
      expect(f.schemaVersion, `${f.rel}: $schema_version=${f.schemaVersion} != x-version=${schema!.version}`)
        .toBe(schema!.version);

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
