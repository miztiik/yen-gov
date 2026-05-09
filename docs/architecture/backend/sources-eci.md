# Backend `sources/eci/` — ECI Source Adapter

**Last Updated**: 2026-05-09

`backend/yen_gov/sources/eci/` is the adapter for the Election Commission of India's surfaces. It owns URL conventions for both the live results portal (`results.eci.gov.in`) and the Statistical Reports hub (`eci.gov.in/statistical-report/...`), the HTML and XLSX parsers, and the per-page commitment about which artifact each ECI page can produce.

## Modules

| File | Responsibility |
| ---- | -------------- |
| [`urls.py`](../../../backend/yen_gov/sources/eci/urls.py) | URL builders for the results portal: `event_index_url`, `partywise_state_url`, `constituencywise_url`. Validates state codes against `^[SU]\\d{2}$`. |
| [`partywise.py`](../../../backend/yen_gov/sources/eci/partywise.py) | `parse_partywise(content) -> PartywiseSnapshot`. Source of truth for party seat counts and party ECI codes within a state. |
| [`constituencywise.py`](../../../backend/yen_gov/sources/eci/constituencywise.py) | `parse_constituencywise(content) -> ConstituencywiseRaw`; `to_constituency_result(raw, *, election, state, body, eci_no, ...)` binds it to `result.constituency.schema.json`. |
| [`categories.py`](../../../backend/yen_gov/sources/eci/categories.py) | Pinned `dict[(state_code, year), int]` of Statistical Report `category_id`s for the new ECI portal. Hand-curated from Phase A recon — extending it requires a code change, not a config edit. |
| [`statistical_report.py`](../../../backend/yen_gov/sources/eci/statistical_report.py) | `statistical_report_catalog_url`, `parse_catalog`, `fetch_catalog`, `download_documents`. Catalog = list of `(xlsx_url, pdf_zip_url)` permalinks under `/all_files/election_report/...` (safe to persist in `sources[]`). |
| [`statistical_report_detailed.py`](../../../backend/yen_gov/sources/eci/statistical_report_detailed.py) | `parse_detailed_results(xlsx_bytes) -> DetailedResultsRaw`; `to_constituency_results(raw, *, election, state, top_n, collapse_others, sources, party_eci_codes=None)` emits one `ConstituencyResult` per AC from Section 10 ("Detailed Results"). |

