# tools/eci_recon

**Last Updated**: 2026-05-15

> Phase A of the [authority hierarchy for past elections](../../docs/architecture/backend/sources-eci.md#authority-hierarchy-for-past-elections): probe ECI's reachable endpoints and produce a Markdown inventory of what's available for the in-scope (state × year) matrix. **Reconnaissance only — does not write to `datasets/`.**

## Run

```bash
python tools/eci_recon/recon.py
```

Historically this tool wrote a human-review inventory outside `docs/`. Durable findings must now be distilled into [backend/sources-eci.md](../../docs/architecture/backend/sources-eci.md) or archived under `docs/archive/`; `notes/` is non-authoritative per CLAUDE.md §3.

## What it probes

For the matrix `{S22, S11, S25} × {2021, 2016, 2011}` plus `S22 × 2026`:

1. **State-code mapping** via `GET /api/get-ac-election-state` on the new portal. Later recon established that the 2024+ Statistical Report landing-page integer is the API `category_id`, not a general state-display-code lookup.
2. **Per-(state, year) notification metadata** via `GET /api/get-ac-election-details?iYear=<y>&st_code=<s>&election_id=3`. This endpoint only carries the active cycle; past cycles return empty. The recon records that fact per cell.
3. **Publications catalogue** via `GET /api/eci-publication` and the paginated `GET /api/general-election-narative-reports-publication`. Filters for documents whose title/description mentions a state in scope, "statistical", "assembly election", or "legislative".
4. **Legacy-host reachability** for `old.eci.gov.in` and `eci.gov.in` (file-host subdomain), where the per-state AE statistical reports for 2021 / 2016 / 2011 actually live. The recon records the HEAD response (or the connect error) so the inventory reflects the truth about *whether the run could see them at all*.

## What it does NOT do

- Does **not** download any XLSX/PDF (Phase B work).
- Does **not** write to `datasets/` (Phase A constraint per [backend/sources-eci.md](../../docs/architecture/backend/sources-eci.md#authority-hierarchy-for-past-elections)).
- Does **not** parse statistical reports (different ADR for that).
- Does **not** persist signed `/eci-backend/.../api/download?url=<blob>` URLs anywhere.

## Constants you may need to refresh

`NEW_PORTAL_SECRET = "ECI@MAIN825"` is embedded in the public ECI JS bundle. If the probes start returning 401/403, refresh by:

```bash
curl -s "https://www.eci.gov.in/static/js/main.<hash>.js" | grep -oE '"ECI@[A-Z0-9]+"' | head -1
```

(The bundle hash changes on each ECI deploy; find the current one via the `<script src="/static/js/main.*.js">` tag in `https://www.eci.gov.in/`.) This is a public constant from a public bundle, not a credential.

## Dependencies

- `httpx` — HTTP client (CLAUDE.md §10 prefers OSS over custom).

No `backend/` imports, no `frontend/` imports — `tools/` is self-contained per CLAUDE.md §4.
