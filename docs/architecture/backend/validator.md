# Validator (`yen_gov.validate`)

**Last Updated**: 2026-06-14

The two-tier validator that enforces CLAUDE.md §11 (schema versioning)
and §12 (provenance) shape across schemas and data files. This doc
explains where each tier runs, why, and what the deliberate descope of
corpus validation from CI is protecting.

## See also

- [CLAUDE.md §11](../../../CLAUDE.md) — schema versioning rules.
- [CLAUDE.md §12](../../../CLAUDE.md) — provenance rules.
- [CLAUDE.md §15](../../../CLAUDE.md) — test coverage policy.
- [ADR-0047](../../reference/decision-index.md) - writer-strict / reader-compatible schema policy.
- [docs/architecture/data/schema-evolution.md](../data/schema-evolution.md)
- [`docs/concepts/data-provenance.md`](../../concepts/data-provenance.md)
- Source: [`backend/yen_gov/validate.py`](../../../backend/yen_gov/validate.py)
- CLI entry: [`backend/yen_gov/cli.py`](../../../backend/yen_gov/cli.py) `validate` command

## The two tiers

| Tier | What it asserts | Where it runs | Wall time |
| --- | --- | --- | --- |
| **A — schema sanity** | Every `*.schema.json` validates against the JSON Schema 2020-12 meta-schema; `x-version` is `<major>.<minor>`; `x-changelog` is non-empty and its tail entry's `version` matches `x-version`; malformed JSON is reported, not crashed on. | `pytest -q` in `backend/`, via fixture tests in `tests/test_validate.py` that construct synthetic schemas in `tmp_path`. Always on; runs in CI. | <1s |
| **B - corpus conformance** | Every `*.json` under `datasets/` and `config/` declares `$schema` and `$schema_version`; the schema resolves; the declared version is accepted by the active compatibility contract; the file validates against the schema the reader is allowed to use. It also owns exhaustive boundary corpus facts: known Hive path shape under `datasets/boundaries/in/`, TopoJSON -> GeoJSON sibling presence, and TopoJSON/GeoJSON feature-count parity. Row E consumes `datasets/schema-compatibility.json` for the `json-corpus` surface; Row H defines the retained historical schema path and resolver used when a future entry needs declared-version validation. | `python -m yen_gov validate --root .` invoked locally before committing changes that touch `datasets/**`, `config/**`, `datasets/schemas/**`, or boundary geometry. NOT gated in CI. | Corpus-sized; local-only |

## Why Tier B is local-only

The production frontend lives in a separate repository and pulls
`datasets/**` at runtime via `https://raw.githubusercontent.com/...`
URLs. This repo's CI builds a Python package and an admin app; neither
artifact carries the corpus into production. Re-validating every
`datasets/**/*.json` on every PR here would be gating a build that
doesn't consume what's being validated.

The contract that actually matters is **between the corpus on `main`
and the frontend reading it over HTTP at runtime**. That contract is
defended in two places:

1. **Producer side, locally**: the engineer making the change runs
   `python -m yen_gov validate --root .` before pushing. CLAUDE.md §11
   and §15 require this for any commit touching schemas or data.
2. **Consumer side, in the frontend repo**: fixed frontend canaries validate
   representative JSON and boundary artifacts against the same contracts at
   frontend build / test time. They prove reader wiring and schema resolution;
   they do not duplicate the full producer corpus walk.

Putting a third gate in this repo's CI — walking 4,842 files on every
PR, including PRs that touch only Python source code — was busywork
that delivered no signal a local pre-commit run wouldn't catch first.

## CLI

```powershell
$env:PYTHONPATH = "backend"
python -m yen_gov validate --root .   # from the repo root; full corpus walk
```

Exit 0 = clean. Exit 1 = at least one Tier-A or Tier-B failure;
per-failure line printed as `[tier X] path: message`.

The `--root` option is the only flag. There is no `--path` filter
today; if three concrete callers earn one, add it then.

## Schema-version compatibility

