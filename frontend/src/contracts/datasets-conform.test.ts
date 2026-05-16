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
  version: string;
  raw: Record<string, unknown>;
}

/** Build an $id → schema map by scanning datasets/schemas/. */
function loadSchemas(): Map<string, SchemaMeta> {
  const out = new Map<string, SchemaMeta>();
  for (const file of globSync("*.schema.json", { cwd: schemasDir, absolute: true })) {
    const raw = JSON.parse(readFileSync(file, "utf-8")) as Record<string, unknown>;
    const id = String(raw["$id"] ?? "");
    const version = String(raw["x-version"] ?? "");
    if (!id || !version) {
      throw new Error(`schema ${file} missing $id or x-version`);
    }
    out.set(id, { path: file, id, version, raw });
  }
  return out;
}

const SCHEMAS = loadSchemas();

// One Ajv instance per process — shared across data-file checks.
const ajv = new Ajv2020({ strict: false, allErrors: true, allowUnionTypes: true });
addFormats(ajv);
for (const meta of SCHEMAS.values()) {
  ajv.addSchema(meta.raw, meta.id);
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
      const schema = SCHEMAS.get(f.schema);
      expect(schema, `unknown $schema ${f.schema} in ${f.rel}`).toBeDefined();
      // §11: $schema_version MUST match the schema's current x-version.
      expect(f.schemaVersion, `${f.rel} missing $schema_version`).toBeDefined();
      expect(f.schemaVersion, `${f.rel}: $schema_version=${f.schemaVersion} != x-version=${schema!.version}`)
        .toBe(schema!.version);

      const validate = ajv.getSchema(f.schema);
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
  // Every file that declares a $schema MUST also carry a `sources` array
  // (per §12 — empty array is the canonical "hand-authored" signal).
  // We iterate over every file (cheap glob result) and short-circuit inside
  // the test when no $schema is declared; this avoids a second parse pass
  // at collect time just to filter the list.
  for (const ref of DATA_FILE_REFS) {
    it(`${ref.rel} has a sources array (if it declares $schema)`, () => {
      const f = parseDataFile(ref);
      if (!f.schema) return;
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
