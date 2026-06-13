"""Unit tests for the pre-1999 LS GE backbone landed in PR-3 of
TODO/20260613-party-deferred-followups-plan.md.

The pre-1999 cohort (1962-1998) adds 10 historical Parliament general
elections to the in-tree event registry + delimitation crosswalk. This is
backbone only: actual TCPD ingest follows in PR-8. These tests pin the
shape so future agents can't accidentally drift the cohort assignments or
constant naming convention.

Max Q1.1c LOAD-BEARING verdict (recorded in the plan-doc): 1967 + 1971 share
their own delimitation cohort (DelimID 2 per TCPD), distinct from the 1976
cohort (DelimID 3) that governs 1977-2004. Splitting these collapses the
post-1956 States Reorganisation territorial rearrangement that the 1967
delimitation captured.
"""

from __future__ import annotations

from yen_gov.canonical.adapters.eci.pc_crosswalk import (
    DELIM_BY_GE_YEAR,
    delim_year_for_ge,
)
from yen_gov.canonical.adapters.eci_ls import (
    EVENT_BY_GE_YEAR,
    LS_1962,
    LS_1967,
    LS_1971,
    LS_1977,
    LS_1980,
    LS_1984,
    LS_1989,
    LS_1991,
    LS_1996,
    LS_1998,
)


# ---------------------------------------------------------------------------
# DELIM_BY_GE_YEAR cohort pins
# ---------------------------------------------------------------------------


def test_delim_by_ge_year_pre1999_cohorts():
    """Verify the 1962-1998 cohort assignments per
    TODO/20260613-party-deferred-followups-plan.md section 5.

    Load-bearing per Max Q1.1c: 1967 + 1971 are their own cohort, distinct
    from the 1976 cohort.
    """
    # 1962 is its own cohort (pre-1967 reorganisation).
    assert DELIM_BY_GE_YEAR[1962] == 1962, "1962 must be its own delim cohort"

    # 1967 + 1971 share the 1967 cohort (DelimID 2 in TCPD).
    assert DELIM_BY_GE_YEAR[1967] == 1967, "1967 should be in delim 1967 cohort"
    assert DELIM_BY_GE_YEAR[1971] == 1967, "1971 should be in delim 1967 cohort"

    # 1977-2004 share the 1976 cohort (DelimID 3 in TCPD) -- nine consecutive
    # general elections fought on the 1976 boundaries.
    for y in (1977, 1980, 1984, 1989, 1991, 1996, 1998, 1999, 2004):
        assert DELIM_BY_GE_YEAR[y] == 1976, (
            f"{y} should be in delim 1976 cohort"
        )

    # 2009-2024 share the 2008 cohort (unchanged from prior shape).
    for y in (2009, 2014, 2019, 2024):
        assert DELIM_BY_GE_YEAR[y] == 2008, (
            f"{y} should be in delim 2008 cohort"
        )


def test_delim_year_for_ge_covers_all_16_events():
    """The :func:`delim_year_for_ge` resolver MUST succeed for every event
    registered in :data:`EVENT_BY_GE_YEAR` (no orphan years)."""
    for ge_year in EVENT_BY_GE_YEAR.keys():
        resolved = delim_year_for_ge(ge_year)
        assert isinstance(resolved, int), (
            f"delim_year_for_ge({ge_year}) returned non-int {resolved!r}"
        )
        assert 1850 <= resolved <= 2100, (
            f"delim_year_for_ge({ge_year}) returned implausible {resolved}"
        )


# ---------------------------------------------------------------------------
# PcGeEvent registry pins
# ---------------------------------------------------------------------------


def test_event_registry_pre1999_constant_shape():
    """Verify the 10 new PcGeEvent constants for pre-1999 LS GEs land on the
    registry with the expected ``period_label`` + ``delim_year`` + vintage.

    Polling-month convention is the first polling month per Wikipedia
    cross-referenced against TCPD ``month`` column, with two named
    overrides (see eci_ls.py module docstring):
      - 1991 = Jun (NOT May) due to the Rajiv Gandhi assassination split.
      - 1998 = Feb (NOT Mar despite TCPD month='3') for the first poll.
    """
    expected = {
        1962: ("LsGenFeb1962", 1962, "1962"),
        1967: ("LsGenFeb1967", 1967, "1967"),
        1971: ("LsGenMar1971", 1967, "1971"),
        1977: ("LsGenMar1977", 1976, "1977"),
        1980: ("LsGenJan1980", 1976, "1980"),
        1984: ("LsGenDec1984", 1976, "1984"),
        1989: ("LsGenNov1989", 1976, "1989"),
        1991: ("LsGenJun1991", 1976, "1991"),
        1996: ("LsGenMay1996", 1976, "1996"),
        1998: ("LsGenFeb1998", 1976, "1998"),
    }
    for year, (label, delim, vintage) in expected.items():
        event = EVENT_BY_GE_YEAR[year]
        assert event.period.period_label == label, (
            f"{year}: period_label {event.period.period_label!r} != {label!r}"
        )
        assert event.period.year == year, (
            f"{year}: period.year {event.period.year} != {year}"
        )
        assert event.delim_year == delim, (
            f"{year}: delim_year {event.delim_year} != {delim}"
        )
        assert event.vintage == vintage, (
            f"{year}: vintage {event.vintage!r} != {vintage!r}"
        )
        assert event.source_input_id == "tcpd_ge", (
            f"{year}: source_input_id {event.source_input_id!r} != 'tcpd_ge'"
        )


def test_event_registry_period_seq_follows_month_convention():
    """``Period.period_seq`` is the calendar month (1..12) per identity.py.

    The 10 NEW pre-1999 constants follow this convention strictly (the older
    LS_1999/2004/2009/2014/2019/2024 constants use a sequential-rank
    convention for historical reasons and are NOT touched).
    """
    expected_seq = {
        1962: 2,   # Feb
        1967: 2,   # Feb
        1971: 3,   # Mar
        1977: 3,   # Mar
        1980: 1,   # Jan
        1984: 12,  # Dec
        1989: 11,  # Nov
        1991: 6,   # Jun
        1996: 5,   # May
        1998: 2,   # Feb
    }
    for year, seq in expected_seq.items():
        event = EVENT_BY_GE_YEAR[year]
        assert event.period.period_seq == seq, (
            f"{year}: period_seq {event.period.period_seq} != {seq}"
        )


def test_event_registry_covers_16_le_GE_years():
    """The registry MUST carry exactly 16 entries (1962, 1967, 1971, 1977,
    1980, 1984, 1989, 1991, 1996, 1998, 1999, 2004, 2009, 2014, 2019, 2024).
    """
    assert sorted(EVENT_BY_GE_YEAR.keys()) == [
        1962, 1967, 1971, 1977, 1980, 1984, 1989, 1991, 1996, 1998,
        1999, 2004, 2009, 2014, 2019, 2024,
    ]


def test_all_pre1999_constants_individually_importable():
    """Each of the 10 named LS_<YEAR> constants resolves to a PcGeEvent with
    a non-empty source_title naming the LS GE year."""
    pairs = [
        (1962, LS_1962),
        (1967, LS_1967),
        (1971, LS_1971),
        (1977, LS_1977),
        (1980, LS_1980),
        (1984, LS_1984),
        (1989, LS_1989),
        (1991, LS_1991),
        (1996, LS_1996),
        (1998, LS_1998),
    ]
    for year, event in pairs:
        assert str(year) in event.source_title, (
            f"LS_{year}.source_title {event.source_title!r} must mention "
            f"the GE year {year}"
        )
