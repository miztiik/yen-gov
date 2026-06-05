# Backend `sources/eci/` — ECI Source Adapter

**Last Updated**: 2026-05-24

`backend/yen_gov/sources/eci/` is the adapter for the Election Commission of India's surfaces. It owns URL conventions for both the live results portal (`results.eci.gov.in`) and the Statistical Reports hub (`eci.gov.in/statistical-report/...`), the HTML and XLSX parsers, and the per-page commitment about which artifact each ECI page can produce.

## Modules

| File | Responsibility |
| ---- | -------------- |
| [`urls.py`](../../../backend/yen_gov/sources/eci/urls.py) | URL builders for the results portal: `event_index_url`, `partywise_state_url`, `constituencywise_url`. Validates state codes against `^[SU]\\d{2}$`. |
| [`partywise.py`](../../../backend/yen_gov/sources/eci/partywise.py) | `parse_partywise(content) -> PartywiseSnapshot`. Source of truth for party seat counts and party ECI codes within a state. |
| [`constituencywise.py`](../../../backend/yen_gov/sources/eci/constituencywise.py) | `parse_constituencywise(content) -> ConstituencywiseRaw`; `to_constituency_result(raw, *, election, state, body, eci_no, ...)` binds it to `result.constituency.schema.json`. |
| [`categories.py`](../../../backend/yen_gov/sources/eci/categories.py) | Loader for [`config/eci-pins.json`](../../../config/eci-pins.json). `category_id_for(state, year)` reads the schema-validated pin file; the config is canonical, not this Python module. |
| [`events.py`](../../../backend/yen_gov/sources/eci/events.py) | `(state, year) -> EventInfo(event_id, has_partywise)` registry. This is the branch point for live partywise reconciliation versus archived Statistical Report-only ingest. |
| [`statistical_report.py`](../../../backend/yen_gov/sources/eci/statistical_report.py) | `statistical_report_catalog_url`, `parse_catalog`, `fetch_catalog`, `download_documents`. Catalog = list of `(xlsx_url, pdf_zip_url)` permalinks under `/all_files/election_report/...` (safe to persist in `sources[]`). |
| [`static_catalog.py`](../../../backend/yen_gov/sources/eci/static_catalog.py) | Synthesises a `CatalogResponse` for legacy cohorts whose Statistical Report is published under `/all_files/full-statistical-reports/<state-slug>/<year>/...` rather than the 2024+ `/api/election-result?category_id=...` endpoint. `resolve_catalog(state, year, *, fetcher)` is the single dispatcher — pinned `(state, year)` win over the static registry, so a future ECI republish under the unified API automatically takes over. Today: 2023 cohort (S12 MP, S26 Chhattisgarh, S16 Mizoram, S29 Telangana). |
| [`statistical_report_detailed.py`](../../../backend/yen_gov/sources/eci/statistical_report_detailed.py) | `parse_detailed_results(xlsx_bytes) -> DetailedResultsRaw`; `to_constituency_results(raw, *, election, state, top_n, collapse_others, sources, party_eci_codes=None)` emits one `ConstituencyResult` per AC from Section 10 ("Detailed Results"). |

