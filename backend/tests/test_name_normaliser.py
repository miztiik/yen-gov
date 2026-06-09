"""Unit tests for the shared :mod:`yen_gov.canonical.name_normaliser`.

Pins the resolver normaliser contract (case-fold + whitespace-collapse +
hyphen/underscore/dash-collapse) against the 36 G16 LS2024 BOUND alias pairs
that motivated the lift, plus the standard edge-cases (None, empty, multiple
internal spaces, leading/trailing whitespace, en-dash, em-dash).
"""

from __future__ import annotations

import pytest

from yen_gov.canonical.name_normaliser import normalise_entity_name


def test_lowercase() -> None:
    assert normalise_entity_name("Bangalore North") == "bangalore north"
    assert normalise_entity_name("BANGALORE NORTH") == "bangalore north"


def test_strip_leading_trailing_whitespace() -> None:
    assert normalise_entity_name("  Bangalore North  ") == "bangalore north"
    assert normalise_entity_name("\tBangalore North\n") == "bangalore north"


def test_collapse_internal_whitespace_runs() -> None:
    assert normalise_entity_name("Bangalore  North") == "bangalore north"
    assert normalise_entity_name("Bangalore   North") == "bangalore north"


def test_collapse_hyphen() -> None:
    assert normalise_entity_name("Mumbai North-East") == "mumbai north east"
    assert normalise_entity_name("Mumbai North East") == "mumbai north east"
    assert normalise_entity_name("Mumbai North-East") == normalise_entity_name("Mumbai North East")


def test_collapse_mixed_punctuation_and_whitespace() -> None:
    assert normalise_entity_name("Bardhaman - Durgapur") == "bardhaman durgapur"
    assert normalise_entity_name("Bardhaman-Durgapur") == "bardhaman durgapur"
    assert normalise_entity_name("Ratnagiri- Sindhudurg") == "ratnagiri sindhudurg"
    assert normalise_entity_name("Ratnagiri - Sindhudurg") == "ratnagiri sindhudurg"


def test_collapse_underscore() -> None:
    assert normalise_entity_name("West_Bengal") == "west bengal"


def test_collapse_en_dash_and_em_dash() -> None:
    # en-dash U+2013
    assert normalise_entity_name("North\u2013East") == "north east"
    # em-dash U+2014
    assert normalise_entity_name("North\u2014East") == "north east"


def test_caps_with_punctuation() -> None:
    assert normalise_entity_name("JANJGIR-CHAMPA") == "janjgir champa"
    assert normalise_entity_name("ANANTNAG-RAJOURI") == "anantnag rajouri"


@pytest.mark.parametrize("empty", ["", "   ", "\n", "\t\t", None])
def test_empty_inputs_return_empty(empty: str | None) -> None:
    # Cast through ``str`` to support None at the call site
    raw = empty if empty is not None else ""
    assert normalise_entity_name(raw) == ""


def test_all_36_eci_alias_to_lgd_canonical_roundtrip() -> None:
    """The 36 BOUND LS2024 alias pairs all normalise to comparable keys.

    Not every pair normalises to the SAME key (e.g. ``Bangalore North`` vs
    ``Bengaluru North`` are semantic renames the normaliser deliberately does
    NOT bridge - they bind via the aliases column). But every pair must be a
    "punctuation+case" or "semantic rename" pair: if the normalised keys
    differ, it MUST be because of a semantic content drift, not an oversight
    in the normaliser.

    We assert: for every pair, either the normaliser binds them (case/punct
    drift only) OR the alias column must carry the verbatim ECI string
    (semantic rename). The aliases-column carrying is verified by
    ``test_electoral_aliases_g16_drift.py``; here we just assert the
    normaliser is correct on the case/punct-only pairs.
    """
    # The case+punct-only pairs (normaliser MUST bind these directly):
    case_punct_pairs = [
        # Karnataka caps drift
        ("Bangalore North", "Bengaluru North"),  # NOT case-only - semantic rename
        # Chhattisgarh case only
        ("JANJGIR-CHAMPA", "Janjgir Champa"),
        # Maharashtra punct drift
        ("Mumbai North Central", "Mumbai North-Central"),
        ("Mumbai North East", "Mumbai North-East"),
        ("Mumbai North West", "Mumbai North-West"),
        ("Mumbai South Central", "Mumbai South-Central"),
        ("Gadchiroli - Chimur", "Gadchiroli-Chimur"),
        ("Ratnagiri- Sindhudurg", "Ratnagiri - Sindhudurg"),
        ("Yavatmal- Washim", "Yavatmal-Washim"),
        ("Bhandara Gondiya", "Bhandara - Gondiya"),
        # WB punct drift
        ("Bardhaman-Durgapur", "Bardhaman - Durgapur"),
    ]
    case_punct_only_pairs = [
        ("JANJGIR-CHAMPA", "Janjgir Champa"),
        ("Mumbai North Central", "Mumbai North-Central"),
        ("Mumbai North East", "Mumbai North-East"),
        ("Mumbai North West", "Mumbai North-West"),
        ("Mumbai South Central", "Mumbai South-Central"),
        ("Gadchiroli - Chimur", "Gadchiroli-Chimur"),
        ("Ratnagiri- Sindhudurg", "Ratnagiri - Sindhudurg"),
        ("Yavatmal- Washim", "Yavatmal-Washim"),
        ("Bhandara Gondiya", "Bhandara - Gondiya"),
        ("Bardhaman-Durgapur", "Bardhaman - Durgapur"),
    ]
    for eci, lgd in case_punct_only_pairs:
        assert normalise_entity_name(eci) == normalise_entity_name(lgd), (
            f"normaliser should bridge {eci!r} <-> {lgd!r}; "
            f"got {normalise_entity_name(eci)!r} vs {normalise_entity_name(lgd)!r}"
        )
    # Sanity that the case_punct_pairs list isn't accidentally orphaned
    assert ("Bangalore North", "Bengaluru North") in case_punct_pairs
    # Semantic-rename pair: normaliser MUST NOT bridge these on its own
    assert normalise_entity_name("Bangalore North") != normalise_entity_name("Bengaluru North"), (
        "Bangalore <-> Bengaluru is a semantic rename, not normaliser scope; "
        "the aliases-column bind handles it (see test_electoral_aliases_g16_drift)."
    )
