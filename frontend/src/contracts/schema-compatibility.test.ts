import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { globSync } from "glob";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import { SUPPORTED_SCHEMA_VERSIONS } from "../lib/canonical/types";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const datasetsDir = resolve(repoRoot, "datasets");
const schemasDir = resolve(datasetsDir, "schemas");
const registryPath = resolve(datasetsDir, "schema-compatibility.json");
const registrySchemaPath = resolve(schemasDir, "schema-compatibility.schema.json");

interface CompatibilityOverride {
  surface: string;
  schema: string;
  accepted_versions: string[];
  validation: string;
  rationale: string;
}

interface CompatibilityRegistry {
  $schema: string;
  $schema_version: string;
  defaults: unknown[];
  overrides: CompatibilityOverride[];
}

function readJson<T>(path: string): T {
  return JSON.parse(readFileSync(path, "utf-8")) as T;
}

function schemaVersions(): Map<string, string> {
  const out = new Map<string, string>();
  for (const file of globSync("*.schema.json", { cwd: schemasDir, absolute: true })) {
    const doc = readJson<Record<string, unknown>>(file);
    const basename = file.split(/[\\/]/).pop()!;
    out.set(basename, String(doc["x-version"] ?? ""));
  }
  return out;
}

function versionTuple(version: string): [number, number] {
  const [major, minor] = version.split(".").map(Number);
  return [major, minor];
}

function compareVersion(left: string, right: string): number {
  const [leftMajor, leftMinor] = versionTuple(left);
  const [rightMajor, rightMinor] = versionTuple(right);
  return leftMajor - rightMajor || leftMinor - rightMinor;
}

const registry = readJson<CompatibilityRegistry>(registryPath);
const registrySchema = readJson<Record<string, unknown>>(registrySchemaPath);

describe("contract - schema compatibility registry", () => {
  it("validates against schema-compatibility.schema.json", () => {
    const ajv = new Ajv2020({ strict: false, allErrors: true });
    addFormats(ajv);
    const validate = ajv.compile(registrySchema);

    const ok = validate(registry);
    if (!ok) {
      const errors = (validate.errors ?? [])
        .map(error => `  ${error.instancePath || "/"} ${error.message} ${JSON.stringify(error.params)}`)
        .join("\n");
      throw new Error(`schema-compatibility.json fails schema:\n${errors}`);
    }
  });

  it("references existing current schemas and sorted accepted versions", () => {
    const versions = schemaVersions();

    expect(registry.overrides.length).toBeGreaterThan(0);
    for (const override of registry.overrides) {
      const current = versions.get(override.schema);
      expect(current, `${override.schema} is missing under datasets/schemas/`).toBeDefined();
      expect(override.accepted_versions, `${override.schema} must include current version`).toContain(current);
      expect(override.accepted_versions, `${override.schema} versions must be sorted`)
        .toEqual([...override.accepted_versions].sort(compareVersion));
    }
  });

  it("does not name old major versions without a retained-schema path", () => {
    const versions = schemaVersions();

    for (const override of registry.overrides) {
      const current = versions.get(override.schema)!;
      const [currentMajor] = versionTuple(current);
      const acceptedMajors = new Set(override.accepted_versions.map(version => versionTuple(version)[0]));

      expect(acceptedMajors, `${override.schema} accepts an old major without retained schemas`).toEqual(
        new Set([currentMajor]),
      );
    }
  });

  it("does not outrun the current frontend canonical reader constant", () => {
    for (const override of registry.overrides.filter(row => row.surface === "canonical-manifest-reader")) {
      const currentRuntimeSet = SUPPORTED_SCHEMA_VERSIONS[override.schema] ?? [];

      expect(
        currentRuntimeSet,
        `${override.schema} registry support is ahead of SUPPORTED_SCHEMA_VERSIONS; Row G must derive runtime support before this can expand`,
      ).toEqual(expect.arrayContaining(override.accepted_versions));
    }
  });
});
