# Data Provenance

**Last Updated**: 2026-05-08

> Every byte yen-gov publishes must be traceable to where it came from. This is non-negotiable (CLAUDE.md Holy Law #9, §12). The mechanism is the `sources` array on every data file (ADR-0002).

## The contract

Every JSON file under `datasets/` and `config/` carries a top-level `sources` array. The validator (CLAUDE.md §11) rejects any file missing it.

```json
"sources": [
  { "url": "https://results.eci.gov.in/ResultAcGenMay2026/ConstituencywiseS22167.htm",
    "fetched_at": "2026-05-08T14:30:00Z" }
]
```

Each entry has two required fields:

- **`url`** — the exact page our pipeline fetched. Not a portal landing page when a deeper page is the real source. Not a search result. The URL bytes were retrieved from.
- **`fetched_at`** — RFC 3339 UTC timestamp of when our pipeline read that URL. Re-fetches update this value (or add a new entry, depending on the writer).

## Three shapes a `sources` array can take

### 1. One source — the simple case

Most downloaded files. One upstream, one fetch.

```json
"sources": [
  { "url": "https://results.eci.gov.in/ResultAcGenMay2026/partywiseresult-S22.htm",
    "fetched_at": "2026-05-08T14:30:00Z" }
]
```

### 2. Multiple sources — composed/aggregated artifacts

A state-level summary aggregated from per-constituency results carries every contributing URL plus the partywise summary URL. Each entry has its own `fetched_at` (the moments may differ across a long pipeline run).

```json
"sources": [
  { "url": "https://results.eci.gov.in/ResultAcGenMay2026/partywiseresult-S22.htm",
    "fetched_at": "2026-05-08T14:30:00Z" },
  { "url": "https://results.eci.gov.in/ResultAcGenMay2026/ConstituencywiseS22001.htm",
    "fetched_at": "2026-05-08T14:30:12Z" },
  { "url": "https://results.eci.gov.in/ResultAcGenMay2026/ConstituencywiseS22002.htm",
    "fetched_at": "2026-05-08T14:30:13Z" }
]
```

This is the canonical way to express composition. There is no "primary" entry; all contributing URLs are peers. Downstream tools that need to render lineage can iterate the array.

### 3. Empty array — hand-authored

```json
"sources": []
```

A maintainer wrote the content directly. No upstream URL was fetched. Empty `sources` is the canonical signal — there is no separate `hand-authored: true` flag, no sentinel string. The absence of upstream URLs *is* the statement.

The commit message that introduces or modifies a hand-authored file MUST record the rationale and any reference materials consulted. Hand-authored is not a license to invent data; it is a declaration that the source is the author plus whatever materials they cite in the commit. If the reference materials are URLs the maintainer consulted but the pipeline did not fetch, put them in `notes` on the relevant rows or in the commit message — they do NOT belong in `sources`, which is reserved for URLs the pipeline actually pulled.

**Canonical case: editorial sidecars (`*.notes.json`).** Indicator-notes sidecars are the textbook hand-authored case — they hold an editor's voice (`editor_note_md`, `policy_context[]`, chart hints) ABOUT the sibling indicator artifact. They ship with `"sources": []`; the editor is the source, the commit message records why. They MAY also cite an external editorial source if the editor leans on one (e.g. a CEA explainer that informed the policy bullets) — in that case the array is non-empty. See [indicator-notes.schema.json](../../datasets/schemas/indicator-notes.schema.json) (v1.1+) and the ADR-0002 "Consequences" clarification 2026-05-16: any file declaring a `$schema` carries the full `sources[]` envelope; there is no filename-pattern exemption.

## What does NOT live in `sources`

- **Intermediate downloaded files** under `.runtime/raw/` (per ADR-0003) are not data files in the `datasets/` sense. They have no `sources` field and no schema; they are throwaway debug artifacts.
- **Reference materials a human consulted** to write a hand-authored file. Those go in commit messages or `notes` fields.
- **Provenance of identifiers** (e.g. "S22 is the ECI code for Tamil Nadu, confirmed by URL X"). The identifier convention is documented in [`identifiers.md`](../reference/identifiers.md); per-file `sources` is for the *content*, not for the *naming*. When a per-row claim *about* an identifier needs to be machine-readable (e.g. "this code-to-name pair was confirmed by a live URL probe vs. only by a published ECI report"), that belongs in a typed schema field — see `verification_status` on `state.schema.json` v3.1 — not in `sources` and not in `notes`. Gregor architecture review 2026-05-11 sums this up: `sources[]` records *what was fetched*; row-level verification summaries are typed fields the schema anticipates.

## Why an array, not a single string

Earlier (schemas v2.0) we used a single `source: string` with a sentinel grammar (`hand-authored`, `derived-from:<path>`, `inherited-from:<id>`, `unknown`). It was discarded in favor of the array because:

- A single string can't honestly express composed/aggregated artifacts. State summaries genuinely have many contributing URLs.
- The sentinel zoo was ceremony for cases that don't actually arise (the `unknown` and `inherited-from:` sentinels were rarely needed in practice).
- The array form has one shape, one parser, no special cases. Empty array carries the hand-authored meaning more cleanly than a string sentinel.

See ADR-0002 for the full rationale.

## Why a per-entry `fetched_at`, not a top-level `fetched_at`

A composed artifact's contributing URLs may be fetched at different moments — sometimes minutes apart in a long pipeline run, sometimes hours apart in a re-fetch scenario. A single top-level `fetched_at` would have to either lie (claim the latest moment for everything) or pick an arbitrary one. Per-entry timestamps avoid both.

## Why this is mandatory

Election data published without provenance is anti-data. A reader cannot:

- assess whether the underlying source has been updated since,
- reproduce the result by re-fetching,
- argue with the source if a number looks wrong,
- trust the publisher.

Treating provenance as a hard contract — enforced by the validator, surfaced in `CLAUDE.md` Holy Laws, captured in every Definition of Done — is what separates a publishing pipeline from a data-laundering one.

## See also

- `CLAUDE.md` Holy Law #9, §12 — authoritative statement.
- [`docs/architecture/decisions/0002-provenance-as-sources-list.md`](../architecture/decisions/0002-provenance-as-sources-list.md) — why this shape.
- [`docs/architecture/decisions/0003-no-fetch-cache.md`](../architecture/decisions/0003-no-fetch-cache.md) — why intermediates in `.runtime/raw/` are excluded.
- [`docs/reference/schemas.md`](../reference/schemas.md) — every schema enforces `sources`.
- [`docs/reference/identifiers.md`](../reference/identifiers.md) — code conventions used inside payloads (separate from the provenance of the payload itself).
- [`docs/architecture/data-flow.md`](../architecture/data-flow.md) — pipeline that emits these files.
