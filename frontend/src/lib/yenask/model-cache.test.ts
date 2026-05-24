// Tests for model-cache.ts.
//
// jsdom does not polyfill the Cache Storage API, so every test uses an
// in-memory stub that records calls and returns canned Responses. The
// stub mirrors the real API closely enough that swapping it for
// `globalThis.caches` in the browser is a one-line change at the call
// site.

import { describe, expect, it } from "vitest";
import {
  type CacheLike,
  type CacheStorageLike,
  clearAllCache,
  deleteModel,
  estimateModelSizeBytes,
  formatCacheSize,
  hasCacheStorage,
  listCachedRepoIds,
  parseRepoIdFromUrl,
} from "./model-cache";

/**
 * In-memory CacheStorageLike. `entries` maps URL → byte-count; the stub
 * returns a Response whose body is a zero-filled Blob of that size, so
 * `estimateModelSizeBytes` exercises the real `response.blob().size`
 * path under test.
 */
function makeStub(entries: Record<string, number>): {
  readonly storage: CacheStorageLike;
} {
  let exists = Object.keys(entries).length > 0;
  const cache: CacheLike = {
    async keys() {
      return Object.keys(entries).map((url) => ({ url }) as Request);
    },
    async match(req: Request | string) {
      const url = typeof req === "string" ? req : req.url;
      const size = entries[url];
      if (size === undefined) return undefined;
      return new Response(new Blob([new Uint8Array(size)]));
    },
    async delete(req: Request | string) {
      const url = typeof req === "string" ? req : req.url;
      if (url in entries) {
        delete entries[url];
        if (Object.keys(entries).length === 0) {
          // matches real Cache Storage: `caches.has(name)` keeps reporting
          // true even when the cache is empty; only `caches.delete(name)`
          // makes `has(name)` return false. Don't change `exists` here.
        }
        return true;
      }
      return false;
    },
  };
  return {
    storage: {
      async open() {
        return cache;
      },
      async delete() {
        if (exists) {
          exists = false;
          for (const k of Object.keys(entries)) delete entries[k];
          return true;
        }
        return false;
      },
      async has() {
        return exists;
      },
    },
  };
}

describe("parseRepoIdFromUrl", () => {
  it("extracts org/name from a resolve URL", () => {
    expect(
      parseRepoIdFromUrl(
        "https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct/resolve/main/onnx/model.onnx",
      ),
    ).toBe("HuggingFaceTB/SmolLM2-135M-Instruct");
  });

  it("extracts org/name from a raw URL", () => {
    expect(
      parseRepoIdFromUrl(
        "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct/raw/main/tokenizer.json",
      ),
    ).toBe("Qwen/Qwen2.5-1.5B-Instruct");
  });

  it("returns null for a non-HuggingFace host", () => {
    expect(
      parseRepoIdFromUrl("https://example.com/Org/Name/resolve/main/f"),
    ).toBeNull();
  });

  it("returns null when the third path segment is not resolve|raw", () => {
    expect(
      parseRepoIdFromUrl(
        "https://huggingface.co/Org/Name/tree/main/file",
      ),
    ).toBeNull();
  });

  it("returns null for malformed URLs", () => {
    expect(parseRepoIdFromUrl("not a url")).toBeNull();
  });

  it("returns null when the path has too few segments", () => {
    expect(parseRepoIdFromUrl("https://huggingface.co/org")).toBeNull();
  });
});

describe("formatCacheSize", () => {
  it("returns em-dash for 0", () => {
    expect(formatCacheSize(0)).toBe("\u2014");
  });

  it("returns em-dash for negative", () => {
    expect(formatCacheSize(-1)).toBe("\u2014");
  });

  it("returns em-dash for NaN", () => {
    expect(formatCacheSize(Number.NaN)).toBe("\u2014");
  });

  it("formats bytes (no decimals)", () => {
    expect(formatCacheSize(512)).toBe("512 B");
  });

  it("formats KB (1 decimal)", () => {
    expect(formatCacheSize(2048)).toBe("2.0 KB");
  });

  it("formats MB (1 decimal)", () => {
    expect(formatCacheSize(5 * 1024 * 1024)).toBe("5.0 MB");
  });

  it("formats GB (2 decimals)", () => {
    expect(formatCacheSize(2 * 1024 * 1024 * 1024)).toBe("2.00 GB");
  });
});

