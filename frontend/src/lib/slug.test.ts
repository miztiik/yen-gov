import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  slugify,
  acSlug,
  parseAcSlug,
  partyIdToSlug,
  partyIdFromSlug,
} from "./slug";

describe("slugify", () => {
  it("lowercases ASCII and collapses whitespace to single dash", () => {
    expect(slugify("Tamil Nadu")).toBe("tamil-nadu");
    expect(slugify("  multi   space  ")).toBe("multi-space");
  });

  it("strips diacritics via NFKD", () => {
    expect(slugify("Mylāpore")).toBe("mylapore");
    expect(slugify("Pondichéry")).toBe("pondichery");
  });

  it("collapses punctuation runs into a single dash", () => {
    expect(slugify("Foo & Bar / Baz")).toBe("foo-bar-baz");
    expect(slugify("a__b--c..d")).toBe("a-b-c-d");
  });

  it("strips leading and trailing dashes", () => {
    expect(slugify("---hello---")).toBe("hello");
  });

  it("returns empty string for input that has no [a-z0-9]", () => {
    expect(slugify("!!!")).toBe("");
    expect(slugify("")).toBe("");
  });
});

describe("acSlug", () => {
  it("composes numeric prefix and slugified name", () => {
    expect(acSlug(167, "Mylapore")).toBe("167-mylapore");
    expect(acSlug(2866, "Tiruvallur")).toBe("2866-tiruvallur");
  });

  it("falls back to bare number when name slugifies to empty", () => {
    expect(acSlug(167, "")).toBe("167");
    expect(acSlug(167, "###")).toBe("167");
  });
});

describe("parseAcSlug", () => {
  it("extracts eci_no from full slug", () => {
    expect(parseAcSlug("167-mylapore")).toBe(167);
    expect(parseAcSlug("2866-tiruvallur-east")).toBe(2866);
  });

  it("accepts bare numeric slug", () => {
    expect(parseAcSlug("167")).toBe(167);
  });

  it("returns null when slug does not start with digits", () => {
    expect(parseAcSlug("mylapore")).toBeNull();
    expect(parseAcSlug("")).toBeNull();
    expect(parseAcSlug("-167")).toBeNull();
  });

  it("round-trips against acSlug for a representative AC", () => {
    const slug = acSlug(167, "Mylapore");
    expect(parseAcSlug(slug)).toBe(167);
  });
});

describe("partyIdToSlug (ADR-0053)", () => {
  it("derives the lowercased party_id tail for common parties", () => {
    expect(partyIdToSlug("parties.IN.INC")).toBe("inc");
    expect(partyIdToSlug("parties.IN.BJP")).toBe("bjp");
    expect(partyIdToSlug("parties.IN.DMK")).toBe("dmk");
    expect(partyIdToSlug("parties.IN.AIADMK")).toBe("aiadmk");
    expect(partyIdToSlug("parties.IN.YSRCP")).toBe("ysrcp");
  });

  it("preserves the CPIM / JDU / JDS shape (parties.csv uses concatenated form)", () => {
    expect(partyIdToSlug("parties.IN.CPIM")).toBe("cpim");
    expect(partyIdToSlug("parties.IN.JDU")).toBe("jdu");
    expect(partyIdToSlug("parties.IN.JDS")).toBe("jds");
  });

  it("converts underscores to dashes for compound tails", () => {
    expect(partyIdToSlug("parties.IN.BSP_A")).toBe("bsp-a");
    expect(partyIdToSlug("parties.IN.CPI_ML_L")).toBe("cpi-ml-l");
    expect(partyIdToSlug("parties.IN.SHS_UBT")).toBe("shs-ubt");
    expect(partyIdToSlug("parties.IN.NCP_SP")).toBe("ncp-sp");
  });

  it("applies the Independent sentinel override (spelled-out)", () => {
    // Hans verdict 5: "IND" is publisher shorthand; "independent" is
    // the noun the citizen reads when sharing the link.
    expect(partyIdToSlug("parties.IN.IND")).toBe("independent");
  });

  it("applies the Arunachal Congress disambiguator override", () => {
    // Bare tail `ac` collides with the RESERVED `ac` chrome token
    // (bare-AC sub-namespace marker). Spelled-out per the same
    // citizen-framing doctrine as Independent.
    expect(partyIdToSlug("parties.IN.AC")).toBe("arunachal-congress");
  });

  it("applies the Goa party disambiguator override (vs state slug)", () => {
    // Bare tail `goa` collides with the state slug `goa`. Spelled-out
    // using the party's `full` name from parties.csv.
    expect(partyIdToSlug("parties.IN.GOA")).toBe("goemcarancho-otrec-astro");
  });

  it("applies the Mahakranti Dal disambiguator override (vs AC slug)", () => {
    // Bare tail `mahad` collides with the AC slug `mahad`
    // (Maharashtra constituency no. 194). Spelled-out using the
    // party's `full` name from parties.csv.
    expect(partyIdToSlug("parties.IN.MAHAD")).toBe("mahakranti-dal");
  });

  it("applies the JIND party disambiguator override (vs current AC slug)", () => {
    // Bare tail `jind` collides with the current Haryana AC slug
    // `jind`. parties.csv does not carry a useful full name for this
    // row (`full` is `NA's`), so the namespace suffix is the least
    // misleading disambiguator.
    expect(partyIdToSlug("parties.IN.JIND")).toBe("jind-party");
  });

  it("emits the bare tail for NOTA (no override needed)", () => {
    expect(partyIdToSlug("parties.IN.NOTA")).toBe("nota");
  });

  it("returns null for the UNK resolver-fallback sentinel", () => {
    // UNK has NO citizen page — it's operator telemetry. Callers
    // MUST fall back to `party_short_raw` plain text.
    expect(partyIdToSlug("parties.IN.UNK")).toBeNull();
  });

  it("handles party_ids without the parties.IN. prefix (degenerate)", () => {
    // The function takes anything containing a dot and returns the
    // last segment. Pathological input still returns a usable string.
    expect(partyIdToSlug("FOO")).toBe("foo");
    expect(partyIdToSlug("namespace.BAR")).toBe("bar");
  });
});

