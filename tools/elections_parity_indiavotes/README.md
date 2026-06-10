# IndiaVotes parity oracle

**Last Updated**: 2026-06-10

One-shot offline parity check between the yen-gov canonical election
summary CSV (`datasets/elections/{parliament,assembly}/.../summary.csv`)
and [IndiaVotes](https://www.indiavotes.com/) scraped HTML. Sole consumer
= the engineer running the gate. Output drops in `datasets/_ops/`. **NEVER
CI.** See [docs/how-to/validate-elections-vs-indiavotes.md](../../docs/how-to/validate-elections-vs-indiavotes.md)
for the operator runbook and the [archived PR-W1c row](../../docs/archive/plans/20260609-election-experience-overhaul-plan.md)
for the design context.

## Data source

The yen-gov side reads from the canonical, OWID-aligned summary table the
backend ingest writes after PR-W2a/W2b:

  - General events: `datasets/elections/parliament/election=<year>/summary.csv`
    (parliament summary is national-scope on disk; the reader filters by
    state inside the tool).
  - Assembly events: `datasets/elections/assembly/state=<slug>/election=<year>/summary.csv`
    (the path partition pins the state).

The surface flip from the long-format per-state CSV at
`datasets/data/datapoints/electoral/<state>_election_results.csv` to the
canonical summary.csv landed in the W1c/W2b follow-up bug-fix PR
(2026-06-10). The original surface used an entity_id grammar
(`IN-PC-1976-S26-1`) DIFFERENT from the canonical PC registry at
`datasets/data/entities/electoral.csv` (`IN-PC-2008-chhattisgarh-294`),
so the two surfaces shared no join key and the diff engine reported 0%
agreement on every PC probe. The new surface carries the canonical
entity_id AND a native `constituency_name` column, so the diff engine
joins on constituency name directly with no electoral.csv name-map
required.

## Packaging shape

The tool ships as a **script**, not an installable package. The
[`pyproject.toml`](pyproject.toml) exists only to pin the dep set; it
intentionally omits `[tool.setuptools.packages.find]`. The operator runs:

```pwsh
py -m venv .venv-parity
.\.venv-parity\Scripts\activate
pip install httpx beautifulsoup4 lxml
python tools/elections_parity_indiavotes/__main__.py --help
```

Do NOT install this into the project venv. It is intentionally isolated so
its deps never leak into the citizen pipeline or backend test surface.

## Usage

```pwsh
python tools/elections_parity_indiavotes/__main__.py `
  --event general-2024 `
  --state chhattisgarh `
  --output datasets/_ops/elections-parity-vs-indiavotes-2026-06-10.csv
```

Event slug grammar matches the PR-0 contract (`^(general|assembly)-\d{4}$`).
Bye-elections are out of scope for v0.1. State slug must exist in
`datasets/taxonomy/entities.json` (e.g. `andhra-pradesh`, `chhattisgarh`,
`uttar-pradesh`).

CSV columns:

```
state, event, constituency_name, source, winner_party, winner_name,
votes, margin, agrees, delta_notes
```

Each constituency emits TWO rows -- one `source=indiavotes`, one
`source=yen-gov` -- so the operator sees the full audit, not just deltas.
`agrees=true` iff both sides report the same normalised winning party.

## Politeness rules

- **1 request per second**, single-threaded. Hardcoded in
  [`scrape.py`](scrape.py) (`REQUEST_INTERVAL_SECONDS = 1.0`).
- **Cache-first.** Pages are cached under
  `datasets/ephemeral/indiavotes-snapshots/<YYYY-MM-DD>/<event>/<state>/page-N.html`;
  re-runs within 7 days are zero network traffic. The ephemeral tier is
  gitignored.
- **Citizen User-Agent.** No `Cookie` / `Referer` / yen-gov-tagged headers.
  IndiaVotes is treated as a goodwill provider.
- **No scraping at scale.** This tool fetches ONE state-event landing page
  per invocation. There is no bulk crawler and there will not be one.
- **No CI.** This is operator tooling. Adding it to a workflow is a Holy
  Law #5 violation (band-aid in the wrong layer).

## When IndiaVotes is unreachable

If the live probe fails (network down, 4xx/5xx, rate-limit), the CLI exits
with code 2 and prints a hint. To validate the diff engine end-to-end
against a synthetic fixture:

```pwsh
python tools/elections_parity_indiavotes/__main__.py `
  --event general-2024 `
  --state chhattisgarh `
  --fixture-html tools/elections_parity_indiavotes/tests/fixtures/indiavotes-chhattisgarh-general-2024.html `
  --output datasets/_ops/elections-parity-vs-indiavotes-synthetic.csv
```

The fixture is a 3-row mini-table that exercises both the agree path and
the mismatch path; the synthetic G1-EVIDENCE oracle is in
[`tests/test_diff.py`](tests/test_diff.py).

## URL template maintenance

[`scrape.py`](scrape.py) hardcodes two URL templates:

```
https://www.indiavotes.com/lok-sabha/<year>/<state-slug>
https://www.indiavotes.com/vidhan-sabha/<state-slug>/<year>
```

If a specific state's actual IndiaVotes landing page diverges (e.g. NCT of
Delhi published under a different slug shape), edit the template in
`scrape.py` for that state. The diff engine, cache layer, and CLI are
template-agnostic; only `scrape.py::resolve_target` needs updating.

## Post-mortem doctrine (Holy Law #5)

If a row in the output CSV records `agrees=false`, **fix the yen-gov
ingest**. Do NOT stash IndiaVotes rows into `source.csv`, do NOT patch the
yen-gov CSV by hand, do NOT add a hardcoded crosswalk. The parity oracle
exists to FIND ingest bugs, not to paper over them. Open an ingest-bug
ticket and route it to the source-of-truth adapter (TCPD for legacy years,
ECI for current years).

## Layer rules

- Self-contained. No imports from `backend/`. Verified by G4 grep gate.
- Reads `datasets/elections/{parliament,assembly}/.../summary.csv` and
  `datasets/taxonomy/entities.json` -- both are CONTRACT surfaces per
  [CLAUDE.md section 4](../../CLAUDE.md), not backend modules.
- Writes only to `datasets/_ops/` (operator state per CLAUDE.md section 3)
  and `datasets/ephemeral/indiavotes-snapshots/` (gitignored).
