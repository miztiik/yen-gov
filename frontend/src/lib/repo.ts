// Single source of truth for the project's source-code / docs host.
//
// Hard-coding `https://github.com/miztiik/yen-gov` at every link site
// would make a fork or a repo move a multi-file find/replace. We resolve
// it once here, allow a build-time override via Vite env, and expose
// helpers that compose the canonical sub-paths.
//
// The default tracks the upstream repository so untouched forks still
// produce working links. Set `VITE_REPO_URL` in `.env.local` (or the
// deploy workflow) to point at a fork or mirror; never trailing-slashed.
//
// Rationale: same shape as DATA_BASE in `paths.ts`. CLAUDE.md §10
// forbids hard-coded values; this is the de-hardcode for the repo URL.
const DEFAULT_REPO_URL = "https://github.com/miztiik/yen-gov";

export const REPO_URL: string =
  (import.meta.env.VITE_REPO_URL as string | undefined)?.replace(/\/+$/, "") ??
  DEFAULT_REPO_URL;

/** Branch the deployed bundle's docs links should point at. */
const DEFAULT_REPO_BRANCH = "main";
export const REPO_BRANCH: string =
  (import.meta.env.VITE_REPO_BRANCH as string | undefined) ?? DEFAULT_REPO_BRANCH;

/**
 * Build a deep link to a Markdown file in the repo, optionally to an
 * anchor inside it. `path` is the repo-relative POSIX path
 * (e.g. `docs/architecture/frontend/psephlab.md`).
 */
export function docsUrl(path: string, anchor?: string): string {
  const base = `${REPO_URL}/blob/${REPO_BRANCH}/${path.replace(/^\/+/, "")}`;
  return anchor ? `${base}#${anchor}` : base;
}
