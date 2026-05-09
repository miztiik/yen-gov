# ADR-0002: Provenance as a list of `{url, fetched_at}` entries

**Last Updated**: 2026-05-08
**Status**: accepted (replaces the earlier sentinel-string approach used in schemas v2.0)

## Context

Earlier in design we adopted a single `source: string` field per data file with a sentinel grammar (`https?://…`, `hand-authored`, `derived-from:<path>`, `inherited-from:<id>`, `unknown`). In review the user pushed back: most of the sentinel zoo was ceremony for cases that don't actually arise in practice, and a single string can't express the common case where a final artifact is composed from multiple upstream pages (e.g. a state summary aggregated from per-AC results).

The user's framing: "the final artifact should say where the source data came from. And even have an option of the schema to say that the source [is] combined from multiple sources. So probably we can have a json list of sources along with the date time stamp."

## Decision

Every data file under `datasets/` carries:

```json
"sources": [
  { "url": "https://results.eci.gov.in/ResultAcGenMay2026/partywiseresult-S22.htm",
    "fetched_at": "2026-05-08T14:30:00Z" }
]
```

Rules:

- `sources` is a top-level array. Each entry has a required `url` (http/https) and a required `fetched_at` (RFC 3339 UTC timestamp) — the moment our pipeline pulled that URL.
- An empty `sources: []` is the canonical signal for **hand-authored** content. No `hand_authored: true` flag; no `unknown` sentinel; absence of upstream URLs *is* the statement.
- Multiple entries are allowed and meaningful: an aggregated artifact lists every upstream URL that contributed to it, each with its own `fetched_at`.
- Item-level provenance overrides (per-row `source` inside collections) are removed. If a collection genuinely combines heterogeneous origins, list them all in the file-level `sources`.
- The `derived-from:` and `inherited-from:` sentinels are removed entirely. Derived artifacts cite the upstream URLs of their inputs (transitively). If the upstream was a non-URL source (PDF, paper publication), upload it to a known URL or treat the derivation as hand-authored with a docs note.
- Intermediate downloaded files in `.runtime/raw/` are NOT subject to this contract — they are throwaway by-products (see ADR-0003).
- `config/processing.json` continues to carry `sources: []` because the schema validator covers it under the same envelope rules; the cost of one empty array is trivial.

Schemas bumped to v3.0 to encode this change.

## Consequences

- **Good**: aggregated artifacts can express their full lineage in machine-readable form. Downstream tools (frontend visualisations, audit reports) can render "data sourced from X URLs fetched between A and B".
- **Good**: simpler grammar — one shape, no sentinel parsing. Pydantic model in `core/models.py` becomes a trivial `list[Source]`.
- **Good**: re-fetching naturally extends the list (or replaces an entry); no string concatenation gymnastics.
- **Cost**: every emit path now needs to thread `fetched_at` through. Mitigated by `core/io.py` accepting a `sources: list[Source]` argument and stamping it.
- **Cost**: hand-authored files lose the explicit `hand-authored` marker. Mitigated by docs (`docs/concepts/data-provenance.md`) explicitly stating the convention.
- **Migration**: schemas v2.0 → v3.0 is a major bump; existing data files (3 of them) are rewritten by hand in the same commit.

## Alternatives considered

- **Keep sentinel strings, add a `sources` array alongside**. Rejected: two ways to express the same thing invites disagreement and bug surfaces.
- **Single `source` URL + separate `derivations: []` array**. Rejected: needlessly distinguishes the "primary" from the "secondary" sources. For a state summary aggregated from 234 AC pages, no entry is more "primary" than the others.
- **Require non-empty `sources` always; add an explicit `hand_authored: true` flag for the hand-authored case**. Considered and rejected via AskUserQuestion 2026-05-08: empty array is unambiguous and shorter; the schema's required-but-may-be-empty semantics carry the meaning.
