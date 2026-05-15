Run on yen-gov repo:

    python tools/iced_full_triage.py

Probes every parameter-free path in the 259-endpoint ICED appendix
(`docs/architecture/backend/sources-iced-api.md`) on both v0 and v1
hosts, captures shape/row-count/time+facet keys/size, marks already-
bound paths, and writes `.runtime/iced_recon/full_triage_<UTC>.{csv,md}`.

Resume: rolling progress lives in `.runtime/iced_recon/_triage_rolling.csv`
— delete it for a fresh sweep, otherwise the script skips paths it has
already probed.

Hard timeout per probe: 18s (some ICED v1 endpoints accept the connection
but never close the response). Polite delay: 0.1s.