Tier B is the corpus-side reader contract. Per [ADR-0047](../../reference/decision-index.md), writers stay strict while readers may become compatible by explicit contract.

The explicit contract lives at `datasets/schema-compatibility.json`, validated by `datasets/schemas/schema-compatibility.schema.json`. PR #467 makes Tier B consume that registry for the `json-corpus` surface. The default remains current-schema only, but an override can accept an older same-major changelog version when `validation` is `current_schema` and the artifact still validates against the current schema.

Declared-version schema resolution is defined by `datasets/schema-evolution.json` and `backend.yen_gov.core.schema_evolution.resolve_schema_for_declared_version()`. The current Tier-B corpus path still validates accepted same-major additive minors with the current schema unless a future compatibility row explicitly chooses retained-schema validation. Old majors remain unsupported until a release entry names a retained schema, translator, or migration.

Retained historical schemas live under `datasets/schemas/archive/<schema-stem>/v<major>.<minor>/<schema-file>`. A release entry with `validation_strategy=declared_schema` must name that file and its SHA-256. If the file is missing, the hash does not match, or the retained schema's `x-version` differs from the declared version, the resolver fails loudly.

Tier B still fails for:

- Unknown schema ids.
- Unsupported future versions.
- Unsupported major versions.
- Declared versions whose artifact shape is invalid for the allowed schema path.
- Old versions that require a retained historical schema or translator that does not exist.

Tier B must not accept an artifact by guessing defaults for missing historical fields.

## Tests

- `backend/tests/test_validate.py` — fixture-based, runs in pytest.
  All cases use `tmp_path` and construct synthetic schemas/data. None
   walk the on-disk corpus. Boundary Tier-B tests seed tiny GeoJSON /
   TopoJSON fixture pairs to cover Hive path shape, sibling presence,
   feature-count parity, and regression guards that `run()` chains each
   check.
- `backend/tests/test_admin_schemas.py` — same pattern, one altitude
  up. Tests the `/api/schemas` FastAPI route by pointing it at a
  `tmp_path` fixture corpus via the `YEN_GOV_REPO_ROOT` env var
  (`monkeypatch.setenv`). Three tests run in ~0.2s. The previous
  version of this file hit the live endpoint, which walked the real
  `datasets/**` corpus inside the route handler — 22s per test, 66s
  total. The endpoint's behaviour was reasserting Tier-B conformance
  on the real repo in HTTP disguise.
- The previous `test_repo_passes_validation` (which walked all of
  `datasets/`), `test_trigger_validate_end_to_end` in
  `test_admin_pipeline.py` (which spawned the walk as a subprocess and
  took 60-180s), and `test_repo_schemas_are_clean` in
  `test_admin_schemas.py` (which asserted the live endpoint reported
  zero corpus failures against the real repo) were all deleted on
  2026-05-16 / 2026-05-17. They tested data quality, not code
  correctness, and were the dominant reason devs ran
  `pytest --ignore=...`. Combined wall-clock savings: ~150s per
  `pytest -q`.

Validator fixture tests assert schema-version relationships, not current
point literals. When a fixture means "the current writer version", source
that value from `yen_gov.core.schema_registry.schema_version()` or from
the fixture schema's own `x-version`; do not hardcode today's value in the
assertion. Explicit version literals remain valid for migration fixtures,
historical/backcompat cases, intentionally bad-version rejection, and
synthetic schemas. See [docs/architecture/testing.md](../testing.md)
`Schema Versions In Tests` for the full test doctrine.

## Pattern: env-var injection for "endpoint walks the corpus"

Any FastAPI route, CLI, or tool that defaults to the real repo root
MUST take that root via an injectable parameter, not a module-level
constant. The shape used here is:

```python
# backend/yen_gov/admin/schemas.py
_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[3]

def _repo_root() -> Path:
    override = os.environ.get("YEN_GOV_REPO_ROOT")
    return Path(override) if override else _DEFAULT_REPO_ROOT
```

Tests then `monkeypatch.setenv("YEN_GOV_REPO_ROOT", str(tmp_path))`
and build whatever minimal corpus the test needs. Production
behaviour is unchanged (env var is absent). The handler reads the root
exactly once per request and threads it through.

