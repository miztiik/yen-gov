import { describe, it, expect } from "vitest";
import { validateSql, FORBIDDEN_KEYWORDS } from "./sqlGuard";

describe("validateSql — happy path", () => {
  it("accepts a simple SELECT", () => {
    expect(validateSql("SELECT * FROM constituencies")).toEqual({ ok: true });
  });

  it("accepts a SELECT with one trailing semicolon", () => {
    expect(validateSql("SELECT 1;")).toEqual({ ok: true });
    expect(validateSql("SELECT 1;   \n")).toEqual({ ok: true });
  });

  it("accepts a SELECT containing line comments", () => {
    expect(validateSql("SELECT 1 -- inline note\n")).toEqual({ ok: true });
  });

  it("accepts a SELECT containing a block comment", () => {
    expect(validateSql("SELECT /* block */ 1")).toEqual({ ok: true });
  });

  it("allows a forbidden keyword that appears only inside a comment", () => {
    expect(validateSql("SELECT 1 -- DELETE FROM x\n")).toEqual({ ok: true });
    expect(validateSql("SELECT /* DROP TABLE x */ 1")).toEqual({ ok: true });
  });

  it("allows forbidden keyword as part of a longer identifier (whole-word match)", () => {
    expect(validateSql("SELECT CREATEDATE FROM t")).toEqual({ ok: true });
    expect(validateSql("SELECT my_drop_col FROM t")).toEqual({ ok: true });
  });
});

describe("validateSql — empty input", () => {
  it("rejects empty queries", () => {
    expect(validateSql("")).toEqual({ ok: false, reason: "Empty query." });
    expect(validateSql("   \n\t  ")).toEqual({ ok: false, reason: "Empty query." });
  });

  it("rejects queries that become empty after stripping comments", () => {
    expect(validateSql("-- only a comment")).toEqual({ ok: false, reason: "Empty query." });
    expect(validateSql("/* nothing */")).toEqual({ ok: false, reason: "Empty query." });
  });
});

describe("validateSql — multiple statements", () => {
  it("rejects two SELECTs in one run", () => {
    const r = validateSql("SELECT 1; SELECT 2");
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toMatch(/one statement/i);
  });

  it("rejects comment-smuggled second statement", () => {
    // A semicolon inside a comment is stripped; one inside a string would
    // still register here, but the fixture below puts a real second
    // statement after a stripped block comment.
    const r = validateSql("SELECT 1 /* sneaky */; DROP TABLE t");
    expect(r.ok).toBe(false);
  });
});

describe("validateSql — read-only enforcement (every forbidden keyword)", () => {
  for (const kw of FORBIDDEN_KEYWORDS) {
    it(`rejects a statement starting with ${kw}`, () => {
      const r = validateSql(`${kw} foo bar`);
      expect(r.ok).toBe(false);
      if (!r.ok) expect(r.reason).toContain(kw);
    });
  }

  it("is case-insensitive", () => {
    const r = validateSql("delete from t");
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain("DELETE");
  });

  it("rejects PRAGMA (sqlite-specific escape hatch)", () => {
    const r = validateSql("PRAGMA writable_schema = 1");
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain("PRAGMA");
  });

  it("rejects ATTACH DATABASE", () => {
    const r = validateSql("ATTACH DATABASE 'evil.db' AS evil");
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toContain("ATTACH");
  });
});