The Statistical Reports parser (XLSX-based) is Phase B work — see [authority hierarchy for past elections](#authority-hierarchy-for-past-elections) below.

## URL conventions

Three builders for the results portal, returning fully-qualified `https://results.eci.gov.in/...` URLs:

- `event_index_url(event_id)` → `/Result<event_id>/index.htm`
- `partywise_state_url(event_id, state_code)` → `/Result<event_id>/partywiseresult-<state>.htm`
- `constituencywise_url(event_id, state_code, eci_no)` → `/Result<event_id>/Constituencywise<state><n>.htm`

`event_id` is the opaque slug ECI assigns each event (e.g. `AcGenMay2026`). It is supplied by `processing.json` / pipeline config — never inferred. State codes are validated against `^[SU]\d{2}$` (matches `state.schema.json`'s ECI code constraint).

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

## Alternatives considered

- **One function `parse_constituencywise_to_result(url, election, top_n, ...)`**. Rejected: collapses parsing and modelling, makes it impossible to test parsing alone without schema constraints, and forces re-fetch to re-derive when knobs change.
- **Have parsers return dicts, not dataclasses**. Rejected: dicts give zero IDE help and zero per-field type checks at the parser/mapper boundary.
- **Auto-discover the partywise table by class name (e.g. `.partywise-table`)**. Rejected: ECI HTML uses bootstrap utility classes (`table table-striped`) shared across many tables. Header-row text matching is more robust to cosmetic class churn.
- **Save HTML fixtures under `tests/fixtures/eci/` and run tests offline**. Rejected: fixtures drift from reality and create false confidence. We accept the live-test cost in exchange for early warning when ECI changes a page.
- **Build `ResultSummary` from partywise alone**. Rejected: the partywise page gives seats, not votes. Emitting a summary with `votes=0` everywhere would technically pass schema but would silently mislead consumers.

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

**Persisted in `sources[]`** (the human-facing landing page):

```
https://www.eci.gov.in/statistical-report/{body}/{year}/{state-code}
```

**Never persisted in `sources[]`** (time-limited signed URLs from the "Download" buttons):

```
https://www.eci.gov.in/eci-backend/public/api/download?url=<base64-blob>
```

These signed URLs expire. We re-resolve them from the landing page on every fetch. The intermediate downloaded XLSX/PDF lives in `.runtime/raw/eci/statistical_report/{body}/{year}/{state-code}/<filename>` per [no fetch cache](../decisions/0003-no-fetch-cache.md) — not a contract surface, gitignored, throwaway.

The ECI URL grammar uses *display* state codes (e.g. `26` for Tamil Nadu), not the `S22`-style codes we use internally. The mapping must be empirically confirmed during the recon pass and recorded in [`docs/reference/identifiers.md`](../../reference/identifiers.md). Until the mapping for a state is confirmed, code MUST NOT silently assume it.

### Two-phase rollout

**Phase A — Reconnaissance** (in `tools/eci_recon/`, per CLAUDE.md §3 / §4: tools are self-contained, no `backend/` imports). **Done 2026-05-09**; output in `notes/eci-recon-2026-05-09.md`. Key findings the parser depends on:

- The new portal's `/statistical-reports` hub table is hardcoded in `main.<hash>.js`. There is no JSON API that returns the (state, year) → URL map; the React bundle IS the canonical inventory. Recon extracts it by regex and prints it into the inventory note.
- 2024+ events use `GET /eci-backend/public/api/election-result?category_id=<int>` with a *cleartext* small integer; the response carries stable `https://www.eci.gov.in/eci-backend/public/all_files/election_report/...` PDF/XLSX permalinks safe to persist in `sources[]`.
- 2021 and earlier link directly to `https://old.eci.gov.in/files/file/<id>-<slug>/` landing pages from the same hub table.
- ECI's `jl()` AES-ECB obfuscation (key `4WS8851W824R456Y`, public constant from the bundle) wraps category_ids on a small set of legacy endpoints (`/api/get-statistical?categories=jl(<id>)`, `/api/get-sub-category`). Implemented in `tools/eci_recon/recon.py` for completeness; **not on the canonical Phase B path** — the hub table gives every URL we need cleartext.
- `old.eci.gov.in` is unreachable from at least one dev environment (Windows box: ConnectTimeout). Recon documents reachability per probe rather than silently dropping URLs it couldn't visit.

**Phase B — Enrichment**. First slice is **2026-only**, scoped to the four state assemblies that polled in May 2026: `S22` (Tamil Nadu), `S11` (Kerala), `S25` (West Bengal), `S03` (Assam). Pipeline shape:

1. **Catalog**: call `GET /api/election-result?category_id=<id>` per state. The `category_id` per `(state, year)` is harvested from the React bundle (Phase A) and pinned in `backend/yen_gov/sources/eci/categories.py` as a `dict[(state, year), int]` with the source URL in a sibling comment. Extending the map requires a code change, not a config edit. Phase A confirmed the pinned values for the 2026 cohort: `S03→23`, `S11→24`, `S22→26`, `S25→27` (each Statistical Report family ships 14 sectioned XLSX/PDF documents).
2. **Download**: every listed `xlsx_url` (and the matching `pdf_zip_url` for human cross-check) to `.runtime/raw/eci/<state>/<year>/<slug>.xlsx` per [no fetch cache](../decisions/0003-no-fetch-cache.md). The landing-page permalink — *not* the path under `.runtime/raw/` — goes into `sources[]` with the fetch timestamp.
3. **Parse**: with `openpyxl` directly. `pandas.read_excel` would pull a 50MB wheel for 90% unused functionality; the read-only XLSX surface fits openpyxl cleanly. Each report section becomes its own emitted artifact under `datasets/results/in/<state>/<year>/<section>.json`, validated against the appropriate result schema.
4. **No `jl()` on the canonical path.** The 2024+ endpoint is cleartext; the helper stays in `tools/eci_recon/` for future legacy probing only.
5. **Hand-curated `category_id` map, not auto-discovery.** Recon is the discovery mechanism; ingestion uses pinned ids. A "figure it out at runtime" approach makes the pipeline non-deterministic and silently breaks when ECI reshuffles the bundle. Mismatch between the pinned id and the next recon run is the early-warning signal.

The catalog + download steps are exposed end-user as `python -m yen_gov eci-statreport <state> <year> [--download] [--skip-pdf]`. Without `--download` the command prints the resolved permalinks (useful for review before pulling 13 MB per state); with `--download` it fetches every XLSX and PDF through the standard `core.http.Fetcher` so on-disk placement under `.runtime/raw/eci/...` matches every other source. The CLI overrides the configured `user_agent` to bare `Mozilla/5.0` because Akamai (fronting `www.eci.gov.in`) blocks the project's default `yen-gov/0.1` UA.

Smoke-tested 2026-05-09: all four states (S22/S11/S25/S03) returned 14 documents each, 28 files per state, ≈3 MB per state.

### Section 10 ("Detailed Results") parser

Section 10 of every Statistical Report carries the per-AC per-candidate vote breakdown — the richest single sheet in the bundle and a near-direct fit for `result.constituency.schema.json`. The XLSX layout (header at row 4) is `STATE/UT NAME | AC NO. | AC NAME | CANDIDATE NAME | GENDER | AGE | CATEGORY | PARTY | SYMBOL | GENERAL | POSTAL | TOTAL | %_OVER_VALID_NOTA | %_OVER_TOTAL_ELECTORS | TOTAL_ELECTORS`. Each AC section ends with a `TURN OUT` sentinel row carrying the polled totals + turnout %; the file ends with a single `GRAND TOTAL:` row and a disclaimer (both ignored).

The parser (`statistical_report_detailed.py`) follows the same two-step convention as the HTML parsers: `parse_detailed_results(bytes) -> DetailedResultsRaw` is pure XLSX → data; `to_constituency_results(raw, *, election, state, top_n, collapse_others, sources)` adds caller-supplied identity coordinates and the processing knobs and emits the schema-bound model. Vote-share columns are taken as-authoritative from ECI's own pre-computed values.

**Party codes**: Section 10 carries party SHORT codes only (TVK, ADMK, INC, IND, NOTA, ...) — no numeric ECI code. The parser leaves `party_eci_code` empty; the mapper (`to_constituency_results`) accepts an optional `party_eci_codes: dict[short → eci_code]` lookup that backfills it. The lookup is built from the live-results `partywiseresult-<state>.htm` snapshot via `pipeline.compose.eci_code_by_short_from_partywise` — the only place that page's numeric codes meet Section 10's short codes. Independents and shorts absent from the partywise table get `null` (schema permits it). Keeping the lookup *outside* the parser preserves the two-step convention: Section 10 → raw is one ingest, partywise → identity-table is another, and the composer is the seam.

**Countermanded ACs are skipped silently.** ECI publishes a stub Section-10 row for postponed/countermanded constituencies (a single zero-vote NOTA row with `polled_total = 0`; e.g. WB 2026 AC #144 FALTA). The schema requires `candidates: minItems: 1` and a non-zero winner — emitting a stub would mislead consumers. Skipping leaves a gap in the per-AC file sequence (`results/144.json` simply does not exist) which is the correct signal: a contiguous AC numbering can't be assumed.

End-to-end emit is exposed as `python -m yen_gov eci-statreport-emit <state> <year> [--event AcGenMay2026] [--output ...]`. The command fetches the catalog, the Section 10 XLSX, AND the live-results `partywiseresult-<state>.htm`; both URLs land in the `sources[]` array of every emitted artifact. Before any artifact is written, `reconcile_winners_against_partywise` cross-checks per-AC winners (aggregated by `party_short`) against partywise `seats_won + leading` — a mismatch aborts the run with a fail-loud `ValueError`, so we never publish a partial slice when the two ECI sources disagree. Outputs under `<output_dir>/`: `results/<eci_no>.json` per AC, `result.summary.json` (state-level rollup, composed directly from the raw sections via `compose_result_summary_from_section_10`), and `parties.json` (canonical roster, same shape as the Phase A pipeline). The state-level `result.summary.json` carries `party_eci_code` on every party_totals row whose short is mapped. Confirmed 2026-05-09 against all four 2026 states: S03=126, S11=140, S22=234, S25=293 (1 countermanded), 793 ConstituencyResult artifacts total, reconciliation passes for all four, validator clean. SQLite is then emitted by `emit_state_sqlite(state_dir=...)` against the same directory (S03 80 KB, S11 96 KB, S22 140 KB, S25 172 KB).

**Out of scope for the first Phase B slice**: 2021 / 2016 / 2011 backfill (blocked on `old.eci.gov.in` reachability — needs a network change or a mirroring decision before it can run); promotion of any reference file from `provisional` to `complete` (needs the Delimitation Order PDF for AC↔PC↔district mapping, independent of statistical-report ingestion); per-AC live counting pages on `results.eci.gov.in` (covered by the live-results scraper, different host and schema).

### WB (S25) bootstrap policy

**Superseded 2026-05-09.** The original plan was to bootstrap WB directly from an ECI Statistical Report at `status: complete`, skipping the Wikipedia-provisional intermediate step that TN and Kerala went through. Phase A surfaced that `old.eci.gov.in` is unreachable from the current dev environment, blocking the ECI-first path indefinitely.

The policy applied: WB and Assam (the two missing 2026-cohort states) were both bootstrapped from Wikipedia at `status: provisional` on 2026-05-09, matching the TN/Kerala pattern. Promotion to `complete` for any of the four states is now a single follow-up gated on the Delimitation Order ingestion, not a per-state divergent path. Cleaner uniformity beats the lost head-start on WB.

### Authority rationale

A clear authority order ends ambiguity over "which source wins when they disagree" — ECI Statistical Reports do. Separating recon from enrichment prevents the "let me also write the parser while I'm here" sprawl: recon's output is reviewed before parser work starts. WB bootstrap from ECI rather than Wikipedia gives us a `complete`-grade reference file from day one for that state, not a `provisional` one. Signed-URL non-persistence is policy: a `sources[]` entry that 404s in a week is worse than no entry — it implies traceability that does not exist.

Acknowledged costs: recon discovers reality. If a state's report is published as a scanned PDF rather than XLSX, Phase B for that state is much harder. We accept this; pretending the data is uniformly XLSX would just defer the surprise.

### Authority — alternatives considered

- **Treat all ECI surfaces (Statistical Reports, Results portal, Delimitation Order, CEO sites) as one undifferentiated "ECI source".** Rejected: they differ in authority, freshness, and format. "Any ECI URL satisfies `status: complete`" loses meaning.
- **Combine recon and enrichment in one workstream.** Rejected: recon's purpose is to surface unknowns; tying it to a parser commits us to a parser shape before we know what we're parsing.
- **Bootstrap WB from Wikipedia for consistency, promote later.** Rejected by user direction. Also dispreferred: every `provisional` file is a future migration we'd rather not create when we can avoid it.
- **Persist signed download URLs in `sources[]` "for traceability".** Rejected: they expire.

## See also

- [Backend overview](overview.md), [Pipeline orchestration](pipeline.md), [Wikipedia adapter](sources-wikipedia.md)
- [`docs/reference/data-sources.md`](../../reference/data-sources.md) — live catalogue of sources and URL grammars.
- [`tools/eci_recon/`](../../../tools/eci_recon/) — Phase A reconnaissance tool.
- [ADR-0003 — No fetch cache](../decisions/0003-no-fetch-cache.md) — `.runtime/raw/` placement for intermediate downloads.
- [Constituency hierarchy & status lifecycle](../data-model.md#constituency-hierarchy-and-status-lifecycle).
