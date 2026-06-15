"""MyNeta / ADR adapters subpackage.

Hosts adapters for civil-society affidavit-disclosure data, primarily from
the Association for Democratic Reforms (ADR) and its candidate-affidavit
explorer at myneta.info. These adapters enrich existing candidacy facts
on `datasets/elections/.../candidacies.csv` with declared-on-affidavit
attributes (criminal cases, total assets / liabilities, declared election
expense). They never mint candidacy rows of their own — the ECI/TCPD
adapters remain the source of truth for who-stood-where-and-won.
"""
