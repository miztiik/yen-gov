# How to run the pipeline

**Last Updated**: 2026-06-08

> **Post-B4 (2026-06-06 / 2026-06-07).** The legacy live-fetch pipeline (`yen-gov run <event> <state>`, `yen-gov reference <state>`, `yen-gov pipeline run`, and 8 other network CLIs) was deleted in B4-pt2.2 (#826) along with `pipeline/run.py` + `pipeline/reference.py`, and `core/http.py` + the `httpx`/`tenacity` runtime dependency were retired in B4-pt2.4 (#828) per [TODO/20260603-data-and-charting-platform-reset-plan.md](../../TODO/20260603-data-and-charting-platform-reset-plan.md) section 21.4. Production runtime no longer fetches over the network. The surviving operator CLIs are listed below; all read local source files (frozen CSV, hand-downloaded XLSX) into the canonical long-format CSV store under `datasets/data/`.

All commands live in [`backend/yen_gov/cli.py`](../../backend/yen_gov/cli.py) and run via `python -m yen_gov <command>` from the `backend/` directory with the venv active.

## Prerequisites

- Python 3.11+ with the backend installed: `pip install -e backend/`.
- For the ECI/TCPD ingest commands: a local copy of the source CSV under `datasets/ephemeral/` (gitignored, see plan section 21.4 / B4 for the operator-handoff convention).
- For `eci-statreport-emit-local`: a hand-downloaded Section 10 XLSX under `datasets/raw_ephemeral_datasets/`.

## Operator commands

| Command | What it does |
| ------- | ------------ |
| `validate` | Two-tier schema validator (CLAUDE.md §11). Tier A (always-on in pytest) + Tier B (corpus walk, local-only). |
| `coverage` | Regenerates [data-inventory.md](../reference/data-inventory.md) from `datasets/taxonomy/election_events.json` + on-disk artifacts. |
| `emit-taxonomy` | Compiles hand-authored taxonomy JSON (entities, office holdings) into canonical CSV under `datasets/data/`. Supports `--dry-run` for byte-compare reports. |
| `check-overlap` | Concept-overlap gate (CLAUDE.md §10): scores a candidate concept against `datasets/taxonomy/concepts.json` before any new `indicator_id` is minted. |
| `pre-flight-ingest` | ADR-0046 6-check gate run before every new-source ingest handover-doc lands. Reads a JSON proposal; writes a JSON report. |

## Election ingest commands

All four ingest commands read a frozen CSV/XLSX off disk and write directly into the canonical Parquet/CSV store. No network. Each is idempotent against `datasets/elections/_inventory.json`; pass `--force` to re-ingest a recorded event.

| Command | Source shape | Writes |
| ------- | ------------ | ------ |
| `ingest-eci-ae-panel --input <csv> --state <S##>` | All-states ECI Assembly Election panel CSV, filtered to one state code. Supports `--delim-id` repetition, `--min-year/--max-year`, `--dry-run` preflight, `--allow-unknown-parties`. | `dim_persons` + `elections_candidacies` + `dim_acs` + party dims + election observations + inventory row. |
| `ingest-eci-ls --input <Report-33.csv> --crosswalk <Report-34.csv>` | ECI 2024 Parliament Report-33 (constituency-wise detailed result) + Report-34 (AC→PC crosswalk). | `dim_pcs` + observations across rewritten per-state shards. |
| `ingest-ls-ge-tcpd --input All_States_GE.csv --year <YYYY>` | One historical Parliament year from the TCPD All-States GE panel. Year must resolve via the `(year → event_id)` registry in `eci_ls.EVENT_BY_GE_YEAR`. | Same shape as `ingest-eci-ls`, scoped to the one historical year. |
| `eci-statreport-emit-local <xlsx>` | Hand-downloaded Section 10 XLSX (filename pattern `YYYY_state_<name>_*.xlsx`; state/year auto-detected). | `datasets/elections/<event>/<state>/results.csv` (researcher-facing CSV bundle, the only post-B4-pt3 emit). |
| `canonical-backfill-eci [--event <id>] [--state <S##>] [--corpus-root <dir>]` | Backfills `datasets/elections/election_results.parquet` from a per-AC JSON corpus (typically a restored snapshot under `datasets/ephemeral/legacy-corpus/elections`). | Re-emits the canonical Parquet's per-state shards. |

Provenance: every emitted observation row carries a `source_id` FK to `datasets/data/entities/source.csv` (CLAUDE.md §12). The four ingest commands derive `source_id` via `backend.yen_gov.canonical.citation.derive_source_id`; `eci-statreport-emit-local` emits with `sources: []` per ADR-0002 (hand-authored / out-of-band ingest signal).

## Force re-collection

There is no force-refetch flag in any config file. Re-ingest works two ways:

- For canonical Parquet/CSV ingest: pass `--force` to the relevant ingest command; the inventory row gates the no-op skip.
- For operator-tier `tools/` fetchers that still touch the network (font builds, raw data refreshes), delete the relevant `.runtime/raw/<source>/...` cache before re-running the tool. `.runtime/raw/` is throwaway debug per [core](../architecture/backend/core.md) and the `.runtime/` gitignore.

See [`how-to/force-recollect.md`](force-recollect.md).

## See also

- [backend/sources-eci.md](../architecture/backend/sources-eci.md) (ECI parser conventions; partial-stale post-B4 banner included)
- [backend/pipeline.md](../architecture/backend/pipeline.md) (composition + reconciler model; pre-B4 narrative)
- [docs/concepts/data-provenance.md](../concepts/data-provenance.md) (what `sources[]` / `source_id` mean in every emitted row)
- [TODO/20260603-data-and-charting-platform-reset-plan.md](../../TODO/20260603-data-and-charting-platform-reset-plan.md) section 21.4 (binding direction for the B4 elections-backend rip)