describe("partyIdFromSlug (ADR-0053)", () => {
  it("reverses the bare-tail derivation", () => {
    expect(partyIdFromSlug("inc")).toBe("parties.IN.INC");
    expect(partyIdFromSlug("bjp")).toBe("parties.IN.BJP");
    expect(partyIdFromSlug("dmk")).toBe("parties.IN.DMK");
    expect(partyIdFromSlug("aiadmk")).toBe("parties.IN.AIADMK");
  });

  it("reverses the dash-to-underscore mapping", () => {
    expect(partyIdFromSlug("bsp-a")).toBe("parties.IN.BSP_A");
    expect(partyIdFromSlug("cpi-ml-l")).toBe("parties.IN.CPI_ML_L");
    expect(partyIdFromSlug("shs-ubt")).toBe("parties.IN.SHS_UBT");
  });

  it("reverses the sentinel override for Independent", () => {
    expect(partyIdFromSlug("independent")).toBe("parties.IN.IND");
  });

  it("reverses the Arunachal Congress override", () => {
    expect(partyIdFromSlug("arunachal-congress")).toBe("parties.IN.AC");
  });

  it("reverses the Goa party disambiguator override", () => {
    expect(partyIdFromSlug("goemcarancho-otrec-astro")).toBe("parties.IN.GOA");
  });

  it("reverses the Mahakranti Dal disambiguator override", () => {
    expect(partyIdFromSlug("mahakranti-dal")).toBe("parties.IN.MAHAD");
  });

  it("reverses the JIND party disambiguator override", () => {
    expect(partyIdFromSlug("jind-party")).toBe("parties.IN.JIND");
  });

  it("recovers parties.IN.NOTA from the bare nota slug", () => {
    expect(partyIdFromSlug("nota")).toBe("parties.IN.NOTA");
  });
});

describe("partyIdToSlug round-trip against the live parties.csv corpus", () => {
  // Walks the on-disk parties.csv and asserts that
  // `partyIdFromSlug(partyIdToSlug(pid)) === pid` for every row except
  // the no-page sentinels. This is the Tier-A invariant that catches
  // any future ingest that mints a party_id whose slug derivation is
  // ambiguous (e.g. a tail with characters the inverse can't recover).
  const repoRoot = resolve(
    fileURLToPath(new URL(".", import.meta.url)),
    "..",
    "..",
    "..",
  );
  const partiesCsvPath = resolve(repoRoot, "datasets/data/entities/parties.csv");

  it("every parties.csv party_id (except UNK) round-trips through the slug derivation", () => {
    const csv = readFileSync(partiesCsvPath, "utf-8");
    const lines = csv.split(/\r?\n/).filter((l) => l.length > 0);
    lines.shift(); // header
    const ids: string[] = [];
    for (const line of lines) {
      const pid = line.split(",", 1)[0];
      if (pid) ids.push(pid);
    }
    expect(ids.length).toBeGreaterThanOrEqual(1000);

    const failures: { pid: string; slug: string | null; recovered: string }[] = [];
    for (const pid of ids) {
      const slug = partyIdToSlug(pid);
      if (slug === null) continue; // UNK: no page, no round-trip
      const recovered = partyIdFromSlug(slug);
      if (recovered !== pid) failures.push({ pid, slug, recovered });
    }
    expect(failures).toEqual([]);
  });
});
