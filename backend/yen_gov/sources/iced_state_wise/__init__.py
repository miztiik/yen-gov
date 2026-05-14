"""ICED (NITI Aayog India Climate & Energy Dashboard) state-wise deep-dive adapter.

Source: https://iced.niti.gov.in/analytics/state-wise-deep-dive

API endpoint (recon 2026-05-14):
    GET https://icedapi.niti.gov.in/analytics/stateWiseDeepDive
        ?year=YYYY-YY&state=Comma,Separated,Names
    Returns: a JSON-encoded **string** = CryptoJS OpenSSL-format
    AES-256-CBC ciphertext, base64-encoded, prefixed with "Salted__"
    (passphrase ``AHten@VP0W3R`` — extracted from main.cb0bb1d44638969b.js,
    module 92340 / N.KEY).

Coverage (per the page's FY dropdown): 11 fiscal years 2015-16 .. 2025-26
× 37 entities (28 states + 8 UTs + "All India") × ~13 indicators across
electricity / economy / demography. Climate indicators (NO2/SO2/PM10/
PM2.5) are present in the response but uniformly N.A. for the entities
sampled, so they are intentionally not ingested in this version.

The adapter is doc-only at the package level so callers must import the
specific submodule they want (``parsers`` for the pure decrypt/extract
helpers; ``ingest`` for the network-touching orchestrator).
"""