Symptoms that this pattern is missing:

- A single pytest test takes >5s and most of that is walking
  `datasets/**`.
- The fix for a "test failed" report is "add the missing file" or
  "regenerate the artifact", not "change the code".
- The test starts failing on a teammate's machine after they pull a
  corpus-only PR.

When you see those, refactor to inject the root before extending the
test.

## Frontend repo split: where the consumer-side test goes

`frontend/src/contracts/datasets-conform.test.ts` is the consumer-side
counterpart to backend Tier-B. It keeps schema registry sanity,
schema-compatibility algorithm tests, and a small explicit artifact
canary list. It must not walk every `datasets/**/*.json`; exhaustive
JSON corpus validation belongs to Tier B. Today it lives in this repo
because the frontend is still co-located; per the deployment doctrine
the frontend will move to a separate repo and pull `datasets/**` at
runtime from `raw.githubusercontent`.

When that split happens:

1. `datasets-conform.test.ts` moves with the frontend, NOT with the
   backend. It remains a fixed canary suite proving the frontend can
   resolve schemas and validate representative artifacts it fetches over
   HTTP.
2. The backend repo's vitest suite goes away entirely.
3. The "no test walks the real corpus" rule generalises from "no
   pytest test" to "no default test in the backend repo, period,
   regardless of language". The producer-side gate stays local
   (`python -m yen_gov validate --root .` before commit) and the
   consumer-side gate stays in the frontend repo.

Until the split: this test stays here, but it follows the same fixed
canary discipline as the rest of the frontend contracts.

## Default frontend corpus-cardinality guardrail

Default frontend tests must not scale with corpus cardinality. No default
frontend Vitest may create one test per dataset file, shard, row,
district, village, ward, panchayat, constituency, party, indicator, path,
or schema artifact. Frontend tests prove consumer behavior with fixtures
and representative canaries. Exhaustive corpus validation belongs to
producer receipts plus backend Tier-B validation.

If a default frontend test uses broad `globSync`, recursive `readdirSync`,
or loops over `datasets/**` to generate test cases, it is presumed wrong
unless bounded by a small explicit canary list.

## Rejected designs

These were considered and explicitly NOT adopted; do not re-propose
without new evidence:

1. **A `.github/workflows/validate-corpus.yml` with workflow-level
   `on.pull_request.paths:` filter on `datasets/**` etc.** Rejected
   because there is no CI consumer in this repo. A PR touching only
   datasets does not produce a build that consumes them; the gate
   belongs at the consumer (frontend repo against raw.githubusercontent
   URLs) or upstream of the push (local pre-commit run).
2. **A `validate --path GLOB` selective CLI.** Premature. Adding a
   knob before three concrete callers ask for it is hardcoding the
   wrong shape. If/when added, the trigger is real call sites, not
   speculation.
3. **A `.pre-commit-config.yaml` hook running the validator.**
   Rejected as ceremony. A 60s pre-commit hook trains engineers to
   `--no-verify`; doctrine that says "run `yen_gov validate` before
   committing data" is a clearer cultural rule than a slow hook devs
   route around.

## Subtree exemptions (`_EXCLUDED_PATH_SEGMENTS`)

Some subtrees under `DATA_ROOTS` are exempt from Tier-B conformance
because they are not contract surfaces. Exemption is a doctrine
decision; the exempt set is small, hand-curated, and a literal
basename match (not a glob / prefix / leading-underscore heuristic).
Stray underscore-prefixed dirs (e.g. an accidental `_scratch/`) MUST
still fail Tier B loudly — per Fowler review 2026-05-17.

Currently exempt:

