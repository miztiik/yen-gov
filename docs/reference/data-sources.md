# Data Sources

**Last Updated**: 2026-05-09

> The "look here first" catalogue. Every external place yen-gov pulls — or might pull — election data from is listed below, with what it covers, what format it ships, and when to use (or avoid) it. When enriching data in future, start here.
>
> The hierarchy is enforced by the [authority hierarchy for past elections](../architecture/backend/sources-eci.md#authority-hierarchy-for-past-elections): **ECI is the canonical source**; everything else is bootstrap, enrichment, or cross-check.

## Source authority order

1. **ECI Statistical Reports** — official tabulated post-election results (XLSX/PDF). Canonical for past elections.
2. **ECI Results Portal** (`results.eci.gov.in`) — live/post-poll constituency pages. Canonical for ECI numbering, party affiliations, and current-cycle results.
3. **ECI Delimitation Order 2008** — canonical for AC↔PC↔district mapping and reservation status.
4. **CEO state offices** — canonical for electoral roll counts and polling-station-level data.
5. **Wikipedia constituency lists** — fast bootstrap; never sufficient alone for `status: complete`.
6. **MyNeta** — canonical for candidate affidavits, declared assets, criminal cases. Not for vote counts.

## ECI Statistical Reports — the treasure trove

**Hub**: <https://www.eci.gov.in/statistical-reports>

**Per-election landing URL grammar** (observed):

```
https://www.eci.gov.in/statistical-report/{body}/{year}/{state-code}
```

| Token | Meaning | Example |
| ----- | ------- | ------- |
| `{body}` | `ae` for Assembly Election, `ge` for General (Lok Sabha) Election | `ae` |
| `{year}` | Year the election concluded | `2026` |
| `{state-code}` | ECI's *display* state code used in URL paths (numeric, NOT the same as the `S22`-style code we use internally) | `26` for Tamil Nadu |

**Confirmed mappings** (from URLs the user supplied or pages we have visited):

| Internal (ECI) | Display state code | State |
| -------------- | ------------------ | ----- |
| `S22`          | `26`               | Tamil Nadu |
| `S11`          | TBC                | Kerala |
| `S25`          | TBC                | West Bengal |

The "TBC" rows are confirmed during the [recon pass](../architecture/backend/sources-eci.md#two-phase-rollout) before any tooling depends on them. Mappings are then promoted into [`identifiers.md`](identifiers.md) as a stable lookup.

**Per-election known URLs** (assembly elections, last three cycles for the in-scope states):

| State | 2026 | 2021 | 2016 | 2011 |
| ----- | ---- | ---- | ---- | ---- |
| Tamil Nadu (S22) | <https://www.eci.gov.in/statistical-report/ae/2026/26> | TBC during recon | TBC | TBC |
| Kerala (S11) | n/a (next cycle 2026 TBC) | TBC | TBC | TBC |
| West Bengal (S25) | n/a (next cycle 2026 TBC) | TBC | TBC | TBC |

The recon script ([`tools/eci_recon/`](../../tools/eci_recon/)) populates the TBCs and lists the actual file artifacts (XLSX names, PDF names, sizes) attached to each landing page.

**Signed download URLs**: ECI's "Download" buttons point at `https://www.eci.gov.in/eci-backend/public/api/download?url=<base64-blob>` — the `url` query param is an encrypted/signed reference that is **time-limited**. We MUST NOT persist these URLs in `sources[]`. Persist the human-facing landing URL (`/statistical-report/...`) and, if needed, document the file name extracted from the response headers; re-resolve the signed URL each fetch. (See ADR-0003: no fetch cache; intermediate downloads live in `.runtime/raw/`.)

## ECI Results Portal

**Hub**: <https://results.eci.gov.in/>

**Per-constituency URL grammar**:

```
https://results.eci.gov.in/Result{ElectionEvent}/Constituencywise{State}{ConstNo:03d}.htm
```

Example: `https://results.eci.gov.in/ResultAcGenMay2026/ConstituencywiseS22167.htm` → TN AC #167 (Mannargudi) for the May 2026 Assembly General Election.

`{ElectionEvent}` is the ECI's per-event slug (e.g. `AcGenMay2026`, `AcGenApr2021`, `LSGenJun2024`). Slug history: TBC during recon. Documented in [backend/sources-eci.md](../architecture/backend/sources-eci.md).

## ECI Term of the Houses

<https://www.eci.gov.in/term-of-the-houses/>

Lists current Lok Sabha and every state Assembly with constitution and dissolution dates. Use to confirm: "when did the 2021 TN assembly's term end" / "when does the 2026 TN assembly start". Critical for naming election events correctly.

## ECI Delimitation Order 2008

<https://eci.gov.in/delimitation-website/> (PDF per state)

The only legally authoritative source for AC↔PC↔district mapping. Required ECI source for promoting any constituency reference file from `status: provisional` to `status: complete` (see [data-model.md](../architecture/data-model.md#constituency-hierarchy-and-status-lifecycle)).

## CEO state portals

| State | URL | Use for |
| ----- | --- | ------- |
| Tamil Nadu | <https://www.elections.tn.gov.in/> / <https://ceotamilnadu.nic.in/> | Electoral roll counts, polling station lists |
| Kerala | <https://www.ceo.kerala.gov.in/> | Same |
| West Bengal | <https://ceowestbengal.nic.in/> | Same |

Format varies wildly across states — usually PDFs; sometimes Excel.

## MyNeta (Association for Democratic Reforms)

**Hub**: <https://www.myneta.info/>

Tamil Nadu specific landing pages:

- 2021 Assembly: <https://www.myneta.info/TamilNadu2021/index.php?action=showWinnersExpense&sortExp=default>
- 2026 Assembly: <https://www.myneta.info/TamilNadu2026/>

Use for **candidate-level enrichment only** — declared assets, criminal cases, education, expense filings. **Do not** use as a source for vote counts; cross-check with ECI before persisting.

## Wikipedia

Bootstrap source for constituency lists, district lists, and election summary tables. Per-state URL grammar (observed):

```
https://en.wikipedia.org/wiki/List_of_constituencies_of_the_<State>_Legislative_Assembly
https://en.wikipedia.org/wiki/<Year>_<State>_Legislative_Assembly_election
https://en.wikipedia.org/wiki/List_of_districts_of_<State>
```

Wikipedia is excellent for fast structured tables and for human-readable history fields (`established_year`, mergers). Per [backend/sources-wikipedia.md](../architecture/backend/sources-wikipedia.md) and CLAUDE.md §10, never the *only* source for a `complete` file.

## What does NOT belong in `sources[]`

(Recap — see [`docs/concepts/data-provenance.md`](../concepts/data-provenance.md) for the canonical rule.)

- **Reference materials a maintainer consulted by hand** — go in commit messages or `notes`, not `sources`.
- **Time-limited signed URLs** (`/eci-backend/public/api/download?url=...`) — persist the landing page URL instead.
- **Search-result pages or portal home pages** — persist the deepest URL the pipeline actually fetched.
- **Files under `.runtime/raw/`** — debug artifacts, not provenance (ADR-0003).

## See also

- [backend/sources-eci.md](../architecture/backend/sources-eci.md) — ECI results portal adapter conventions and authority hierarchy for past elections.
- [backend/sources-wikipedia.md](../architecture/backend/sources-wikipedia.md) — Wikipedia adapter scope.
- [data-model.md](../architecture/data-model.md#constituency-hierarchy-and-status-lifecycle) — `status: complete` requires an ECI source.
- [`docs/concepts/data-provenance.md`](../concepts/data-provenance.md) — `sources[]` contract.
- [`docs/concepts/electoral-hierarchy.md`](../concepts/electoral-hierarchy.md) — what each source can authoritatively tell us about.
- [`docs/reference/identifiers.md`](identifiers.md) — `S22` ↔ display-code mapping (populated as recon confirms).