The Statistical Reports parser (XLSX-based) is Phase B work — see [authority hierarchy for past elections](#authority-hierarchy-for-past-elections) below.

## URL conventions

Three builders for the results portal, returning fully-qualified `https://results.eci.gov.in/...` URLs:

- `event_index_url(event_id)` → `/Result<event_id>/index.htm`
- `partywise_state_url(event_id, state_code)` → `/Result<event_id>/partywiseresult-<state>.htm`
- `constituencywise_url(event_id, state_code, eci_no)` → `/Result<event_id>/Constituencywise<state><n>.htm`

`event_id` is the opaque slug ECI assigns each event (e.g. `AcGenMay2026`). It is supplied by `processing.json` / pipeline config — never inferred. State codes are validated against `^[SU]\d{2}$` (matches the ECI code constraint shared across the canonical taxonomy — `entity.schema.json` `entity_code` for `entity_type IN ('state','ut')` — and the legacy `state.schema.json` retired in Phase C).

Verified on 2026-05-08 against the live AcGenMay2026 event. ECI does not version these URLs; if the next election renames them, exactly one file changes.

## Two-step parser: HTML → raw dataclass → schema-bound model

For each page family, parsing splits into two phases:

1. **`parse_<page>(content: bytes) -> <Page>Raw`** — pure HTML→data. No knowledge of schema, election context, or processing knobs. Returns an adapter-local `@dataclass(frozen=True)`.
2. **`to_<artifact>(raw, *, election, state, body, eci_no, top_n, collapse_others, sources, party_lookup=None) -> <ArtifactModel>`** — adds caller-supplied identity coordinates and config-driven knobs, builds the pydantic model.

The split exists because the page does not contain its own identity (election id, state code, body, AC number) — those come from the URL the pipeline used to fetch it. Mixing "what I parsed" and "what the caller told me" in one function makes both halves hard to test.

### Page-by-page commitments

| Page                         | Parser produces                                         | Why this artifact                                                                                                          |
| ---------------------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `partywiseresult-<state>`    | `PartywiseSnapshot` (state name, total seats, party rows with seats won/leading/total + ECI numeric code) | Source of truth for **party seat counts** and **party ECI codes** within a state. Does NOT carry vote totals or vote share. |
| `Constituencywise<state><n>` | `ConstituencywiseRaw` → `ConstituencyResult`            | Atomic election artifact: candidates, NOTA, polled votes. Bound to `result.constituency.schema.json`.                       |

`ResultSummary` is intentionally NOT produced by either parser alone — it requires per-party vote totals which only appear by aggregating across constituencies. The pipeline composes it from the two streams (partywise gives party identity + seats won; constituencywise gives votes). That composition is in [`pipeline/compose.py`](pipeline.md), not in `sources/`.

### Party-name resolution

Constituencywise pages carry only **full** party names (e.g. `"Tamilaga Vettri Kazhagam"`). The schema requires `party_short` to be a non-empty string. To bridge:

- `to_constituency_result` accepts an optional `party_lookup: dict[full_name, (short, eci_code)]`.
- When supplied, the mapper fills `party_short` and `party_eci_code` from it.
- When absent, `party_short` falls back to the full name and `party_eci_code` is `None` (schema permits null).
- Independents (`party == "Independent"`) always become `party_short="IND"`, `party_eci_code=None`.

Building the lookup is the partywise parser's job — its rows already carry `(full_name, short_name, eci_code)`. The pipeline glue passes it down.

### Failure mode: fail loud on structural surprise

Parsers raise `ValueError` when the page doesn't match the expected shape (missing header, table not found, NOTA row absent, footer Total missing). Silent fallback to a partial artifact would let an ECI redesign go unnoticed for an entire election cycle.

## Design rationale

- **Future ECI changes are localised.** A URL change touches `urls.py`. An HTML change touches one parser. Schema-binding code (`to_*` mappers) is unaffected by HTML drift.
- **Parsers are testable in isolation** against either bytes-in-memory fixtures or live URLs without dragging the schema/Tier-B validator through every test.
- **Identity coordinates are explicit** in the function signature, so a unit test can't accidentally bind the wrong election/state to parsed data.

Acknowledged costs:

- The two-step pattern is more boilerplate than a one-call `fetch_and_parse`. Worth it because the pipeline reuses `to_*` with cached HTML during reprocessing.
- Party-name resolution is a runtime concern, not a parser concern — `party_short` may temporarily equal the full name during single-page testing. The pipeline always passes a lookup in production runs.

The following h3 subsections fold in the source-authority + current-year-scope rationale from the originating `docs/architecture/decisions/` ADRs per [parent plan section 9](../../../TODO/20260603-data-and-charting-platform-reset-plan.md) (keep-receipts ADR retirement) and [decision-index.md](../../reference/decision-index.md). The verbatim rejected alternatives live under [Alternatives considered](#alternatives-considered) below as additional h3 subsections.

### ADR-0016: eci-statistical-reports-canonical

**Context.** [ADR-0015](#adr-0015-constituency-hierarchy-fields) introduced the `status: provisional | complete` lifecycle on `constituency.schema.json` and required at least one ECI-domain URL in `sources[]` before promoting to `complete`. It listed the Delimitation Order 2008 (PDF), `results.eci.gov.in` (HTML), and CEO state portals (mixed) as the acceptable ECI sources in that order. Two facts changed the picture: (1) the user identified the [ECI Statistical Reports hub](https://www.eci.gov.in/statistical-reports) as a much richer resource - per-election landing pages carry the full official statistical report (constituency-wise results, candidate-wise results, party-wise summary, vote share, electors, turnout), many published as XLSX which we can parse losslessly; (2) the user explicitly designated ECI as the canonical source for enrichment, asked to bootstrap West Bengal (S25) reference data from ECI rather than Wikipedia, and asked for an exploration pass against TN, Kerala, and WB across the last three assembly cycles. ADR-0016 codified the policy before tooling was written so the recon and enrichment workstreams would not accumulate ad hoc decisions.

**Decision.** Five rules: (1) **ECI Statistical Reports are the canonical source for any past-election enrichment** - for any past election (assembly or general), when filling out fields that are not pure constituency reference (boundary) data (results, vote counts, candidate counts, electors at poll-time, turnout), the ECI Statistical Report for that election is the source of truth; Wikipedia and MyNeta are downgraded to enrichment/cross-check roles for those fields. Vote counts, candidate counts, party-wise totals, turnout - ECI Statistical Report only. Electors (poll-time snapshot) - ECI Statistical Report (Form 20-equivalent tables) preferred; CEO electoral roll PDFs as fallback. AC<->PC<->district mapping - Delimitation Order 2008 remains the legal source; ECI Statistical Reports often also publish this mapping per election (Delimitation Order wins on conflict). Candidate affidavit data (assets, criminal cases) - MyNeta (ECI does not publish this in structured form). Wikipedia reduced to fast bootstrap for constituency names/numbers (provisional state) + historical narrative fields (`established_year`, district lineage) that ECI does not publish. (2) **URL grammar and persistence rules**: persisted in `sources[]` is the human-facing landing page (`https://www.eci.gov.in/statistical-report/{body}/{year}/{category_id}`); NEVER persisted is the time-limited signed URL (`/api/download?url=<base64-blob>`); the canonical pin store is `config/eci-pins.json`. (3) **Two-phase rollout**: Phase A reconnaissance (standalone `tools/eci_recon/`, no `backend/` imports, recon outputs a markdown inventory - no data ingested into `datasets/`); Phase B enrichment (XLSX parser, schema-driven not heuristic; each parsed report becomes either a new `datasets/elections/...` artifact OR the ECI source that promotes a `constituencies.json` from `provisional` to `complete`). (4) **WB (S25) bootstrap policy**: WB had no `datasets/reference/in/states/S25/` files; the user directed "include WB; ECI is the official source; bootstrap from ECI and enrich with Wiki" - recon pass includes WB even without WB reference data; bootstrap order reversed from how TN/Kerala were bootstrapped (once recon confirms an ECI Statistical Report exists for WB-2021 in a parseable form (XLSX), generate `S25/constituencies.json` directly from the ECI report). The 2026-05-09 superseder reverted this: `old.eci.gov.in` is unreachable from the current dev environment, blocking the ECI-first path indefinitely; WB and Assam were both bootstrapped from Wikipedia at `status: provisional` matching the TN/Kerala pattern. Cleaner uniformity beats the lost head-start.

**Consequences.** Clear authority order ends ambiguity over "which source wins when they disagree" - ECI Statistical Reports do. Separating recon from enrichment prevents the "let me also write the parser while I'm here" sprawl. Signed-URL non-persistence is now in policy, not implicit - tooling that violates it fails review, not validation-after-the-fact. Costs: recon discovers reality - if a state's report is published as a scanned PDF rather than XLSX, Phase B for that state is much harder (accepted; pretending the data is uniformly XLSX would just defer the surprise). State-code mapping (`S22 <-> 26`, etc.) is empirically confirmed, not assumed - recon must record it explicitly. Schemas unchanged at landing; `docs/reference/data-sources.md` carries the URL grammar; `tools/eci_recon/` arrives in the next change.

### ADR-0017: eci-current-year-ingestion

**Context.** [ADR-0016](#adr-0016-eci-statistical-reports-canonical) made ECI Statistical Reports the canonical past-election enrichment source and split the work into Phase A (recon) + Phase B (download, parse, ingest). Phase A surfaced two facts that changed Phase B's shape: (1) **two clean URL families, not one** - the new portal serves 2024+ events with a JSON inventory at `/eci-backend/public/api/election-result?category_id=<int>` whose entries point at stable `https://www.eci.gov.in/eci-backend/public/all_files/election_report/...` PDF/XLSX permalinks; pre-2024 cycles (2021 and earlier) only exist as `https://old.eci.gov.in/files/file/<id>-<slug>/` landing pages hardcoded in the React `/statistical-reports` hub table. (2) **The legacy host is unreachable from at least one dev environment** (Phase A run from a Windows box: ConnectTimeout on every probe). Pre-2024 backfill therefore needs a network change before it can run. In parallel the user narrowed the immediate ask: only the current cycle (2026 AE: Tamil Nadu, Kerala, West Bengal, Assam) needs to be ingested in this slice. Pre-2024 backfill is deferred until either the network blocker is solved or a separate ADR explicitly schedules it.

**Decision.** Phase B's first slice is **2026-only**, restricted to the four in-scope state assemblies that polled in May 2026: `S22` (TN), `S11` (Kerala), `S25` (WB), `S03` (Assam). Pipeline shape: (1) **Catalog** per state by calling `GET /eci-backend/public/api/election-result?category_id=<id>` once; the current implementation stores `(state, year) -> category_id` pins in `config/eci-pins.json`, validates them with `eci_pins.schema.json`, loads via `backend/yen_gov/sources/eci/categories.py`. Phase A confirmed `S22 x 2026 -> 26`. (2) **Download** every listed `xlsx_url` (and matching `pdf_zip_url` for human cross-check) to `.runtime/raw/eci/<state>/<year>/<slug>.xlsx`; landing-page permalink (`xlsx_url` itself) goes into `sources[]` with fetch timestamp; the file under `.runtime/raw/` does not. (3) **Parse** the XLSX with `openpyxl` (already transitive via `pandas`; if not present add `openpyxl` directly - pandas-only would pull a 50MB wheel for 90% unused functionality). Each report section becomes its own emitted artifact under `datasets/results/in/<state>/<year>/<section>.json` validated against the appropriate result schema. (4) **Hand-curated `category_id` map, not auto-discovery**: the hub-table extractor in `tools/eci_recon/recon.py` is the DISCOVERY mechanism; the INGESTION path uses pinned ids. This keeps Phase B reproducible - a Wikipedia-style "we'll figure it out at runtime" approach makes the pipeline non-deterministic and silently breaks when ECI reshuffles the bundle. (5) **No `jl()` AES-ECB obfuscation on the canonical path** - the 2024+ endpoint takes a cleartext `category_id`; the `jl()` helper stays in `tools/eci_recon/` for future legacy-endpoint probing only. Out of scope for this ADR: 2021/2016/2011 backfill (blocked on `old.eci.gov.in` reachability and a separate decision on whether to host a mirror in the repo's release artifacts; track via follow-up ADR when network blocker resolves); `results.eci.gov.in` per-AC live counting pages (different host, different schema, different ADR); promotion of any reference file from `provisional` to `complete` (requires Delimitation Order PDF for AC<->PC<->district mapping; independent of statistical-report ingestion).

**Consequences.** Single-network-source dependency for the first slice - only `www.eci.gov.in` (via Akamai) needs to be reachable; the Windows dev box can complete the run end-to-end. The `category_id` map is small (4 entries for the 2026 cohort) and can be code-reviewed by hand; the upstream URL each value came from is preserved in the same file. Stable permalinks (`/all_files/election_report/...`) are safe to persist in `sources[]` - no reconciliation needed when ECI reshuffles `/api/download?url=<blob>` signed URLs. Costs: the pinned `category_id` map will rot when ECI reorganizes the bundle - recon runs catch this (when the hub-table URL for `(state, 2026)` no longer matches the pinned id, the next CI run flags a mismatch; acceptable maintenance burden for the determinism gain). Past-election enrichment is deferred - cross-cycle swing analysis (the use case ADR-0015 calls out as bread-and-butter) cannot be served until the legacy backfill ADR lands.

## Alternatives considered

- **One function `parse_constituencywise_to_result(url, election, top_n, ...)`**. Rejected: collapses parsing and modelling, makes it impossible to test parsing alone without schema constraints, and forces re-fetch to re-derive when knobs change.
- **Have parsers return dicts, not dataclasses**. Rejected: dicts give zero IDE help and zero per-field type checks at the parser/mapper boundary.
- **Auto-discover the partywise table by class name (e.g. `.partywise-table`)**. Rejected: ECI HTML uses bootstrap utility classes (`table table-striped`) shared across many tables. Header-row text matching is more robust to cosmetic class churn.
- **Save HTML fixtures under `tests/fixtures/eci/` and run tests offline**. Rejected: fixtures drift from reality and create false confidence. We accept the live-test cost in exchange for early warning when ECI changes a page.
- **Build `ResultSummary` from partywise alone**. Rejected: the partywise page gives seats, not votes. Emitting a summary with `votes=0` everywhere would technically pass schema but would silently mislead consumers.

The following h3 subsections fold in the verbatim rejected-alternatives traces from the source-authority + current-year-scope ADRs (companions to the [Design rationale](#design-rationale) h3 subsections above) per [parent plan section 9](../../../TODO/20260603-data-and-charting-platform-reset-plan.md). Append-only.

### ADR-0016 rejected alternatives

Verbatim from the originating ADR. Append-only per parent plan section 9 (keep-receipts).

- **Treat all ECI surfaces (Statistical Reports, Results portal, Delimitation Order, CEO sites) as one undifferentiated "ECI source".** Rejected: they differ in authority, freshness, and format. Saying "any ECI URL satisfies `status: complete`" loses meaning.
- **Combine recon and enrichment in one workstream.** Rejected: recon's purpose is to surface unknowns; tying it to a parser commits us to a parser shape before we know what we're parsing. CLAUDE.md section 6 explicitly: "Level 4+ - propose breakdown first."
- **Bootstrap WB from Wikipedia like TN/Kerala for consistency, promote later.** Rejected by user direction at the time of ADR-0016. Also dispreferred because every `provisional` file is a future migration we'd rather not create when we can avoid it. (Superseded 2026-05-09: `old.eci.gov.in` unreachable; WB + Assam both bootstrapped from Wikipedia matching TN/Kerala pattern; cleaner uniformity wins.)
- **Persist signed download URLs in `sources[]` "for traceability".** Rejected: they expire. A `sources[]` entry that 404s in a week is worse than no entry - it implies traceability that does not exist.

### ADR-0017 rejected alternatives

Verbatim from the originating ADR. Append-only per parent plan section 9 (keep-receipts).

- **Auto-discovery via `extract_hub_table()` at ingestion time.** Rejected: makes ingestion non-deterministic, couples the parser to a regex over a minified JS bundle, and means a malformed bundle takes the pipeline down rather than failing recon visibly.
- **Phase B = "everything in the hub table" in one go.** Rejected: blocked on `old.eci.gov.in` reachability and would conflate two different network/parsing risk profiles into a single change.
- **Persist signed `/api/download?url=<blob>` URLs.** Forbidden by ADR-0016 - they're time-limited. Recon and ingestion both record the underlying landing-page permalink instead.
- **Use `pandas.read_excel` directly.** Rejected for the dependency cost; `openpyxl` is the right unit of dependency for read-only XLSX consumption.

## Authority hierarchy for past elections

For any past election (assembly or general), when filling out fields that are not pure constituency reference (boundary) data — i.e. results, vote counts, candidate counts, electors at poll-time, turnout — the **ECI Statistical Report** for that election is the source of truth. Wikipedia and MyNeta are downgraded to enrichment/cross-check roles for those fields.

| Field | Canonical source | Fallback |
| ----- | ---------------- | -------- |
| Vote counts, candidate counts, party-wise totals, turnout | ECI Statistical Report | none |
| Electors (poll-time snapshot) | ECI Statistical Report (Form 20-equivalent tables) | CEO state electoral roll PDFs |
| AC↔PC↔district mapping | Delimitation Order 2008 (legal source) | ECI Statistical Reports (when they republish it; Delimitation wins on conflict) |
| Candidate affidavit data (assets, criminal cases) | MyNeta | ECI does not publish this in structured form |
| Constituency *names* and *numbers* (provisional) | Wikipedia (fast bootstrap) | ECI |
| Historical narrative (`established_year`, district lineage) | Wikipedia | ECI does not publish |

### URL grammar — Statistical Reports

For 2024+ Statistical Report catalogues, the trailing integer in the public landing URL is the same `category_id` used by the JSON API. It is **not** the yen-gov `S22` state code and should not be documented as a display-state lookup.

**Human-facing landing page** (safe to cite in docs and commit messages):

```
https://www.eci.gov.in/statistical-report/{body}/{year}/{category_id}
```

**Machine catalogue endpoint** (what `statistical_report_catalog_url(category_id)` fetches):

```
https://www.eci.gov.in/eci-backend/public/api/election-result?category_id=<category_id>
```

**Never persisted in `sources[]`** (time-limited signed URLs from the "Download" buttons):

```
https://www.eci.gov.in/eci-backend/public/api/download?url=<base64-blob>
```

These signed URLs expire. We re-resolve them from the landing/catalogue on every fetch. The intermediate downloaded XLSX/PDF lives in `.runtime/raw/eci/...` per [no fetch cache](../decisions/0003-no-fetch-cache.md) — not a contract surface, gitignored, throwaway.

The 2021-and-earlier archive is different: the hub table points directly at `https://old.eci.gov.in/files/file/<id>-<slug>/` landing pages. Those permalinks are also safe for provenance, but they are not `category_id` catalogues.

### Two-phase rollout

**Phase A — Reconnaissance** (in `tools/eci_recon/`, per CLAUDE.md §3 / §4: tools are self-contained, no `backend/` imports). **Done 2026-05-09 / 2026-05-11**; the durable findings now live in this doc and the historical trace is archived at [ECI Statistical Report reconnaissance](../../archive/eci-statistical-report-recon-2026-05.md). Key findings the parser depends on:

- The new portal's `/statistical-reports` hub table is hardcoded in `main.<hash>.js`. There is no JSON API that returns the (state, year) → URL map; the React bundle IS the canonical inventory. Recon extracts it by regex and prints it into the inventory note.
- 2024+ events use `GET /eci-backend/public/api/election-result?category_id=<int>` with a *cleartext* small integer; the response carries stable `https://www.eci.gov.in/eci-backend/public/all_files/election_report/...` PDF/XLSX permalinks safe to persist in `sources[]`.
- 2021 and earlier link directly to `https://old.eci.gov.in/files/file/<id>-<slug>/` landing pages from the same hub table.
- ECI's `jl()` AES-ECB obfuscation (key `4WS8851W824R456Y`, public constant from the bundle) wraps category_ids on a small set of legacy endpoints (`/api/get-statistical?categories=jl(<id>)`, `/api/get-sub-category`). Implemented in `tools/eci_recon/recon.py` for completeness; **not on the canonical Phase B path** — the hub table gives every URL we need cleartext.
- `old.eci.gov.in` is unreachable from at least one dev environment (Windows box: ConnectTimeout). Recon documents reachability per probe rather than silently dropping URLs it couldn't visit.

**Phase B — Enrichment**. The first slice was the May-2026 assembly cohort; the same Section 10 path now handles the pinned 2024-2026 assembly catalogues and the 2023 static-catalog cohort. Pipeline shape:

1. **Catalog**: call `GET /api/election-result?category_id=<id>` per state/year when a 2024+ pin exists. The `(state, year) -> category_id` value is stored in [`config/eci-pins.json`](../../../config/eci-pins.json), validated by [`eci_pins.schema.json`](../../../datasets/schemas/eci_pins.schema.json), and loaded by `categories.py`. Extending the map is a config update, normally after recon confirms the Statistical Report family.
2. **Download**: every listed `xlsx_url` (and the matching `pdf_zip_url` for human cross-check) to `.runtime/raw/eci/<state>/<year>/<slug>.xlsx` per [no fetch cache](../decisions/0003-no-fetch-cache.md). The landing-page permalink — *not* the path under `.runtime/raw/` — goes into `sources[]` with the fetch timestamp.
3. **Parse**: with `openpyxl` directly. `pandas.read_excel` would pull a 50MB wheel for 90% unused functionality; the read-only XLSX surface fits openpyxl cleanly. Each report section becomes its own emitted artifact under `datasets/results/in/<state>/<year>/<section>.json`, validated against the appropriate result schema.
4. **No `jl()` on the canonical path.** The 2024+ endpoint is cleartext; the helper stays in `tools/eci_recon/` for future legacy probing only.
5. **Hand-curated pins, not auto-discovery at ingest time.** Recon is the discovery mechanism; ingestion uses pinned ids. A "figure it out at runtime" approach makes the pipeline non-deterministic and silently breaks when ECI reshuffles the bundle. Mismatch between the pin and the next recon run is the early-warning signal.

#### Choosing the right catalogue

ECI can publish multiple catalogues with the same `cat_name`. Bihar 2025 is the anchor case: `category_id=15` was the per-AC live-results catalogue (243 documents, one per AC) while `category_id=16` was the 14-statement Statistical Report catalogue our parser consumes. The pin MUST target the Statistical Report family: `index_name == "Copy of Index Cards [Digital]"` and a statement bundle whose Section 10 is the Detailed Results XLSX. `cat_name` alone is not a safe discriminator.

#### Existing recon and ingest affordances

Before writing a new throwaway recon script, use the maintained path:

- `python -m yen_gov eci-statreport <state> <year>` — inspect the pinned catalogue.
- `python -m yen_gov eci-statreport --category-id <id>` — inspect a fresh public URL like `/statistical-report/ae/<year>/<id>` before editing pins.
- `python -m yen_gov eci-statreport-emit <state> <year>` — emit Section 10 artifacts for a registered event.
- [`tools/eci_recon/enumerate_categories.py`](../../../tools/eci_recon/enumerate_categories.py) — sweep candidate ids when the portal has changed.

To register a new assembly event for ingest: confirm the Statistical Report `category_id`, update [`config/eci-pins.json`](../../../config/eci-pins.json), add or update [`events.py`](../../../backend/yen_gov/sources/eci/events.py) with `event_id` and `has_partywise`, add cohort metadata under `datasets/events/in/eci/<event_id>/election.json` when the cohort is new, then run `eci-statreport-emit` and the ingestion gate below.

The catalog + download steps are exposed end-user as `python -m yen_gov eci-statreport <state> <year> [--download] [--skip-pdf]`. Without `--download` the command prints the resolved permalinks (useful for review before pulling 13 MB per state); with `--download` it fetches every XLSX and PDF through the standard `core.http.Fetcher` so on-disk placement under `.runtime/raw/eci/...` matches every other source. The CLI overrides the configured `user_agent` to bare `Mozilla/5.0` because Akamai (fronting `www.eci.gov.in`) blocks the project's default `yen-gov/0.1` UA.

Smoke-tested 2026-05-09: all four states (S22/S11/S25/S03) returned 14 documents each, 28 files per state, ≈3 MB per state.

### Section 10 ("Detailed Results") parser

Section 10 of every Statistical Report carries the per-AC per-candidate vote breakdown — the richest single sheet in the bundle and a near-direct fit for `result.constituency.schema.json`. ECI has shipped two layouts under this title since 2023, both supported by the parser via header-name-based column resolution (so a future column tweak fails loudly rather than silently shifting an index):

- **2024+ (15 cols, May-2026 cohort and the post-API archived states):** `STATE/UT NAME | AC NO. | AC NAME | CANDIDATE NAME | GENDER | AGE | CATEGORY | PARTY | SYMBOL | GENERAL | POSTAL | TOTAL | OVER VALID VOTES + NOTA | OVER TOTAL ELECTORS | TOTAL ELECTORS`. The TURN OUT row's turnout % is read from the dedicated *OVER TOTAL ELECTORS* column.
- **2023 (14 cols, Nov-2023 cohort — MP / Chhattisgarh / Mizoram / Telangana):** `STATE/UT NAME | AC NO. | AC NAME | CANDIDATE NAME | SEX | AGE | CATEGORY | PARTY | SYMBOL | GENERAL | POSTAL | TOTAL | % VOTES POLLED | TOTAL ELECTORS`. The TURN OUT row's turnout % is read from the single % column. Backed by `static_catalog.py` rather than `/api/election-result`.

Resolving by header name rather than fixed indices was the structural fix when the 2023 cohort landed: the original parser hardcoded column 13 for turnout and column 14 for total_electors, both off-by-one for the 14-col layout. A single-layout regression test wouldn't have caught it; [`test_sources_eci_statistical_report_detailed.py`](../../../backend/tests/test_sources_eci_statistical_report_detailed.py) now pins both layouts.

Each AC section ends with a `TURN OUT` sentinel row carrying the polled totals + turnout %; the file ends with a single `GRAND TOTAL:` row and a disclaimer (both ignored).

The parser (`statistical_report_detailed.py`) follows the same two-step convention as the HTML parsers: `parse_detailed_results(bytes) -> DetailedResultsRaw` is pure XLSX → data; `to_constituency_results(raw, *, election, state, top_n, collapse_others, sources)` adds caller-supplied identity coordinates and the processing knobs and emits the schema-bound model. Vote-share columns are taken as-authoritative from ECI's own pre-computed values.

**Party codes**: Section 10 carries party SHORT codes only (TVK, ADMK, INC, IND, NOTA, ...) — no numeric ECI code. The parser leaves `party_eci_code` empty; the mapper (`to_constituency_results`) accepts an optional `party_eci_codes: dict[short → eci_code]` lookup that backfills it. The lookup is built from the live-results `partywiseresult-<state>.htm` snapshot via `pipeline.compose.eci_code_by_short_from_partywise` — the only place that page's numeric codes meet Section 10's short codes. Independents and shorts absent from the partywise table get `null` (schema permits it). Keeping the lookup *outside* the parser preserves the two-step convention: Section 10 → raw is one ingest, partywise → identity-table is another, and the composer is the seam.

**Countermanded ACs are skipped silently.** ECI publishes a stub Section-10 row for postponed/countermanded constituencies (a single zero-vote NOTA row with `polled_total = 0`; e.g. WB 2026 AC #144 FALTA). The schema requires `candidates: minItems: 1` and a non-zero winner — emitting a stub would mislead consumers. Skipping leaves a gap in the per-AC file sequence (`results/144.json` simply does not exist) which is the correct signal: a contiguous AC numbering can't be assumed.

End-to-end emit is exposed as `python -m yen_gov eci-statreport-emit <state> <year> [--event AcGenMay2026] [--output ...]`. The command resolves the catalog through `static_catalog.resolve_catalog(state, year, *, fetcher)` — pinned `(state, year)` use the 2024+ `/api/election-result` path; legacy cohorts use the synthesised static catalog with no network call to discover URLs. For the static path the Fetcher is given an extra browser-fingerprint header set (`Sec-Fetch-*` + `Accept` + `Referer`) because the Akamai WAF in front of `www.eci.gov.in` returns 403 on `/all_files/full-statistical-reports/` for minimalist clients (verified 2026-05-12; recon at [`tools/eci_2023_recon.py`](../../../tools/eci_2023_recon.py)). The fetched Section 10 XLSX URL plus, when available, the live-results `partywiseresult-<state>.htm` URL land in the `sources[]` array of every emitted artifact. Before any artifact is written, `reconcile_winners_against_partywise` cross-checks per-AC winners (aggregated by `party_short`) against partywise `seats_won + leading` — a mismatch aborts the run with a fail-loud `ValueError`, so we never publish a partial slice when the two ECI sources disagree. Reconciliation is skipped for archived events with no live-results page (`has_partywise=False` in `events.py`), including every 2024+-archived cohort and the entire 2023 cohort. Outputs under `<output_dir>/`: `results/<eci_no>.json` per AC, `result.summary.json` (state-level rollup, composed directly from the raw sections via `compose_result_summary_from_section_10`), and `parties.json` (live cohorts: full roster from the partywise snapshot; archived cohorts: the registry-resolvable subset from Section 3 via `pipeline.compose.load_eci_party_registry()` aggregated across every existing `parties.json` on disk; see [Central party registry](#central-party-registry). Per-state resolution rate for archived cohorts is bounded by what's in the live cohorts; dropped shorts are logged on the emit line and remain visible in `result.summary.json` with `party_eci_code: null`). Confirmed 2026-05-09 against all four 2026 states: S03=126, S11=140, S22=234, S25=293 (1 countermanded), 793 ConstituencyResult artifacts total, reconciliation passes for all four, validator clean. Confirmed 2026-05-12 against the 2023 cohort: S12=230 (BJP=163 / INC=66), S26=90 (BJP=54 / INC=35), S16=40 (ZPM=27 / MNF=10), S29=119 (INC=64 / BRS=39); validator clean.

**Out of scope for the first Phase B slice**: 2021 / 2016 / 2011 backfill (blocked on `old.eci.gov.in` reachability — needs a network change or a mirroring decision before it can run); promotion of any reference file from `provisional` to `complete` (needs the Delimitation Order PDF for AC↔PC↔district mapping, independent of statistical-report ingestion); per-AC live counting pages on `results.eci.gov.in` (covered by the live-results scraper, different host and schema).

#### Historical hand-import path (`eci-statreport-emit-local`)

The 2016-2023 backfill was lifted from blocker status by a parallel CLI: `python -m yen_gov eci-statreport-emit-local <file.xlsx>`. Operator hand-downloads the Section 10 XLSX from `old.eci.gov.in` (it remains the only authoritative source for these cohorts) into `datasets/raw_ephemeral_datasets/`, then runs the command. Filename pattern `YYYY_state_<name>_*.xlsx` is auto-decoded to `(state_code, year)` against an internal name→ECI map; `--state` and `--year` overrides exist for one-offs. The file is then parsed in-process via the same `parse_detailed_results` → `to_constituency_results` → `compose_result_summary_from_section_10` pipeline as the network path, but with `sources=[]` (the hand-authored signal per ADR-0002) instead of a real `SourceRef`. On success the source XLSX is unlinked (drop dir is ephemeral by convention); `--keep-source` overrides for debugging.

Output parity with the live emit path: per-AC `results/<eci_no>.json`, `result.summary.json`, `parties.json` (registry-resolved subset, see below), and `results.csv`. Reconciliation against partywise is intentionally skipped (no partywise snapshot for archived cohorts).

> **Historical note (PR-R.3, 2026-05-19)**: this command previously also emitted a `results.sqlite` sibling that `psephlab` Compare/Psephlab and the per-AC winners overlay loaded directly via `sql.js`. Both consumers now read the canonical Parquet store via DuckDB-WASM (`frontend/src/lib/psephlab/canonical-loaders.ts`), and the SQLite emitter was deleted along with the 41 `results.sqlite` files. The `--no-sqlite` flag is gone.

Because Section 10 across 2016-2023 ships in three structurally different sheet shapes, `parse_detailed_results` dispatches via `_detect_layout`:

| Layout | Cohorts | Shape | Discriminator |
| --- | --- | --- | --- |
| A | 2019+ Delhi/AP/Haryana/Jharkhand/Bihar; every 2021+ event | 14-15 cols, `STATE/UT NAME` header, `TURNOUT`/`TURN OUT` sentinel row between ACs | `STATE/UT NAME` in first 20 rows |
| B | 2016-2017 Assam/Kerala/Goa/HP | No STATE col, no sentinel; AC boundary inferred from `Constituency No.` change. Carries `Candidate Sex/Age/Category` as separate columns. | `Constituency No` in first 20 rows |
| C | 2018 Karnataka | No header row at all; AC announced by marker row `['Constituency', '<n>', '.', '<name>', 'TOTAL ELECTORS :', N]`; positional column indices (gender/age/category at fixed offsets) | `Constituency` + `TOTAL ELECTORS` in first 20 rows |

All three flows produce the same `DetailedResultsRaw` shape, so `to_constituency_results` is layout-agnostic. The schema bumped from 3.1 → 3.2 to carry the optional gender/age/category fields surfaced by Layouts B and C (Layout A's 2024+ files also carry them; older Layout A files just leave them `None`). Anchor tests in [`backend/tests/test_sources_eci_historical_imports.py`](../../../backend/tests/test_sources_eci_historical_imports.py) pin one known winner per layout against the emitted artifacts.

Confirmed 2026-05-13 against all 15 hand-imports: Assam-2016=126, Kerala-2016=140, Goa-2017=40, HP-2017=68, Karnataka-2018=223, AP-2019=175, Haryana-2019=90, Jharkhand-2019=81, Bihar-2020=243, Delhi-2020=70, Assam-2021=126, Kerala-2021=140, Goa-2022=40, HP-2022=68, Karnataka-2023=224. All artifacts schema-valid; Assam+Kerala 2021 share `AcGenApr2021`.

#### Historical AE panel CSV path (`ingest-eci-ae-panel`)

For state assembly panels that are already transcribed from ECI Statistical Reports, the canonical path is `python -m yen_gov ingest-eci-ae-panel <csv> --state <S##>`. The adapter reads the CSV as an operator input, filters to one ECI state code, and emits directly through the canonical `BatchEnvelope` writer. It does not create per-person JSON sidecars or legacy election-result JSON projections.

For the all-states AE panel at `datasets/ephemeral/All_States_AE.csv`, ingestion proceeds state-by-state, never across states in one write. The approved 2026-05-24 rollout admits only `DelimID=3` and `DelimID=4` rows: `DelimID=3` maps to the current pre-2008 `delim_year=1976` entity cycle, and `DelimID=4` maps to `delim_year=2008`. Operators must run the read-only preflight first:

`python -m yen_gov ingest-eci-ae-panel --input datasets/ephemeral/All_States_AE.csv --state <S##> --delim-id 3 --delim-id 4 --dry-run`

The dry-run reports rows by delimitation, registered/missing events, unresolved party tokens, and skipped rows without writing Parquet or inventory. Actual state PRs then ingest exactly one state, merge that state, and only then move to the next state. The state PR sequence and gates live in [`TODO/20260524-ae-panel-statewise-delim3-4-plan.md`](../../../TODO/20260524-ae-panel-statewise-delim3-4-plan.md).

The rollout has three explicit state-token classes:

- **Straight current-state tokens** are eligible for the normal one-state PR loop when the dry-run shows only the current state's rows. Telangana (`State_Name=Telangana`) is in this class: its 2014/2018 rows are already scoped to the post-formation state, while `State_Name=Andhra_Pradesh` remains separate.
- **Delhi historical caveat**: `State_Name=Delhi` remains in the normal `U05` statewise loop, but its 1977/1983 ECI panel rows are Delhi Metropolitan Council elections, not Legislative Assembly elections. Those rows are allowed only with event notes that say the Council had an advisory role and no legislative powers; 1993 onward is the restored NCT Legislative Assembly sequence.
- **Filterable split-state tokens** can be ingested only for the current-state era until a historical entity exists. Andhra Pradesh is the anchor: post-2014 `State_Name=Andhra_Pradesh` rows are a valid current `S01` slice; pre-2014 rows describe undivided Andhra Pradesh and must not be written into current Andhra Pradesh or Telangana partitions.
- **Deferred/problem tokens** are not part of the normal loop. `Madras` and `Mysore` are legacy pre-renaming tokens with no `DelimID=3/4` rows in the approved window; their successor current states are `Tamil_Nadu` and `Karnataka`. `Goa_Daman_&_Diu` is a predecessor UT, not current Goa, and needs a historical entity/delimitation contract. `Jammu_&_Kashmir` needs a separate post-2019 state/UT split decision before writing historical rows into current `U08` / Ladakh-era taxonomy.

The event identity comes from `backend/yen_gov/sources/eci/events.py`, not from local string synthesis in the adapter. This keeps the backend registry, `datasets/taxonomy/election_events.json`, and frontend event picker in one contract: if the citizen can select an event, the backend knows the same event id. Ordinary events use the `(state, year) -> event_id` registry; rare duplicate-election years use the month-aware `(state, year, month) -> event_id` override. Bihar 2005 is the anchor: February 2005 and October-November 2005 are distinct Assembly elections and must not collapse onto one `event_id`.

Rows emitted by this path use ECI citation-ledger provenance (`producer = "Election Commission of India"`, `verification_method = "transcribed"`, `confidence_tier = "gold"`, `is_issuing_authority = true`). The adapter writes `dim_persons`, `elections_candidacies`, `dim_acs`, party dims, election observations, and inventory rows in the same transaction-shaped writer envelope, then records discrepancy counts for operator review.

#### Ingestion test gate (mandatory)

Every Section 10 ingest — live (`eci-statreport-emit`), 2024+ pinned (`--category-id`), or hand-imported (`eci-statreport-emit-local`) — MUST clear the same three-tier gate before the emitting commit lands. This is binding per CLAUDE.md §15; "I'll add a test later" is a Definition-of-Done failure (§9).

| Tier | Command | What it asserts | Failure means |
| --- | --- | --- | --- |
| **Schema / file conformance** | `python -m yen_gov validate` | Every file under `datasets/` carries the required `$schema` + `$schema_version`, validates against its declared schema, and the `sources` array has the required `{url, fetched_at}` shape (§12). | A bad emit, a stale `$schema_version`, or a missing/malformed `sources` array. Re-emit, do not patch the artifact by hand. |
| **Cross-registry integrity** | `pytest backend/tests/test_datasets_integrity.py -q` | Reference catalogues stay consistent: every `event_id` registered in `events.py` exists in [`election-events.json`](../../../datasets/reference/in/election-events.json); every emitted result file's `name`/`number` is reservable against the AC reference for that state; per-AC `sources[]` URLs match the upstream cohort. | A new event was registered without the catalogue entry, or an emit raced ahead of an AC reference update. Add the missing entry first; do not delete the integrity assertion. |
| **Adapter anchors** | `pytest backend/tests/test_sources_eci_*.py -q` | One known-winner / known-runner-up assertion per layout (Layout A live, Layout A 2024+ pin, Layout B 2016-2017, Layout C 2018) against the actually-emitted artifact for one canonical AC. New cohorts get a new anchor. | The parser silently mis-bound a column or row across a layout boundary. Investigate the cohort, not the test. |

The full suite (`pytest -q` from `backend/`, currently 173 tests) runs all three tiers plus everything else. A red suite at commit time blocks the commit per §9 / §15. The reviewer is expected to ask "which anchor pins this cohort?" for any new event ingested.

When a hand-import lands a *new* layout (rare — three exist today) the gate expects: (a) a `_detect_layout` branch + parser function in [`statistical_report_detailed.py`](../../../backend/yen_gov/sources/eci/statistical_report_detailed.py), (b) one new anchor in `test_sources_eci_historical_imports.py`, (c) a new row in the Layout table above. None of those three are optional.

### When `parties.json` gets emitted (and when it doesn't)

`parties.json` is the per-event canonical roster of political parties — `{eci_code (numeric), short_name, full_name}`. Its schema requires `eci_code`, so the emit path branches on whether the numeric code is recoverable for this `(state, year)`:

| Cohort kind | `has_partywise` | Source of `eci_code` | `parties.json` |
| --- | :---: | --- | --- |
| **Live** (May-2026 today; any future event for which the live-results portal still serves `partywiseresult-<state>.htm`) | `True` | The partywise HTML page is the authority — it carries `(eci_code, short, full)` directly. | Full roster, one entry per party in the partywise table. |
| **Archived with on-disk registry hits** (every cohort ingested via Statistical Reports today: 2023 cohort + the 10 archived 2024+ pins + Delhi 2025) | `False` | Section 3 (List of Political Parties Participated) gives `(short, full)` only; numeric codes come from `pipeline.compose.load_eci_party_registry()` (see "Central party registry" below). | Resolved subset only — Section 3 parties whose `short_name` exists in the registry. Dropped `short_name`s are logged on the emit line and surface in `result.summary.json` with `party_eci_code: null`; the operator triages them by promoting the label into [`datasets/taxonomy/parties.json`](../../../datasets/taxonomy/parties.json) (as a new entry or an `aliases[]` entry on an existing party). |
| **Archived with zero registry hits** (transitional — would only happen on a fresh checkout with no central master and no live cohort yet ingested) | `False` | Nothing. | Skipped. The emit line says `parties.json: SKIPPED`. The slice still ships per-AC results + `result.summary.json` with `party_eci_code: null` everywhere. |

#### Central party registry

`load_eci_party_registry(elections_root)` returns `{short_name → PartyRegistryEntry}` built **solely** from the canonical taxonomy at [`datasets/taxonomy/parties.json`](../../../datasets/taxonomy/parties.json) (v2.1, 108 parties as of 2026-05-19). Each taxonomy entry contributes:

- one primary key under its `short_name`,
- one secondary key under `full_name` (if distinct from the short), and
- one secondary key per `aliases[]` entry (e.g. `ADMK → AIADMK`, `CPM → CPI(M)`).

`eci_code` on the entry is `eci_codes[0]` if present, else `None`. The per-event `parties.json` schema still requires a non-null `eci_code`, so taxonomy rows with no observed numeric code drop out of the resolved subset — they surface in `result.summary.json` with `party_eci_code: null` instead. The fix for a dropped label is always: edit the taxonomy file (add an alias, add a missing code, add a new party row) and re-emit. There is no auto-appended overlay anymore.

> **Historical note (PR-R.3, 2026-05-19)**: the registry was previously a three-layer merge of (a) per-event `parties.json` shards, (b) `datasets/reference/in/parties-discovered.json` (auto-extended at emit time), and (c) `datasets/reference/in/parties.json` (hand-curated master). The auto-extending overlay was retired because it conflated lifecycles — every re-ingest of one event rewrote the overlay's `fetched_at` for every party, and the overlay's existence let operator curation drift behind upstream surface area indefinitely. `datasets/taxonomy/parties.json` is now the single hand-curated roster; the per-event shards are derived. The frontend reads party metadata through view-model loaders over `dim_parties` + `dim_party_alliances` (no separate registry fetch).

Concretely, what the emit log tells you:

```
parties.json: 4 parties (102 dropped — short_names absent from registry: AAAP, ...)
  └─ archived path; 4 of 106 Section-3 parties resolved against datasets/taxonomy/parties.json
  └─ triage the 102 dropped shorts by adding them (or an aliases[] entry) to datasets/taxonomy/parties.json and re-emitting
parties.json: SKIPPED (no partywise snapshot and no Section 3)
  └─ very unusual; means the catalog had no Section 3 either
(no parties.json line)
  └─ live path; full roster always emitted
```

`reconcile_winners_against_partywise` only runs on the live path. Archived cohorts trust Section 10 alone (there is no second source to cross-check against), and the validator picks up any internal inconsistency at file-write time. Increasing archived-cohort coverage means growing the registry — either by ingesting more live cohorts, or by a future adapter for `notification.eci.gov.in` (the canonical party-registration source for the full ~2,800 entry party universe).

### WB (S25) bootstrap policy

**Superseded 2026-05-09.** The original plan was to bootstrap WB directly from an ECI Statistical Report at `status: complete`, skipping the Wikipedia-provisional intermediate step that TN and Kerala went through. Phase A surfaced that `old.eci.gov.in` is unreachable from the current dev environment, blocking the ECI-first path indefinitely.

The policy applied: WB and Assam (the two missing 2026-cohort states) were both bootstrapped from Wikipedia at `status: provisional` on 2026-05-09, matching the TN/Kerala pattern. Promotion to `complete` for any of the four states is now a single follow-up gated on the Delimitation Order ingestion, not a per-state divergent path. Cleaner uniformity beats the lost head-start on WB.

### Authority rationale

A clear authority order ends ambiguity over "which source wins when they disagree" — ECI Statistical Reports do. Separating recon from enrichment prevents the "let me also write the parser while I'm here" sprawl: recon's output is reviewed before parser work starts. Signed-URL non-persistence is policy: a `sources[]` entry that 404s in a week is worse than no entry — it implies traceability that does not exist.

Acknowledged costs: recon discovers reality. If a state's report is published as a scanned PDF rather than XLSX, Phase B for that state is much harder. We accept this; pretending the data is uniformly XLSX would just defer the surprise.

### Authority — alternatives considered

- **Treat all ECI surfaces (Statistical Reports, Results portal, Delimitation Order, CEO sites) as one undifferentiated "ECI source".** Rejected: they differ in authority, freshness, and format. "Any ECI URL satisfies `status: complete`" loses meaning.
- **Combine recon and enrichment in one workstream.** Rejected: recon's purpose is to surface unknowns; tying it to a parser commits us to a parser shape before we know what we're parsing.
- **Keep recon findings only in `notes/` / TODO files.** Rejected: `notes/` and `TODO/` are working memory. Durable ingest mechanics belong here, with historical trace in `docs/archive/` if useful.
- **Persist signed download URLs in `sources[]` "for traceability".** Rejected: they expire.

## See also

- [Backend overview](overview.md), [Pipeline orchestration](pipeline.md), [Wikipedia adapter](sources-wikipedia.md)
- [`docs/reference/data-sources.md`](../../reference/data-sources.md) — live catalogue of sources and URL grammars.
- [`tools/eci_recon/`](../../../tools/eci_recon/) — Phase A reconnaissance tool.
- [ADR-0003 — No fetch cache](../decisions/0003-no-fetch-cache.md) — `.runtime/raw/` placement for intermediate downloads.
- [Constituency hierarchy & status lifecycle](../data-model.md#constituency-hierarchy-and-status-lifecycle).
