"""Tests for the post-merge resolution of the 6 PR-Q1b Class-C dual-spelling pairs.

PR-Q1b (2026-06-12). After ``tools.dedupe_parties_csv --include-class-c --apply``
merges each pair into a single canonical row, the resolver's full-name
fallback (PR-Q1 commit 2) MUST resolve the publisher's long-form string to
the surviving canonical ``party_id``. Both the legacy short alias and the
publisher-variant alias also resolve to that same canonical id.

These tests run against the LIVE ``datasets/data/entities/parties.csv`` (no
fixture) and serve as the regression-guard against a future PR accidentally
re-introducing a Class-C collision (e.g. by re-minting one of the deleted
``parties.IN.JNJP`` / ``parties.IN.AJSUP`` / ``parties.IN.RALTP`` /
``parties.IN.ICP`` / ``parties.IN.SRPP`` / ``parties.IN.ADAL`` rows or by
adding a different row whose ``full`` collides with one of the six).

Per the test file's own header convention (``test_party_resolver_full_fallback.py``):
the autouse fixture clears ``load_resolver``'s lru_cache so a fresh resolver
is built for each test from the live on-disk parties.csv.
"""

from __future__ import annotations

import pytest

from yen_gov.canonical.party_resolver import load_resolver


@pytest.fixture(autouse=True)
def _reset_resolver_cache() -> None:
    load_resolver.cache_clear()


def test_jannayak_janta_party_resolves_to_canonical() -> None:
    """JNJP merged into JJP; the Haryana-based Jannayak Janta Party
    (Dushyant Chautala, founded 2018) resolves on its full name + on
    either historical abbreviation.
    """
    resolver = load_resolver()
    expected = "parties.IN.JJP"

    assert resolver.resolve("JANNAYAK JANTA PARTY", None) == expected
    assert resolver.resolve("Jannayak Janta Party", None) == expected
    assert resolver.resolve("JJP", None) == expected
    assert resolver.resolve("JNJP", None) == expected


def test_all_jharkhand_students_union_resolves_to_canonical() -> None:
    """AJSUP merged into AJSU; the Jharkhand-based All Jharkhand Students
    Union (Sudesh Mahto, founded 1986) resolves on its full name + on
    either historical abbreviation. The pre-existing ``AJSU Party`` alias
    (TCPD label) also resolves.
    """
    resolver = load_resolver()
    expected = "parties.IN.AJSU"

    assert resolver.resolve("ALL JHARKHAND STUDENTS UNION", None) == expected
    assert resolver.resolve("AJSU", None) == expected
    assert resolver.resolve("AJSUP", None) == expected
    assert resolver.resolve("AJSU PARTY", None) == expected


def test_rashtriya_loktantrik_party_resolves_to_canonical() -> None:
    """RALTP merged into RLP; the Rajasthan-based Rashtriya Loktantrik
    Party (Hanuman Beniwal, founded 2018) resolves on its full name + on
    either historical abbreviation, including the publisher's ``RaLtP``
    mixed-case variant.
    """
    resolver = load_resolver()
    expected = "parties.IN.RLP"

    assert resolver.resolve("RASHTRIYA LOKTANTRIK PARTY", None) == expected
    assert resolver.resolve("RLP", None) == expected
    assert resolver.resolve("RALTP", None) == expected
    # The publisher uses ``RaLtP`` in the rajasthan/2018 corpus.
    assert resolver.resolve("RaLtP", None) == expected


def test_indian_christian_secular_party_resolves_to_canonical() -> None:
    """ICP merged into ICSP; the Indian Christian Secular Party resolves
    on its full name + on either historical abbreviation. The pre-existing
    ``INDIAN CHRISTIAN SECULAR PARTY`` alias (curator-added before the
    merge) continues to resolve.
    """
    resolver = load_resolver()
    expected = "parties.IN.ICSP"

    assert resolver.resolve("INDIAN CHRISTIAN SECULAR PARTY", None) == expected
    assert resolver.resolve("ICSP", None) == expected
    assert resolver.resolve("ICP", None) == expected


def test_sikkim_republican_party_resolves_to_canonical() -> None:
    """SRPP merged into SKPP; the Sikkim Republican Party resolves on
    its full name + on either historical abbreviation. The pre-existing
    ``SIKKIM REPUBLICAN PARTY`` alias on the SKPP row continues to
    resolve.
    """
    resolver = load_resolver()
    expected = "parties.IN.SKPP"

    assert resolver.resolve("SIKKIM REPUBLICAN PARTY", None) == expected
    assert resolver.resolve("SKPP", None) == expected
    assert resolver.resolve("SRPP", None) == expected


def test_apna_dal_soneylal_resolves_to_canonical() -> None:
    """ADAL merged into ADS; Apna Dal (Soneylal) (Anupriya Patel, UP)
    resolves on its full name + on either historical abbreviation. The
    ECI-canonical short ``AD(S)`` is preserved on the keep row; the
    publisher's bare ``ADAL`` short is now an alias on the same row.
    """
    resolver = load_resolver()
    expected = "parties.IN.ADS"

    assert resolver.resolve("APNA DAL (SONEYLAL)", None) == expected
    assert resolver.resolve("AD(S)", None) == expected
    assert resolver.resolve("ADAL", None) == expected