describe("hasCacheStorage", () => {
  it("returns false when cacheStorage is null", async () => {
    expect(await hasCacheStorage(null)).toBe(false);
  });

  it("returns true when the stub reports the cache exists", async () => {
    const { storage } = makeStub({
      "https://huggingface.co/Org/Name/resolve/main/file": 100,
    });
    expect(await hasCacheStorage(storage)).toBe(true);
  });

  it("returns false when the stub reports the cache is absent", async () => {
    const { storage } = makeStub({});
    expect(await hasCacheStorage(storage)).toBe(false);
  });

  it("returns false when has() throws", async () => {
    const broken: CacheStorageLike = {
      async open() {
        throw new Error("denied");
      },
      async delete() {
        return false;
      },
      async has() {
        throw new Error("denied");
      },
    };
    expect(await hasCacheStorage(broken)).toBe(false);
  });
});

describe("listCachedRepoIds", () => {
  it("returns [] when cacheStorage is null", async () => {
    expect(await listCachedRepoIds(null)).toEqual([]);
  });

  it("returns [] when the cache is absent", async () => {
    const { storage } = makeStub({});
    expect(await listCachedRepoIds(storage)).toEqual([]);
  });

  it("deduplicates repo_ids across multiple cached files", async () => {
    const { storage } = makeStub({
      "https://huggingface.co/Org/Foo/resolve/main/model.onnx": 100,
      "https://huggingface.co/Org/Foo/resolve/main/tokenizer.json": 50,
      "https://huggingface.co/Org/Bar/resolve/main/model.onnx": 200,
    });
    expect(await listCachedRepoIds(storage)).toEqual([
      "Org/Bar",
      "Org/Foo",
    ]);
  });

  it("ignores entries from non-HuggingFace hosts", async () => {
    const { storage } = makeStub({
      "https://cdn.example.com/x/y/resolve/main/z": 999,
      "https://huggingface.co/Org/Foo/resolve/main/model.onnx": 100,
    });
    expect(await listCachedRepoIds(storage)).toEqual(["Org/Foo"]);
  });
});

describe("estimateModelSizeBytes", () => {
  it("returns 0 when cacheStorage is null", async () => {
    expect(await estimateModelSizeBytes("Org/Foo", null)).toBe(0);
  });

  it("returns 0 when the cache is absent", async () => {
    const { storage } = makeStub({});
    expect(await estimateModelSizeBytes("Org/Foo", storage)).toBe(0);
  });

  it("sums the sizes of matching entries only", async () => {
    const { storage } = makeStub({
      "https://huggingface.co/Org/Foo/resolve/main/a": 100,
      "https://huggingface.co/Org/Foo/resolve/main/b": 250,
      "https://huggingface.co/Org/Bar/resolve/main/c": 999,
    });
    expect(await estimateModelSizeBytes("Org/Foo", storage)).toBe(350);
  });

  it("returns 0 when no entry matches the repo", async () => {
    const { storage } = makeStub({
      "https://huggingface.co/Org/Foo/resolve/main/a": 100,
    });
    expect(await estimateModelSizeBytes("Org/Missing", storage)).toBe(0);
  });
});

describe("deleteModel", () => {
  it("returns 0 when cacheStorage is null", async () => {
    expect(await deleteModel("Org/Foo", null)).toBe(0);
  });

  it("returns 0 when the cache is absent", async () => {
    const { storage } = makeStub({});
    expect(await deleteModel("Org/Foo", storage)).toBe(0);
  });

  it("removes only matching entries and returns the count", async () => {
    const { storage } = makeStub({
      "https://huggingface.co/Org/Foo/resolve/main/a": 100,
      "https://huggingface.co/Org/Foo/resolve/main/b": 50,
      "https://huggingface.co/Org/Bar/resolve/main/c": 200,
    });
    expect(await deleteModel("Org/Foo", storage)).toBe(2);
    expect(await listCachedRepoIds(storage)).toEqual(["Org/Bar"]);
  });

  it("returns 0 when no entry matches the repo", async () => {
    const { storage } = makeStub({
      "https://huggingface.co/Org/Foo/resolve/main/a": 100,
    });
    expect(await deleteModel("Org/Missing", storage)).toBe(0);
    expect(await listCachedRepoIds(storage)).toEqual(["Org/Foo"]);
  });
});

describe("clearAllCache", () => {
  it("returns false when cacheStorage is null", async () => {
    expect(await clearAllCache(null)).toBe(false);
  });

  it("returns true when the cache existed and was removed", async () => {
    const { storage } = makeStub({
      "https://huggingface.co/Org/Foo/resolve/main/a": 100,
    });
    expect(await clearAllCache(storage)).toBe(true);
    expect(await listCachedRepoIds(storage)).toEqual([]);
  });

  it("returns false when the cache was already absent", async () => {
    const { storage } = makeStub({});
    expect(await clearAllCache(storage)).toBe(false);
  });

  it("returns false when delete() throws", async () => {
    const broken: CacheStorageLike = {
      async open() {
        throw new Error("denied");
      },
      async delete() {
        throw new Error("denied");
      },
      async has() {
        return true;
      },
    };
    expect(await clearAllCache(broken)).toBe(false);
  });
});
