# Backend `sources/wikipedia/` — Wikipedia Source Adapter

**Last Updated**: 2026-05-09

`backend/yen_gov/sources/wikipedia/` is the adapter for the English Wikipedia. It supplies *reference* data ECI does not publish in machine-readable form: districts per state, and per-state assembly constituencies with reservation status. It also implements a heuristic district-name resolver to bridge spelling drift between Wikipedia's two relevant page families.

Wikipedia is a **bootstrap source**, never the only source for a `status: complete` reference file (see also: [authority hierarchy](sources-eci.md#authority-hierarchy-for-past-elections)).

## Modules

| File | Responsibility |
| ---- | -------------- |
| [`urls.py`](../../../backend/yen_gov/sources/wikipedia/urls.py) | URL builders + ECI-state-code → Wikipedia-article-name map. |
| [`districts.py`](../../../backend/yen_gov/sources/wikipedia/districts.py) | Parses `List of districts of <State>` → `DistrictsCollection`. |
| [`constituencies.py`](../../../backend/yen_gov/sources/wikipedia/constituencies.py) | Parses `List of constituencies of the <State> Legislative Assembly` → `ConstituenciesCollection`. Includes `build_district_lookup()` two-pass resolver. |

## URL building

State-name routing is an explicit dict in `urls.py`:

```python
_ECI_TO_WIKI_STATE = {"S22": "Tamil Nadu", ...}
```

Adding state support means adding the entry. We chose explicit lookup over generic name normalisation because (a) the set is finite (36 states/UTs), (b) Wikipedia article names occasionally differ from official English names ("Odisha" vs older "Orissa" redirects), and (c) a missing entry must fail loudly with a `ValueError`, not silently 404.

This dict is *adapter-local routing data*, not user-facing taxonomy (CLAUDE.md §6). The user-facing names live in `state.schema.json`-validated content.

## User-Agent

`en.wikipedia.org` returns 403 to default httpx User-Agents. The Wikipedia API etiquette page asks for a descriptive UA identifying the project and a contact URL. Tests and the pipeline both send:

```
yen-gov/<version> (https://github.com/yen-gov/yen-gov; election data pipeline) httpx
```

Test code carries the same string; bot-mitigation is per-UA, not per-IP.

## District parser — two-pass with predecessor resolution

1. Parse rows into adapter-local `_Row` dataclasses with raw `predecessors: list[str]`.
2. Build `name → code` map across all current rows.
3. Resolve each row's predecessor names against the map. Names that resolve become the `split_from` id list; names that don't (older districts no longer existing as standalones) are dropped and recorded in `notes`.

This keeps the schema's `split_from: array of strings` invariant intact — every entry references a current district id — without losing the unresolved information.

## Constituency parser — minimal per-row data

The page's first wikitable carries `# | Constituency | Reserved | Electors | Change | District | …`. We extract only the first three columns and emit `ConstituencyEntry(eci_no, name, reservation, district_id=None)`:

- Wikipedia uses rowspans for repeated district names, which lxml's `text_content()` does not unfold.
- ECI's spelling for districts varies ("Tirunelveli" vs "Thirunelveli"), so a string match against `district.json` ids would be brittle.
- `constituency.district_id` is *optional* in the schema. Filling it is a downstream concern (see [district-name resolution](#district-name-resolution-for-ac-tables) below).

Reservation tokens are normalised explicitly:

| Wikipedia cell | Normalised |
| -------------- | ---------- |
| `-`, `—`, `–`, blank, `GEN`, `General`, `None` | `GEN` |
| `SC`           | `SC`       |
| `ST`           | `ST`       |
| anything else  | **raises** `ValueError` |

A new reservation code (e.g. a Wikipedia editor invents `Backward`) must surface as a parser failure rather than be silently coerced.

The constituency parser asserts that the parsed AC numbers form a contiguous `1..N` sequence. A missed row or duplicate would otherwise quietly land in the artifact.

All Wikipedia-bootstrapped constituency files are emitted with `status: "provisional"` per [constituency hierarchy & status lifecycle](../data-model.md#constituency-hierarchy-and-status-lifecycle). Wikipedia alone cannot promote a file to `complete`.

## District-name resolution for AC tables

Wikipedia's "List of constituencies of the X Legislative Assembly" tables already carry a District column, but the strings in that column do not match the names emitted by `parse_districts` 1:1. Real cases observed in TN + KL:

| AC table writes  | Districts page writes      |
| ---------------- | -------------------------- |
| `Thiruvallur`    | `Tiruvallur`               |
| `Tirupattur`     | `Tirupathur`               |
| `Kanniyakumari`  | `Kanyakumari`              |
| `Chennai`        | `Chennai (formerly Madras)`|
| `Kasargod`       | `Kasaragod`                |

These are not data errors — Indian district names have multiple defensible romanisations; different Wikipedia editors picked different ones. A naive casefolded equality check resolved 192 of 234 TN ACs and 135 of 140 KL ACs, leaving 47 unresolved across two states.

A two-pass resolver in `sources.wikipedia.constituencies`:

1. **Exact key**: `_strip_parens(name).casefold().strip()` — handles the parenthesised-suffix case (`Chennai (formerly Madras)` → `chennai`).
2. **Skeleton key**: a deterministic `_norm()` that lowercases, drops non-alpha, removes every `h`, removes vowels after the first character, and collapses repeated letters. Designed to make `Thiruvallur` / `Tiruvallur` / `Tirupathur` / `Tirupattur` / `Kanniyakumari` / `Kanyakumari` / `Kasargod` / `Kasaragod` all collide with their counterpart on the districts side.

`build_district_lookup()` indexes each district under **both** keys so callers see a single dict-of-strings interface.

If both passes miss, `district_id` is left absent — the entry stays valid under the provisional schema, and the unresolved cell is silently tolerated. We do not promote `status` to `complete` on Wikipedia data alone (that requires `pc_id` too, which Wikipedia AC tables don't carry).

### Resolver rationale

The rules give 100% resolution on TN (234/234) and KL (140/140) without per-state alias tables, and they're general (not state-specific) so new states should mostly work without adjustment. Status stays `provisional` until an authoritative ECI cross-check fills `pc_id`.

Acknowledged costs:

- The skeleton can in principle collide between two genuinely different districts that share a consonant skeleton. Mitigation: `build_district_lookup()` uses `setdefault`, so the first-registered district wins, and the lookup is built per-state (collision risk is bounded by the ~38 districts in the largest state we'll see).
- Heuristic rules will need tuning for north-eastern states (Khasi/Garo/Mizo names) where vowel-collapse may collide. We accept that and will revisit when those states are onboarded.

## Design rationale

- TN-only first slice can ship: districts.json + constituencies.json + everything ECI-derived. Other states unblocked by adding one URL-map entry.
- Parser failures are loud — tests catch reservation-token surprises and missing rows in CI's live tests.
- Zero coupling to `core.http.Fetcher`. The parser takes bytes; the orchestrator decides where they came from.

Acknowledged costs:

- Wikipedia drift (table reorganisations, header renames) breaks our parsers. Mitigated by header-text matching being lenient ("estd" or "established", any "reserv*" header) and live tests catching the change before code that consumes the artifact runs.
- District resolution for constituencies is heuristic until LGD codes land. `district_id` will stay `None` for any AC the resolver can't match.

## Alternatives considered

### Adapter scope

- **Wikipedia REST/Action API instead of HTML scraping**. Rejected: the data we need lives in human-edited wikitables, not in structured infoboxes or Wikidata claims for these specific articles. Wikidata occasionally lacks reservation status entirely.
- **Wikidata SPARQL for districts and ACs**. Rejected for now: Wikidata coverage of Indian electoral geography is uneven (some districts have items, some don't; reservation status is rarely modelled). Worth revisiting if/when coverage improves.
- **Generic `parse_wikitable(headers, content)` reused across pages**. Rejected: each page has page-specific concerns. A shared helper would be a thin wrapper over lxml that hides nothing.
- **Use Wikipedia's "Code" field as the canonical district id permanently**. Accepted as a temporary measure (`id_source="wikipedia"`); the schema's two-valued `id_source` lets us migrate to LGD codes by re-emitting the file with `id_source="lgd"` when we add an LGD adapter.

### District-name resolver

- **Hand-rolled per-state alias tables** (`{"Thiruvallur": "TAL", ...}`). Rejected: hardcoding (CLAUDE.md Holy Law #6) and unbounded maintenance — every new state needs a fresh alias table built by hand.
- **Levenshtein/Damerau-Levenshtein fuzzy match with a distance threshold**. Rejected: introduces a dependency for a problem that's already solvable with deterministic string ops; thresholds are inherently fiddly.
- **Extract LGD codes from gov.in Local Government Directory and match those instead**. The right long-term answer (CLAUDE.md §13) — when LGD codes land we'll use those for both districts.json and the AC↔district join, and this resolver becomes the fallback for states the LGD scrape doesn't cover.

## See also

- [Backend overview](overview.md), [Core](core.md), [Pipeline](pipeline.md)
- [ECI source adapter](sources-eci.md) — the canonical source for results data.
- [Constituency hierarchy & status lifecycle](../data-model.md#constituency-hierarchy-and-status-lifecycle)
- [`docs/concepts/electoral-hierarchy.md`](../../concepts/electoral-hierarchy.md)
