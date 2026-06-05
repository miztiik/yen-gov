/// <reference types="svelte" />
/// <reference types="vite/client" />

// Build-time globals injected by vite.config.ts `define` (U2c, plan
// section 21.8 footer line). Sourced from GITHUB_SHA in CI or
// `git rev-parse --short HEAD` locally; falls back to the literal "dev"
// if git is unavailable. BUILD_DATE is the YYYY-MM-DD slice of build-
// time wall-clock (operational telemetry per CLAUDE.md section 10
// carve-out, NOT data-row provenance).
declare const __BUILD_SHA__: string;
declare const __BUILD_DATE__: string;
