"""Tests for the ``full``-name fallback in ``party_resolver.load_resolver``.

PR-Q1 commit 2 (2026-06-12). Adds a CONDITIONAL fallback that indexes a row's
upper-cased ``full`` value into ``by_alias`` when three skip rules clear:
sentinel placeholder, multi-row collision, explicit-alias-wins. These tests
exercise each rule in isolation against ``tmp_path``-isolated parties.csv
fixtures.

The fixture autouse below mirrors the precedent in
``test_recon_thecont1_state.py`` and ``test_recon_tcpd_state.py``: each test
calls ``load_resolver.cache_clear()`` to ensure a fresh resolver is built
for the test's tmp_path parties.csv. Without the clear, the lru_cache can
serve a previous test's resolver and confuse assertions on the new fixture.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yen_gov.canonical.party_resolver import load_resolver


@pytest.fixture(autouse=True)
def _reset_resolver_cache() -> None:
    load_resolver.cache_clear()


_HEADER = (
    "party_id,short,full,eci_codes,brand_colour,symbol_asset,wikipedia,"
    "aliases,recognition_scope,home_state_codes,founded_year,"
    "dissolved_year,predecessor_party_ids,successor_party_ids,"
    "name_history,claims_to_parent_name,name_native_script,is_sentinel\n"
)


def _write_parties(path: Path, body: str) -> Path:
    """Write a parties.csv fixture (schema v1.1, 18 columns)."""
    path.write_text(_HEADER + body, encoding="utf-8")
    return path


def test_full_name_resolves_when_alias_missing(tmp_path: Path) -> None:
    """Row with ``short=TMP`` + ``full=Tipra Motha Party`` + no aliases
    resolves on the full-name string via the conditional fallback.
    """
    parties = _write_parties(
        tmp_path / "parties.csv",
        "parties.IN.TMP,TMP,Tipra Motha Party,,,,,,,,,,,,,,,\n",
    )
    resolver = load_resolver(parties)

    assert resolver.resolve("TIPRA MOTHA PARTY", None) == "parties.IN.TMP"


def test_case_insensitive_full_match(tmp_path: Path) -> None:
    """The full-name fallback is upper-cased at load time + at resolve time;
    case differences in the publisher string still hit.
    """
    parties = _write_parties(
        tmp_path / "parties.csv",
        "parties.IN.TMP,TMP,Tipra Motha Party,,,,,,,,,,,,,,,\n",
    )
    resolver = load_resolver(parties)

    # ``resolver.resolve`` upper-cases ``party_short`` internally; the
    # caller passes the publisher string as-is.
    assert resolver.resolve("tipra motha party", None) == "parties.IN.TMP"


def test_full_collision_returns_unk(tmp_path: Path) -> None:
    """Two rows sharing the same upper-cased ``full`` value are both
    dropped from the fallback index (collision skip rule). The publisher
    string that matches their ``full`` resolves to ``parties.IN.UNK``.
    """
    parties = _write_parties(
        tmp_path / "parties.csv",
        "parties.IN.JJP,JJP,Jannayak Janta Party,,,,,,,,,,,,,,,\n"
        "parties.IN.JNJP,JNJP,Jannayak Janta Party,,,,,,,,,,,,,,,\n",
    )
    resolver = load_resolver(parties)

    # The shorts still resolve normally...
    assert resolver.resolve("JJP", None) == "parties.IN.JJP"
    assert resolver.resolve("JNJP", None) == "parties.IN.JNJP"
    # ...but the colliding full does not.
    assert resolver.resolve("JANNAYAK JANTA PARTY", None) == "parties.IN.UNK"


def test_sentinel_placeholder_full_never_indexed(tmp_path: Path) -> None:
    """A row whose ``full`` matches a ``_SENTINEL_FULL_PLACEHOLDERS`` entry
    does NOT contribute that string to the fallback index, even when it is
    the only row carrying that full. ~60 such rows exist on disk; left
    un-skipped, ``resolver.resolve("NA'S", None)`` would resolve to the
    first one and silently mis-attribute every empty publisher cell.
    """
    parties = _write_parties(
        tmp_path / "parties.csv",
        "parties.IN.FOO,FOO,NA'S,,,,,,,,,,,,,,,\n",
    )
    resolver = load_resolver(parties)

    # The short still resolves...
    assert resolver.resolve("FOO", None) == "parties.IN.FOO"
    # ...but the sentinel-placeholder full does not.
    assert resolver.resolve("NA'S", None) == "parties.IN.UNK"


def test_explicit_alias_beats_full(tmp_path: Path) -> None:
    """A short or alias on row A holds priority over a colliding ``full``
    on row B (explicit-alias-wins skip). Resolving the shared string
    returns row A's pid, not row B's.
    """
    parties = _write_parties(
        tmp_path / "parties.csv",
        "parties.IN.AAA,AAA,Party Alpha,,,,,BBB,,,,,,,,,,\n"
        "parties.IN.XXX,XXX,BBB,,,,,,,,,,,,,,,\n",
    )
    resolver = load_resolver(parties)

    # Row A's alias 'BBB' must win over Row B's full 'BBB'.
    assert resolver.resolve("BBB", None) == "parties.IN.AAA"
    # Shorts continue to resolve normally for both.
    assert resolver.resolve("AAA", None) == "parties.IN.AAA"
    assert resolver.resolve("XXX", None) == "parties.IN.XXX"
