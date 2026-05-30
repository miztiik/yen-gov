import registry from "../../../../datasets/schema-compatibility.json";

export const CANONICAL_MANIFEST_READER_SURFACE = "canonical-manifest-reader";

interface CompatibilityOverride {
  surface: string;
  schema: string;
  accepted_versions: readonly string[];
}

interface CompatibilityRegistry {
  overrides: readonly CompatibilityOverride[];
}

function canonicalManifestReaderVersions(
  compatibilityRegistry: CompatibilityRegistry,
): Record<string, readonly string[]> {
  return Object.freeze(Object.fromEntries(
    compatibilityRegistry.overrides
      .filter(row => row.surface === CANONICAL_MANIFEST_READER_SURFACE)
      .map(row => [row.schema, Object.freeze([...row.accepted_versions])]),
  ));
}

export const CANONICAL_MANIFEST_READER_SCHEMA_VERSIONS = canonicalManifestReaderVersions(registry);

export function acceptedSchemaVersions(schemaFile: string): readonly string[] {
  return CANONICAL_MANIFEST_READER_SCHEMA_VERSIONS[schemaFile] ?? [];
}

export const SUPPORTED_SCHEMA_VERSIONS = CANONICAL_MANIFEST_READER_SCHEMA_VERSIONS;
