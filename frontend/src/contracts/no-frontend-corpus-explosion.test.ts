// Guardrail for default frontend tests: source scans are fine, corpus walks
// are not. Frontend Vitest may inspect a constant-size set of source files,
// fixtures, and canaries, but it must not create test cases from live
// datasets/** cardinality.

import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { globSync } from "glob";

const repoRoot = resolve(fileURLToPath(new URL(".", import.meta.url)), "..", "..", "..");
const frontendRoot = resolve(repoRoot, "frontend");
const SELF = "src/contracts/no-frontend-corpus-explosion.test.ts";

const TEST_SOURCE_GLOBS = ["src/**/*.test.ts"] as const;

interface GuardViolation {
  file: string;
  rule: string;
  line: number;
  excerpt: string;
}

interface CallSite {
  text: string;
  offset: number;
}

function toPosixPath(path: string): string {
  return path.split(sep).join("/");
}

function lineNumberAt(source: string, offset: number): number {
  return source.slice(0, offset).split(/\r?\n/).length;
}

function excerpt(text: string): string {
  return text.replace(/\s+/g, " ").trim().slice(0, 220);
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function extractCall(source: string, name: string, offset: number): CallSite | undefined {
  const openParen = source.indexOf("(", offset);
  if (openParen === -1) return undefined;

  let depth = 0;
  let quote: string | undefined;
  let escaped = false;

  for (let index = openParen; index < source.length; index += 1) {
    const char = source[index];
    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === quote) {
        quote = undefined;
      }
      continue;
    }

    if (char === '"' || char === "'" || char === "`") {
      quote = char;
      continue;
    }
    if (char === "(") {
      depth += 1;
    } else if (char === ")") {
      depth -= 1;
      if (depth === 0) {
        return { text: source.slice(offset, index + 1), offset };
      }
    }
  }

  return { text: source.slice(offset, Math.min(source.length, offset + name.length + 500)), offset };
}

function findCalls(source: string, name: string): CallSite[] {
  const calls: CallSite[] = [];
  const pattern = new RegExp(`\\b${name}\\s*\\(`, "g");
  for (let match = pattern.exec(source); match; match = pattern.exec(source)) {
    const call = extractCall(source, name, match.index);
    if (call) calls.push(call);
  }
  return calls;
}

