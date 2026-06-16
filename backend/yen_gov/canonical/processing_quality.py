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

_PARTY_FOUNDED_YEAR_BACKFILL_NOTE = (
    "founded_year transcribed from third-party party-catalogue website "
    "on 2026-06-15; cross-checked against publisher records where available"
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


def derive_processing_for_party_founded_year_backfill(
    party_id: str,  # noqa: ARG001 - reserved for future per-party divergence
) -> tuple[str, str]:
    """Return ``(processing_level, processing_note)`` for the parties.csv
    ``founded_year`` backfill (PR-1 of TODO/20260615-party-page-citizen-fixes-plan.md).

    Sibling to :func:`derive_processing` (not a replacement): the candidacy /
    summary writer keeps its UNK-only major trigger; this helper carries the
    L-1 doctrine for the parties.csv catalogue surface, where every row that
    is backfilled with a third-party-transcribed ``founded_year`` carries
    ``processing_level="major"`` plus the L-1 note verbatim.

    The ``party_id`` argument is accepted (and intentionally unused today)
    so future per-party divergence (e.g. one party where the year IS taken
    direct from the ECI public register, warranting ``minor`` + empty note)
    can be wired in without changing the call-site signature.

    The note text is the verbatim L-1 string ratified by user signoff in
    the plan-doc Scope-change ledger (row L-1, 2026-06-15). It MUST NOT
    name the third-party acquisition site (L-2 doctrine extension); the
    citizen sees only the operational receipt ("third-party party-catalogue
    website on 2026-06-15; cross-checked against publisher records where
    available"). The acquisition site is operator knowledge in the
    curator's notebook, never on the row.
    """
    return "major", _PARTY_FOUNDED_YEAR_BACKFILL_NOTE
