# How to force re-collection of an indicator

**Last Updated**: 2026-06-08
**Audience**: operators with local clone of `yen-gov`.

> **Post-B4 (2026-06-06 / 2026-06-07).** Production runtime no longer fetches over the network; the legacy live-fetch loop (`yen-gov run`, `core/http.py`, `httpx`/`tenacity` runtime) was retired per [TODO/20260603-data-and-charting-platform-reset-plan.md](../../TODO/20260603-data-and-charting-platform-reset-plan.md) section 21.4. "Force recollect" today means either re-running a frozen-CSV ingest with `--force` or deleting a debug cache under `.runtime/raw/` before re-running an operator-tier `tools/` fetcher.

## Recipe A — re-ingest a canonical election artifact

The four surviving election ingest commands gate the no-op skip on a row in `datasets/elections/_inventory.json`. Pass `--force` to bypass:

- `python -m yen_gov ingest-eci-ae-panel --input <csv> --state <S##> --force`
- `python -m yen_gov ingest-eci-ls --input <Report-33.csv> --crosswalk <Report-34.csv> --force`
- `python -m yen_gov ingest-ls-ge-tcpd --input All_States_GE.csv --year <YYYY> --force`
- `python -m yen_gov canonical-backfill-eci --event <id> --state <S##>`

No state lives outside the inventory row; once `--force` runs, the next non-`--force` invocation skips again.

## Recipe B — re-fetch a `.runtime/raw/` debug cache (operator tier)

For operator-tier tools under [`tools/`](../../tools/) that still touch the network for a one-shot asset population (font builds, raw-data refreshes), the cache layer is `rm`:

1. Identify the relevant cache prefix under `.runtime/raw/<source>/`.
2. Delete the cache directory:

   ```powershell
   Remove-Item .runtime/raw/<source>/<path> -Recurse -Force
   ```

3. Re-run the tool. `.runtime/raw/` is throwaway debug per [core](../architecture/backend/core.md) (no schema, no contract surface, gitignored).

## Why no flag

A boolean force-refetch flag would be state. State duplicates state: the inventory row already says "this event was ingested"; the `--force` flag overrides that one decision without leaving residue. For the operator-tier `tools/` fetchers, `rm` of the debug cache is unambiguous and leaves nothing to remember to clear.

## See also

- [run-the-pipeline.md](run-the-pipeline.md) — surviving operator + ingest CLIs.
- [data-provenance](../concepts/data-provenance.md) — what `source_id` / `sources[]` mean on every re-ingested row.
- [core](../architecture/backend/core.md) — post-B4 `core/` module map.
