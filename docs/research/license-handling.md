# Research: License handling (D9 implementation)

**Last Updated**: 2026-05-10
**Status**: planned — referenced from Phase A schema work and Phase C frontend rail

## Question

How does yen-gov honour data licenses end-to-end without dropping useful but ambiguously-licensed data?

User direction (D9, locked 2026-05-10): **don't hide "Unspecified" or NC datasets by default**. Show every layer with a license badge. Sort/prefer permissive-first. NC datasets are link-out-only (no bundled file).

## Constraints

1. **Honesty over filtering**: "Unspecified" is a true label; suppressing it would lie about the data. Show the badge, let the citizen judge.
2. **Attribution by construction**: every emitted artifact carries `sources[].name` + `.authority` + `.url` (CLAUDE.md §12 + D3 schema additions). The frontend renders attribution beside each layer; a citizen never sees a chart without knowing where the data came from.
3. **NC means no redistribution of bytes**: NC-licensed data (e.g. SHRUG, CC BY-NC-SA) does not get bundled. The frontend renders a card linking out to the source, with our research note attached. (Holy Law #1: static-first — we cannot apply NC enforcement at runtime, so we apply it at emit time.)
4. **License preference order** for picking among equivalent upstreams: `CC0` ≻ `CC-BY-4.0` ≻ `India OGL` ≻ `ODbL` ≻ other open ≻ `Unspecified`.

## Implementation

### Schema (Phase A)

- `metadata.license` is an object: `{ id (SPDX or canonical short), name (human), url (terms link or null), redistributable (bool) }`. The `redistributable` flag is `false` for any NC license and for licenses we explicitly know forbid bundling; `true` otherwise; `null` for `Unspecified`.

### Emit time (backend)

- Backend pipeline writes the artifact only if `redistributable != false`. NC datasets emit a stub: `<dataset>.link.json` carrying `metadata` + `sources` + `redistributable: false`, but no payload. Frontend handles the link-out from there.

### Frontend (Phase C)

- Every map layer's legend chip shows: layer name + license badge (colour-coded permissive→ambiguous→link-only) + a "i" → opens the source card.
- Source card: `name`, `authority`, `url`, `fetched_at`, `license.name + url`, citation BibTeX.
- A "filter by license" widget exists but defaults to **show all**.

### CI

- Validator (Tier B) rejects any artifact whose `license` is missing on a non-election dataset.
- A separate CI step (`scripts/check-license-redistribution.py`) walks `datasets/` and verifies that every payload file has `license.redistributable != false`. NC stubs are exempt.

## Open follow-ups

- SPDX coverage: India OGL is not in the SPDX list. We use `IndiaOGL` as our canonical id, document it in this note, and surface it in the frontend badge component.
- "Unspecified" with strong public-domain inference (e.g. government PDF without a notice): we still label `Unspecified` and add a `notes` field explaining the inference. We do not upgrade the label to OGL without a written permission.
- License migration: when an upstream clarifies a previously-Unspecified license, we update the artifact's `metadata.license` and bump the schema version of the artifact's source — track via a per-dataset research-note diff.

## References

- SPDX list: <https://spdx.org/licenses/>
- India OGL: <https://data.gov.in/sites/default/files/Gazette_Notification_OGDL.pdf>
- CC license matrix: <https://creativecommons.org/about/cclicenses/>
- ODbL: <https://opendatacommons.org/licenses/odbl/>
