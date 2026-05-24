// YENASK model cache — operations on the browser's transformers-cache.
//
// @huggingface/transformers v3+ caches model assets in the Cache Storage
// API under the cache name "transformers-cache". Each cached file is a
// Response object keyed by its HuggingFace CDN URL, e.g.:
//
//   https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct/resolve/main/onnx/model_q4f16.onnx
//
// This module wraps the Cache Storage API with four operator-facing
// primitives used by the model picker:
//
//   listCachedRepoIds()       — which models have at least one cached file?
//   estimateModelSizeBytes()  — how big is the cache for a specific repo?
//   deleteModel()             — remove all cached files for a specific repo
//   clearAllCache()           — drop the whole transformers-cache
//
// All four accept an optional `CacheStorageLike` injection so they can
// be unit-tested without the browser Cache Storage API (which jsdom does
// NOT polyfill). The default uses `globalThis.caches`.
//
// Per Slice B (plan-doc D-22 Jony AMEND verdict): the picker shows
// per-model cache state and a per-model Delete-from-cache action;
// nothing forces the cache to be deletable as a single all-or-nothing
// blob from the citizen UI. The model-registry remains the source of
// truth for "which models exist"; clearing the cache does NOT remove a
// model from the picker (it just resets that model's cache state to
// "Not downloaded").

const TRANSFORMERS_CACHE_NAME = "transformers-cache";

/** Minimal subset of the Cache interface we depend on. */
export interface CacheLike {
  keys(): Promise<readonly Request[]>;
  match(request: Request | string): Promise<Response | undefined>;
  delete(request: Request | string): Promise<boolean>;
}

/** Minimal subset of the CacheStorage interface we depend on. */
export interface CacheStorageLike {
  open(name: string): Promise<CacheLike>;
  delete(name: string): Promise<boolean>;
  has(name: string): Promise<boolean>;
}

function defaultCacheStorage(): CacheStorageLike | null {
  if (typeof globalThis === "undefined") return null;
  const caches = (globalThis as { caches?: CacheStorageLike }).caches;
  return caches ?? null;
}

/**
 * Parses the HuggingFace repo_id ("org/name") from a full CDN URL.
 * Accepts both `resolve` and `raw` URL shapes; returns null when the URL
 * doesn't match.
 *
 * Exposed (not just an internal helper) so the picker can decode test
 * fixtures and so tests can assert behaviour for unusual upstream URL
 * shapes without re-implementing the parser.
 */
export function parseRepoIdFromUrl(url: string): string | null {
  let u: URL;
  try {
    u = new URL(url);
  } catch {
    return null;
  }
  if (u.hostname !== "huggingface.co") return null;
  const parts = u.pathname.split("/").filter((p) => p.length > 0);
  // expected: <org>/<name>/<resolve|raw>/<rev>/...
  if (parts.length < 4) return null;
  if (parts[2] !== "resolve" && parts[2] !== "raw") return null;
  return `${parts[0]}/${parts[1]}`;
}

/**
 * Returns true when the browser exposes Cache Storage AND the
 * transformers-cache exists. Returns false on SSR, on jsdom test envs
 * without a stub, in private-browsing modes that disable Cache Storage,
 * or before any model has been downloaded.
 */
export async function hasCacheStorage(
  cacheStorage: CacheStorageLike | null = defaultCacheStorage(),
): Promise<boolean> {
  if (!cacheStorage) return false;
  try {
    return await cacheStorage.has(TRANSFORMERS_CACHE_NAME);
  } catch {
    return false;
  }
}

/**
 * Returns the sorted, deduplicated list of HuggingFace repo_ids present
 * in the transformers-cache. Each repo_id appears once even when many
 * files are cached for it.
 */
export async function listCachedRepoIds(
  cacheStorage: CacheStorageLike | null = defaultCacheStorage(),
): Promise<readonly string[]> {
  if (!cacheStorage) return [];
  if (!(await hasCacheStorage(cacheStorage))) return [];
  const cache = await cacheStorage.open(TRANSFORMERS_CACHE_NAME);
  const keys = await cache.keys();
  const repos = new Set<string>();
  for (const req of keys) {
    const repo = parseRepoIdFromUrl(req.url);
    if (repo) repos.add(repo);
  }
  return Array.from(repos).sort();
}

/**
 * Sums byte size of every cached entry whose URL belongs to `repoId`.
 * Returns 0 when the cache is empty or no entries match.
 *
 * Implementation note: forces each matching Response body to materialise
 * via `response.blob().size`. On real browser entries the bytes are
 * already on disk so this is fast; on in-memory stubs it scales with
 * stub size. The picker calls this once per registered model on mount
 * and after each cache mutation — not on every render.
 */
export async function estimateModelSizeBytes(
  repoId: string,
  cacheStorage: CacheStorageLike | null = defaultCacheStorage(),
): Promise<number> {
  if (!cacheStorage) return 0;
  if (!(await hasCacheStorage(cacheStorage))) return 0;
  const cache = await cacheStorage.open(TRANSFORMERS_CACHE_NAME);
  const keys = await cache.keys();
  let total = 0;
  for (const req of keys) {
    if (parseRepoIdFromUrl(req.url) !== repoId) continue;
    const res = await cache.match(req);
    if (!res) continue;
    try {
      const blob = await res.blob();
      total += blob.size;
    } catch {
      // a corrupt entry — skip but don't poison the sum.
    }
  }
  return total;
}

/**
 * Deletes every cached entry that belongs to `repoId`. Returns the
 * count of entries actually removed. Safe to call when the cache is
 * absent or no entries match.
 */
export async function deleteModel(
  repoId: string,
  cacheStorage: CacheStorageLike | null = defaultCacheStorage(),
): Promise<number> {
  if (!cacheStorage) return 0;
  if (!(await hasCacheStorage(cacheStorage))) return 0;
  const cache = await cacheStorage.open(TRANSFORMERS_CACHE_NAME);
  const keys = await cache.keys();
  let deleted = 0;
  for (const req of keys) {
    if (parseRepoIdFromUrl(req.url) !== repoId) continue;
    const ok = await cache.delete(req);
    if (ok) deleted += 1;
  }
  return deleted;
}

/**
 * Deletes the whole transformers-cache (every model, every file).
 * Returns true when the cache existed and was removed; false otherwise.
 *
 * The picker offers this as a single explicit "Clear all" action with
 * a two-step inline confirm — see Yenask.svelte. Active model state is
 * not touched here; the picker re-checks readiness after clearing and
 * the operator must re-Prepare to use any model again.
 */
export async function clearAllCache(
  cacheStorage: CacheStorageLike | null = defaultCacheStorage(),
): Promise<boolean> {
  if (!cacheStorage) return false;
  try {
    return await cacheStorage.delete(TRANSFORMERS_CACHE_NAME);
  } catch {
    return false;
  }
}

/**
 * Human-readable byte-count for the picker. Mirrors the size-rendering
 * convention in Yenask.svelte's `formatBytes` (used for download
 * progress) but extends to GB for large models. Returns "—" for 0 or
 * negative so the picker can distinguish "no data" from a real value.
 */
export function formatCacheSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) {
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}
