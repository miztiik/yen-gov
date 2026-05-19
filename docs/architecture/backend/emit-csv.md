# Backend `emit/` — CSV Bundle Emitter

**Last Updated**: 2026-05-19

`backend/yen_gov/emit/csv_bundle.py` writes the per-state `results.csv` artifact at `datasets/elections/<event>/<state>/results.csv`. CSV is a **derived secondary artifact** built from the same validated `ConstituencyResult` records the canonical pipeline produces in-memory (primary API `emit_state_csv_from_data(constituencies=[...])`, see [ADR-0029](../decisions/0029-canonical-store-pipeline-shapes.md)). It is **not a contract surface** — no JSON Schema, no `x-version`/`x-changelog`. Column order is documented inline in the module and versioned via the `LAYOUT_VERSION` integer constant. Intended as a researcher-facing bulk download (Tier 3 in [dataset-shapes.md](../../concepts/dataset-shapes.md)).

> The per-state `result.summary.json` sibling that historically sat in the same directory retired in PR-O.4 (TODO row `1.8b-ii`, 2026-05-19), and the per-AC `results/<ac>.json` shards retired in PR-P (TODO row `1.8c`, 2026-05-19). The canonical Parquet at `datasets/elections/election_results.parquet` + the four dim tables are now the single source of truth for election data; this CSV emitter is unaffected — it now reads directly from the in-memory `ConstituencyResult` objects the canonical pipeline produces. The disk-walking wrapper `emit_state_csv(state_dir=...)` is preserved only for ad-hoc replays against legacy checkouts that still carry the per-AC JSON shards.

## Decisions in one screen

1. **One `.csv` per event/state.** Path: `datasets/elections/<event>/<state>/results.csv`. After PR-P (TODO row `1.8c`, 2026-05-19) the per-AC `results/<ac>.json` shards no longer exist on disk; the CSV is now built directly from the canonical pipeline's in-memory `ConstituencyResult` list. After PR-R.3 (TODO row `1.8e`, 2026-05-19) the previously co-located `results.sqlite` sibling is gone too — the CSV is the only on-disk artifact in `datasets/elections/<event>/<state>/`.
2. **Long format, one row per candidate.** NOTA gets its own row (`is_nota = 1`) at `rank = max_rank + 1` per AC. The collapsed `others` aggregate is intentionally NOT emitted — researchers who need the long tail re-ingest from the canonical JSON. The CSV is the top-N + NOTA view, matching the JSON contract surface exactly.
3. **Derived, not a contract.** No JSON Schema. Layout changes bump `LAYOUT_VERSION` (currently `1`) and are noted in this doc.
4. **Committed to git.** Same reasoning as the pre-PR-R.3 SQLite emitter ([ADR-0014](../decisions/0014-sqlite-emitter.md), now superseded): symmetric with JSON, byte-deterministic, small enough to track (~50–150 KB per state). The deploy step already does `cp -r datasets _site/data`.
5. **Auto-emit by default; `--csv/--no-csv` to skip.** `yen-gov run …` produces JSON + CSV in one shot.
6. **Lives in `backend/yen_gov/emit/`.** Reads validated JSON, never imports from `pipeline/`. A failure here must not block JSON emission.

## Columns (v1)

| Column | Source | Notes |
| --- | --- | --- |
| `election` | per-AC JSON `.election` | e.g. `AcGenMay2026` |
| `state` | per-AC JSON `.state` | ECI state code, e.g. `S22` |
| `body` | per-AC JSON `.body` | `AC` or `PC` |
| `ac_eci_no` | per-AC JSON `.eci_no` | canonical name per [ADR-0019](../decisions/0019-dataset-topology-and-column-discipline.md) |
| `constituency_name` | per-AC JSON `.constituency_name` | |
| `electors` | `.totals.electors` | nullable |
| `votes_polled` | `.totals.votes_polled` | nullable |
| `turnout_pct` | `.totals.turnout_pct` | nullable |
| `rank` | per-candidate `.rank`, NOTA = max + 1 | integer |
| `candidate_name` | per-candidate `.name` or `"NOTA"` | |
| `party_short` | per-candidate `.party_short` or `"NOTA"` | |
| `party_eci_code` | per-candidate `.party_eci_code` | empty for independents / NOTA |
| `votes` | per-candidate `.votes` or NOTA votes | |
| `vote_share_pct` | per-candidate `.vote_share_pct` | |
| `is_winner` | `1` on the winning row, else `0` | |
| `is_nota` | `1` on the NOTA row, else `0` | |
| `gender` | per-candidate `.gender` | empty when absent |
| `age` | per-candidate `.age` | empty when absent |
| `category` | per-candidate `.category` | empty when absent |

## Determinism guarantees

Same JSON inputs MUST produce a byte-identical CSV output. The emitter:

- Sorts rows by `(ac_eci_no, rank)`.
- Uses `\n` line terminators (not platform-native `\r\n`).
- Writes UTF-8 bytes via a `StringIO` buffer, not OS-default text mode.
- Atomic temp-file + `os.replace`.
- Never embeds wall-clock timestamps.

The corresponding test is `tests/test_emit_csv_bundle.py::test_emit_is_byte_deterministic`.

## Why long format

- Round-trips losslessly to per-AC JSON; the inverse (wide-with-top-N-as-columns) pre-decides what "top-N" means at emit time and loses information when N changes.
- `df.pivot` collapses long → wide in one line of pandas.
- Matches Lokniti / TCPD-IED convention; researchers know how to consume it.

## See also

- [dataset-shapes.md](../../concepts/dataset-shapes.md) — the per-state CSV is the only researcher-facing on-disk bundle left after PR-R.3 (SQLite tier retired).
- [ADR-0014](../decisions/0014-sqlite-emitter.md) — derived-artifact philosophy (now superseded by canonical Parquet + DuckDB-WASM; the CSV emitter still follows the same patterns).
- [ADR-0019](../decisions/0019-dataset-topology-and-column-discipline.md) — column naming.