| Segment | Why exempt |
| --- | --- |
| `ephemeral` | Operator scratch directory (`datasets/ephemeral/...`). Whole subtree is gitignored (`.gitignore = *`); same rationale as `.runtime/` per CLAUDE.md §2. Holds raw XLSX/PDF dumps, restored legacy-corpus snapshots, and operator inventory sidecars (e.g. `_ingest_inventory.json`) that are NOT contract surfaces. Added 2026-05-20 — `python -m yen_gov validate` was reporting `datasets/ephemeral/_ingest_inventory.json: missing or empty '$schema' field` for a gitignored operator sidecar, which is the validator-tests-DATA-not-CODE smell from the 2026-05-16 descope lesson one layer up: pytest-tier-A doesn't walk it, but Tier-B was. |

Historical note: `_test` was previously exempt as a cross-language
test-fixture subtree (`datasets/_test/temporal-range-fixtures/cases.json`).
T.1 deleted that subtree — shared cross-language
fixtures now live under `backend/tests/fixtures/` (Python-owned, single
source of truth) pointed at by both pytest (`backend/tests/test_derive_temporal_range.py`)
and vitest (`frontend/src/lib/indicators.test.ts`). `_ops/` is NOT in the
exempt set: JSON under `_ops/` MUST carry `$schema` like any other contract
surface (current contents are non-JSON Parquet).

To add a new exemption:

1. Open a Plan-tier discussion: why is this subtree not a contract
   surface? What gitignore / lifecycle / consumer story justifies
   skipping it?
2. Add the literal basename to `_EXCLUDED_PATH_SEGMENTS` in
   `backend/yen_gov/validate.py` (NOT a glob, NOT a prefix — literal
   `parts` match).
3. Add a fixture test in `backend/tests/test_validate.py` mirroring
   `test_tier_b_skips_ephemeral_subtree` that constructs a fake
   subtree under `tmp_path` and asserts no failures reference it.
4. Update this table in the same commit.

Do NOT exempt subtrees that contain published artifacts the frontend
consumes at runtime. That's the consumer-side contract; skipping it
here is silently breaking the bet from "Frontend repo split: where the
consumer-side test goes" above.

## Forbidden-path checks

Beyond per-file schema conformance, Tier-B carries a small registry of
**forbidden-path** checks that enforce CLAUDE.md §10 anti-patterns
computationally rather than purely textually. Each check is a stand-alone
function in `backend/yen_gov/validate.py` chained into `run()`; tests live
in `backend/tests/test_validate.py` and use `tmp_path` fixtures (no real
corpus walks per CLAUDE.md §10 anti-pattern).

| Function | What it forbids | Allowlist input | Tests |
| --- | --- | --- | --- |
| `tier_b_meadow_shard_contract` | New `*.json` files under `datasets/indicators/in/`. The legacy folded-indicator shards retire family-by-family. New content must land on the canonical CSV store under `datasets/data/`. | `datasets/_ops/meadow-shard-contract.txt` (one POSIX path per line; `#`-comments + blank lines ignored). | 6 cases - passes when allowlisted, rejects new shard, rejects orphan allowlist entry, no-op when indicators dir absent, requires allowlist when indicators dir present, regression guard that `run()` chains the check. |
| `tier_b_legacy_boundary_sidecars` | Legacy boundary sidecars (`*.sources.json`, `*.metadata.json`, `*.unkeyed.json`) and per-state villages index manifests under `datasets/boundaries/`. Boundary metadata now lives in `datasets/data/entities/boundary_layer.csv`. | `datasets/_ops/legacy-boundary-sidecars.txt` | 7 cases - passes when allowlisted, rejects sidecars/indexes, rejects orphan allowlist entries, no-op when the boundary tree is absent, requires allowlist when needed, regression guard that `run()` chains the check. |

## Boundary corpus checks

Row A of the frontend corpus test-tier reset moved the exhaustive boundary
encoding proof from default Vitest into Tier B:

| Function | What it asserts | Tests |
| --- | --- | --- |
| `tier_b_boundary_hive_path_shape` | Every `.geojson` and `.topojson` under `datasets/boundaries/in/` matches a known Hive path family. | Fixture accepts representative families, rejects an unknown family, and guards `run()` chaining. |
| `tier_b_boundary_topo_sibling_pairs` | Every `.topojson` under `datasets/boundaries/in/` has a sibling `.geojson`; GeoJSON-only legacy shards remain allowed. | Fixture permits GeoJSON-only, rejects orphan TopoJSON, and guards `run()` chaining. |
| `tier_b_boundary_topo_feature_count_parity` | For every TopoJSON/GeoJSON pair, TopoJSON object geometry count equals GeoJSON `features.length`. | Fixture accepts matching pairs, rejects mismatch, and guards `run()` chaining. |

