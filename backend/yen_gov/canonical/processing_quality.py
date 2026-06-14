"""Per-row processing-level helpers (OWID-aligned vocabulary).

Adopts the OWID metadata vocabulary verbatim (enum: ``minor`` | ``major``)
as a per-row column on the four election file_classes (assembly/parliament
x candidacies/summary). The free-text ``processing_note`` companion mirrors
OWID's ``description_processing``.

OWID reference: https://docs.owid.io/projects/etl/architecture/metadata/reference/

Per-row vs per-variable scope is named divergence #6 in
:doc:`docs/concepts/owid-alignment.md`; the vocabulary itself is unchanged.
See :doc:`docs/concepts/data-quality.md` for citizen-facing copy.

This module centralises the UNK note literal so writers + the one-off
backfill share one source of truth. Writers call these helpers when
constructing candidacy + summary rows; the backfill script under
``tools/backfill_processing_level.py`` mirrors the same logic for the
existing on-disk corpus.
"""

from __future__ import annotations

UNK_PARTY_ID = "parties.IN.UNK"

_UNK_NOTE_TEMPLATE = (
    "Publisher label {label!r} unmatched against TCPD/ECI catalogues; "
    "awaiting oracle resolution per datasets/_ops/unk-ledger-2026-06-12.csv."
)


def derive_processing(party_id: str, party_short_raw: str | None) -> tuple[str, str]:
    """Return ``(processing_level, processing_note)`` for one candidacy/summary row.

    ``party_id == "parties.IN.UNK"`` is the only fresh-write trigger for
    ``major``: the upstream publisher short survives on ``party_short_raw``
    but did not match any canonical party_id (see
    :mod:`yen_gov.canonical.party_resolver`). Every other row defaults to
    ``minor`` + empty note.

    The historical Bihar 2000 BJC + KSP mints carry hand-authored notes
    set by the one-off backfill (``tools/backfill_processing_level.py``);
    writers do not re-derive those at re-emit time. The asymmetry is
    intentional per the data-quality doctrine: fresh writes default to
    ``minor`` unless the writer has explicit reason to mint ``major``
    (UNK resolution being the only such reason today).
    """
    if party_id == UNK_PARTY_ID:
        label = (party_short_raw or "").strip()
        return "major", _UNK_NOTE_TEMPLATE.format(label=label)
    return "minor", ""