function firstStringArgument(call: string): string | undefined {
  const match = /\(\s*(["'`])([^"'`]+)\1/.exec(call);
  return match?.[2].replace(/\\/g, "/");
}

function namesDatasetsRoot(call: string, pattern: string | undefined): boolean {
  if (pattern?.startsWith("datasets/")) return true;
  return (
    /\b(?:datasetsDir|datasetsRoot|boundariesRoot|boundaryFamilyRoot|dataRoot)\b/.test(call) ||
    /resolve\s*\([\s\S]{0,180}["']datasets["'][\s\S]{0,180}\)/.test(call) ||
    /["']datasets\/(?:boundaries|data)[\/]/.test(call)
  );
}

function isBroadDatasetGlob(call: string): boolean {
  const pattern = firstStringArgument(call);
  if (!pattern) return false;
  const broadCorpusPattern =
    /(?:^|\/)\*\*\/\*\.(?:geojson|topojson|json)$/.test(pattern) ||
    /(?:^|\/)\*\*\/\*\.\{[^}]*\b(?:geojson|topojson|json)\b[^}]*\}/.test(pattern) ||
    /^datasets\/\*\*\//.test(pattern);
  return broadCorpusPattern && namesDatasetsRoot(call, pattern);
}

function hasDatasetsBoundaryOrDataRoot(source: string): boolean {
  return (
    /resolve\s*\([\s\S]{0,180}["']datasets["']\s*,\s*["'](?:boundaries|data)["']/.test(source) ||
    /["']datasets\/(?:boundaries|data)[\/]/.test(source)
  );
}

function matchingBraceOffset(source: string, openBraceOffset: number): number | undefined {
  let depth = 0;
  let quote: string | undefined;
  let escaped = false;

  for (let index = openBraceOffset; index < source.length; index += 1) {
    const char = source[index];
    if (quote) {
      if (escaped) {
        escaped = false;
      } else if (char === "\\") {
        escaped = true;
      } else if (char === quote) {
        quote = undefined;
      }
      continue;
    }

    if (char === '"' || char === "'" || char === "`") {
      quote = char;
      continue;
    }
    if (char === "{") {
      depth += 1;
    } else if (char === "}") {
      depth -= 1;
      if (depth === 0) return index;
    }
  }

  return undefined;
}

function functionBody(source: string, functionOffset: number): string | undefined {
  const openBraceOffset = source.indexOf("{", functionOffset);
  if (openBraceOffset === -1) return undefined;
  const closeBraceOffset = matchingBraceOffset(source, openBraceOffset);
  if (closeBraceOffset === undefined) return undefined;
  return source.slice(openBraceOffset + 1, closeBraceOffset);
}

function hasRecursiveReadDir(source: string): boolean {
  const declarationPattern = /function\s*\*?\s+(\w+)\s*\([^)]*\)\s*(?::[^{}]+)?\{/g;
  for (let match = declarationPattern.exec(source); match; match = declarationPattern.exec(source)) {
    const body = functionBody(source, match.index);
    if (!body?.includes("readdirSync")) continue;
    if (new RegExp(`\\b${escapeRegExp(match[1])}\\s*\\(`).test(body)) return true;
  }

  const arrowPattern = /const\s+(\w+)\s*=\s*(?:\([^)]*\)|\w+)\s*(?::[^=]+)?=>\s*\{/g;
  for (let match = arrowPattern.exec(source); match; match = arrowPattern.exec(source)) {
    const body = functionBody(source, match.index);
    if (!body?.includes("readdirSync")) continue;
    if (new RegExp(`\\b${escapeRegExp(match[1])}\\s*\\(`).test(body)) return true;
  }

  return false;
}

function assignedBroadCorpusLists(source: string): { name: string; offset: number; call: string }[] {
  const assignments: { name: string; offset: number; call: string }[] = [];
  const pattern = /\b(?:const|let|var)\s+(\w+)\s*=\s*globSync\s*\(/g;
  for (let match = pattern.exec(source); match; match = pattern.exec(source)) {
    const callOffset = source.indexOf("globSync", match.index);
    const call = extractCall(source, "globSync", callOffset);
    if (call && isBroadDatasetGlob(call.text)) {
      assignments.push({ name: match[1], offset: match.index, call: call.text });
    }
  }
  return assignments;
}

function generatedTestOffsetFor(source: string, listName: string): number | undefined {
  const variable = escapeRegExp(listName);
  const patterns = [
    new RegExp(`\\b(?:it|test)\\.each\\s*\\(\\s*${variable}\\b`),
    new RegExp(`for\\s*\\([^)]*\\bof\\s+${variable}\\b[^)]*\\)\\s*\\{[\\s\\S]{0,900}\\b(?:it|test)\\s*\\(`),
    new RegExp(`${variable}\\.forEach\\s*\\([\\s\\S]{0,900}\\b(?:it|test)\\s*\\(`),
  ];
  const offsets = patterns
    .map(pattern => source.search(pattern))
    .filter(offset => offset >= 0);
  return offsets.length > 0 ? Math.min(...offsets) : undefined;
}

function scanSource(source: string, file: string): GuardViolation[] {
  const violations: GuardViolation[] = [];

  for (const call of findCalls(source, "globSync")) {
    if (!isBroadDatasetGlob(call.text)) continue;
    violations.push({
      file,
      rule: "broad-dataset-glob",
      line: lineNumberAt(source, call.offset),
      excerpt: excerpt(call.text),
    });
  }

  if (hasDatasetsBoundaryOrDataRoot(source) && hasRecursiveReadDir(source)) {
    const offset = source.search(/readdirSync\s*\(/);
    violations.push({
      file,
      rule: "recursive-dataset-readdir",
      line: lineNumberAt(source, Math.max(offset, 0)),
      excerpt: "recursive readdirSync rooted at datasets/boundaries or datasets/data",
    });
  }

  for (const assignment of assignedBroadCorpusLists(source)) {
    const offset = generatedTestOffsetFor(source, assignment.name);
    if (offset === undefined) continue;
    violations.push({
      file,
      rule: "generated-tests-from-corpus-list",
      line: lineNumberAt(source, offset),
      excerpt: `${assignment.name} from ${excerpt(assignment.call)} feeds generated it/test blocks`,
    });
  }

  return violations;
}

function frontendTestSources(): string[] {
  return TEST_SOURCE_GLOBS.flatMap(pattern =>
    globSync(pattern, { cwd: frontendRoot, absolute: true, nodir: true }),
  ).sort();
}

describe("frontend corpus-cardinality guard", () => {
  it("rejects broad dataset glob lists that generate tests", () => {
    const bad = String.raw`
      import { globSync } from "glob";
      import { it } from "vitest";
      const datasetsDir = resolve(repoRoot, "datasets");
      const files = globSync("**/*.geojson", { cwd: datasetsDir, absolute: true });
      for (const file of files) {
        it(file, () => expect(file).toBeTruthy());
      }
    `;

    expect(scanSource(bad, "src/contracts/bad.test.ts").map(violation => violation.rule)).toEqual([
      "broad-dataset-glob",
      "generated-tests-from-corpus-list",
    ]);
  });

  it("rejects recursive dataset directory walkers", () => {
    const bad = String.raw`
      const corpusRoot = resolve(repoRoot, "datasets", "boundaries");
      function walkCorpus(dir: string): string[] {
        const out: string[] = [];
        for (const entry of readdirSync(dir, { withFileTypes: true })) {
          if (entry.isDirectory()) out.push(...walkCorpus(resolve(dir, entry.name)));
        }
        return out;
      }
      const files = walkCorpus(corpusRoot);
      expect(files.length).toBe(4700);
    `;

    expect(scanSource(bad, "src/contracts/bad-recursive.test.ts").map(violation => violation.rule)).toContain(
      "recursive-dataset-readdir",
    );
  });

  it("accepts bounded explicit canary lists", () => {
    const good = String.raw`
      const BOUNDARY_CANARIES = [
        // Canary: root singleton path shape.
        "states/all.geojson",
        // Canary: nested partition path shape.
        "panchayats/state=tamil-nadu/district=568/all.topojson",
      ] as const;

      it.each(BOUNDARY_CANARIES)("%s is readable", (relPath) => {
        expect(relPath).toMatch(/all\.(?:geojson|topojson)$/);
      });
    `;

    expect(scanSource(good, "src/contracts/good-canary.test.ts")).toEqual([]);
  });

  it("default frontend Vitest source files do not reintroduce corpus-sized tests", () => {
    const violations = frontendTestSources().flatMap(absPath => {
      const relPath = toPosixPath(relative(frontendRoot, absPath));
      if (relPath === SELF) return [];
      return scanSource(readFileSync(absPath, "utf8"), relPath);
    });

    expect(
      violations,
      `Default frontend Vitest must stay constant-size. Use fixtures or explicit canaries here; move exhaustive datasets/** proof to backend Tier-B or producer receipts.\n${JSON.stringify(violations, null, 2)}`,
    ).toEqual([]);
  });
});