Frontend `boundaries-conform.test.ts` keeps a small canary set for Hive
path grammar, sidecar absence, ledger presence, states join key, and
TopoJSON decode. It is not the exhaustive boundary corpus gate.

### Shape of a forbidden-path check

Each check is a `def tier_b_<name>(root: Path) -> list[Failure]:` function
that takes a repo root and returns a list of `Failure` records. The check
is responsible for:

1. **No-op gating** — if the forbidden subtree is gone (final retirement
   PR has shipped), the check returns `[]` without requiring the allowlist.
   This is the retirement contract: the directory, the allowlist, and the
   check all disappear together; the check must not fail mid-retirement.
2. **Allowlist-present sanity** — if the forbidden subtree exists but the
   allowlist file is missing, fail loudly. Prevents silent passes from
   accidental allowlist deletion.
3. **Two symmetric failure modes** — files on disk not in allowlist
   ("forbidden new …"), and allowlist entries with no on-disk file
   ("orphan allowlist entry …"). Both surface so the allowlist stays in
   sync with reality.
4. **Plain-text allowlist** — `.txt` format under `datasets/_ops/` (per
   the operator-state directory's purpose per CLAUDE.md §3). JSON
   allowlists would themselves require `$schema` under §11, adding
   ceremony with no upside. `#`-comments and blank lines supported.

### Why allowlists live under `datasets/_ops/`

`datasets/_ops/` is the operator-state directory per CLAUDE.md §3 — it
holds operational assets that are committed (vs `.runtime/`'s ephemeral
gitignored state) but are NOT citizen-facing fact tables. A forbidden-path
allowlist is exactly this shape: it documents WHICH files are permitted
to exist under a forbidden subtree pending family-by-family retirement.
Operators editing a family retirement PR amend the allowlist as part of the
same change. When the allowlist becomes empty AND the forbidden
subtree is empty, the allowlist file deletes alongside the legacy code.

Alternative homes considered and rejected:

1. **Constants in `validate.py`** — violates CLAUDE.md §6 (hardcoding
   taxonomy). The allowlist is reference data, not validator logic.
2. **`datasets/indicators/in/.allowlist`** — co-located but hidden-file
   pattern is discoverable only via `ls -la`; doesn't fit the established
   `_ops/` pattern; would need a per-forbidden-subtree dot-file rather
   than one canonical home.
3. **JSON allowlist with `$schema`** — heavier than the use case warrants.
   Plain text is grep-able, diff-friendly, and one-`Set.add`-per-line to
   parse. Schema overhead has no downstream consumer.

### Adding a new forbidden-path check

1. Add a sorted plain-text allowlist under `datasets/_ops/` (e.g.
   `datasets/_ops/<name>-allowlist.txt`).
2. Add the path constants near the top of `backend/yen_gov/validate.py`
   alongside `LEGACY_INDICATOR_SHARDS_*` (one DIR constant, one ALLOWLIST
   constant).
3. Add a `tier_b_<name>(root: Path) -> list[Failure]` function modelled
   on `tier_b_meadow_shard_contract` (see "Shape of a
   forbidden-path check" above).
4. Chain the function into `run()`.
5. Mirror the six Tier-A test cases in `backend/tests/test_validate.py`,
   reusing the `_seed_indicator_tree` helper as a template (parameterise
   on dir + allowlist constants).
6. Add a row to the table at the top of this section.
7. Add an entry to `datasets/_ops/README.md`.
8. Add an "Enforced by Tier-B" sentence to the matching CLAUDE.md §10
   anti-pattern entry.
9. Add a sentence to the subsystem doc that owns the retired surface so agents
   can find the invariant without reading historical ledgers.

## Tier C - per-source parity (operator-only)

Tier C is the cross-source validation seam introduced by the [electoral-data quality + party-catalogue plan](../../archive/plans/20260610-electoral-data-quality-and-party-catalogue-plan.md) (closed 2026-06-11). It compares yen-gov's canonical store against external publishers (TCPD, ECI registered-parties list, Wikipedia, bhukyavenkatamahesh/election-viz, thecont1/india-votes-data, IndiaVotes) and emits a per-row verdict CSV the operator reviews before applying enrichments.

Tier C is operator-only by design (Gregor verdict, Wave 0 / section 6 of the plan-doc). It is NOT chained into `python -m yen_gov validate --root .` and it does NOT block CI. Its outputs (verdict CSVs) ARE committed to the repo as audit ledgers.

### CLI shape

Three sub-commands under `python -m yen_gov`, each scoped to a different parity granularity:

| Sub-command | Granularity | Compares | When to run |
| --- | --- | --- | --- |
| `parity` | per-party-roster (Shape-A) | `parties.csv` rows vs an external party-list snapshot (TCPD-PoliticalPartiesIndia, ECI registered list, Wikipedia List of political parties in India) | After every Wave B PR-W-* enrichment lands; cited in the PR body as the source of the proposed mint / enrich / alias-add actions. |
| `parity-event` | per-constituency (Shape-B) | yen-gov per-AC results vs an external per-AC source (thecont1/india-votes-data + TCPD All_States_AE.csv filtered by state-event) | Per-state per-event sweep; one run per Stream C / Stream D Wave PR (TN AcGenMay2026, MH AcGenNov2024, KA AcGenMay2023, MP AcGenNov2023, WB AcGenApr2021). |
| `parity-pc` | per-PC (parliament) | yen-gov per-PC results vs bhukyavenkatamahesh/election-viz + TCPD All_States_GE.csv filtered by election | Per-parliament-event sweep; one run per LS-2024 (PR-PC-LS2024) and LS-2019 (PR-PC-LS2019) PRs. |

CLI usage shape (verbatim from the parity sub-command help):

```powershell
python -m yen_gov parity `
  --source <tcpd-parties | eci-registered | wikipedia-parties | indiavotes-state | bhukyavenkatamahesh-pc | thecont1-state> `
  --vintage <YYYY-MM-DD | YYYY> `
  [--state <slug>] `
  [--event <AcGen* | LsGen*>] `
  [--kind <assembly | parliament>] `
  --report <output-csv-path>
```

The CLI dispatches to a registered adapter under `backend/yen_gov/canonical/recon/adapters/<source>.py`. Each adapter exposes an `ADAPTER` module-level constant; the parity CLI walks the registry at startup. Adding a new source is a one-file PR: drop a `recon/adapters/<source>.py` carrying a `ShapeARow` (or per-event / per-PC analogue) mapper and an `ADAPTER` constant.

### Verdict.csv shape (Shape-A)

The Shape-A intermediate carries one row per external party reference. The aggregator joins against the canonical `parties.csv` and emits a verdict row per pairing:

| Column | Purpose |
| --- | --- |
| `external_key` | The publisher's per-row identifier (TCPD `Party_Abbreviation`, ECI registration number, etc.). |
| `external_short` | The publisher's short label verbatim. |
| `external_full` | The publisher's long name verbatim. |
| `proposed_party_id` | The canonical `parties.IN.<X>` the aggregator believes this row maps to (NULL if it proposes a mint). |
| `current_party_id` | The canonical id currently resolved by the central resolver (or NULL if the resolver returns `parties.IN.UNK`). |
| `action` | Enum: `match` (already resolves cleanly), `enrich` (resolves but missing metadata that the external carries), `mint-new` (no canonical row exists), `alias-add` (canonical row exists but the alias set is missing this label), `conflict` (publisher disagrees with another publisher on a fact). |
| `n_oracles_present` | Number of external sources that emitted a row for this external_key in the parity run. |
| `n_oracles_agreeing` | Number that agree with `proposed_party_id`. |
| `oracles_agreeing` | Pipe-list of source names that agree. |
| `oracles_disagreeing` | Pipe-list of source names that disagree. |
| `verdict` | Enum: `VERIFIED` / `DISPUTED` / `UNVERIFIED` (see Fowler rule below). |
| `curator_note` | Hand-curated commentary; NULL on first emit. |
| `curator_source_id` | FK to `datasets/data/entities/source.csv`; NULL on first emit. |

### Verdict rule (Fowler machine-decidable contract)

The verdict enum follows ONE deterministic rule, ratified by Fowler in the panel-converged Wave 0 review (2026-06-10):

```
verdict = VERIFIED  iff  n_oracles_agreeing == n_oracles_present  AND  n_oracles_present >= 2
verdict = DISPUTED  iff  n_oracles_present >= 2  AND  n_oracles_agreeing < n_oracles_present
verdict = UNVERIFIED iff  n_oracles_present < 2
```

No LLM judgement. No "looks plausible" heuristics. The rule is machine-decidable so that re-runs are deterministic and a verdict.csv committed at time `T1` reproduces byte-identical when re-emitted at `T2` against the same external snapshots.

Only `VERIFIED` rows are auto-applied to `parties.csv`. `DISPUTED` rows stay in the verdict.csv as a permanent audit ledger; the curator opens an issue and adds a `curator_note` + `curator_source_id` to the row in a follow-up commit. `UNVERIFIED` rows leave `parties.csv` unchanged.

### Operator-committed-snapshot pattern

No Tier-C run hits a live publisher URL from CI. Every external source is pre-fetched once by the operator into `datasets/ephemeral/<source>/<vintage>/<filename>`, committed to the repo, and read locally by the parity adapter. The operator-committed snapshot is the audit trail:

- Wikipedia / TCPD / thecont1 / bhukyavenkatamahesh: one-off git-clone or wget into `datasets/ephemeral/<source>/<vintage>/`, then `git add` + commit.
- ECI Statistical Report Section 33 CSVs (2019 + 2024 PC-level): already on disk under `datasets/ephemeral/<year>_india_loksabha_33-Constituency-Wise-Detailed-Result.csv`.
- ECI registered-parties list: parsed via Wikipedia's mirror table (Wikipedia cites ECI's last publication date), since ECI does not publish the list in a machine-readable form.

The snapshot's content_hash is implicit in the git tree; the verdict.csv emitted at PR commit SHA `<sha>` lives at `datasets/ephemeral/party-parity/<source>/<vintage>/<sha>/verdict.csv`. Subsequent re-runs of the same parity at a later SHA emit a sibling verdict.csv under the new SHA path; the historical verdict.csv stays unchanged. Per Q3 default (Wave 0 / Gregor section 5 of the plan-doc): ONE frozen verdict.csv per PR-W or PR-S revision; subsequent re-runs are NOT auto-committed.

### CI hygiene

If a publisher changes their HTML schema between an operator's snapshot capture and a re-run, the parity adapter exits non-zero with a clear error message (the schema-validator on the adapter's parse path raises). The CLI does NOT silently emit an empty verdict.csv. The verdict.csv at the time of the affected PR remains the operator's audit trail; re-snapshotting is the operator's call.

### See also (Tier C-specific)

- [../../concepts/party-identity.md](../../concepts/party-identity.md) - the 4-class collision taxonomy + resolver priority that Tier-C parity verifies.
- [../data/party-lineage.md](../data/party-lineage.md) - the 33-case lineage catalogue that PR-W-* enrichments draw from.
- [../../archive/plans/20260610-electoral-data-quality-and-party-catalogue-plan.md](../../archive/plans/20260610-electoral-data-quality-and-party-catalogue-plan.md) - the umbrella plan; section 3 (per-PR briefs) carries the exact CLI invocations each Wave B / C / D PR used.
- [../../how-to/ship-a-pr.md](../../how-to/ship-a-pr.md) - the 5-gate Definition-of-Done; Tier C is NOT one of the gates by design.
