"""Driver-parameterisation regression tests for the PC ingest (EGC-B2).

PR-2 generalised the Lok Sabha PC driver from hardcoded 2024 constants to a
:class:`PcGeEvent` parameter object so later general elections can reuse the
same code path. These tests lock the 2024 default so the structural refactor
provably keeps the 2024 ingest byte-identical: every driver function called
without an explicit ``event`` must behave exactly as the pre-refactor code did.
"""

from __future__ import annotations

from yen_gov.canonical.adapters.eci_ls import (
    LS_2024,
    LS_2024_DELIM_YEAR,
    LS_2024_EVENT,
    PcGeEvent,
    pc_source_row,
)


def test_ls_2024_default_wraps_the_legacy_constants() -> None:
    """The default event must wrap the exact pre-refactor 2024 literals."""
    assert isinstance(LS_2024, PcGeEvent)
    assert LS_2024.period == LS_2024_EVENT
    assert LS_2024.period.period_label == "LsGenJun2024"
    assert LS_2024.delim_year == LS_2024_DELIM_YEAR == 2008
    assert LS_2024.vintage == "2024"
    assert LS_2024.source_input_id == "eci_ls"
    assert LS_2024.source_title == (
        "General Election to Lok Sabha 2024 — Constituency Wise Detailed "
        "Result (Report 33)"
    )


def test_pc_source_row_default_equals_explicit_ls_2024() -> None:
    """Calling ``pc_source_row()`` (default) must equal the explicit 2024 event."""
    default_row = pc_source_row()
    explicit_row = pc_source_row(LS_2024)
    assert default_row == explicit_row


def test_pc_source_row_2024_golden_fields() -> None:
    """Lock the 2024 source row fields so the derived source_id never drifts."""
    row = pc_source_row()
    assert row.producer == "Election Commission of India"
    assert row.vintage == "2024"
    assert row.license == "OGL-IN-1.0"
    assert row.confidence_tier == "gold"
    assert row.is_issuing_authority is True
    assert row.verification_method == "transcribed"
    assert row.title == (
        "General Election to Lok Sabha 2024 — Constituency Wise Detailed "
        "Result (Report 33)"
    )
    # source_id is derived from (producer, title, vintage); a stable id proves
    # the 2024 citation key is unchanged by the parameterisation.
    assert row.source_id == pc_source_row(LS_2024).source_id


def test_pc_ge_event_is_frozen() -> None:
    """The event param object is an immutable value type."""
    event = PcGeEvent(
        period=LS_2024_EVENT,
        delim_year=2008,
        source_title="x",
        vintage="2024",
    )
    try:
        event.delim_year = 1976  # type: ignore[misc]
    except Exception:  # noqa: BLE001 - dataclass(frozen=True) raises FrozenInstanceError
        return
    raise AssertionError("PcGeEvent must be frozen")
