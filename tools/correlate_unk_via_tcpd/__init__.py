"""TCPD Party_ID correlator for UNK publisher labels (post-2026-06-12).

Walks the on-disk UNK rows in ``datasets/elections/**/candidacies.csv`` and
correlates each distinct publisher label against:

1. TCPD's per-candidacy panel (``All_States_AE.csv`` + ``All_States_GE.csv``)
   which carries a numeric ``Party_ID`` per row -> a stable cross-year /
   cross-state party identifier.
2. TCPD's per-party catalogue (``TCPD-PoliticalPartiesIndia_1962_2021.csv``)
   which carries ``Party_Name`` / ``Party_Type`` / ``Frequent_Abbreviation``
   per ``Party_ID`` for the mint payload.
3. The pre-X1b legacy ``elections_candidacies.parquet`` (recovered from
   parent-of ``b8108ceb8``) as a tertiary oracle for labels TCPD does not
   carry.

Output is a verdict.csv at
``datasets/ephemeral/party-parity/tcpd-correlate/<sha>/verdict.csv`` for
the curator (and the sibling ``correlate_unk_apply`` tool) to action.
"""
