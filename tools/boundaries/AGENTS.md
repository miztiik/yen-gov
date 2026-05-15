# AGENTS.md — tools/boundaries

**Last Updated**: 2026-05-15

Canonical rationale lives in [docs/architecture/data/boundaries.md](../../docs/architecture/data/boundaries.md) and source catalogue decisions live in [docs/reference/boundary-data-sources.md](../../docs/reference/boundary-data-sources.md). This file is only the module map for the boundary build tools.

## Invariants

- **Self-contained.** No imports from `backend/` (CLAUDE.md §4). The script uses Python stdlib only; mapshaper and tippecanoe are external binaries on `PATH`.
- **Writes to `datasets/boundaries/in/` and `.runtime/raw/boundaries/` only.** Raw downloads land in `.runtime/` per ADR-0003; published artifacts (PMTiles + manifest.json) land in `datasets/boundaries/in/`.
- **Manifest is the provenance carrier.** PMTiles binary files cannot embed a `sources` field — the sibling `manifest.json` carries CLAUDE.md §12 provenance for every packed file. If you add a new output, you MUST add a record to the manifest in the same run; the script does this automatically.
- **POSIX paths in manifest.** Output `path` strings are forward-slash, repo-relative (CLAUDE.md §2). The script normalises before writing.
- **Atomic downloads.** `download()` writes to `<dest>.part` then `replace()`s; partial files never appear with the canonical name.
- **Fail loudly.** `subprocess.run(check=True)` everywhere. A silent simplification or pack failure would publish a bad manifest.

## Editing pipeline.json

Adding a state means adding one entry under `inputs`. The frontend learns about new files by reading `manifest.json` — no map-component changes required for additional `kind: "ac"` entries.

Removing a source: drop the entry from `inputs` AND remove the corresponding output file in the same PR. The CI workflow does not delete stale outputs (intentional — destructive ops belong in human-reviewed PRs).

## Phase boundary

This module owns the **build** of boundary artifacts. It does NOT:

- Render maps (that's `frontend/src/lib/MapChoropleth.svelte`, Phase 1d).
- Validate political accuracy of AC numbering (manual verification gate; the build script trusts the upstream property names declared in `pipeline.json`).
- Maintain the canonical state-name → ECI-code map (lives in `datasets/reference/in/states.json`).

If you find yourself patching feature properties or renaming layers inside the simplification step, stop — that smell means the upstream is wrong and we should switch sources, not paper over it.
