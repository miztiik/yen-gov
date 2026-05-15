# ADR-0017: ECI current-year-only ingestion (Phase B scope, 2026 cohort)

**Last Updated**: 2026-05-15
**Status**: accepted; superseded for current implementation details by [ECI source adapter](../backend/sources-eci.md)

## Context

ADR-0016 made ECI Statistical Reports the canonical past-election enrichment source and split the work into two phases: Phase A (recon — done; distilled into [ECI source adapter](../backend/sources-eci.md) and archived at [ECI Statistical Report reconnaissance](../../archive/eci-statistical-report-recon-2026-05.md)) and Phase B (download, parse, ingest). Phase A surfaced two facts that change Phase B's shape:

1. **Two clean URL families**, not one. The new portal serves 2024+ events with a JSON inventory at `/eci-backend/public/api/election-result?category_id=<int>` whose entries point at stable `https://www.eci.gov.in/eci-backend/public/all_files/election_report/...` PDF/XLSX permalinks. Pre-2024 cycles (2021 and earlier) only exist as `https://old.eci.gov.in/files/file/<id>-<slug>/` landing pages, hardcoded in the React `/statistical-reports` hub table.
2. **The legacy host is unreachable from at least one dev environment we've tried** (Phase A run from a Windows box: ConnectTimeout on every probe). Pre-2024 backfill therefore needs a network change before it can run.

In parallel the user has narrowed the immediate ask: **only the current cycle (2026 AE: Tamil Nadu, Kerala, West Bengal, Assam)** needs to be ingested in this slice. Pre-2024 backfill is deferred until either the network blocker is solved or a separate ADR explicitly schedules it.

## Decision

Phase B's first slice is **2026-only**, restricted to the four in-scope state assemblies that polled in May 2026: `S22` (Tamil Nadu), `S11` (Kerala), `S25` (West Bengal), `S03` (Assam). The pipeline shape:

1. **Catalog**, per state, by calling `GET /eci-backend/public/api/election-result?category_id=<id>` once. The current implementation stores `(state, year) -> category_id` pins in [`config/eci-pins.json`](../../../config/eci-pins.json), validates them with [`eci_pins.schema.json`](../../../datasets/schemas/eci_pins.schema.json), and loads them through `backend/yen_gov/sources/eci/categories.py`. Phase A confirmed `S22 × 2026 → 26`.
2. **Download** every listed `xlsx_url` (and the matching `pdf_zip_url` for human cross-check) to `.runtime/raw/eci/<state>/<year>/<slug>.xlsx` per ADR-0003. The landing-page permalink (`xlsx_url` itself) goes into `sources[]` with the fetch timestamp; the file under `.runtime/raw/` does not.
3. **Parse** the XLSX with `openpyxl` (already a transitive dep via `pandas`; if not present, add `openpyxl` directly — pandas-only would pull a 50MB wheel for 90% unused functionality). Each report section becomes its own emitted artifact under `datasets/results/in/<state>/<year>/<section>.json`, validated against the appropriate result schema.
4. **Hand-curated `category_id` map**, not auto-discovery. The hub-table extractor in `tools/eci_recon/recon.py` is the *discovery* mechanism; the *ingestion* path uses pinned ids. This keeps Phase B reproducible — a Wikipedia-style "we'll figure it out at runtime" approach makes the pipeline non-deterministic and silently breaks when ECI reshuffles the bundle.
5. **No `jl()` AES-ECB obfuscation on the canonical path.** The 2024+ endpoint takes a cleartext `category_id`. The `jl()` helper stays in `tools/eci_recon/` for future legacy-endpoint probing only.

### Out of scope for this ADR

- **2021 / 2016 / 2011 backfill.** Blocked on `old.eci.gov.in` reachability and a separate decision on whether to host a mirror in the repo's release artifacts. Track via a follow-up ADR when the network blocker is resolved.
- **`results.eci.gov.in` per-AC live counting pages.** Different host, different schema, different ADR (ADR-0008 covers the existing scraper).
- **Promotion of any reference file from `provisional` to `complete`.** That requires the Delimitation Order PDF for the AC↔PC↔district mapping (ADR-0015) and is independent of statistical-report ingestion.

## Consequences

**Positive**

- Single-network-source dependency for the first slice — only `www.eci.gov.in` (via Akamai) needs to be reachable. The Windows dev box can complete the run end-to-end.
- The `category_id` map is small (4 entries for the 2026 cohort). It can be code-reviewed by hand and the upstream URL each value came from is preserved in the same file.
- Stable permalinks (`/all_files/election_report/...`) are safe to persist in `sources[]`. No reconciliation needed when ECI reshuffles `/api/download?url=<blob>` signed URLs.

**Negative**

- The pinned `category_id` map will rot when ECI reorganizes the bundle. Recon runs catch this — when the hub-table URL for `(state, 2026)` no longer matches the pinned id, the next CI run flags a mismatch. Acceptable maintenance burden for the determinism gain.
- Past-election enrichment is deferred. Cross-cycle swing analysis (the use case ADR-0015 calls out as bread-and-butter) cannot be served until the legacy backfill ADR lands.

## Alternatives considered

- **Auto-discovery via `extract_hub_table()` at ingestion time.** Rejected: makes ingestion non-deterministic, couples the parser to a regex over a minified JS bundle, and means a malformed bundle takes the pipeline down rather than failing recon visibly.
- **Phase B = "everything in the hub table" in one go.** Rejected: blocked on `old.eci.gov.in` reachability and would conflate two different network/parsing risk profiles into a single change.
- **Persist signed `/api/download?url=<blob>` URLs.** Forbidden by ADR-0016 — they're time-limited. Recon and ingestion both record the underlying landing-page permalink instead.
- **Use `pandas.read_excel` directly.** Rejected for the dependency cost; `openpyxl` is the right unit of dependency for read-only XLSX consumption.

## See also

- [ADR-0016 — ECI Statistical Reports as canonical past-election enrichment source](0016-eci-statistical-reports-canonical.md) (Phase A/B split this builds on)
- [ADR-0003 — No HTTP cache layer; intermediates live in `.runtime/raw/`](0003-no-fetch-cache.md)
- [ADR-0008 — ECI source adapter: URL conventions + two-step parsing](0008-eci-source-adapter.md) (covers `results.eci.gov.in`, the live-counting host)
- [ECI Statistical Report reconnaissance](../../archive/eci-statistical-report-recon-2026-05.md) — archived Phase A output this ADR built on
