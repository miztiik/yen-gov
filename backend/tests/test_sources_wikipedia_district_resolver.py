"""Offline tests for the Wikipedia AC-table district resolver.

Companion to ``test_sources_wikipedia_live.py``: those exercise the parser
end-to-end against live Wikipedia. These pin the pure-Python normalisation
logic (`_norm`, `build_district_lookup`, `_resolve_district_id`) so the
real-world transliteration variants encountered in TN + KL stay matched.
"""

from __future__ import annotations

import pytest

from yen_gov.sources.wikipedia.constituencies import (
    _norm, _resolve_district_id, build_district_lookup,
)


# Real (district-name-on-Wikipedia, district-id-in-our-districts.json,
# variant-seen-in-AC-table) triples from the TN and KL Wikipedia pages.
@pytest.mark.parametrize("wiki_name, did, ac_table_name", [
    ("Tiruvallur",                "TAL", "Thiruvallur"),         # Th↔T
    ("Tiruvarur",                 "TAR", "Thiruvarur"),
    ("Tirupathur",                "TIA", "Tirupattur"),          # th↔tt
    ("Kanyakumari",               "KAY", "Kanniyakumari"),       # extra n+i
    ("Chennai (formerly Madras)", "CHN", "Chennai"),             # parens
    ("Kasaragod",                 "KAS", "Kasargod"),            # missing 'a'
    ("Tiruvallur",                "TAL", "Tiruvallur"),          # exact
])
def test_resolves_known_variants(wiki_name, did, ac_table_name):
    lookup = build_district_lookup([(wiki_name, did)])
    assert _resolve_district_id(ac_table_name, lookup) == did


def test_unknown_returns_none():
    lookup = build_district_lookup([("Chennai", "CHN")])
    assert _resolve_district_id("Mumbai", lookup) is None


def test_empty_inputs_return_none():
    assert _resolve_district_id(None, {"chennai": "CHN"}) is None
    assert _resolve_district_id("Chennai", None) is None
    assert _resolve_district_id("", {"chennai": "CHN"}) is None


def test_norm_collapses_skeleton():
    # `_norm` is the fallback fuzzy key — equal skeletons collide.
    assert _norm("Thiruvallur") == _norm("Tiruvallur")
    assert _norm("Tirupathur") == _norm("Tirupattur")
    assert _norm("Kanniyakumari") == _norm("Kanyakumari")
    assert _norm("Kasargod") == _norm("Kasaragod")


def test_lookup_indexes_both_keys():
    lookup = build_district_lookup([("Tiruvallur", "TAL")])
    # raw casefold key
    assert lookup["tiruvallur"] == "TAL"
    # `_norm` skeleton key
    assert lookup[_norm("Tiruvallur")] == "TAL"
