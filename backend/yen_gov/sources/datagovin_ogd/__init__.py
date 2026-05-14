"""data.gov.in OGD API source: fiscal indicators from public datasets.

The Open Government Data (OGD) Platform India exposes ministry-curated
datasets via an authenticated REST API. We use it for *historical*
state-finance series that pre-date the RBI publication's current
3-year window — extending coverage backward without compromising
provenance (every artifact's `sources[]` cites the API URL plus the
upstream Rajya Sabha question / publication).
"""
