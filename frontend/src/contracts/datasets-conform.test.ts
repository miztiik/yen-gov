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

interface DataFile {
  path: string;
  rel: string;
  schema: string | undefined;
  schemaVersion: string | undefined;
  body: Record<string, unknown>;
}

/** Discover every JSON file under datasets/ (excluding the schemas/ dir itself). */
function discoverDataFiles(): DataFile[] {
  const files = globSync("**/*.json", { cwd: datasetsDir, absolute: true, ignore: ["schemas/**"] });
  const out: DataFile[] = [];
  for (const path of files) {
    let body: Record<string, unknown>;
    try {
      body = JSON.parse(readFileSync(path, "utf-8"));
    } catch (e) {
      out.push({
        path, rel: path.slice(datasetsDir.length + 1).replaceAll("\\", "/"),
        schema: undefined, schemaVersion: undefined,
        body: { __parseError: String(e) } as Record<string, unknown>,
      });
      continue;
    }
    out.push({
      path,
      rel: path.slice(datasetsDir.length + 1).replaceAll("\\", "/"),
      schema: typeof body["$schema"] === "string" ? (body["$schema"] as string) : undefined,
      schemaVersion: typeof body["$schema_version"] === "string" ? (body["$schema_version"] as string) : undefined,
      body,
    });
  }
  return out;
}

const DATA_FILES = discoverDataFiles();

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
    expect(DATA_FILES.length).toBeGreaterThan(0);
  });
});

// Per-file conformance. Each data file becomes one test so a failure
// names the offending file directly in the test output.
describe("contract — every datasets/*.json validates against its declared $schema", () => {
  for (const f of DATA_FILES) {
    it(f.rel, () => {
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
  for (const f of DATA_FILES.filter(d => d.schema !== undefined)) {
    it(`${f.rel} has a sources array`, () => {
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
