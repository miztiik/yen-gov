// Single source of truth for runtime URL prefixes.
//
// `import.meta.env.BASE_URL` is Vite's documented contract for the deployed
// base path. It is whatever the build's `base` config resolves to (default
// "/", or "/yen-gov/" when the bundle is served under a project Pages
// subpath). Vite guarantees a trailing slash, so concatenating "data" gives
// the right shape in both dev (`/data/...`) and prod (`/yen-gov/data/...`).
//
// Anything that builds a URL to a file under datasets/ MUST go through
// DATA_BASE — we deliberately keep this string out of individual call sites
// so a future move (custom domain, CDN, S3 origin) is a one-line change
// here and an env var swap in the deploy workflow.
//
// Rationale: docs/architecture/deployment.md > "Pages URL base".
export const DATA_BASE = `${import.meta.env.BASE_URL}data`;
